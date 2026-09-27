from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import date
from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from mcp import ClientSession
try:
    from mcp.client.streamable_http import streamable_http_client
except ImportError:  # 兼容旧版 MCP SDK 的函数命名。
    from mcp.client.streamable_http import streamablehttp_client as streamable_http_client

from .config import (
    JSON_RETRY_LIMIT,
    MAX_TOOL_CALLS,
    MCP_URL,
)
from .db import get_session_state, persist_event
from .logging_utils import logger
from .models import AnalysisResult, AgentFailure, EmailDraft, SessionState
from .utils import create_llm, extract_tool_text, parse_json_object


AnalysisEvent = dict[str, Any]
EventSink = Callable[[AnalysisEvent], Awaitable[None]]

SYNTHESIS_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
你是跨境电商公司的销售个人助理。只能依据输入的客户、订单、跟进和资料内容回答。
不要编造业务事实；没有数据时写入 risks_and_missing_data。
页面语言为中文。邮件根据客户国家选择中文或英文，无法判断时使用英文。
只输出一个合法 JSON 对象，不要 Markdown 代码围栏，不要额外解释。

JSON 必须严格符合以下字段：
{{
  "customer_profile": {{}},
  "recent_orders": [],
  "followup_summary": [],
  "product_materials": [],
  "sales_materials": [],
  "customer_status": "",
  "followup_suggestions": [],
  "email_draft": {{
    "recipient": "",
    "subject": "",
    "body": "",
    "language": "",
    "tone": ""
  }},
  "risks_and_missing_data": [],
  "evidence": [
    {{
      "source_type": "",
      "source_id": "",
      "title": "",
      "content": ""
    }}
  ]
}}

客户上下文：
{customer_context}

邮件字段规则：
- customer.name 是客户或公司名称，不是联系人姓名。
- customer.contact_name 是邮件称呼必须使用的联系人全名。
- customer.email 是邮件收件地址，必须原样填入 recipient。
- 海外客户（country 不是中国或中国大陆）的邮件 subject 和 body 必须全部使用英文，不能出现中文字符。
- 海外客户的邮件正文必须使用 customer.contact_name 的全名称呼，不能使用客户公司名，也不能自行猜测或缩写联系人姓名。

产品资料：
{product_materials}

销售资料：
{sales_materials}

销售问题：
{query}

