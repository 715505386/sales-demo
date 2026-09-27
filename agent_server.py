from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from sales_assistant.agent import sales_agent
from sales_assistant.config import AGENT_HOST, AGENT_PORT
from sales_assistant.db import ensure_database
from sales_assistant.models import ChatRequest


app = FastAPI(title="Sales Assistant Agent")


@app.get("/health")
async def health() -> dict[str, str]:
    """返回 Agent 服务健康状态。

    参数：无。
    返回值：包含服务状态的字典。
    """
    return {"status": "ok"}


async def event_stream(request: ChatRequest) -> AsyncIterator[str]:
    """把 Agent 分析过程转换为逐行 JSON 流。

    参数：
        request：聊天请求，包含会话 ID、用户消息和可选请求 ID。
    返回值：异步迭代器，每次产出一行 JSON 字符串。
    """
    request_id = request.request_id or str(uuid.uuid4())
    queue: asyncio.Queue[dict | None] = asyncio.Queue()

    async def emit(event: dict) -> None:
        """把 Agent 内部事件放入流式响应队列。

        参数：
            event：需要发给前端的进度、工具调用或模型生成事件。
        返回值：无。
        """
        event["request_id"] = request_id
        await queue.put(event)

    async def produce() -> None:
        """后台执行 Agent 分析并把最终结果写入队列。

        参数：无。
        返回值：无。完成后写入空事件作为流结束标记。
        """
        try:
            async for item in sales_agent.analyze(
                session_id=request.session_id,
                request_id=request_id,
                message=request.message,
                sink=emit,
            ):
                await queue.put({"type": "result", "payload": item})
        except Exception as exc:
            await queue.put(
                {
                    "type": "result",
                    "payload": {
                        "status": "failed",
                        "request_id": request_id,
                        "message": f"Agent 服务失败：{exc}",
                    },
                }
            )
        finally:
            await queue.put(None)

    producer = asyncio.create_task(produce())
    try:
        while True:
            event = await queue.get()
            if event is None:
                break
            yield json.dumps(event, ensure_ascii=False, default=str) + "\n"
    finally:
        if not producer.done():
            producer.cancel()


@app.post("/chat")
async def chat(request: ChatRequest) -> StreamingResponse:
    """处理前端聊天请求并返回流式响应。

    参数：
        request：聊天请求体。
    返回值：NDJSON 格式的 StreamingResponse。
    """
    return StreamingResponse(event_stream(request), media_type="application/x-ndjson")


def main() -> None:
    """启动 Agent HTTP 服务。

    参数：无。
    返回值：无。函数会启动 Uvicorn 服务并阻塞。
    """
    import uvicorn

    ensure_database()
    uvicorn.run(app, host=AGENT_HOST, port=AGENT_PORT)


if __name__ == "__main__":
    main()
