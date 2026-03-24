from __future__ import annotations

from pathlib import Path

from langchain_classic.chains import create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, PromptTemplate
from langchain_openai import ChatOpenAI

from ingest import load_vectorstore
from prompts import QA_SYSTEM_PROMPT, SUMMARY_PROMPT
from utils import OUTPUTS_DIR, Settings


def _chat_kwargs(settings: Settings) -> dict:
    kwargs = {
        "model": settings.chat_model,
        "temperature": 0,
        "api_key": settings.openai_api_key,
    }
    if settings.openai_base_url:
        kwargs["base_url"] = settings.openai_base_url
    return kwargs


def get_chat_model(settings: Settings) -> ChatOpenAI:
    return ChatOpenAI(**_chat_kwargs(settings))


def retrieve_documents(query: str, settings: Settings, k: int = 4) -> list[Document]:
    vectorstore = load_vectorstore(settings)
    return vectorstore.similarity_search(query, k=k)


def format_source_label(doc: Document, index: int) -> str:
    source = doc.metadata.get("source", "unknown")
    page = doc.metadata.get("page")
    source_name = Path(str(source)).name
    suffix = f" | 第 {page + 1} 页" if isinstance(page, int) else ""
    return f"片段 {index} | {source_name}{suffix}"


def build_source_labels(docs: list[Document]) -> list[str]:
    return [format_source_label(doc, idx) for idx, doc in enumerate(docs, start=1)]


def build_context_preview(docs: list[Document], max_chars: int = 220) -> list[dict]:
    previews: list[dict] = []
    for idx, doc in enumerate(docs, start=1):
        content = doc.page_content.strip().replace("\n", " ")
        snippet = content[:max_chars].strip()
        if len(content) > max_chars:
            snippet = f"{snippet}..."

        previews.append(
            {
                "index": idx,
                "label": format_source_label(doc, idx),
                "snippet": snippet,
                "metadata": doc.metadata,
            }
        )
    return previews


def answer_question(question: str, settings: Settings) -> dict:
    vectorstore = load_vectorstore(settings)
    retriever = vectorstore.as_retriever(search_kwargs={"k": 4})
    llm = get_chat_model(settings)

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", QA_SYSTEM_PROMPT),
            ("human", "{input}"),
        ]
    )
    document_chain = create_stuff_documents_chain(llm, prompt)
    retrieval_chain = create_retrieval_chain(retriever, document_chain)
    result = retrieval_chain.invoke({"input": question})
    return result


def summarize_knowledge_base(settings: Settings) -> str:
    vectorstore = load_vectorstore(settings)
    docs = vectorstore.similarity_search("请总结这批资料的核心主题、关键内容和复习重点", k=8)
    context = "\n\n".join(doc.page_content for doc in docs)

    llm = get_chat_model(settings)
    prompt = PromptTemplate.from_template(SUMMARY_PROMPT)
    chain = prompt | llm | StrOutputParser()
    return chain.invoke({"context": context})


def save_markdown(filename: str, content: str) -> Path:
    output_path = OUTPUTS_DIR / filename
    output_path.write_text(content, encoding="utf-8")
    return output_path
