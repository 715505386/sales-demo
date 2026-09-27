from __future__ import annotations

import json
import re
from typing import Any

from langchain_openai import ChatOpenAI

from .config import (
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MODEL,
    LLM_TEMPERATURE,
    LLM_TIMEOUT_SECONDS,
)


def create_llm() -> ChatOpenAI | None:
    """根据配置创建 LangChain ChatOpenAI 客户端。

    参数：无。
    返回值：配置了 API Key 时返回模型客户端，否则返回 None。
    """
    if not LLM_API_KEY:
        return None
    return ChatOpenAI(
        model=LLM_MODEL,
        base_url=LLM_BASE_URL,
        api_key=LLM_API_KEY,
        temperature=LLM_TEMPERATURE,
        timeout=LLM_TIMEOUT_SECONDS,
        max_retries=0,
    )


def parse_json_object(text: str) -> dict[str, Any]:
    """从模型输出中解析 JSON 对象。

    参数：
        text：模型返回的原始文本，可能包含 Markdown 代码围栏。
    返回值：解析后的 JSON 字典。
    """
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("模型没有返回 JSON 对象")
    return json.loads(cleaned[start : end + 1])


def extract_tool_text(result: Any) -> str:
    """从 MCP 工具调用结果中提取文本内容。

    参数：
        result：MCP SDK 返回的工具调用结果对象。
    返回值：工具结果文本；无法直接提取时返回序列化后的 JSON 字符串。
    """
    parts = getattr(result, "content", [])
    for part in parts:
        text = getattr(part, "text", None)
        if text:
            return text
    return json.dumps(result, ensure_ascii=False, default=str)
