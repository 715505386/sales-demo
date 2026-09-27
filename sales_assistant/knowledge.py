from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .config import KNOWLEDGE_DIR


def _terms(text: str) -> set[str]:
    """把文本拆成用于关键词匹配的中英文词集合。

    参数：
        text：待分析文本。
    返回值：小写英文词和中文双字片段组成的集合。
    """
    normalized = (text or "").lower()
    terms = set(re.findall(r"[a-z0-9][a-z0-9_-]*", normalized))
    for block in re.findall(r"[\u4e00-\u9fff]+", normalized):
        terms.update(block[index : index + 2] for index in range(len(block) - 1))
        if len(block) >= 2:
            terms.add(block)
    return terms


def _chunks(path: Path, category: str) -> list[dict[str, Any]]:
    """按 Markdown 标题把资料文件切成可检索片段。

    参数：
        path：Markdown 文件路径。
        category：资料类别，例如 products 或 sales。
    返回值：包含来源、标题和正文的片段列表。
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    chunks: list[dict[str, Any]] = []
    title = path.stem
    body: list[str] = []

    def flush() -> None:
        """把当前标题下的正文写入片段列表。

        参数：无。
        返回值：无。
        """
        if not body:
            return
        content = "\n".join(body).strip()
        chunks.append(
            {
                "source_type": category,
                "source_id": f"{path.name}#{title}",
                "title": title,
                "content": content,
            }
        )

    for line in lines:
        if line.startswith("#"):
            flush()
            title = line.lstrip("#").strip() or path.stem
            body = [line]
        else:
            body.append(line)
    flush()
    return chunks


def search_knowledge(category: str, query: str, limit: int = 5) -> dict[str, Any]:
    """检索指定类别的本地 Markdown 资料。

    参数：
        category：资料目录名称，例如 products 或 sales。
        query：检索关键词文本。
        limit：最多返回的片段数量。
    返回值：包含状态、命中片段和提示信息的字典。
    """
    directory = KNOWLEDGE_DIR / category
    query_terms = _terms(query)
    results: list[dict[str, Any]] = []

    for path in sorted(directory.glob("*.md")):
        for chunk in _chunks(path, category):
            # 多关键词采用“命中任意关键词”策略，并用命中数量作为相关性分数。
            matched = query_terms & _terms(chunk["content"])
            if matched:
                results.append(
                    {
                        **chunk,
                        "score": len(matched),
                        "matched_terms": sorted(matched),
                    }
                )

    results.sort(key=lambda item: (-item["score"], item["source_id"]))
    if not results:
        return {"status": "no_data", "data": [], "message": "没有找到相关资料。"}
    return {"status": "success", "data": results[:limit], "message": None}
