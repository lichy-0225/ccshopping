"""Minimal DeepSeek OpenAI-compatible client.

The client is intentionally isolated from deterministic product and safety
logic. If the network or key is unavailable, callers can fall back to the
deterministic demo wording.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

try:
    from dotenv import load_dotenv
except ImportError:  # Keep the MVP runnable before optional dependencies install.
    def load_dotenv() -> None:
        env_file = Path(__file__).resolve().parents[3] / ".env"
        if not env_file.exists():
            return
        for raw_line in env_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))

from pathlib import Path

load_dotenv()


class DeepSeekClient:
    def __init__(self) -> None:
        self.api_key = os.getenv("LLM_API_KEY", "").strip()
        self.base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
        self.model = os.getenv("LLM_MODEL", "deepseek-v4-flash").strip() or "deepseek-v4-flash"
        self.timeout = float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
        self.max_output_tokens = int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "512"))

    @property
    def configured(self) -> bool:
        return bool(self.api_key)

    def chat(self, messages: list[dict], tools: list[dict] | None = None, max_tokens: int | None = None) -> dict[str, Any]:
        if not self.configured:
            return {"choices": [{"message": {"role": "assistant", "content": None}}]}
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "thinking": {"type": "disabled"},
            "max_tokens": max_tokens or self.max_output_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def complete(self, system: str, user: str) -> str | None:
        data = self.chat([{"role": "system", "content": system}, {"role": "user", "content": user}])
        content = data.get("choices", [{}])[0].get("message", {}).get("content")
        return content.strip() if isinstance(content, str) else None

    def test_connection(self) -> dict[str, Any]:
        if not self.configured:
            return {"configured": False, "ok": False, "error": "LLM_API_KEY 未配置"}
        try:
            content = self.complete("只回复 OK，不要添加其他内容。", "连接测试")
            return {"configured": True, "ok": bool(content), "model": self.model}
        except httpx.HTTPStatusError as exc:
            return {"configured": True, "ok": False, "model": self.model, "error": f"DeepSeek HTTP {exc.response.status_code}"}
        except (httpx.HTTPError, ValueError) as exc:
            return {"configured": True, "ok": False, "model": self.model, "error": type(exc).__name__}
