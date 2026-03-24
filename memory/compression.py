from __future__ import annotations

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate

from qa_chain import get_chat_model
from utils import Settings


COMPRESSION_PROMPT = PromptTemplate.from_template(
    """
你是一个上下文压缩器。请将下面的运行历史压缩为结构化中文摘要，必须保留：
1. 已完成事项
2. 未完成事项
3. 关键证据
4. 已尝试但失败的方法
5. 仍待满足的 criteria

运行历史：
{content}
"""
)


def compress_history(content: str, settings: Settings) -> str:
    if not content.strip():
        return ""
    model = get_chat_model(settings)
    chain = COMPRESSION_PROMPT | model | StrOutputParser()
    return chain.invoke({"content": content})
