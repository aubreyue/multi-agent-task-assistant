import { useEffect, useState } from "react";
import sheepImage from "../../pics/helloworld.jpg";

const API_BASE = (import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000/api").replace(/\/$/, "");
const TABS = ["多Agent任务", "资料总结", "资料库", "记忆库"];

async function apiGet(path) {
  const response = await fetch(`${API_BASE}${path}`);
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "请求失败");
  }
  return data;
}

async function apiPost(path, body) {
  const response = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "请求失败");
  }
  return data;
}

async function uploadFiles(files) {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));
  const response = await fetch(`${API_BASE}/uploads`, {
    method: "POST",
    body: formData,
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || "上传失败");
  }
  return data;
}

function ResultPanel({ title, children }) {
  return (
    <section className="result-panel">
      <h3>{title}</h3>
      {children}
    </section>
  );
}

function StatusChip({ tone, children }) {
  return <span className={`status-chip ${tone}`}>{children}</span>;
}

export default function App() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [activeTab, setActiveTab] = useState("多Agent任务");
  const [runtimeMode, setRuntimeMode] = useState("quick");
  const [status, setStatus] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [autoRebuild, setAutoRebuild] = useState(true);
  const [qaQuestion, setQaQuestion] = useState("");
  const [qaResult, setQaResult] = useState(null);
  const [agentTask, setAgentTask] = useState("基于当前学习资料，整理一份关于向量检索的复习提纲，并导出为 markdown。");
  const [agentCriteriaText, setAgentCriteriaText] = useState("优先基于本地资料回答\n结论要有资料依据\n资料不足时联网补充");
  const [agentResult, setAgentResult] = useState(null);
  const [summaryResult, setSummaryResult] = useState(null);
  const [memoryStats, setMemoryStats] = useState(null);
  const [memoryList, setMemoryList] = useState([]);
  const [runtimeTasks, setRuntimeTasks] = useState([]);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const qaBusy = busy.includes("正在基于学习资料回答问题");
  const runtimeBusy = busy.includes("Multi-Agent 运行时");
  const qaNotice = notice.startsWith("学习问答结果已保存到") ? notice : "";
  const runtimeNotice = notice.startsWith("运行时任务记录已保存到") ? notice : "";
  const taskAreaError = activeTab === "多Agent任务" && !!error;
  const sidebarBusy = qaBusy || runtimeBusy ? "" : busy;
  const sidebarNotice = qaNotice || runtimeNotice ? "" : notice;
  const sidebarError = taskAreaError ? "" : error;

  const quickModeStatus = qaBusy
    ? { tone: "info", text: busy }
    : taskAreaError
      ? { tone: "error", text: error }
      : qaNotice
        ? { tone: "success", text: qaNotice }
        : {
            tone: "info",
            text: "快速问答结果会显示在这里，方便你确认本轮回答是否已经完成保存。",
          };

  const taskModeStatus = runtimeBusy
    ? { tone: "info", text: busy }
    : taskAreaError
      ? { tone: "error", text: error }
      : runtimeNotice
        ? { tone: "success", text: runtimeNotice }
        : {
            tone: "info",
            text: "任务模式的运行记录会显示在这里，方便你查看本轮任务结果保存位置。",
          };

  const refreshStatus = async () => {
    const [statusData, docsData] = await Promise.all([
      apiGet("/status"),
      apiGet("/documents"),
    ]);
    setStatus(statusData);
    setDocuments(docsData.documents);
    setMemoryStats(await apiGet("/memory/stats"));
    const memoryData = await apiGet("/memory/list");
    setMemoryList(memoryData.memories);
    const runtimeTaskData = await apiGet("/runtime/tasks");
    setRuntimeTasks(runtimeTaskData.tasks);
  };

  useEffect(() => {
    refreshStatus().catch((err) => setError(err.message));
  }, []);

  const handleUpload = async (event) => {
    const files = Array.from(event.target.files || []);
    if (!files.length) return;
    setBusy("正在上传文件...");
    setError("");
    setNotice("");
    try {
      const result = await uploadFiles(files);
      if (autoRebuild) {
        const rebuild = await apiPost("/vectorstore/rebuild", {});
        setNotice(`已上传 ${result.saved_count} 个文件，并完成向量库更新。${rebuild.message}`);
      } else {
        setNotice(`已上传 ${result.saved_count} 个文件。`);
      }
      await refreshStatus();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("");
      event.target.value = "";
    }
  };

  const handleRebuild = async () => {
    setBusy("正在构建向量库...");
    setError("");
    setNotice("");
    try {
      const result = await apiPost("/vectorstore/rebuild", {});
      setNotice(result.message);
      await refreshStatus();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("");
    }
  };

  const handleAsk = async () => {
    if (!qaQuestion.trim()) return;
    setBusy("正在基于学习资料回答问题...");
    setError("");
    setNotice("");
    try {
      const result = await apiPost("/qa", { question: qaQuestion });
      setQaResult(result);
      setNotice(`学习问答结果已保存到 ${result.output_path}`);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("");
    }
  };

  const handleAgent = async () => {
    if (!agentTask.trim()) return;
    setBusy("Multi-Agent 运行时正在规划任务、调度 worker 并整理结果...");
    setError("");
    setNotice("");
    try {
      const criteria = agentCriteriaText
        .split("\n")
        .map((item) => item.trim())
        .filter(Boolean);
      const result = await apiPost("/runtime/run", { task: agentTask, max_rounds: 3, criteria });
      setAgentResult(result);
      setNotice(`运行时任务记录已保存到 ${result.output_path}`);
      await refreshStatus();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("");
    }
  };

  const handleSummary = async () => {
    setBusy("正在生成学习资料总结...");
    setError("");
    setNotice("");
    try {
      const result = await apiPost("/summary", {});
      setSummaryResult(result);
      setNotice(`学习资料总结已保存到 ${result.output_path}`);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy("");
    }
  };

  const handleClearHistory = () => {
    setQaResult(null);
    setAgentResult(null);
    setSummaryResult(null);
    setNotice("已清空当前前端会话中的问答、运行时任务和总结结果。");
    setError("");
  };

  return (
    <div className={sidebarOpen ? "page-shell" : "page-shell collapsed"}>
      {!sidebarOpen ? (
        <button
          className="sidebar-toggle collapsed"
          onClick={() => setSidebarOpen(true)}
          aria-label="展开侧边栏"
          title="展开侧边栏"
        >
          »
        </button>
      ) : null}
      <aside className="sidebar">
        <div className="sidebar-panel">
          <button
            className="sidebar-toggle in-sidebar"
            onClick={() => setSidebarOpen(false)}
            aria-label="收起侧边栏"
            title="收起侧边栏"
          >
            «
          </button>
          <p className="sidebar-copy sidebar-intro">
            让 Master 负责接收任务和调度通用 Worker，Worker 直接调用 RAG、联网搜索、MCP 与记忆工具完成工作，Final Checker 负责审核结果质量，并把高价值结果沉淀进长期记忆。
          </p>
          <div className="visual-node node-accent sidebar-master">
            <strong>Master Agent</strong>
            <span>负责规划任务、派发 Worker、汇总结果并检查 stop criteria。</span>
          </div>
          <div className="sidebar-visual">
            <div className="visual-node">
              <strong>Worker Agents</strong>
              <span>通用执行单元，不固定角色，按子任务自主调用工具完成工作。</span>
            </div>
            <div className="visual-node node-warm">
              <strong>Final Checker</strong>
              <span>对最终候选答案做任务完成度和证据充分性审核。</span>
            </div>
            <div className="visual-node">
              <strong>Tool Registry</strong>
              <span>统一注册 RAG、Search、MCP、Export 与 Memory 工具供 runtime 共享。</span>
            </div>
            <div className="visual-node">
              <strong>Memory Layer</strong>
              <span>短期记忆管理上下文预算，长期记忆支持入库、检索与去重。</span>
            </div>
            <div className="visual-footer compact">
              任务编排、工具使用、结果审核、记忆沉淀和前端展示形成一个闭环。
            </div>
          </div>
          <div className="sidebar-meta">
            <div>
              <span>资料目录</span>
              <strong>{status?.data_dir || "-"}</strong>
            </div>
            <div>
              <span>输出目录</span>
              <strong>{status?.outputs_dir || "-"}</strong>
            </div>
          </div>
          <div className="status-row">
            <span>资料索引状态</span>
            <strong className={status?.vectorstore_ready ? "status-badge ready" : "status-badge"}>
              {status?.vectorstore_ready ? "已构建" : "未构建"}
            </strong>
          </div>
          <label className="upload-box">
            <span className="upload-title">上传学习资料</span>
            <span className="upload-copy">导入讲义、论文、技术文档或笔记</span>
            <span className="upload-hint">Limit 200MB per file • MD, TXT, PDF</span>
            <input type="file" multiple accept=".md,.txt,.pdf" onChange={handleUpload} />
          </label>
          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={autoRebuild}
              onChange={(event) => setAutoRebuild(event.target.checked)}
            />
            <span>上传后自动重建资料索引</span>
          </label>
          <div className="status-row">
            <span>已纳入资料数</span>
            <strong className="count-badge">{documents.length}</strong>
          </div>
          <div className="status-row">
            <span>长期记忆数</span>
            <strong className="count-badge">{memoryStats?.total_memories ?? 0}</strong>
          </div>
          <button className="primary-button" onClick={handleRebuild} disabled={!!busy}>
            构建 / 更新资料索引
          </button>
          <button className="secondary-button" onClick={handleClearHistory} disabled={!!busy}>
            清空当前结果
          </button>
          {sidebarBusy ? <div className="status-info">{sidebarBusy}</div> : null}
          {sidebarNotice ? <div className="status-success">{sidebarNotice}</div> : null}
          {sidebarError ? <div className="status-error">{sidebarError}</div> : null}
        </div>
      </aside>

      <main className="main-panel">
        <section className="hero">
          <div className="hero-layout">
            <div className="hero-main">
              <div className="hero-copy">
                <div className="eyebrow">Master + Workers + Checker + Memory</div>
                <div className="hero-copy-grid">
                  <h1>
                    <span>Multi-Agent</span>
                    <span>私人任务助理</span>
                  </h1>
                  <div className="hero-image-wrap">
                    <img src={sheepImage} alt="sheep illustration" className="hero-image" />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <nav className="tab-row">
          {TABS.map((tab) => (
            <button
              key={tab}
              className={tab === activeTab ? "tab active" : "tab"}
              onClick={() => setActiveTab(tab)}
            >
              {tab}
            </button>
          ))}
        </nav>

        {activeTab === "多Agent任务" ? (
          <section className="content-card">
            <h2>任务运行</h2>
            <p className="content-copy">快速问答适合单问题检索回答；任务模式适合需要规划、补救、审核和记忆沉淀的复杂任务。</p>
            <div className={`inline-status ${runtimeMode === "quick" ? `status-${quickModeStatus.tone}` : `status-${taskModeStatus.tone}`}`}>
              {runtimeMode === "quick" ? quickModeStatus.text : taskModeStatus.text}
            </div>
            <div className="mode-switcher">
              <button
                className={runtimeMode === "quick" ? "mode-pill active" : "mode-pill"}
                onClick={() => setRuntimeMode("quick")}
              >
                快速问答
              </button>
              <button
                className={runtimeMode === "task" ? "mode-pill active" : "mode-pill"}
                onClick={() => setRuntimeMode("task")}
              >
                任务模式
              </button>
            </div>

            {runtimeMode === "quick" ? (
              <>
                <textarea
                  className="task-box"
                  value={qaQuestion}
                  onChange={(event) => setQaQuestion(event.target.value)}
                  placeholder="例如：这份讲义里关于 RAG 的核心概念是什么？"
                />
                <button className="primary-button" onClick={handleAsk} disabled={!!busy}>
                  开始问答
                </button>
                {qaResult ? (
                  <div className="stack">
                    <ResultPanel title="回答">{qaResult.answer}</ResultPanel>
                    <ResultPanel title="引用来源">
                      <ul className="clean-list">
                        {qaResult.sources.map((source) => (
                          <li key={source}>{source}</li>
                        ))}
                      </ul>
                    </ResultPanel>
                    <ResultPanel title="片段预览">
                      <div className="stack">
                        {qaResult.source_previews.map((item) => (
                          <div className="trace-item" key={item.label}>
                            <strong>{item.label}</strong>
                            <span>{item.snippet}</span>
                          </div>
                        ))}
                      </div>
                    </ResultPanel>
                  </div>
                ) : null}
              </>
            ) : (
              <>
                <textarea
                  className="task-box"
                  value={agentTask}
                  onChange={(event) => setAgentTask(event.target.value)}
                  placeholder="例如：先检索资料和长期记忆，再整理一份关于向量检索与多 Agent Runtime 的结构化研究总结。"
                />
                <textarea
                  className="task-box compact"
                  value={agentCriteriaText}
                  onChange={(event) => setAgentCriteriaText(event.target.value)}
                  placeholder="每行一条完成标准，例如：优先基于本地资料回答"
                />
                <button className="primary-button" onClick={handleAgent} disabled={!!busy}>
                  运行 Multi-Agent Runtime
                </button>
                {agentResult ? (
                  <div className="stack">
                <ResultPanel title="Master 总结">{agentResult.master_summary}</ResultPanel>
                <ResultPanel title="最终输出">{agentResult.final_answer}</ResultPanel>
                <ResultPanel title="当前完成标准">
                  <div className="stack">
                    {(agentResult.plans?.[agentResult.plans.length - 1]?.stop_criteria || []).map((item, index) => (
                      <div className="trace-item" key={`${item}-${index}`}>
                        <span>{item}</span>
                      </div>
                    ))}
                  </div>
                </ResultPanel>
                <ResultPanel title="运行诊断">
                  <div className="stack">
                    <div className="trace-item">
                      <strong>rounds</strong>
                      <span>{agentResult.diagnostics.total_rounds}</span>
                    </div>
                    <div className="trace-item">
                      <strong>workers</strong>
                      <span>{agentResult.diagnostics.total_workers}</span>
                    </div>
                    <div className="trace-item">
                      <strong>memory hits / writes</strong>
                      <span>{agentResult.diagnostics.memory_hit_count} / {agentResult.diagnostics.memory_write_count}</span>
                    </div>
                    <div className="trace-item">
                      <strong>compression count</strong>
                      <span>{agentResult.diagnostics.compression_count}</span>
                    </div>
                  </div>
                </ResultPanel>
                <ResultPanel title="回合摘要">
                  <div className="stack">
                    {agentResult.round_summaries.map((item) => (
                      <div className="trace-item timeline-card" key={`round-${item.round_index}`}>
                        <strong>round {item.round_index}</strong>
                        <span>{item.master_summary}</span>
                        <div className="chip-row">
                          <StatusChip tone={item.checker_passed ? "success" : "warn"}>
                            {item.checker_passed ? "通过" : "继续补充"}
                          </StatusChip>
                          <StatusChip tone={item.checker_passed ? "success" : item.completion_status === "accepted_with_gaps" ? "accent" : "warn"}>
                            {item.completion_status}
                          </StatusChip>
                          <StatusChip tone="neutral">workers {item.worker_count}</StatusChip>
                          <StatusChip tone="neutral">score {item.checker_score}</StatusChip>
                          {item.compression_applied ? <StatusChip tone="accent">压缩</StatusChip> : null}
                        </div>
                        <div className="timeline-meta">
                          <span>stop reason: {item.stopping_reason || "continue_revision"}</span>
                          <span>blocking gaps: {item.blocking_requirements?.length || 0}</span>
                          <span>advisory gaps: {item.advisory_gaps?.length || 0}</span>
                        </div>
                        {item.blocking_requirements?.length ? (
                          <div className="trace-item gap-card">
                            <strong>本轮阻塞缺口</strong>
                            {item.blocking_requirements.map((gap, gapIndex) => (
                              <span key={`${gap}-${gapIndex}`}>{gap}</span>
                            ))}
                          </div>
                        ) : null}
                        {item.advisory_gaps?.length ? (
                          <div className="trace-item gap-card soft">
                            <strong>本轮建议补充</strong>
                            {item.advisory_gaps.map((gap, gapIndex) => (
                              <span key={`${gap}-${gapIndex}`}>{gap}</span>
                            ))}
                          </div>
                        ) : null}
                      </div>
                    ))}
                  </div>
                </ResultPanel>
                <ResultPanel title="Worker 执行结果">
                  <div className="stack">
                    {agentResult.worker_results.map((item) => (
                      <div className="trace-item" key={item.task_id}>
                        <strong>{item.task_id}</strong>
                        <span>{item.summary}</span>
                      </div>
                    ))}
                  </div>
                </ResultPanel>
                <ResultPanel title="Checker 结果">
                  <div className="stack">
                    <div className="trace-item timeline-card">
                      <strong>{agentResult.checker.passed ? "已通过" : "需返工"}</strong>
                      <div className="chip-row">
                        <StatusChip tone={agentResult.checker.passed ? "success" : "warn"}>
                          {agentResult.checker.completion_status}
                        </StatusChip>
                        <StatusChip tone="neutral">score {agentResult.checker.score}</StatusChip>
                      </div>
                    </div>
                    {agentResult.checker.issues.map((issue, index) => (
                      <div className="trace-item" key={`${issue}-${index}`}>
                        <span>{issue}</span>
                      </div>
                    ))}
                    {agentResult.checker.blocking_requirements?.length ? (
                      <div className="trace-item gap-card">
                        <strong>必须补齐</strong>
                        {agentResult.checker.blocking_requirements.map((item, index) => (
                          <span key={`${item}-${index}`}>{item}</span>
                        ))}
                      </div>
                    ) : null}
                    {agentResult.checker.advisory_gaps?.length ? (
                      <div className="trace-item gap-card soft">
                        <strong>可接受缺口</strong>
                        {agentResult.checker.advisory_gaps.map((item, index) => (
                          <span key={`${item}-${index}`}>{item}</span>
                        ))}
                      </div>
                    ) : null}
                    {agentResult.checker.notes ? (
                      <div className="trace-item">
                        <strong>审核说明</strong>
                        <span>{agentResult.checker.notes}</span>
                      </div>
                    ) : null}
                  </div>
                </ResultPanel>
                <ResultPanel title="长期记忆命中">
                  <div className="stack">
                    {agentResult.memory_hits.length ? agentResult.memory_hits.map((item) => (
                      <div className="trace-item" key={`${item.memory_id}-${item.summary}`}>
                        <strong>{item.memory_type}</strong>
                        <span>{item.summary}</span>
                      </div>
                    )) : <div className="trace-item"><span>本轮未命中长期记忆。</span></div>}
                  </div>
                </ResultPanel>
                <ResultPanel title="长期记忆写入">
                  <div className="stack">
                    {agentResult.memory_writes.length ? agentResult.memory_writes.map((item) => (
                      <div className="trace-item" key={`${item.fingerprint}-${item.title}`}>
                        <strong>{item.title}</strong>
                        <span>{item.summary}</span>
                      </div>
                    )) : <div className="trace-item"><span>本轮没有新增长期记忆。</span></div>}
                  </div>
                </ResultPanel>
                <ResultPanel title="上下文快照">
                  <div className="stack">
                    {agentResult.context_snapshots.map((item, index) => (
                      <div className="trace-item" key={`${item.task_id}-${index}`}>
                        <strong>snapshot #{index + 1}</strong>
                        <span>compression: {item.compression_applied ? "yes" : "no"} | token_estimate: {item.token_estimate}</span>
                      </div>
                    ))}
                  </div>
                </ResultPanel>
                <ResultPanel title="运行轨迹">
                  <div className="stack">
                    {agentResult.traces.map((trace, index) => (
                      <div className="trace-item" key={`${trace}-${index}`}>
                        <span>{trace}</span>
                      </div>
                    ))}
                  </div>
                </ResultPanel>
                <ResultPanel title="最近运行任务">
                  <div className="stack">
                    {runtimeTasks.map((item) => (
                      <div className="trace-item timeline-card" key={`task-${item.id}`}>
                        <strong>#{item.id} · {item.status}</strong>
                        <span>{item.task}</span>
                        <div className="chip-row">
                          <StatusChip tone={item.status === "completed" ? "success" : item.status === "failed" ? "danger" : "warn"}>
                            {item.status}
                          </StatusChip>
                          <StatusChip tone="neutral">checker {item.checker_score}</StatusChip>
                        </div>
                      </div>
                    ))}
                  </div>
                </ResultPanel>
                  </div>
                ) : null}
              </>
            )}
          </section>
        ) : null}

        {activeTab === "资料总结" ? (
          <section className="content-card">
            <h2>资料总结</h2>
            <p className="content-copy">面向整个学习资料库生成一份总览，适合快速把握当前主题和复习重点。</p>
            <button className="primary-button" onClick={handleSummary} disabled={!!busy}>
              生成总结
            </button>
            {summaryResult ? <ResultPanel title="摘要内容">{summaryResult.summary}</ResultPanel> : null}
          </section>
        ) : null}

        {activeTab === "资料库" ? (
          <section className="content-card">
            <h2>资料库</h2>
            <p className="content-copy">展示当前已纳入学习资料库管理的文件，方便检查讲义、论文和笔记是否已入库。</p>
            <div className="doc-grid">
              {documents.map((doc) => (
                <article className="doc-card" key={doc.path}>
                  <strong>{doc.name}</strong>
                  <span>{doc.suffix}</span>
                  <span>{doc.size_kb} KB</span>
                  <code>{doc.path}</code>
                </article>
              ))}
            </div>
          </section>
        ) : null}

        {activeTab === "记忆库" ? (
          <section className="content-card">
            <h2>记忆库</h2>
            <p className="content-copy">展示当前长期记忆中的高价值结果，用于后续任务复用、召回和偏好参考。</p>
            <div className="stack">
              {memoryList.map((item) => (
                <article className="doc-card" key={`${item.memory_id}-${item.fingerprint}`}>
                  <strong>{item.title}</strong>
                  <span>{item.memory_type}</span>
                  <span>quality: {item.quality_score}</span>
                  <code>{item.source}</code>
                  <p>{item.summary}</p>
                </article>
              ))}
              {!memoryList.length ? <div className="trace-item"><span>当前还没有长期记忆。</span></div> : null}
            </div>
          </section>
        ) : null}
      </main>
    </div>
  );
}

  );
}
