from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any, Iterator

import pymysql
from pymysql.cursors import DictCursor

from .config import (
    MYSQL_DATABASE,
    MYSQL_HOST,
    MYSQL_PASSWORD,
    MYSQL_PORT,
    MYSQL_USER,
)


@contextmanager
def connection() -> Iterator[pymysql.connections.Connection]:
    """创建并自动关闭 MySQL 连接。

    参数：无。
    返回值：可在 with 语句中使用的 PyMySQL 连接对象。
    """
    conn = pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE,
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=True,
        connect_timeout=5,
        read_timeout=30,
        write_timeout=30,
    )
    try:
        yield conn
    finally:
        conn.close()


def ensure_database() -> None:
    """检查 MySQL 是否可连接。

    参数：无。
    返回值：无。连接失败时会抛出数据库异常。
    """
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")


def find_customers(query: str) -> list[dict[str, Any]]:
    """按客户名称或公司名称模糊查询客户。

    参数：
        query：销售输入或 Agent 提取出的客户查询词。
    返回值：客户候选列表，每个元素是客户基础信息字典。
    """
    query = query.strip()
    if not query:
        return []
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, name, email, country, company, industry,
                       contact_name, status
                FROM customers
                WHERE LOWER(name) LIKE CONCAT('%%', LOWER(%s), '%%')
                   OR INSTR(LOWER(%s), LOWER(name)) > 0
                   OR LOWER(company) LIKE CONCAT('%%', LOWER(%s), '%%')
                ORDER BY
                    CASE
                        WHEN LOWER(name) = LOWER(%s) THEN 0
                        WHEN INSTR(LOWER(%s), LOWER(name)) > 0 THEN 1
                        ELSE 2
                    END,
                    name
                LIMIT 10
                """,
                (query, query, query, query, query),
            )
            return list(cursor.fetchall())


def get_customer_orders(customer_id: int) -> dict[str, Any]:
    """读取指定客户的全部订单。

    参数：
        customer_id：客户 ID。
    返回值：包含状态、客户 ID、订单列表和可选提示信息的字典。
    """
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, order_no, customer_id, order_date, product_name,
                       quantity, amount, currency, status
                FROM orders
                WHERE customer_id = %s
                ORDER BY order_date DESC, id DESC
                """,
                (customer_id,),
            )
            rows = list(cursor.fetchall())
    return {
        "status": "success",
        "customer_id": customer_id,
        "data": rows,
        "message": "没有订单记录。" if not rows else None,
    }


def get_customer_followups(customer_id: int) -> dict[str, Any]:
    """读取指定客户的历史跟进记录。

    参数：
        customer_id：客户 ID。
    返回值：包含状态、客户 ID、跟进列表和可选提示信息的字典。
    """
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, customer_id, followup_date, channel, summary,
                       next_action, owner
                FROM followups
                WHERE customer_id = %s
                ORDER BY followup_date DESC, id DESC
                """,
                (customer_id,),
            )
            rows = list(cursor.fetchall())
    return {
        "status": "success",
        "customer_id": customer_id,
        "data": rows,
        "message": "没有跟进记录。" if not rows else None,
    }


def persist_event(event: dict[str, Any]) -> None:
    """把会话状态、聊天消息、工具调用或分析结果写入 MySQL。

    参数：
        event：事件字典，必须包含事件类型和会话 ID。
    返回值：无。未知事件类型会抛出 ValueError。
    """
    event_type = event["event_type"]
    session_id = event["session_id"]
    request_id = event.get("request_id")

    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO chat_sessions(session_id, state_json)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE updated_at = CURRENT_TIMESTAMP
                """,
                (session_id, json.dumps({}, ensure_ascii=False)),
            )

            if event_type == "state":
                # 候选客户选择等多轮状态只更新会话表，避免污染聊天消息。
                cursor.execute(
                    """
                    UPDATE chat_sessions
                    SET state_json = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE session_id = %s
                    """,
                    (json.dumps(event.get("state", {}), ensure_ascii=False), session_id),
                )
            elif event_type == "message":
                cursor.execute(
                    """
                    INSERT INTO chat_messages
                        (session_id, request_id, role, message_type, content)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        session_id,
                        request_id,
                        event["role"],
                        event.get("message_type", "chat"),
                        event["content"],
                    ),
                )
            elif event_type == "tool_call":
                # 工具调用日志保留参数、结果、状态和耗时，用于页面展示和问题排查。
                cursor.execute(
                    """
                    INSERT INTO tool_call_logs
                        (session_id, request_id, tool_name, arguments_json,
                         result_json, status, duration_ms)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        session_id,
                        request_id,
                        event["tool_name"],
                        json.dumps(event.get("arguments", {}), ensure_ascii=False),
                        json.dumps(event.get("result"), ensure_ascii=False),
                        event.get("status", "success"),
                        event.get("duration_ms"),
                    ),
                )
            elif event_type == "analysis_result":
                cursor.execute(
                    """
                    INSERT INTO analysis_results
                        (session_id, request_id, status, result_json)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        session_id,
                        request_id,
                        event.get("status", "completed"),
                        json.dumps(event.get("result"), ensure_ascii=False),
                    ),
                )
            else:
                raise ValueError(f"Unsupported event type: {event_type}")


def get_session_state(session_id: str) -> dict[str, Any]:
    """读取当前聊天会话的多轮状态。

    参数：
        session_id：Streamlit 会话 ID。
    返回值：保存的状态字典；没有状态时返回空字典。
    """
    with connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT state_json FROM chat_sessions WHERE session_id = %s",
                (session_id,),
            )
            row = cursor.fetchone()
    if not row or not row["state_json"]:
        return {}
    value = row["state_json"]
    return value if isinstance(value, dict) else json.loads(value)
