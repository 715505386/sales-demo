# 销售个人助理 Demo 第一版规格

Status: ready-for-agent
Version: v1

## Goal

为跨境电商销售人员提供一个只读的客户分析助手。销售输入客户名称和自然语言问题：

> 这个客户最近情况怎么样，下一步该怎么跟进？

系统读取客户、订单和历史跟进数据，检索产品与销售资料，生成客户近况、跟进建议和邮件草稿。

## Scope

- 单 Agent、单 MCP
- Streamlit 聊天入口
- Agent 使用 LangChain `ChatOpenAI`
- Agent 与 MCP 通过 MCP Streamable HTTP 通信
- MySQL 8.x 保存业务数据、会话、消息、工具调用日志和分析结果
- Docker Compose 启动 MySQL 并初始化 10 至 20 条模拟客户数据
- 客户名称大小写/文本模糊匹配；多结果时在聊天中列出候选，销售回复编号
- 客户、订单、历史跟进查询
- 本地 Markdown 产品资料和销售资料检索
- 客户近况总结、下一步跟进建议和邮件草稿
- 结构化 JSON 输出并由页面渲染
- 工具调用、服务进度和用户可见的生成过程流式展示
- 所有会话、消息、工具调用和分析结果写入 MySQL
- 模型 JSON 解析失败时自动重试一次
- 第一版不执行任何写操作

## Agent workflow

1. 从问题中识别客户名称；缺失时追问。
2. 调用 `find_customer(query)`。
3. 无匹配时要求重新输入；多匹配时列候选并保存待选状态。
4. 唯一客户或销售选择后，调用客户、订单和跟进读取工具。
5. 根据客户上下文生成产品和销售资料检索关键词。
6. 调用资料检索工具。
7. 生成固定 JSON，并校验输出 Schema。
8. 记录完整过程和最终结果。

## MCP tools

- `find_customer(query)`
- `get_customer_orders(customer_id)`
- `get_customer_followups(customer_id)`
- `search_sales_materials(query)`
- `search_product_materials(query)`

MCP 工具只读。Agent 不直接连接 MySQL。

## Final output

```json
{
  "customer_profile": {},
  "recent_orders": [],
  "followup_summary": [],
  "product_materials": [],
  "sales_materials": [],
  "customer_status": "",
  "followup_suggestions": [],
  "email_draft": {
    "recipient": "",
    "subject": "",
    "body": "",
    "language": "",
    "tone": ""
  },
  "risks_and_missing_data": [],
  "evidence": []
}
```

`evidence` 使用 `source_type`、`source_id`、`title`、`content` 字段。

## Data and persistence

MySQL tables:

- `customers`
- `orders`
- `followups`
- `chat_sessions`
- `chat_messages`
- `tool_call_logs`
- `analysis_results`

知识库按 Markdown 标题分片。关键词匹配大小写不敏感，命中任意关键词，按命中数量排序。

## Runtime

```text
Streamlit -> Agent HTTP service -> MCP Streamable HTTP -> MySQL
```

模型配置从本地 `sales_assistant/config.py` 读取；仓库只保留配置模板，真实 API Key 不提交。

启动方式：

```text
docker compose up -d mysql
python mcp_server.py
python agent_server.py
streamlit run app.py
```

## Error handling

- MCP、MySQL、模型超时或调用失败：返回可读错误，并记录会话和工具调用日志。
- 输出 JSON 非法：自动重试一次；仍失败则返回结构化失败状态。
- 数据缺失：继续生成结果，并写入 `risks_and_missing_data`。
- 不展示模型隐藏思考链，只展示工具状态、服务进度和最终可见内容。

## Out of scope

- 多 Agent、多 MCP
- 记录跟进、发送邮件、修改客户数据
- 真实 CRM、邮箱或企业 IM 对接
- 登录、权限、多租户
- 向量数据库和 Embedding 检索
- 长期记忆、定时任务、移动端
- 自动化测试；第一版只做人工验收

## Manual acceptance

1. 明确客户名称完成完整分析。
2. 多客户匹配后通过编号选择并继续分析。
3. 缺少客户名称时主动追问。
4. 客户不存在时给出明确提示。
5. 无订单或无跟进时正常输出并提示缺失数据。
6. MCP 或 MySQL 失败时展示可读错误。
7. 非法 JSON 自动重试一次。
8. 页面可查看聊天、工具调用和最终分析结果。