当前日期：2026-09-25
""",
        )
    ]
)


def _event(
    event_type: str,
    message: str,
    *,
    request_id: str,
    **extra: Any,
) -> AnalysisEvent:
    """构造前端可消费的 Agent 流式事件。

    参数：
        event_type：事件类型，例如 progress、tool_start、tool_end。
        message：展示给用户的事件说明。
        request_id：本次分析请求 ID。
        extra：附加事件字段。
    返回值：标准事件字典。
    """
    return {
        "type": event_type,
        "message": message,
        "request_id": request_id,
        **extra,
    }


def _extract_customer_query(message: str) -> str:
    """从销售问题中提取客户查询词。

    参数：
        message：销售输入的自然语言问题。
    返回值：提取出的客户名称或公司名称；无法提取时返回空字符串。
    """
    patterns = [
        r"(?:客户|关于|看看|分析)\s*([A-Za-z0-9\u4e00-\u9fff][^，。！？,!?]*)",
        r"([A-Za-z\u4e00-\u9fff][A-Za-z0-9\u4e00-\u9fff ]{1,}?)\s*(?:的)?\s*(?:最近|情况|跟进)",
    ]
    for pattern in patterns:
        match = re.search(pattern, message)
        if match:
            candidate = match.group(1).strip()
            candidate = re.split(
                r"(?:最近|情况|跟进|下一步|怎么跟进)",
                candidate,
                maxsplit=1,
            )[0].strip()
            if candidate in {"客户", "这个客户", "该客户", "此客户"}:
                continue
            if candidate:
                return candidate
    return ""


def _parse_choice(message: str, candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    """把销售回复的编号解析为候选客户。

    参数：
        message：销售回复内容，通常是“1”或“2号”。
        candidates：上一轮保存的候选客户列表。
    返回值：选中的客户字典；无法匹配时返回 None。
    """
    match = re.fullmatch(r"\s*(\d+)\s*[号.]?\s*", message)
    if not match:
        return None
    index = int(match.group(1)) - 1
    return candidates[index] if 0 <= index < len(candidates) else None


_CJK_RE = re.compile(r"[\u3400-\u9fff]")


def _is_overseas_customer(customer: dict[str, Any]) -> bool:
    """判断客户是否属于海外客户。"""
    return str(customer.get("country", "")).strip() not in {"中国", "中国大陆"}


def _english_email_draft(
    customer: dict[str, Any],
    orders: list[dict[str, Any]],
    followups: list[dict[str, Any]],
) -> EmailDraft:
    """为海外客户生成包含真实联系人和业务事实的英文邮件。"""
    contact_name = str(customer.get("contact_name", "")).strip()
    recipient = str(customer.get("email", "")).strip()
    latest_order = orders[0] if orders else {}
    order_no = str(latest_order.get("order_no", "")).strip()
    product_name = str(latest_order.get("product_name", "")).strip()
    latest_followup = followups[0] if followups else {}
    next_action = str(latest_followup.get("next_action", "")).strip()

    order_reference = f"your recent order {order_no}" if order_no else "your recent business"
    product_reference = f" for {product_name}" if product_name else ""
    next_step = (
        f"We would also like to follow up on the next step: {next_action}"
        if next_action
        else "We would also like to understand your upcoming procurement plans."
    )
    greeting = f"Dear {contact_name}," if contact_name else "Hello,"
    body = (
        f"{greeting}\n\n"
        f"I hope you are doing well. I am following up on {order_reference}"
        f"{product_reference}. Could you share your current usage and expected demand "
        "for the next three months?\n\n"
        f"{next_step} Please also let us know your procurement timeline and budget window "
        "so that we can provide the right support.\n\n"
        "I look forward to your reply and would be happy to answer any questions.\n\n"
        "Best regards,"
    )
    subject = f"Follow-up on order {order_no}" if order_no else "Follow-up on your recent business"
    return EmailDraft(
        recipient=recipient,
        subject=subject,
        body=body,
        language="English",
        tone="professional and friendly",
    )


def _normalize_email_draft(
    result: AnalysisResult,
    customer: dict[str, Any],
    orders: list[dict[str, Any]],
    followups: list[dict[str, Any]],
) -> AnalysisResult:
    """校正收件人和海外邮件语言，避免模型混淆公司名与联系人名。"""
    expected_recipient = str(customer.get("email", "")).strip()
    expected_contact = str(customer.get("contact_name", "")).strip()
    draft = result.email_draft
    overseas = _is_overseas_customer(customer)
    body_and_subject = f"{draft.subject}\n{draft.body}"
    language = draft.language.strip().lower()
    english_required = overseas and (
        language not in {"en", "english"}
        or bool(_CJK_RE.search(body_and_subject))
        or (bool(expected_contact) and expected_contact.casefold() not in draft.body.casefold())
    )
    recipient_mismatch = bool(expected_recipient) and draft.recipient.strip().casefold() != expected_recipient.casefold()

    if overseas and (english_required or recipient_mismatch):
        result.email_draft = _english_email_draft(customer, orders, followups)
    else:
        updates: dict[str, str] = {}
        if expected_recipient:
            updates["recipient"] = expected_recipient
        if overseas:
            updates["language"] = "English"
        if updates:
            result.email_draft = draft.model_copy(update=updates)
    return result


class SalesAgent:
    """单 Agent 编排器，负责客户识别、MCP 工具调用和结构化结果生成。"""

    def __init__(self) -> None:
        """初始化 Agent 实例。

        参数：无。
        返回值：无。
        """
        self.llm = create_llm()

    async def _emit(
        self,
        sink: EventSink | None,
        event: AnalysisEvent,
    ) -> None:
        """向流式响应接收器发送事件。

        参数：
            sink：事件接收函数；为空时忽略事件。
            event：需要发送的事件字典。
        返回值：无。
        """
        if sink:
            await sink(event)

    async def _call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        session_id: str,
        request_id: str,
        sink: EventSink | None,
    ) -> dict[str, Any]:
        """通过 MCP Streamable HTTP 调用单个只读工具。

        参数：
            name：MCP 工具名。
            arguments：工具参数。
            session_id：当前聊天会话 ID。
            request_id：当前分析请求 ID。
            sink：流式事件接收函数。
        返回值：工具返回的 JSON 字典。
        """
        if not hasattr(self, "_tool_count"):
            self._tool_count = 0
        self._tool_count += 1
        if self._tool_count > MAX_TOOL_CALLS:
            raise RuntimeError("本次分析已达到 MCP 工具调用上限。")

        await self._emit(
            sink,
            _event(
                "tool_start",
                f"正在调用 {name}",
                request_id=request_id,
                tool_name=name,
                arguments=arguments,
            ),
        )
        started = time.perf_counter()
        try:
            # MCP 是业务数据的唯一访问边界，Agent 不直接连接数据库或知识库。
            async with streamable_http_client(MCP_URL) as streams:
                read, write = streams[:2]
                async with ClientSession(read, write) as client:
                    await client.initialize()
                    result = await asyncio.wait_for(
                        client.call_tool(name, arguments),
                        timeout=30,
                    )
            payload = json.loads(extract_tool_text(result))
            duration_ms = round((time.perf_counter() - started) * 1000)
            # 每次工具调用都持久化，便于页面展开查看和后续问题排查。
            persist_event(
                {
                    "event_type": "tool_call",
                    "session_id": session_id,
                    "request_id": request_id,
                    "tool_name": name,
                    "arguments": arguments,
                    "result": payload,
                    "status": "success",
                    "duration_ms": duration_ms,
                }
            )
            await self._emit(
                sink,
                _event(
                    "tool_end",
                    f"{name} 完成",
                    request_id=request_id,
                    tool_name=name,
                    arguments=arguments,
                    result=payload,
                    duration_ms=duration_ms,
                    status="success",
                ),
            )
            return payload
        except Exception as exc:
            duration_ms = round((time.perf_counter() - started) * 1000)
            persist_event(
                {
                    "event_type": "tool_call",
                    "session_id": session_id,
                    "request_id": request_id,
                    "tool_name": name,
                    "arguments": arguments,
                    "result": {"error": str(exc)},
                    "status": "failed",
                    "duration_ms": duration_ms,
                }
            )
            await self._emit(
                sink,
                _event(
                    "tool_end",
                    f"{name} 失败",
                    request_id=request_id,
                    tool_name=name,
                    arguments=arguments,
                    result={"error": str(exc)},
                    duration_ms=duration_ms,
                    status="failed",
                ),
            )
            raise

    async def _fallback(
        self,
        query: str,
        customer: dict[str, Any],
        orders: list[dict[str, Any]],
        followups: list[dict[str, Any]],
        products: list[dict[str, Any]],
        sales: list[dict[str, Any]],
    ) -> AnalysisResult:
        """在没有模型 API Key 时生成确定性的本地分析结果。

        参数：
            query：销售原始问题。
            customer：客户基础信息。
            orders：客户订单列表。
            followups：客户历史跟进列表。
            products：命中的产品资料片段。
            sales：命中的销售资料片段。
        返回值：符合 AnalysisResult 的结构化结果。
        """
        latest_order = orders[0] if orders else None
        latest_followup = followups[0] if followups else None
        product_names = "、".join(dict.fromkeys(row["product_name"] for row in orders)) or "暂无"
        country = customer.get("country", "")
        email_language = "中文" if country in {"中国", "中国大陆"} else "英文"
        suggestion = (
            f"围绕最近产品 {product_names} 确认使用反馈、未来三个月需求和新增站点计划，"
            "建议安排一次 20 分钟回访。"
        )
        return AnalysisResult(
            customer_profile=customer,
            recent_orders=orders,
            followup_summary=followups,
            product_materials=products,
            sales_materials=sales,
            customer_status=(
                f"{customer['status']}客户，已有 {len(orders)} 笔订单，"
                f"最近订单日期为 {latest_order['order_date'] if latest_order else '暂无'}。"
            ),
            followup_suggestions=[suggestion],
            email_draft={
                "recipient": customer["email"],
                "subject": f"Follow-up on {customer['company']} cooperation",
                "body": (
                    f"Hello {customer['contact_name']},\n\n"
                    "I would like to follow up on your recent product usage and discuss "
                    "your upcoming business plans. Would you be available for a short call?"
                ),
                "language": email_language,
                "tone": "professional",
            },
            risks_and_missing_data=[
                message
                for message, missing in (
                    ("缺少订单记录", not orders),
                    ("缺少历史跟进记录", not followups),
                    ("没有检索到产品资料", not products),
                    ("没有检索到销售资料", not sales),
                    ("最近跟进没有明确下一步动作", bool(latest_followup and not latest_followup.get("next_action"))),
                )
                if missing
            ],
            evidence=[
                {
                    "source_type": "order",
                    "source_id": str(row["order_no"]),
                    "title": f"订单 {row['order_no']}",
                    "content": json.dumps(row, ensure_ascii=False, default=str),
                }
                for row in orders[:3]
            ]
            + [
                {
                    "source_type": "followup",
                    "source_id": str(row["id"]),
                    "title": f"跟进记录 {row['id']}",
                    "content": row["summary"],
                }
                for row in followups[:3]
            ]
            + [
                {
                    "source_type": "product_material",
                    "source_id": row["source_id"],
                    "title": row["title"],
                    "content": row["content"],
                }
                for row in products[:3]
            ]
            + [
                {
                    "source_type": "sales_material",
                    "source_id": row["source_id"],
                    "title": row["title"],
                    "content": row["content"],
                }
                for row in sales[:3]
            ],
        )

    async def _synthesize(
        self,
        query: str,
        context: dict[str, Any],
        products: dict[str, Any],
        sales: dict[str, Any],
        *,
        request_id: str,
        sink: EventSink | None,
    ) -> AnalysisResult:
        """调用大模型生成最终结构化分析结果。

        参数：
            query：销售原始问题或客户选择后的原始查询。
            context：客户、订单和跟进组成的上下文。
            products：产品资料检索结果。
            sales：销售资料检索结果。
            request_id：当前分析请求 ID。
            sink：流式事件接收函数。
        返回值：通过 Pydantic 校验的分析结果。
        """
        customer = context["customer"]
        orders = context["orders"]
        followups = context["followups"]
        product_rows = products.get("data", [])
        sales_rows = sales.get("data", [])
        if not self.llm:
            return await self._fallback(
                query,
                customer,
                orders,
                followups,
                product_rows,
                sales_rows,
            )

        prompt = SYNTHESIS_PROMPT
        last_error: Exception | None = None
        for attempt in range(JSON_RETRY_LIMIT + 1):
            try:
                if attempt:
                    # 模型第一次没有返回合法 JSON 时，第二次只强调结构化约束。
                    prompt = ChatPromptTemplate.from_messages(
                        [
                            (
                                "system",
                                "上一次输出不是合法 JSON。请严格只返回符合字段要求的 JSON，不要解释。",
                            ),
                            *SYNTHESIS_PROMPT.messages,
                        ]
                    )
                content_parts: list[str] = []
                async for chunk in (prompt | self.llm).astream(
                    {
                        "customer_context": json.dumps(context, ensure_ascii=False, default=str),
                        "product_materials": json.dumps(products, ensure_ascii=False, default=str),
                        "sales_materials": json.dumps(sales, ensure_ascii=False, default=str),
                        "query": query,
                    }
                ):
                    piece = chunk.content if isinstance(chunk.content, str) else str(chunk.content)
                    if piece:
                        content_parts.append(piece)
                        # 前端只展示用户可理解的生成进度，不暴露模型隐藏思考过程。
                        await self._emit(
                            sink,
                            _event(
                                "model_delta",
                                "模型正在生成结构化结果",
                                request_id=request_id,
                                chars_generated=sum(len(item) for item in content_parts),
                            ),
                        )
                content = "".join(content_parts)
                result = AnalysisResult.model_validate(parse_json_object(content))
                return _normalize_email_draft(result, customer, orders, followups)
            except Exception as exc:
                last_error = exc
                logger.warning("structured synthesis attempt %s failed: %s", attempt + 1, exc)
        raise ValueError(f"模型结构化输出失败：{last_error}")

    async def analyze(
        self,
        *,
        session_id: str,
        request_id: str,
        message: str,
        sink: EventSink | None = None,
    ) -> AsyncIterator[AnalysisEvent]:
        """执行一次客户分析流程。

        参数：
            session_id：当前聊天会话 ID。
            request_id：当前分析请求 ID。
            message：销售输入的自然语言问题或候选编号。
            sink：可选的流式事件接收函数。
        返回值：异步产出最终结果事件；过程事件通过 sink 推送。
        """
        self._tool_count = 0
        state = SessionState.model_validate(get_session_state(session_id) or {})
        persist_event(
            {
                "event_type": "message",
                "session_id": session_id,
                "request_id": request_id,
                "role": "user",
                "content": message,
            }
        )

        try:
            await self._emit(
                sink,
                _event("progress", "正在识别客户", request_id=request_id),
            )
            selected = _parse_choice(message, state.pending_candidates)
            query = state.pending_query or _extract_customer_query(message)
            if selected:
                # 如果上一轮有候选客户，本轮编号会直接恢复原始问题并继续分析。
                customer = selected
            else:
                if not query:
                    result = AgentFailure(
                        status="input_required",
                        message="请在问题中提供客户名称，例如“张三科技最近情况怎么样，下一步该怎么跟进？”",
                        request_id=request_id,
                    )
                    persist_event(
                        {
                            "event_type": "message",
                            "session_id": session_id,
                            "request_id": request_id,
                            "role": "assistant",
                            "message_type": "input_required",
                            "content": result.message,
                        }
                    )
                    yield result.model_dump()
                    return
                matches = await self._call_tool(
                    "find_customer",
                    {"query": query},
                    session_id=session_id,
                    request_id=request_id,
                    sink=sink,
                )
                candidates = matches.get("data", [])
                if not candidates:
                    result = AgentFailure(
                        status="input_required",
                        message=f"没有找到与“{query}”匹配的客户，请重新输入客户名称。",
                        request_id=request_id,
                    )
                    persist_event(
                        {
                            "event_type": "message",
                            "session_id": session_id,
                            "request_id": request_id,
                            "role": "assistant",
                            "message_type": "input_required",
                            "content": result.message,
                        }
                    )
                    yield result.model_dump()
                    return
                if len(candidates) > 1:
                    # 多候选时把候选列表和原始查询持久化，等待销售下一轮选择。
                    new_state = SessionState(
                        pending_candidates=candidates,
                        pending_query=query,
                    )
                    persist_event(
                        {
                            "event_type": "state",
                            "session_id": session_id,
                            "state": new_state.model_dump(),
                        }
                    )
                    lines = ["匹配到多个客户，请回复编号："]
                    lines.extend(
                        f"{index}. {row['name']}（{row['company']}，{row['country']}）"
                        for index, row in enumerate(candidates, start=1)
                    )
                    result = AgentFailure(
                        status="input_required",
                        message="\n".join(lines),
                        request_id=request_id,
                        candidates=candidates,
                    )
                    yield result.model_dump()
                    return
                customer = candidates[0]

            clean_state = SessionState()
            # 客户已确定后清空候选状态，避免下一轮误用旧候选。
            persist_event(
                {
                    "event_type": "state",
                    "session_id": session_id,
                    "state": clean_state.model_dump(),
                }
            )
            await self._emit(
                sink,
                _event("progress", f"已确定客户：{customer['name']}", request_id=request_id),
            )
            if selected and not query:
                query = state.pending_query or customer["name"]

            await self._emit(
                sink,
                _event("progress", "正在读取订单和历史跟进", request_id=request_id),
            )
            orders_result, followups_result = await asyncio.gather(
                self._call_tool(
                    "get_customer_orders",
                    {"customer_id": customer["id"]},
                    session_id=session_id,
                    request_id=request_id,
                    sink=sink,
                ),
                self._call_tool(
                    "get_customer_followups",
                    {"customer_id": customer["id"]},
                    session_id=session_id,
                    request_id=request_id,
                    sink=sink,
                ),
            )
            orders = orders_result.get("data", [])
            followups = followups_result.get("data", [])
            # 检索词由客户画像、订单产品和跟进摘要共同组成，保证资料检索围绕当前客户。
            keywords = " ".join(
                [query, customer["name"], customer["industry"], customer["status"]]
                + [row["product_name"] for row in orders]
                + [row["summary"] for row in followups]
            )
            await self._emit(
                sink,
                _event("progress", "正在检索产品和销售资料", request_id=request_id),
            )
            products_result, sales_result = await asyncio.gather(
                self._call_tool(
                    "search_product_materials",
                    {"query": keywords},
                    session_id=session_id,
                    request_id=request_id,
                    sink=sink,
                ),
                self._call_tool(
                    "search_sales_materials",
                    {"query": keywords},
                    session_id=session_id,
                    request_id=request_id,
                    sink=sink,
                ),
            )
            await self._emit(
                sink,
                _event("progress", "正在生成客户总结和跟进建议", request_id=request_id),
            )
            context = {
                "customer": customer,
                "orders": orders,
                "followups": followups,
            }
            result = await self._synthesize(
                query,
                context,
                products_result,
                sales_result,
                request_id=request_id,
                sink=sink,
            )
            payload = result.model_dump(mode="json")
            persist_event(
                {
                    "event_type": "analysis_result",
                    "session_id": session_id,
                    "request_id": request_id,
                    "status": "completed",
                    "result": payload,
                }
            )
            persist_event(
                {
                    "event_type": "message",
                    "session_id": session_id,
                    "request_id": request_id,
                    "role": "assistant",
                    "message_type": "analysis",
                    "content": json.dumps(payload, ensure_ascii=False),
                }
            )
            yield {"status": "completed", "request_id": request_id, "result": payload}
        except Exception as exc:
            logger.exception("Sales agent request failed")
            failure = AgentFailure(
                status="failed",
                message=f"销售助理处理失败：{exc}",
                request_id=request_id,
            )
            persist_event(
                {
                    "event_type": "analysis_result",
                    "session_id": session_id,
                    "request_id": request_id,
                    "status": "failed",
                    "result": failure.model_dump(),
                }
            )
            yield failure.model_dump()


sales_agent = SalesAgent()


async def collect_analysis(
    *,
    session_id: str,
    request_id: str,
    message: str,
    sink: EventSink | None = None,
) -> list[AnalysisEvent]:
    """收集一次 Agent 分析的最终事件列表，主要用于调试或烟雾检查。

    参数：
        session_id：当前聊天会话 ID。
        request_id：当前分析请求 ID。
        message：销售输入内容。
        sink：可选流式事件接收函数。
    返回值：最终事件列表。
    """
    events: list[AnalysisEvent] = []
    async for item in sales_agent.analyze(
        session_id=session_id,
        request_id=request_id,
        message=message,
        sink=sink,
    ):
        events.append(item)
    return events
