"""Provider-neutral LLM call wrapper for backend agents.

The wrapper keeps model access optional: callers can ask whether a configured
client is available and fall back to deterministic logic when credentials are
missing or a provider call fails.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - dependency is optional at import time
    load_dotenv = None


DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-sonnet-4-5",
    "zai": "glm-5.1",
    "custom": "",
}

DEFAULT_BASE_URLS: dict[str, str] = {
    "zai": "https://api.z.ai/api/paas/v4/",
}


class LLMConfigurationError(RuntimeError):
    """Raised when no usable LLM configuration is available."""


class LLMCallError(RuntimeError):
    """Raised when a configured provider call fails."""


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    model: str
    api_key: str
    base_url: str = ""
    enabled: bool = True
    timeout: float = 60.0

    @property
    def configured(self) -> bool:
        return bool(self.enabled and self.provider and self.model and self.api_key)

    def public(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "base_url": self.base_url,
            "enabled": self.enabled,
            "has_api_key": bool(self.api_key),
            "masked_api_key": mask_secret(self.api_key),
        }


def mask_secret(value: str) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}****{value[-4:]}"


def load_llm_config(
    *,
    outputs_dir: str | Path = "outputs",
    config_path: str | Path | None = None,
) -> LLMConfig:
    """Load LLM settings from outputs/llm_config.json with env fallback."""

    if load_dotenv is not None:
        load_dotenv()

    file_config = _read_config_file(config_path or Path(outputs_dir) / "llm_config.json")
    provider = _clean(file_config.get("provider") or os.getenv("LLM_PROVIDER") or _default_provider()).lower()
    enabled = _as_bool(file_config.get("enabled"), default=_as_bool(os.getenv("LLM_ENABLED"), default=True))
    model = _clean(
        file_config.get("model")
        or os.getenv("LLM_MODEL")
        or os.getenv(f"{provider.upper()}_MODEL")
        or (os.getenv("AGENT_MODEL") if provider in {"anthropic", "zai"} else "")
        or DEFAULT_MODELS.get(provider, "")
    )
    base_url = _clean(
        file_config.get("base_url")
        or os.getenv("LLM_BASE_URL")
        or os.getenv(f"{provider.upper()}_BASE_URL")
        or DEFAULT_BASE_URLS.get(provider, "")
    )
    api_key = _clean(file_config.get("api_key") or _env_api_key(provider))
    timeout = _float_env("LLM_TIMEOUT_SECONDS", 20.0)
    return LLMConfig(provider=provider, model=model, api_key=api_key, base_url=base_url, enabled=enabled, timeout=timeout)


def is_llm_configured(*, outputs_dir: str | Path = "outputs") -> bool:
    return load_llm_config(outputs_dir=outputs_dir).configured


def complete_text(
    prompt: str,
    *,
    system: str = "",
    outputs_dir: str | Path = "outputs",
    temperature: float = 0.2,
    max_tokens: int = 1600,
) -> str:
    """Complete a single prompt using the configured provider."""

    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    return chat(messages, outputs_dir=outputs_dir, temperature=temperature, max_tokens=max_tokens)


def complete_json(
    prompt: str,
    *,
    system: str = "",
    outputs_dir: str | Path = "outputs",
    temperature: float = 0.0,
    max_tokens: int = 1200,
) -> dict[str, Any]:
    """Complete a prompt and parse the first JSON object from the response."""

    text = complete_text(
        prompt,
        system=system,
        outputs_dir=outputs_dir,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return parse_json_object(text)


def chat(
    messages: Iterable[Mapping[str, str]],
    *,
    outputs_dir: str | Path = "outputs",
    temperature: float = 0.2,
    max_tokens: int = 1600,
) -> str:
    config = load_llm_config(outputs_dir=outputs_dir)
    if not config.configured:
        raise LLMConfigurationError("LLM is not configured")
    if config.provider == "anthropic":
        return _chat_anthropic(config, messages, temperature=temperature, max_tokens=max_tokens)
    if config.provider in {"openai", "custom", "zai"}:
        return _chat_openai_compatible(config, messages, temperature=temperature, max_tokens=max_tokens)
    raise LLMConfigurationError(f"Unsupported LLM provider: {config.provider}")


def try_complete_text(
    prompt: str,
    *,
    system: str = "",
    outputs_dir: str | Path = "outputs",
    temperature: float = 0.2,
    max_tokens: int = 1600,
) -> str | None:
    """Best-effort completion. Returns None on missing config or call failure."""

    try:
        return complete_text(
            prompt,
            system=system,
            outputs_dir=outputs_dir,
            temperature=temperature,
            max_tokens=max_tokens,
        ).strip()
    except (LLMConfigurationError, LLMCallError, ValueError):
        return None


def try_complete_json(
    prompt: str,
    *,
    system: str = "",
    outputs_dir: str | Path = "outputs",
    temperature: float = 0.0,
    max_tokens: int = 1200,
) -> dict[str, Any] | None:
    try:
        return complete_json(
            prompt,
            system=system,
            outputs_dir=outputs_dir,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except (LLMConfigurationError, LLMCallError, ValueError, json.JSONDecodeError):
        return None


def parse_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, flags=re.DOTALL)
    if fence:
        cleaned = fence.group(1)
    elif not cleaned.startswith("{"):
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            cleaned = cleaned[start : end + 1]
    data = json.loads(cleaned)
    if not isinstance(data, dict):
        raise ValueError("LLM response JSON must be an object")
    return data


def _chat_anthropic(
    config: LLMConfig,
    messages: Iterable[Mapping[str, str]],
    *,
    temperature: float,
    max_tokens: int,
) -> str:
    try:
        import anthropic
    except Exception as exc:  # pragma: no cover - depends on local install
        raise LLMConfigurationError("anthropic package is not installed") from exc

    system_parts: list[str] = []
    provider_messages: list[dict[str, str]] = []
    for message in messages:
        role = message.get("role", "user")
        content = message.get("content", "")
        if role == "system":
            system_parts.append(content)
        else:
            provider_messages.append({"role": "assistant" if role == "assistant" else "user", "content": content})

    try:
        client_kwargs: dict[str, Any] = {"api_key": config.api_key, "timeout": config.timeout}
        if config.base_url:
            client_kwargs["base_url"] = config.base_url
        client = anthropic.Anthropic(**client_kwargs)
        request_kwargs: dict[str, Any] = {
            "model": config.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": provider_messages,
        }
        if system_parts:
            request_kwargs["system"] = "\n\n".join(system_parts)
        response = client.messages.create(**request_kwargs)
        parts = [getattr(block, "text", "") for block in getattr(response, "content", [])]
        text = "".join(parts).strip()
    except Exception as exc:  # pragma: no cover - provider/network dependent
        raise LLMCallError(f"Anthropic call failed: {exc}") from exc
    if not text:
        raise LLMCallError("Anthropic response was empty")
    return text


def _chat_openai_compatible(
    config: LLMConfig,
    messages: Iterable[Mapping[str, str]],
    *,
    temperature: float,
    max_tokens: int,
) -> str:
    base_url = (config.base_url or "https://api.openai.com/v1").rstrip("/")
    endpoint = base_url if base_url.endswith("/chat/completions") else f"{base_url}/chat/completions"
    payload = {
        "model": config.model,
        "messages": [{"role": item.get("role", "user"), "content": item.get("content", "")} for item in messages],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=config.timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")[:600]
        raise LLMCallError(f"OpenAI-compatible call failed: HTTP {exc.code} {body}") from exc
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise LLMCallError(f"OpenAI-compatible call failed: {exc}") from exc

    try:
        text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LLMCallError("OpenAI-compatible response did not include choices[0].message.content") from exc
    if not text:
        raise LLMCallError("OpenAI-compatible response was empty")
    return str(text).strip()


def _read_config_file(path: str | Path) -> dict[str, Any]:
    candidate = Path(path)
    if not candidate.exists():
        return {}
    try:
        data = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _env_api_key(provider: str) -> str:
    if provider == "anthropic":
        return os.getenv("ANTHROPIC_API_KEY") or os.getenv("LLM_API_KEY") or ""
    if provider in {"openai", "custom"}:
        return os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY") or ""
    if provider == "zai":
        return os.getenv("ZAI_API_KEY") or os.getenv("GLM_API_KEY") or os.getenv("LLM_API_KEY") or ""
    return os.getenv("LLM_API_KEY") or ""


def _default_provider() -> str:
    if os.getenv("ZAI_API_KEY") or os.getenv("GLM_API_KEY"):
        return "zai"
    if os.getenv("ANTHROPIC_API_KEY") and not os.getenv("OPENAI_API_KEY"):
        return "anthropic"
    return "openai"


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _as_bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in {"0", "false", "no", "off", "disabled"}


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, ""))
    except ValueError:
        return default
