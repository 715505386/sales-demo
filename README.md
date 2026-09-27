# 销售个人助理 Demo

这是一个面向跨境电商销售岗位的第一版个人助理 Demo。当前版本只做 **单 Agent、单 MCP、只读分析**：读取客户、订单和跟进记录，检索产品与销售资料，生成客户近况、下一步跟进建议和邮件草稿。

第一版不会记录跟进、不会发送邮件、不会修改客户资料。

## 架构

```text
Streamlit 聊天页面
        ↓ HTTP NDJSON 流
Agent HTTP 服务
        ↓ MCP Streamable HTTP
销售 MCP 服务
        ↓
MySQL 8.x + 本地 Markdown 知识库
```

核心文件：

- `app.py`：Streamlit 聊天页面。
- `agent_server.py`：Agent HTTP 服务，负责流式返回处理进度。
- `mcp_server.py`：MCP 服务入口。
- `sales_assistant/agent.py`：客户识别、工具调用、资料检索和结构化输出编排。
- `sales_assistant/mcp_server.py`：五个只读 MCP 工具。
- `sales_assistant/db.py`：MySQL 查询和会话审计持久化。
- `knowledge_base/products/`：产品资料。
- `knowledge_base/sales/`：销售资料。
- `sql/init.sql`：MySQL 表结构和模拟数据。
- `start_demo.py`：一键启动脚本。
- `start_demo.bat`：Windows 双击启动脚本。

## 环境要求

- Windows
- Docker Desktop，并确保 Linux Engine 已启动
- Python 环境：推荐 `D:\Anaconda\envs\lang_env\python.exe`
- Python 依赖：

```powershell
D:\Anaconda\envs\lang_env\python.exe -m pip install -r requirements.txt
```

## 配置模型

复制 `config.example.py` 为本地 `config.py`，填写模型配置：

```python
LLM_API_KEY = "你的 API Key"
LLM_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
LLM_MODEL = "qwen3.7-max"
```

也可以使用环境变量：

```powershell
$env:LLM_API_KEY = "你的 API Key"
$env:LLM_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
$env:LLM_MODEL_NAME = "qwen3.7-max"
```

真实密钥不要提交到 Git。没有配置 API Key 时，Agent 会使用本地确定性降级结果，仍可验证 MySQL、MCP 和页面链路。

## 一键启动

方式一：命令行启动并自动打开页面。

```powershell
D:\Anaconda\envs\lang_env\python.exe start_demo.py
```

方式二：双击运行：

```text
start_demo.bat
```

启动成功后会自动打开：

```text
http://localhost:8501
```

## 分服务启动

如果需要逐个排查服务，可以按下面顺序启动：

```powershell
docker compose up -d mysql
D:\Anaconda\envs\lang_env\python.exe mcp_server.py
D:\Anaconda\envs\lang_env\python.exe agent_server.py
D:\Anaconda\envs\lang_env\python.exe -m streamlit run app.py
```

服务地址：

- Streamlit 页面：`http://localhost:8501`
- Agent 健康检查：`http://127.0.0.1:5201/health`
- MCP 地址：`http://127.0.0.1:8201/mcp`

## MCP 工具

当前只有五个只读工具：

- 模糊查询客户（`find_customer(query)`）
- 查询客户订单（`get_customer_orders(customer_id)`）
- 查询客户跟进（`get_customer_followups(customer_id)`）
- 检索产品资料（`search_product_materials(query)`）
- 检索销售资料（`search_sales_materials(query)`）

Agent 不直接访问业务数据，所有客户、订单、跟进和资料读取都通过 MCP。

## 用于测试全部功能的用例

在 Streamlit 聊天框中依次测试：

1. 明确客户名称的完整分析

```text
张三科技最近情况怎么样，下一步该怎么跟进？
```

预期：页面展示客户概况、订单、历史跟进、产品资料、销售资料、客户状态、跟进建议、邮件草稿和证据来源。

2. 英文客户名称和英文邮件草稿

```text
Acme Trading 最近情况怎么样，下一步该怎么跟进？
```

预期：能匹配海外客户，邮件草稿语言应偏英文。

3. 模糊匹配多个客户

```text
Acme 最近情况怎么样？
```

预期：页面列出多个候选客户。继续输入：

```text
1
```

预期：系统沿用上一轮问题，继续完成客户分析。

4. 缺少客户名称

```text
这个客户最近情况怎么样？
```

预期：系统要求补充客户名称，不自行猜测客户。

5. 客户不存在

```text
不存在客户最近情况怎么样？
```

预期：系统提示未找到匹配客户，并要求重新输入。

6. 数据缺失分支

```text
Pacific Home 最近情况怎么样，下一步该怎么跟进？
```

预期：即使订单或跟进记录不足，也能输出结果，并在风险和缺失数据中说明。

7. 工具调用详情

任意完成一次分析后，展开“MCP 工具调用详情”区域。

预期：能看到工具名称、参数、返回摘要、状态和耗时。

8. 数据持久化检查

进入 MySQL 容器或使用客户端查询：

```sql
SELECT COUNT(*) FROM chat_sessions;
SELECT COUNT(*) FROM chat_messages;
SELECT COUNT(*) FROM tool_call_logs;
SELECT COUNT(*) FROM analysis_results;
```

预期：完成分析后，这些表中有对应记录。

## 常见问题

### Docker 无法连接

如果看到类似下面的错误：

```text
failed to connect to the docker API ... dockerDesktopLinuxEngine
```

说明 Docker Desktop 没有启动，或 Linux Engine 未运行。打开 Docker Desktop，等待状态变为 Running 后再执行启动命令。

### 端口被占用

默认端口：

- MySQL：`3306`
- Agent：`5201`
- MCP：`8201`
- Streamlit：`8501`

如果端口被占用，可以通过环境变量调整 Agent 和 MCP 端口。
