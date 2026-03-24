# Memory Design

## 短期记忆

- Pinned Context
- Sliding Window
- LLM Compression
- Context Budget Manager
- Rehydration

## 长期记忆

- 类型：fact / preference / artifact_summary / research_note / task_pattern
- 入库：checker 通过后的高价值结果
- 检索：Master 规划前、Worker 执行前、Checker 审核前

## 去重

- 原文归一化
- 指纹哈希
- 强去重
- 简单近似重复判断
