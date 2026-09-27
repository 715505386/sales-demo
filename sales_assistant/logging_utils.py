from __future__ import annotations

import logging
from pathlib import Path

from .config import LOG_PATH


def get_logger() -> logging.Logger:
    """创建项目共享日志器。

    参数：无。
    返回值：配置了文件和控制台输出的 logging.Logger。
    """
    logger = logging.getLogger("sales_assistant")
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return logger
    Path(LOG_PATH).parent.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(LOG_PATH, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.addHandler(logging.StreamHandler())
    return logger


logger = get_logger()
