from __future__ import annotations

# 第一阶段长期记忆向量检索直接使用 SQLite 中保存的 embedding_json + Python 余弦相似度。
# 这里保留文件作为后续切换到独立 FAISS/pgvector 的扩展点。

