# Multi-Agent 私人任务助理

一个面向个人资料与学习资料场景的 `Multi-Agent` 任务助理项目。项目重点不在于做一个聊天页面，而是围绕复杂任务构建完整 Agent 闭环：`任务规划 -> 工具执行 -> 结果审核 -> 记忆沉淀 -> 运行观测`。

## 项目亮点

- 设计 `Master + Worker + Checker` 多智能体运行时，支持复杂任务拆解、子任务执行、结果审核与多轮补救。
- 将 `RAG`、联网搜索、长期记忆检索、导出能力与 `MCP` 工具统一封装为 Agent 可调用工具。
- 实现短期记忆与长期记忆双层机制，支持上下文压缩、历史经验复用与高价值结果沉淀。
- 记录任务轮次、工具调用轨迹、缺口分级与记忆命中结果，提升 Agent 系统的可观测性与可调试性。

## 这个项目解决什么问题

很多资料型 Agent demo 能完成单轮问答，但在更真实的任务场景里往往会遇到这些问题：

- 复杂任务缺乏清晰的拆解与执行路径
- 工具调用过程不可见，难以判断是否正确使用了外部能力
- 输出看似完整，但缺少证据支持或遗漏关键要求
- 历史任务结论难以沉淀，后续任务无法复用

这个项目尝试把这些问题落到一个完整的工程实现中：

- `Master` 负责任务规划、派发 Worker、维护 stop criteria
- `Worker` 作为通用执行单元，自主调用工具完成子任务
- `Checker` 负责评估完成度、证据充分性与缺口类型
- `Memory Layer` 管理短期上下文与长期知识沉淀

## 核心能力

### 1. Multi-Agent Runtime

- `Master` 根据用户任务、长期记忆命中和 revision feedback 生成子任务
- `Worker` 基于统一工具层执行任务，并在结果不足时进行重试
- `Checker` 输出 `passed`、`score`、`blocking_requirements`、`advisory_gaps`、`completion_status`
- 当存在阻塞缺口时，系统会根据 Checker 反馈进入下一轮补救

### 2. RAG + Tool Calling

- 支持 `.md`、`.txt`、`.pdf` 文档导入、切分、向量化与 `FAISS` 检索
- 提供本地问答、来源引用与片段预览
- 支持“本地资料优先、资料不足再联网补充”的知识获取流程
- 通过统一 `Tool Registry` 暴露本地 RAG、`web_search`、记忆检索、导出与 MCP 工具

### 3. Memory

- `Short-term Memory`：维护固定上下文、最近事件与压缩历史
- `Long-term Memory`：对高价值任务结果、研究结论、任务模式进行沉淀
- 支持长期记忆检索复用与 fingerprint 去重
- 使用 `SQLite` 记录任务、消息、worker 运行、记忆与运行产物

### 4. 可观测性

- 记录回合摘要、工具调用轨迹、Checker 结论与缺口类型
- 支持查看长期记忆命中与写入结果
- 输出运行记录，便于调试 Agent 执行路径与结果质量

## 系统结构

```text
multi_agent_task_assistant/
├── backend/            # API 入口
├── frontend/           # 控制台界面
├── runtime/            # Master / Worker / Checker / Planner
├── tools/              # Tool Registry 与工具封装
├── memory/             # 短期记忆、长期记忆、压缩、去重、检索
├── storage/            # SQLite 初始化与 repository
├── docs/               # 架构与设计文档
├── tests/              # 单元测试
├── data/               # 本地资料
├── outputs/            # 导出与运行记录
├── state/              # runtime.db 与记忆相关状态
├── vectorstore/        # 文档向量库
├── qa_chain.py         # 本地 RAG 问答链
├── mcp_server.py       # MCP 服务
└── web_tools.py        # 联网搜索工具
```

## 演示方式

推荐用下面这组步骤快速理解项目能力：

1. 上传 1 到 3 份讲义或技术文档到 `data/`
2. 构建或更新向量索引
3. 先在学习问答里验证本地 RAG 是否可用
4. 再输入一个带完成标准的复杂任务，观察：
   - Master 如何拆解任务
   - Worker 调用了哪些工具
   - Checker 是否给出 blocking gaps / advisory gaps
   - 系统是否命中或写入长期记忆

推荐任务示例：

- `先基于当前资料总结 RAG 的核心概念，再说明引用来源；如果资料不足，可联网补充背景知识。`
- `检查当前资料是否包含作者或发布者信息；若不足则联网补充，并整理成简短研究摘要。`
- `先检索长期记忆和本地资料，再输出一份关于多 Agent Runtime 的结构化学习笔记。`


## 技术栈

- `LangChain`
- `FAISS`
- `SQLite`
- `MCP`
- `Tavily Search`
- `FastAPI`
- `React + Vite`

## API

主要接口：

- `GET /api/status`
- `GET /api/documents`
- `POST /api/uploads`
- `POST /api/vectorstore/rebuild`
- `POST /api/qa`
- `POST /api/summary`
- `POST /api/runtime/run`
- `GET /api/runtime/tasks`
- `GET /api/memory/list`
- `GET /api/memory/stats`
- `POST /api/memory/search`

## 环境变量

最小环境变量：

```env
OPENAI_API_KEY=
OPENAI_BASE_URL=
CHAT_MODEL=
EMBEDDING_MODEL=
TAVILY_API_KEY=
FRONTEND_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

## 本地启动

```bash
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

前端开发：

```bash
cd frontend
npm install
npm run dev
```

## 当前阶段与下一步

当前已经完成：

- `RAG` 问答与来源引用
- `Master-Worker-Checker` 运行时
- 短期 / 长期记忆
- 缺口驱动补救
- 运行轨迹与回合级可观测性

后续可以继续迭代：

- 更精细的 worker 并行与重试策略
- 更强的长期记忆评分、合并与淘汰机制
- 更系统的评测集与自动化测试
- 更成熟的运行可视化与分析面板
