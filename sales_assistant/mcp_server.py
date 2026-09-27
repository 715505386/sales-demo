from __future__ import annotations

import json

from mcp.server.fastmcp import FastMCP

from .config import MCP_HOST, MCP_PORT
from .db import (
    ensure_database,
    find_customers,
    get_customer_followups,
    get_customer_orders,
)
from .knowledge import search_knowledge


sales_mcp = FastMCP(
    name="SalesAssistantTools",
    instructions="Read-only customer, order, follow-up, product and sales material tools.",
    log_level="ERROR",
    host=MCP_HOST,
    port=MCP_PORT,
)


@sales_mcp.tool(name="find_customer", description="Find customers by fuzzy name or company match.")
def find_customer(query: str) -> str:
    """MCP 工具：模糊查询客户。

    参数：
        query：客户名称或公司名称查询词。
    返回值：JSON 字符串，包含客户候选列表。
    """
    return json.dumps(
        {"status": "success", "data": find_customers(query)},
        ensure_ascii=False,
        default=str,
    )


@sales_mcp.tool(name="get_customer_orders", description="Read all orders for one customer.")
def get_customer_orders_tool(customer_id: int) -> str:
    """MCP 工具：查询客户订单。

    参数：
        customer_id：客户 ID。
    返回值：JSON 字符串，包含订单列表。
    """
    return json.dumps(get_customer_orders(customer_id), ensure_ascii=False, default=str)


@sales_mcp.tool(name="get_customer_followups", description="Read all follow-up records for one customer.")
def get_customer_followups_tool(customer_id: int) -> str:
    """MCP 工具：查询客户历史跟进。

    参数：
        customer_id：客户 ID。
    返回值：JSON 字符串，包含跟进记录列表。
    """
    return json.dumps(get_customer_followups(customer_id), ensure_ascii=False, default=str)


@sales_mcp.tool(name="search_product_materials", description="Search product Markdown materials.")
def search_product_materials(query: str) -> str:
    """MCP 工具：检索产品资料。

    参数：
        query：Agent 生成的产品相关检索文本。
    返回值：JSON 字符串，包含命中的产品资料片段。
    """
    return json.dumps(
        search_knowledge("products", query),
        ensure_ascii=False,
        default=str,
    )


@sales_mcp.tool(name="search_sales_materials", description="Search sales Markdown materials.")
def search_sales_materials(query: str) -> str:
    """MCP 工具：检索销售资料。

    参数：
        query：Agent 生成的销售策略检索文本。
    返回值：JSON 字符串，包含命中的销售资料片段。
    """
    return json.dumps(
        search_knowledge("sales", query),
        ensure_ascii=False,
        default=str,
    )


def main() -> None:
    """启动 MCP Streamable HTTP 服务。

    参数：无。
    返回值：无。函数会启动 MCP 服务并阻塞。
    """
    ensure_database()
    print(f"Sales MCP running at http://{MCP_HOST}:{MCP_PORT}/mcp")
    sales_mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
