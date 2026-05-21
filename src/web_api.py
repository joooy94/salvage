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

from .disposition_graph import build_disposition_graph
from .graph import converse_accident, solve_accident
from .llm_client import load_llm_config, mask_secret, try_complete_text
from .wiki_builder.graph_builder import build_graph

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


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1)
    session_id: str
    mode: str | None = None


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
    loaded = load_llm_config(outputs_dir=OUTPUTS_DIR)
    return {
        "provider": loaded.provider,
        "model": loaded.model,
        "base_url": loaded.base_url,
        "enabled": loaded.enabled,
        "has_api_key": bool(loaded.api_key),
        "masked_api_key": mask_secret(loaded.api_key),
        "updated_at": config.get("updated_at") or "",
    }


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
                    "title": page.path.stem if page.path.parent.as_posix() == "generated_plans" else page.title,
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
    debate_summary = _debate_summary(state.get("debate_rounds", []))
    parse_summary = str(state.get("parse_report") or "").strip() or _accident_summary(state.get("accident", {}))
    phases = [
        {
            "id": "parse",
            "tag": "parse",
            "title": "事故信息提取",
            "status": "warning" if state.get("accident", {}).get("missing_fields") else "done",
            "summary": parse_summary,
            "details": parse_summary,
        },
        {
            "id": "match",
            "tag": "match",
            "title": "历史案例参考",
            "status": "done",
            "summary": state.get("similar_cases", "案例匹配未返回结果。"),
        },
        {
            "id": "aggressive",
            "tag": "aggressive",
            "title": "激进方案 Agent",
            "status": "done",
            "summary": _first_lines(state.get("aggressive_plan", "激进方案未生成。"), 4),
            "details": state.get("aggressive_plan", ""),
        },
        {
            "id": "conservative",
            "tag": "conservative",
            "title": "保守安全 Agent",
            "status": "done",
            "summary": _first_lines(state.get("conservative_plan", "保守方案未生成。"), 4),
            "details": state.get("conservative_plan", ""),
        },
        {
            "id": "debate",
            "tag": "plan",
            "title": "主流程多轮辩论",
            "status": "done",
            "summary": debate_summary or "主流程辩论记录未生成，需复核模型配置。",
            "details": debate_summary,
        },
        {
            "id": "check",
            "tag": "check",
            "title": "合规审核",
            "status": "warning" if state.get("accident", {}).get("missing_fields") else "done",
            "summary": state.get("compliance_report", "合规审核未生成。"),
        },
        {
            "id": "final",
            "tag": "final",
            "title": "最终决策",
            "status": "done",
            "summary": "决策 Agent 已基于事故信息、依据、双方方案、主流程辩论和合规审核生成最终处置方案。",
        },
    ]
    return phases


def _first_lines(text: str, limit: int = 3) -> str:
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    return "\n".join(lines[:limit])


def _accident_summary(accident: Dict[str, Any]) -> str:
    if not isinstance(accident, dict) or not accident:
        return "未读取到结构化事故信息，需重新提交事故描述或检查事故解析节点。"
    fields = [
        ("井型", accident.get("well_type")),
        ("鱼顶/事故深度", accident.get("depth")),
        ("落鱼类型", accident.get("fish_type")),
        ("落鱼描述", accident.get("fish_description")),
        ("井液/钻井液", accident.get("mud_type")),
        ("扣型", accident.get("thread_type")),
        ("井斜角", accident.get("inclination")),
    ]
    lines = ["## 事故信息提取", *[f"- {label}：{value}" for label, value in fields if value not in (None, "", [])]]
    missing = accident.get("missing_fields") or []
    lines.append(f"- 缺失信息：{'、'.join(missing) if missing else '暂无关键缺失项。'}")
    return "\n".join(lines)


def _debate_summary(rounds: Any) -> str:
    if not isinstance(rounds, list):
        return ""
    lines = []
    for item in rounds[:6]:
        if not isinstance(item, dict):
            continue
        title = item.get("title") or item.get("agent") or "Agent"
        content = item.get("content") or ""
        if content:
            lines.append(f"- **{title}**：{content}")
    return "\n".join(lines)


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


def _plan_version_entry(version: int, content: str, result: Dict[str, Any], timestamp: str) -> Dict[str, Any]:
    return {
        "version": version,
        "title": f"处置方案 v{version}",
        "content": content,
        "created_at": timestamp,
        "output_path": result.get("output_path") or "",
        "generated_plan_path": result.get("generated_plan_path") or "",
        "confidence_score": result.get("confidence_score", 0.0),
        "mode": result.get("mode") or "solve",
    }


