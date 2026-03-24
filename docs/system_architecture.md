# 系统架构

## 分层

- Runtime Layer: Master / Worker / Checker
- Tool Layer: RAG / Search / MCP / Export / Memory
- Memory Layer: Short-term / Long-term / Compression / Dedup
- Data Layer: SQLite + embedding 存储
- Presentation Layer: FastAPI + React

## 执行流

1. 用户提交任务
2. 系统召回长期记忆
3. Master 规划子任务
4. Worker 调工具执行
5. 短期记忆记录并按需压缩
6. Checker 审核
7. 高价值结果写入长期记忆
