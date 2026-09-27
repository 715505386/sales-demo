from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class Evidence(BaseModel):
    """分析结论的证据来源模型。"""

    model_config = ConfigDict(extra="forbid")

    source_type: str
    source_id: str
    title: str
    content: str


class EmailDraft(BaseModel):
    """邮件草稿模型，表示生成但尚未发送的邮件内容。"""

    model_config = ConfigDict(extra="forbid")

    recipient: str
    subject: str
    body: str
    language: str
    tone: str


class AnalysisResult(BaseModel):
    """Agent 最终结构化分析结果模型。"""

    model_config = ConfigDict(extra="forbid")

    customer_profile: dict[str, Any]
    recent_orders: list[dict[str, Any]]
    followup_summary: list[dict[str, Any]]
    product_materials: list[dict[str, Any]]
    sales_materials: list[dict[str, Any]]
    customer_status: str
    followup_suggestions: list[str]
    email_draft: EmailDraft
    risks_and_missing_data: list[str]
    evidence: list[Evidence]


class ChatRequest(BaseModel):
    """前端发送给 Agent HTTP 服务的聊天请求模型。"""

    model_config = ConfigDict(extra="forbid")

    session_id: str
    message: str = Field(min_length=1)
    request_id: str | None = None


class SessionState(BaseModel):
    """当前会话的多轮状态模型。"""

    model_config = ConfigDict(extra="forbid")

    pending_candidates: list[dict[str, Any]] = Field(default_factory=list)
    pending_query: str | None = None


class AgentFailure(BaseModel):
    """Agent 无法完成分析时返回给前端的结构化失败模型。"""

    status: Literal["failed", "input_required"]
    message: str
    request_id: str
    candidates: list[dict[str, Any]] = Field(default_factory=list)