def _update_session_result(session_id: str | None, description: str, result: Dict[str, Any]) -> None:
    if not session_id:
        return
    sessions = _read_sessions()
    now = datetime.now().isoformat(timespec="seconds")
    final_plan = result.get("final_plan", "")
    snapshot = {
        "description": description,
        "updated_at": now,
        "messages": [
            {"role": "user", "content": description, "created_at": now},
            {"role": "assistant", "content": "已完成处置方案生成，详见 Agent 阶段卡片与最终方案 Markdown。", "created_at": now},
        ],
        "accident": result.get("accident", {}),
        "parse_report": result.get("parse_report", ""),
        "similar_cases": result.get("similar_cases", ""),
        "aggressive_plan": result.get("aggressive_plan", ""),
        "conservative_plan": result.get("conservative_plan", ""),
        "compliance_report": result.get("compliance_report", ""),
        "final_plan": final_plan,
        "plan_versions": [_plan_version_entry(1, final_plan, result, now)] if final_plan else [],
        "current_plan_version": 1 if final_plan else 0,
        "evidence": result.get("evidence", []),
        "wiki_pages_used": result.get("wiki_pages_used", []),
        "confidence_score": result.get("confidence_score", 0.0),
        "output_path": result.get("output_path", ""),
        "generated_plan_path": result.get("generated_plan_path", ""),
        "phases": _phases_from_state(result),
    }
    snapshot["disposition_graph"] = build_disposition_graph(snapshot)
    for item in sessions:
        if str(item.get("id")) == session_id:
            item.update(snapshot)
            if not item.get("title") or str(item.get("title")).startswith("新建事故会话"):
                item["title"] = description[:24] or "事故会话"
            break
    else:
        sessions.insert(
            0,
            {
                "id": session_id,
                "title": description[:24] or "事故会话",
                "created_at": now,
                **snapshot,
            },
        )
    _write_sessions(sessions)


def _find_session(session_id: str) -> Dict[str, Any] | None:
    for item in _read_sessions():
        if str(item.get("id")) == session_id:
            return item
    return None


def _append_session_messages(session_id: str, question: str, answer: str) -> None:
    sessions = _read_sessions()
    now = datetime.now().isoformat(timespec="seconds")
    for item in sessions:
        if str(item.get("id")) != session_id:
            continue
        messages = item.get("messages")
        if not isinstance(messages, list):
            messages = []
            if item.get("description"):
                messages.append({"role": "user", "content": item.get("description", ""), "created_at": item.get("created_at", "")})
            if item.get("final_plan"):
                messages.append({"role": "assistant", "content": "已完成处置方案生成，详见 Agent 阶段卡片与最终方案 Markdown。", "created_at": item.get("updated_at", "")})
        messages.extend(
            [
                {"role": "user", "content": question, "created_at": now},
                {"role": "assistant", "content": answer, "created_at": now},
            ]
        )
        item["messages"] = messages
        item["updated_at"] = now
        break
    _write_sessions(sessions)


def _update_session_conversation(session_id: str, question: str, result: Dict[str, Any]) -> None:
    sessions = _read_sessions()
    now = datetime.now().isoformat(timespec="seconds")
    answer = result.get("answer", "")
    for item in sessions:
        if str(item.get("id")) != session_id:
            continue
        messages = item.get("messages")
        if not isinstance(messages, list):
            messages = []
            if item.get("description"):
                messages.append({"role": "user", "content": item.get("description", ""), "created_at": item.get("created_at", "")})
            if item.get("final_plan"):
                messages.append({"role": "assistant", "content": "已完成处置方案生成，详见 Agent 阶段卡片与最终方案 Markdown。", "created_at": item.get("updated_at", "")})
        messages.extend(
            [
                {"role": "user", "content": question, "created_at": now},
                {"role": "assistant", "content": answer, "created_at": now},
            ]
        )
        final_plan = result.get("final_plan") or result.get("current_plan") or item.get("final_plan", "")
        plan_versions = item.get("plan_versions")
        if not isinstance(plan_versions, list):
            existing_plan = item.get("final_plan", "")
            plan_versions = [_plan_version_entry(1, existing_plan, item, item.get("updated_at") or now)] if existing_plan else []
        if result.get("plan_updated") and final_plan:
            plan_versions.append(_plan_version_entry(len(plan_versions) + 1, final_plan, result, now))

        item.update(
            {
                "updated_at": now,
                "messages": messages,
                "accident": result.get("accident", item.get("accident", {})),
                "parse_report": result.get("parse_report", item.get("parse_report", "")),
                "similar_cases": result.get("similar_cases", item.get("similar_cases", "")),
                "aggressive_plan": result.get("aggressive_plan", item.get("aggressive_plan", "")),
                "conservative_plan": result.get("conservative_plan", item.get("conservative_plan", "")),
                "compliance_report": result.get("compliance_report", item.get("compliance_report", "")),
                "final_plan": final_plan,
                "plan_versions": plan_versions,
                "current_plan_version": len(plan_versions),
                "evidence": result.get("evidence", item.get("evidence", [])),
                "wiki_pages_used": result.get("wiki_pages_used", item.get("wiki_pages_used", [])),
                "confidence_score": result.get("confidence_score", item.get("confidence_score", 0.0)),
                "output_path": result.get("output_path", item.get("output_path", "")),
                "generated_plan_path": result.get("generated_plan_path", item.get("generated_plan_path", "")),
                "debate_rounds": result.get("debate_rounds", item.get("debate_rounds", [])),
                "last_intent": result.get("input_intent", ""),
                "last_mode": result.get("mode", ""),
                "phases": _phases_from_state(result),
            }
        )
        item["disposition_graph"] = build_disposition_graph(item)
        break
    _write_sessions(sessions)


