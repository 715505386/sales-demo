from __future__ import annotations

import json
import os
import uuid

import httpx
import streamlit as st


AGENT_URL = os.getenv("SALES_AGENT_URL", "http://127.0.0.1:5201")

st.set_page_config(page_title="销售个人助理", page_icon="S", layout="wide")
st.title("销售个人助理")
st.caption("只读客户分析：客户近况、跟进建议、产品资料和邮件草稿")

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []


def render_result(result: dict) -> None:
    """渲染 Agent 返回的结构化客户分析结果。

    参数：
        result：符合分析结果 Schema 的字典。
    返回值：无。函数直接向 Streamlit 页面写入组件。
    """
    st.subheader("客户概况")
    st.json(result.get("customer_profile", {}), expanded=False)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("订单概况")
        st.dataframe(result.get("recent_orders", []), use_container_width=True, hide_index=True)
    with col2:
        st.subheader("历史跟进")
        st.dataframe(result.get("followup_summary", []), use_container_width=True, hide_index=True)

    st.subheader("客户当前状态")
    st.write(result.get("customer_status", ""))

    st.subheader("下一步跟进建议")
    for suggestion in result.get("followup_suggestions", []):
        st.markdown(f"- {suggestion}")

    st.subheader("邮件草稿")
    draft = result.get("email_draft", {})
    st.markdown(f"**收件人：** {draft.get('recipient', '')}")
    st.markdown(f"**主题：** {draft.get('subject', '')}")
    st.markdown(f"**语言 / 语气：** {draft.get('language', '')} / {draft.get('tone', '')}")
    st.text_area("正文", draft.get("body", ""), height=180, disabled=True)

    risks = result.get("risks_and_missing_data", [])
    if risks:
        st.warning("\n".join(f"- {item}" for item in risks))

    with st.expander("产品资料依据", expanded=False):
        st.json(result.get("product_materials", []), expanded=False)
    with st.expander("销售资料依据", expanded=False):
        st.json(result.get("sales_materials", []), expanded=False)
    with st.expander("证据来源", expanded=False):
        st.json(result.get("evidence", []), expanded=False)


def render_message(message: dict) -> None:
    """渲染历史聊天消息和对应的工具调用详情。

    参数：
        message：保存在 Streamlit 会话中的单条消息。
    返回值：无。函数直接写入页面。
    """
    with st.chat_message(message["role"]):
        if message["role"] == "user":
            st.markdown(message["content"])
            return
        if message.get("status") == "completed":
            render_result(message["result"])
        else:
            st.markdown(message.get("message", "未完成本次分析。"))
            candidates = message.get("candidates", [])
            if candidates:
                st.dataframe(candidates, use_container_width=True, hide_index=True)

        tool_logs = message.get("tool_logs", [])
        if tool_logs:
            with st.expander("MCP 工具调用详情", expanded=False):
                for item in tool_logs:
                    st.json(item, expanded=False)


for history_item in st.session_state.messages:
    render_message(history_item)


def run_request(prompt: str) -> dict:
    """向 Agent 服务发送用户问题并消费流式事件。

    参数：
        prompt：销售输入的自然语言问题或候选客户编号。
    返回值：Agent 最终结果字典，附带本次 MCP 工具调用日志。
    """
    tool_logs: list[dict] = []
    final_payload: dict | None = None
    with httpx.Client(timeout=180) as client:
        with client.stream(
            "POST",
            f"{AGENT_URL}/chat",
            json={
                "session_id": st.session_state.session_id,
                "message": prompt,
                "request_id": str(uuid.uuid4()),
            },
        ) as response:
            response.raise_for_status()
            with st.status("正在处理...", expanded=True) as status:
                # Agent 返回 NDJSON 流；页面按事件类型展示进度、工具状态和最终结果。
                for line in response.iter_lines():
                    if not line:
                        continue
                    event = json.loads(line)
                    if event.get("type") == "progress":
                        status.write(event.get("message", "处理中"))
                    elif event.get("type") == "tool_start":
                        status.write(f"调用 `{event.get('tool_name')}`")
                    elif event.get("type") == "tool_end":
                        tool_logs.append(event)
                        status.write(
                            f"`{event.get('tool_name')}`：{event.get('status')} "
                            f"({event.get('duration_ms', 0)} ms)"
                        )
                    elif event.get("type") == "result":
                        final_payload = event["payload"]
                status.update(label="处理完成", state="complete", expanded=False)
    if final_payload is None:
        raise RuntimeError("Agent 没有返回最终结果。")
    final_payload["tool_logs"] = tool_logs
    return final_payload


prompt = st.chat_input("例如：张三科技最近情况怎么样，下一步该怎么跟进？")
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        try:
            result = run_request(prompt)
            if result.get("status") == "completed":
                render_result(result["result"])
            else:
                st.markdown(result.get("message", "未完成本次分析。"))
                if result.get("candidates"):
                    st.dataframe(result["candidates"], use_container_width=True, hide_index=True)
            if result.get("tool_logs"):
                with st.expander("MCP 工具调用详情", expanded=False):
                    for item in result["tool_logs"]:
                        st.json(item, expanded=False)
            st.session_state.messages.append({"role": "assistant", **result})
        except Exception as exc:
            st.error(f"无法连接 Agent 服务：{exc}")
