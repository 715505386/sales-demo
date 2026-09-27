# ADR 0001: 第一版采用单 Agent 和单 MCP

## Decision

第一版使用一个销售 Agent 和一个销售 MCP 服务。Agent 通过 MCP Streamable HTTP 调用五个只读工具，MCP 访问 MySQL 和本地 Markdown 资料。

## Rationale

当前业务场景集中在“查询客户近况并生成跟进建议”。单 Agent 能保持流程可观察，单 MCP 能明确数据访问边界，同时为后续拆分保留协议边界。

## Consequences

- Streamlit 只连接 Agent HTTP 服务。
- Agent 不直接访问客户、订单、跟进和知识库数据。
- 第一版不包含写工具，不执行跟进记录或邮件发送。
- 后续增加权限、多 Agent 或多 MCP 前，需要先验证第一版人工验收场景。