def _answer_followup(question: str, session: Dict[str, Any]) -> str:
    evidence_lines = []
    for item in session.get("evidence", [])[:10]:
        page = item.get("source_page") or ""
        summary = item.get("summary") or item.get("quote") or ""
        if page or summary:
            evidence_lines.append(f"- {page}：{summary}")
    prompt = f"""请基于同一事故会话回答用户追问，不要重新生成完整处置方案。

要求：
1. 只回答追问本身，必要时引用已有方案、标准页、案例页或标注工程推断。
2. 不得编造标准条款、页码、扭矩、拉力、震击参数。
3. 如追问需要新增现场信息，明确说明需要补充什么。
4. 用简洁 Markdown 输出，可使用表格。

事故信息：
{json.dumps(session.get("accident", {}), ensure_ascii=False)}

已有最终方案：
{str(session.get("final_plan", ""))[:6000]}

已有合规审核：
{str(session.get("compliance_report", ""))[:2000]}

证据摘要：
{chr(10).join(evidence_lines) or "暂无证据摘要。"}

用户追问：
{question}
"""
    answer = try_complete_text(
        prompt,
        system="你是钻具落断事故处置方案问答助手，只基于当前会话上下文作答。",
        outputs_dir=OUTPUTS_DIR,
        temperature=0.15,
        max_tokens=1600,
    )
    if answer:
        return answer
    return _fallback_followup_answer(question, session)


