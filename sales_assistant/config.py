from __future__ import annotations

import os
from pathlib import Path

try:
    import config as local_config
except ImportError:
    local_config = None


ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_DIR = Path(os.getenv("SALES_KNOWLEDGE_DIR", str(ROOT / "knowledge_base")))
LOG_PATH = Path(os.getenv("SALES_LOG_PATH", str(ROOT / "logs" / "sales_assistant.log")))

AGENT_HOST = os.getenv("SALES_AGENT_HOST", "127.0.0.1")
AGENT_PORT = int(os.getenv("SALES_AGENT_PORT", "5201"))
MCP_HOST = os.getenv("SALES_MCP_HOST", "127.0.0.1")
MCP_PORT = int(os.getenv("SALES_MCP_PORT", "8201"))
MCP_URL = os.getenv("SALES_MCP_URL", f"http://{MCP_HOST}:{MCP_PORT}/mcp")

def _setting(name: str, default: str) -> str:
    """读取配置项，环境变量优先，其次使用本地 config.py。

    参数：
        name：配置项名称。
        default：没有配置时使用的默认值。
    返回值：最终配置值字符串。
    """
    return os.getenv(name, getattr(local_config, name, default))


MYSQL_HOST = _setting("MYSQL_HOST", "127.0.0.1")
MYSQL_PORT = int(_setting("MYSQL_PORT", "3306"))
MYSQL_USER = _setting("MYSQL_USER", "sales_demo")
MYSQL_PASSWORD = _setting("MYSQL_PASSWORD", "sales_demo_password")
MYSQL_DATABASE = _setting("MYSQL_DATABASE", "sales_demo")

LLM_API_KEY = os.getenv("DASHSCOPE_API_KEY", _setting("LLM_API_KEY", ""))
LLM_BASE_URL = _setting(
    "LLM_BASE_URL",
    getattr(local_config, "LLM_BASE_URL", ""),
)
LLM_MODEL = _setting("LLM_MODEL_NAME", getattr(local_config, "LLM_MODEL", ""))
LLM_TEMPERATURE = float(_setting("LLM_TEMPERATURE", "0.2"))
LLM_TIMEOUT_SECONDS = float(_setting("LLM_TIMEOUT_SECONDS", "60"))

MAX_TOOL_CALLS = 10
MAX_AGENT_ROUNDS = 5
JSON_RETRY_LIMIT = 1
