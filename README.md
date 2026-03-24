# Multi-Agent 私人任务助理

一个面向个人资料与学习资料的 `Multi-Agent` 任务助理项目，目标不是做“又一个聊天页面”，而是把任务拆解、工具调用、结果审核、记忆沉淀和前端观测串成一个完整闭环。

技术栈：

- `FastAPI`
- `React + Vite`
- `LangChain`
- `FAISS`
- `SQLite`
- `MCP`
- `Tavily Search`

核心能力：

- `Master + Worker + Final Checker`
- `Short-term Memory + Long-term Memory`
- `RAG + Web Search + MCP Tools`
- `运行轨迹 + 回合摘要 + 缺口分级`

## 这个项目解决什么问题

很多资料型 Agent demo 只能做单轮问答，很难回答下面这些更真实的问题：

- 一个复杂任务怎么拆成多个步骤
- 工具到底有没有被正确调用
- 结果不完整时系统怎么知道还要继续补
- 历史结论怎么沉淀并在后续任务里复用
- 前端怎么把整个 Agent 运行过程讲清楚

这个项目围绕这些问题做了一个学习型但完整的工程实现：

- `Master` 负责任务规划、派发和停机判断
- `Worker` 是通用执行单元，不预设固定角色
- `Final Checker` 审核任务完成度、证据充分性和缺口类型
- `Memory Layer` 管理上下文和长期沉淀
- 前端把回合状态、阻塞缺口、记忆命中、补救路径展示出来

## 当前能力

### 1. 资料入库与本地 RAG

- 支持导入 `.md`、`.txt`、`.pdf`
- 对学习资料切分、向量化并写入 `FAISS`
- 提供本地问答、来源引用和片段预览

### 2. Multi-Agent Runtime

- `Master` 接收任务并生成子任务
- `Worker` 直接调用统一工具层执行任务
- `Final Checker` 输出：
  - `passed`
  - `score`
  - `blocking_requirements`
  - `advisory_gaps`
  - `completion_status`
- 当存在阻塞缺口时，Master 会基于缺口反馈继续规划补救轮

### 3. 记忆层

- `Short-term Memory`
  - `Pinned Context`
  - `Sliding Window`
  - `LLM Compression`
- `Long-term Memory`
  - 高价值结果入库
  - 向量检索复用
  - 强去重和简单近似重复处理
- `SQLite` 记录任务、worker 运行、记忆和运行产物

### 4. 工具层

运行时统一通过 `Tool Registry` 暴露能力，包括：

- 本地 RAG 工具
- `web_search`
- MCP 工具
- 导出工具
- 记忆检索工具

### 5. 前端控制台

前端已支持：

- 学习问答
- 多 Agent 任务运行
- 资料总结
- 资料库浏览
- 记忆库查看
- 回合摘要 / 缺口 / 运行轨迹 / 记忆命中展示

## 系统结构

```text
langchain_knowledge_qa/
├── backend/            # FastAPI API
├── frontend/           # React 控制台
├── runtime/            # Master / Worker / Checker / Planner
├── tools/              # Tool Registry 与工具封装
├── memory/             # 短期记忆、长期记忆、压缩、去重、检索
├── storage/            # SQLite 初始化与 repository
├── docs/               # 架构与产品文档
├── tests/              # 轻量单元测试
├── data/               # 本地资料
├── outputs/            # 导出与运行记录
├── vectorstore/        # 资料向量库
├── qa_chain.py         # 本地问答链
├── mcp_server.py       # MCP 服务
└── web_tools.py        # 联网搜索工具
```

## 演示建议

最推荐的演示顺序：

1. 上传 1 到 3 份讲义或技术文档到 `data/`
2. 点击“构建 / 更新资料索引”
3. 在“学习问答”里问一个资料内问题
4. 在“多Agent任务”里输入一个有明确完成标准的任务
5. 观察：
   - Master 规划
   - Worker 结果
   - Checker 结论
   - blocking / advisory gaps
   - 长期记忆命中与写入

推荐任务示例：

- `先基于当前资料总结 RAG 的核心概念，再说明引用来源；如果资料不足，可联网补充背景知识。`
- `检查当前资料是否包含作者或发布者信息；若不足则联网补充，并整理成简短研究摘要。`
- `先检索长期记忆和本地资料，再输出一份关于多 Agent Runtime 的结构化学习笔记。`

推荐完成标准示例：

- `优先基于本地资料回答`
- `结论要说明资料依据`
- `资料不足时允许联网补充`

## 适合在简历或面试里怎么讲

一句话版本：

> 我做了一个面向个人资料和学习资料的 Multi-Agent 任务助理，重点实现了 Master-Worker-Checker 运行时、短期/长期记忆、RAG 与联网搜索协同，以及可观测的前端任务控制台。

展开版可以强调：

- 不只是聊天，而是任务拆解与调度
- 不只是生成答案，而是会审核结果并区分阻塞缺口与建议缺口
- 不只是单轮上下文，而是有短期上下文管理和长期记忆沉淀
- 不只是后端脚本，而是有前后端分离和运行轨迹展示

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

后端参考 [`.env.example`](/Users/aubreyue/STUDY/AI%20Agent/langchain_knowledge_qa/.env.example)  
前端参考 [frontend/.env.example](/Users/aubreyue/STUDY/AI%20Agent/langchain_knowledge_qa/frontend/.env.example)

最低需要：

```env
OPENAI_API_KEY=
OPENAI_BASE_URL=
CHAT_MODEL=
EMBEDDING_MODEL=
TAVILY_API_KEY=
FRONTEND_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

前端本地开发：

```env
VITE_API_BASE=http://127.0.0.1:8000/api
```

## 本地启动

安装 Python 依赖：

```bash
pip install -r requirements.txt
```

启动后端：

```bash
uvicorn backend.main:app --reload
```

启动前端：

```bash
cd frontend
npm install
npm run dev
```

## 公网部署

推荐组合：

- 前端：`Vercel`
- 后端：`Render`

关键点：

- 前端通过 `VITE_API_BASE` 指向后端
- 后端通过 `FRONTEND_ORIGINS` 配置跨域
- Render 默认磁盘是临时的，适合演示，不适合长期保存资料和输出

仓库里已经提供：

- [render.yaml](/Users/aubreyue/STUDY/AI%20Agent/langchain_knowledge_qa/render.yaml)

## 当前阶段与下一步

当前已经完成：

- 资料型 RAG
- Multi-Agent runtime
- 短期 / 长期记忆
- 缺口驱动补救
- 回合级可观测面板

如果继续迭代，最值得补的是：

- 更精细的 worker 并行与重试策略
- 更强的长期记忆评分和合并策略
- 更系统的评测集和自动化测试
- 更成熟的任务控制台和运行可视化
