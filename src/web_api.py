"""FastAPI service layer for the drilling accident disposition backend."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import unquote

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .graph import solve_accident

try:
    from .wiki_loader import load_all_pages, load_page
except Exception:
    load_all_pages = None
    load_page = None


WIKI_DIR = Path(os.getenv("WIKI_DIR", "wiki"))
OUTPUTS_DIR = Path(os.getenv("OUTPUTS_DIR", "outputs"))


class SolveRequest(BaseModel):
    description: str = Field(..., min_length=1)
    session_id: str | None = None
    archive: bool = True


class SessionCreateRequest(BaseModel):
    title: str | None = None
    description: str | None = None


class LLMConfigRequest(BaseModel):
    provider: str = "openai"
    model: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    enabled: bool = True
    clear_key: bool = False


def _llm_config_path() -> Path:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    return OUTPUTS_DIR / "llm_config.json"


def _read_llm_config_raw() -> Dict[str, Any]:
    path = _llm_config_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _write_llm_config_raw(config: Dict[str, Any]) -> None:
    path = _llm_config_path()
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def _public_llm_config(config: Dict[str, Any]) -> Dict[str, Any]:
    api_key = str(config.get("api_key") or "")
    return {
        "provider": config.get("provider") or "openai",
        "model": config.get("model") or "",
        "base_url": config.get("base_url") or "",
        "enabled": bool(config.get("enabled", True)),
        "has_api_key": bool(api_key),
        "masked_api_key": _mask_secret(api_key),
        "updated_at": config.get("updated_at") or "",
    }


def _mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}****{value[-4:]}"


def _safe_wiki_path(path: str) -> Path:
    clean = unquote(path).lstrip("/")
    if clean == "wiki":
        clean = ""
    elif clean.startswith("wiki/"):
        clean = clean[len("wiki/") :]
    candidate = (WIKI_DIR / clean).resolve()
    root = WIKI_DIR.resolve()
    if root not in candidate.parents and candidate != root:
        raise HTTPException(status_code=400, detail="Invalid wiki path")
    return candidate


def _list_markdown(root: Path) -> List[Dict[str, Any]]:
    if load_all_pages is not None:
        try:
            return [
                {
                    "path": page.relative_path,
                    "title": page.title,
                    "category": page.path.parent.as_posix() if page.path.parent.as_posix() != "." else "root",
                    "source_pdf": page.metadata.get("source_pdf"),
                    "updated_at": page.metadata.get("extracted_at") or page.metadata.get("updated_at"),
                    "metadata": page.metadata,
                }
                for page in load_all_pages(root)
            ]
        except Exception:
            pass
    if not root.exists():
        return []
    pages = []
    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(root).as_posix()
        pages.append(
            {
                "path": rel,
                "title": path.stem,
                "category": path.parent.relative_to(root).as_posix() if path.parent != root else "root",
            }
        )
    return pages


def _count_pages(pages: List[Dict[str, Any]], category: str) -> int:
    return sum(1 for page in pages if str(page.get("category", "")).startswith(category))


def _phases_from_state(state: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        {
            "id": "parse",
            "tag": "parse",
            "title": "事故信息提取",
            "status": "done",
            "summary": state.get("parse_report", "已完成事故信息结构化。"),
        },
        {
            "id": "match",
            "tag": "match",
            "title": "历史案例参考",
            "status": "done",
            "summary": state.get("similar_cases", "案例匹配未返回结果。"),
        },
        {
            "id": "plan",
            "tag": "plan",
            "title": "处置方案生成",
            "status": "done",
            "summary": "已生成最终处置方案，包含分阶段处置、判断节点、应急预案和参考依据。",
        },
        {
            "id": "check",
            "tag": "check",
            "title": "合规审核",
            "status": "warning" if state.get("accident", {}).get("missing_fields") else "done",
            "summary": state.get("compliance_report", "合规审核未生成。"),
        },
    ]


def _read_sessions() -> List[Dict[str, Any]]:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    sessions_path = OUTPUTS_DIR / "sessions.json"
    if not sessions_path.exists():
        return []
    try:
        data = json.loads(sessions_path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _write_sessions(sessions: List[Dict[str, Any]]) -> None:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUTS_DIR / "sessions.json").write_text(
        json.dumps(sessions, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def create_app() -> FastAPI:
    app = FastAPI(title="钻具落断事故处置系统 API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/api/health")
    def health() -> Dict[str, Any]:
        pages = _list_markdown(WIKI_DIR)
        standards_count = _count_pages(pages, "standards")
        cases_count = _count_pages(pages, "cases")
        wiki_ok = WIKI_DIR.exists() and standards_count >= 3 and cases_count >= 15
        return {
            "status": "ok" if wiki_ok else "degraded",
            "wiki_ok": wiki_ok,
            "wiki_dir": str(WIKI_DIR),
            "wiki_exists": WIKI_DIR.exists(),
            "wiki_page_count": len(pages),
            "standards_count": standards_count,
            "cases_count": cases_count,
            "outputs_dir": str(OUTPUTS_DIR),
            "time": datetime.now().isoformat(timespec="seconds"),
        }

    @app.get("/api/sessions")
    def list_sessions() -> List[Dict[str, Any]]:
        return _read_sessions()

    @app.get("/api/llm/config")
    def get_llm_config() -> Dict[str, Any]:
        return _public_llm_config(_read_llm_config_raw())

    @app.post("/api/llm/config")
    def save_llm_config(payload: LLMConfigRequest) -> Dict[str, Any]:
        existing = _read_llm_config_raw()
        incoming_key = (payload.api_key or "").strip()
        if payload.clear_key:
            api_key = ""
        elif incoming_key:
            api_key = incoming_key
        else:
            api_key = str(existing.get("api_key") or "")

        config = {
            "provider": payload.provider.strip() or "openai",
            "model": (payload.model or "").strip(),
            "base_url": (payload.base_url or "").strip(),
            "api_key": api_key,
            "enabled": payload.enabled,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        _write_llm_config_raw(config)
        return _public_llm_config(config)

    @app.post("/api/sessions")
    def create_session(payload: SessionCreateRequest) -> Dict[str, Any]:
        sessions = _read_sessions()
        session = {
            "id": datetime.now().strftime("%Y%m%d%H%M%S%f"),
            "title": payload.title or "新建事故会话",
            "description": payload.description or "",
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }
        sessions.insert(0, session)
        _write_sessions(sessions)
        return session

    @app.post("/api/solve")
    def solve(payload: SolveRequest) -> Dict[str, Any]:
        state = solve_accident(
            payload.description,
            wiki_dir=str(WIKI_DIR),
            outputs_dir=str(OUTPUTS_DIR),
            archive=payload.archive,
        )
        return {
            "session_id": payload.session_id,
            "accident": state.get("accident", {}),
            "parse_report": state.get("parse_report", ""),
            "similar_cases": state.get("similar_cases", ""),
            "aggressive_plan": state.get("aggressive_plan", ""),
            "conservative_plan": state.get("conservative_plan", ""),
            "compliance_report": state.get("compliance_report", ""),
            "final_plan": state.get("final_plan", ""),
            "evidence": state.get("evidence", []),
            "wiki_pages_used": state.get("wiki_pages_used", []),
            "confidence_score": state.get("confidence_score", 0.0),
            "output_path": state.get("output_path"),
            "generated_plan_path": state.get("generated_plan_path"),
            "phases": _phases_from_state(state),
        }

    @app.get("/api/outputs/{output_id}")
    def get_output(output_id: str) -> Dict[str, Any]:
        filename = output_id if output_id.endswith(".md") else f"{output_id}.md"
        path = (OUTPUTS_DIR / filename).resolve()
        root = OUTPUTS_DIR.resolve()
        if root not in path.parents and path != root:
            raise HTTPException(status_code=400, detail="Invalid output id")
        if not path.exists():
            raise HTTPException(status_code=404, detail="Output not found")
        return {"id": path.stem, "path": str(path), "content": path.read_text(encoding="utf-8")}

    @app.get("/api/wiki/pages")
    def wiki_pages() -> List[Dict[str, Any]]:
        return _list_markdown(WIKI_DIR)

    @app.get("/api/wiki/search")
    def wiki_search(q: str = Query("", max_length=100)) -> List[Dict[str, Any]]:
        needle = q.strip().lower()
        results = []
        for page in _list_markdown(WIKI_DIR):
            path = _safe_wiki_path(page["path"])
            text = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
            haystack = f"{page['title']} {page['path']} {text[:2000]}".lower()
            if not needle or needle in haystack:
                results.append({**page, "excerpt": text[:220]})
        return results[:50]

    @app.get("/api/wiki/pages/{path:path}")
    def wiki_page(path: str) -> Dict[str, Any]:
        candidate = _safe_wiki_path(path)
        if not candidate.exists() or not candidate.is_file():
            raise HTTPException(status_code=404, detail="Wiki page not found")
        if load_page is not None:
            try:
                page = load_page(path, WIKI_DIR)
                return {
                    "path": page.relative_path,
                    "title": page.title,
                    "content": page.content,
                    "source_pdf": page.metadata.get("source_pdf"),
                    "updated_at": page.metadata.get("extracted_at") or page.metadata.get("updated_at"),
                    "metadata": page.metadata,
                }
            except Exception:
                pass
        return {
            "path": candidate.relative_to(WIKI_DIR.resolve()).as_posix(),
            "title": candidate.stem,
            "content": candidate.read_text(encoding="utf-8", errors="ignore"),
        }

    return app


app = create_app()