def _fallback_followup_answer(question: str, session: Dict[str, Any]) -> str:
    final_plan = str(session.get("final_plan", ""))
    compliance = str(session.get("compliance_report", ""))
    if any(term in question for term in ["依据", "标准", "行标", "引用"]):
        return "\n".join(
            [
                "## 引用依据说明",
                "",
                "当前会话已有方案主要依据已归档方案中的“关键引用摘录”和“参考依据”。",
                "",
                compliance or "- 合规审核未返回详细内容，需复核 Wiki 标准页。",
            ]
        )
    if any(term in question for term in ["激进", "保守", "差异", "区别"]):
        return "\n".join(
            [
                "| 维度 | 激进方案 | 保守方案 |",
                "| --- | --- | --- |",
                "| 目标 | 尽快恢复作业 | 优先控制井控安全和事故扩大风险 |",
                "| 起始动作 | 快速复核后尽快进入清洁、打捞或强化路径 | 先复核井况、循环洗井/冲砂，再逐级升级 |",
                "| 参数要求 | 所有强化参数需现场设计确认 | 不凭空给出上提、扭矩、震击参数 |",
                "| 停止条件 | 井控风险、循环失效、工具异常立即转保守 | 任一阶段异常即暂停复核 |",
            ]
        )
    return "\n".join(
        [
            "## 追问回答",
            "",
            "这个问题应结合当前已生成方案判断。核心原则是：先关闭缺失信息和高风险项，再决定是否升级处置。",
            "",
            "- 扣型、井斜、落鱼尺寸等缺失信息仍应标为待确认。",
            "- 无现场强度校核时，不应给出精确上提力、扭矩或震击参数。",
            "- 需要具体条款时，请打开已归档方案中的参考依据或 Wiki 标准页复核。",
            "",
            "当前最终方案摘要：",
            final_plan[:800] or "当前会话没有可用最终方案。",
        ]
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

    @app.delete("/api/sessions/{session_id}")
    def delete_session(session_id: str) -> Dict[str, Any]:
        sessions = _read_sessions()
        remaining = [item for item in sessions if str(item.get("id")) != session_id]
        if len(remaining) == len(sessions):
            raise HTTPException(status_code=404, detail="Session not found")
        _write_sessions(remaining)
        return {"deleted": True, "id": session_id}

    @app.get("/api/sessions/{session_id}/disposition-graph")
    def session_disposition_graph(session_id: str) -> Dict[str, Any]:
        session = _find_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return build_disposition_graph(session)

    @app.post("/api/solve")
    def solve(payload: SolveRequest) -> Dict[str, Any]:
        state = solve_accident(
            payload.description,
            wiki_dir=str(WIKI_DIR),
            outputs_dir=str(OUTPUTS_DIR),
            archive=payload.archive,
        )
        response = {
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
            "llm": {
                "enabled": state.get("llm_enabled", False),
                "provider": state.get("llm_provider", ""),
                "fallback_reason": state.get("llm_fallback_reason", ""),
            },
            "output_path": state.get("output_path"),
            "generated_plan_path": state.get("generated_plan_path"),
            "phases": _phases_from_state(state),
            "plan_version": 1 if state.get("final_plan") else 0,
        }
        response["disposition_graph"] = build_disposition_graph({**response, "description": payload.description})
        _update_session_result(payload.session_id, payload.description, response)
        return response

    @app.post("/api/chat")
    def chat_followup(payload: ChatRequest) -> Dict[str, Any]:
        session = _find_session(payload.session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        result = converse_accident(
            payload.question,
            session,
            wiki_dir=str(WIKI_DIR),
            outputs_dir=str(OUTPUTS_DIR),
            mode=payload.mode,
        )
        existing_versions = session.get("plan_versions") if isinstance(session.get("plan_versions"), list) else []
        next_version = len(existing_versions) + 1 if result.get("plan_updated") else len(existing_versions)
        _update_session_conversation(payload.session_id, payload.question, result)
        response = {
            "session_id": payload.session_id,
            "answer": result.get("answer", ""),
            "mode": result.get("mode") or "explain",
            "intent": result.get("input_intent", ""),
            "route_reason": result.get("route_reason", ""),
            "plan_updated": bool(result.get("plan_updated")),
            "accident": result.get("accident", {}),
            "parse_report": result.get("parse_report", ""),
            "similar_cases": result.get("similar_cases", ""),
            "aggressive_plan": result.get("aggressive_plan", ""),
            "conservative_plan": result.get("conservative_plan", ""),
            "compliance_report": result.get("compliance_report", ""),
            "final_plan": result.get("final_plan") or result.get("current_plan", ""),
            "evidence": result.get("evidence", []),
            "wiki_pages_used": result.get("wiki_pages_used", []),
            "confidence_score": result.get("confidence_score", 0.0),
            "output_path": result.get("output_path"),
            "generated_plan_path": result.get("generated_plan_path"),
            "debate_rounds": result.get("debate_rounds", []),
            "phases": _phases_from_state(result),
            "plan_version": next_version,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        response["disposition_graph"] = build_disposition_graph({**session, **response, "description": session.get("description", "")})
        return response

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

    @app.get("/api/wiki/graph")
    def wiki_graph() -> Dict[str, Any]:
        graph_path = Path("graph") / "graph.json"
        if not graph_path.exists():
            try:
                build_graph(WIKI_DIR, "graph")
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"Failed to build wiki graph: {exc}") from exc
        try:
            data = json.loads(graph_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=500, detail="Invalid graph.json") from exc
        return data if isinstance(data, dict) else {"nodes": [], "edges": []}

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

    @app.delete("/api/wiki/generated-plans/{path:path}")
    def delete_generated_plan(path: str) -> Dict[str, Any]:
        candidate = _safe_wiki_path(path)
        try:
            rel = candidate.relative_to(WIKI_DIR.resolve()).as_posix()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid wiki path") from exc
        if not rel.startswith("generated_plans/") or candidate.suffix != ".md":
            raise HTTPException(status_code=400, detail="Only generated plan pages can be deleted")
        if not candidate.exists() or not candidate.is_file():
            raise HTTPException(status_code=404, detail="Generated plan not found")
        candidate.unlink()
        output_peer = OUTPUTS_DIR / candidate.name
        if output_peer.exists() and output_peer.is_file():
            output_peer.unlink()
        _remove_index_link(candidate.stem)
        return {"deleted": True, "path": rel}

    return app


app = create_app()


def _remove_index_link(title: str) -> None:
    index_path = WIKI_DIR / "index.md"
    if not index_path.exists():
        return
    try:
        lines = index_path.read_text(encoding="utf-8").splitlines()
        filtered = [line for line in lines if line.strip() != f"- [[{title}]]"]
        index_path.write_text("\n".join(filtered).rstrip() + "\n", encoding="utf-8")
    except OSError:
        return
