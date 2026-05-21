import { Check, Link2 } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { AgentPhase, DispositionGraph, PlanVersion, WikiPage } from "../api";
import { ChatMessage } from "../App";
import DispositionGraphPane from "./DispositionGraphPane";
import MarkdownView from "./MarkdownView";

type ChatThreadProps = {
  finalPlan: string;
  planVersions: PlanVersion[];
  pendingMode: "explain" | "solve" | null;
  messages: ChatMessage[];
  phases: AgentPhase[];
  dispositionGraph?: DispositionGraph | null;
  onOpenWiki: (pageOrPath: WikiPage | string) => void;
  wikiPages: WikiPage[];
};

const tagText = {
  parse: "事故解析",
  match: "案例匹配",
  aggressive: "激进方案",
  conservative: "保守方案",
  plan: "方案生成",
  check: "合规审核",
  final: "最终决策",
};

const statusText = {
  pending: "待处理",
  running: "进行中",
  done: "完成",
  warning: "需复核",
};

function ChatThread({ dispositionGraph, finalPlan, planVersions, pendingMode, messages, phases, onOpenWiki, wikiPages }: ChatThreadProps) {
  const isEmpty = messages.length === 0 && phases.length === 0 && !finalPlan;
  const endRef = useRef<HTMLDivElement | null>(null);
  const [activeView, setActiveView] = useState<"plan" | "graph" | "agents" | "chat">("plan");
  const { setupMessages, laterMessages } = useMemo(() => splitMessages(messages, Boolean(finalPlan || phases.length)), [messages, finalPlan, phases.length]);
  const latestPlan = planVersions[planVersions.length - 1];
  const activePlanLabel = latestPlan ? `v${latestPlan.version}` : finalPlan ? "v1" : "无方案";

  useEffect(() => {
    if (!finalPlan && !planVersions.length && phases.length) {
      setActiveView("agents");
    }
    if ((finalPlan || planVersions.length) && !pendingMode) {
      setActiveView("plan");
    }
  }, [finalPlan, phases.length, pendingMode, planVersions.length]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [activeView, messages.length, phases.length, finalPlan, pendingMode, planVersions.length]);

  return (
    <section className="chat-area" aria-label="事故处置分析">
      <div className="decision-header">
        <div>
          <div className="decision-title">处置决策工作台</div>
          <div className="decision-subtitle">当前方案 {activePlanLabel} · {phases.length ? `${phases.length} 个 Agent 阶段` : "待生成 Agent 流程"}</div>
        </div>
        <div className="decision-tabs" role="tablist" aria-label="决策视图">
          <button className={activeView === "plan" ? "active" : ""} type="button" onClick={() => setActiveView("plan")}>方案版本</button>
          <button className={activeView === "graph" ? "active" : ""} type="button" onClick={() => setActiveView("graph")}>处置图谱</button>
          <button className={activeView === "agents" ? "active" : ""} type="button" onClick={() => setActiveView("agents")}>Agent 流程</button>
          <button className={activeView === "chat" ? "active" : ""} type="button" onClick={() => setActiveView("chat")}>对话记录</button>
        </div>
      </div>

      {pendingMode ? <ThinkingBubble mode={pendingMode} hasPlan={Boolean(finalPlan || planVersions.length)} /> : null}

      {isEmpty ? <EmptyWorkbench /> : null}

      {activeView === "plan" ? (
        <PlanVersionList finalPlan={finalPlan} planVersions={planVersions} onOpenWiki={onOpenWiki} wikiPages={wikiPages} />
      ) : null}

      {activeView === "graph" ? (
        <DispositionGraphPane graph={dispositionGraph} onOpenWiki={onOpenWiki} />
      ) : null}

      {activeView === "agents" ? (
        <AgentFlow phases={phases} onOpenWiki={onOpenWiki} wikiPages={wikiPages} />
      ) : null}

      {activeView === "chat" ? (
        <ConversationView setupMessages={setupMessages} laterMessages={laterMessages} onOpenWiki={onOpenWiki} wikiPages={wikiPages} />
      ) : null}
      <div ref={endRef} />
    </section>
  );
}

function EmptyWorkbench() {
  return (
    <article className="agent-card empty-session-card">
      <div className="agent-card-head">
        <span className="agent-card-title">新建事故会话</span>
        <span className="agent-status done">待输入</span>
      </div>
      <div className="agent-card-body">
        输入事故描述后，系统会生成方案版本，并在 Agent 流程中展示事故解析、案例匹配、激进方案、保守方案、主流程辩论、合规审核和最终决策。
      </div>
    </article>
  );
}

function AgentFlow({
  phases,
  onOpenWiki,
  wikiPages,
}: {
  phases: AgentPhase[];
  onOpenWiki: (pageOrPath: WikiPage | string) => void;
  wikiPages: WikiPage[];
}) {
  if (!phases.length) {
    return (
      <article className="agent-card">
        <div className="agent-card-body">暂无 Agent 流程。生成方案后会在这里展示各专家节点与主流程辩论。</div>
      </article>
    );
  }
  return (
    <div className="agent-flow">
      {phases.map((phase, index) => (
        <div className="agent-step" key={phase.id}>
          <div className="agent-step-header">
            <span className="agent-index">{index + 1}</span>
            <span className={`agent-tag tag-${phase.tag}`}>{tagText[phase.tag]}</span>
            <span>{phase.status === "warning" ? "存在待复核项" : statusText[phase.status]}</span>
          </div>
          <article className="agent-card">
            <div className="agent-card-head">
              <span className="agent-card-title">{phase.title}</span>
              <span className={`agent-status ${phase.status}`}>
                <Check size={12} aria-hidden="true" />
                {statusText[phase.status]}
              </span>
            </div>
            <div className="agent-card-body">
              <MarkdownView content={phase.summary} onOpenWiki={onOpenWiki} wikiPages={wikiPages} />
              {phase.details ? (
                <details className="agent-details">
                  <summary>查看完整决策</summary>
                  <MarkdownView content={phase.details} onOpenWiki={onOpenWiki} wikiPages={wikiPages} />
                </details>
              ) : null}
              {phase.citations?.length ? (
                <div className="citation-row">
                  {phase.citations.map((citation) => (
                    <button className="cite" key={`${phase.id}-${citation.label}`} onClick={() => onOpenWiki(citation.page)} type="button">
                      <Link2 size={10} aria-hidden="true" />
                      {citation.label}
                    </button>
                  ))}
                </div>
              ) : null}
            </div>
          </article>
        </div>
      ))}
    </div>
  );
}

function ConversationView({
  setupMessages,
  laterMessages,
  onOpenWiki,
  wikiPages,
}: {
  setupMessages: ChatMessage[];
  laterMessages: ChatMessage[];
  onOpenWiki: (pageOrPath: WikiPage | string) => void;
  wikiPages: WikiPage[];
}) {
  const hasMessages = setupMessages.length || laterMessages.length;
  if (!hasMessages) {
    return (
      <article className="agent-card">
        <div className="agent-card-body">暂无对话记录。</div>
      </article>
    );
  }
  return (
    <div className="conversation-panel">
      <MessageList messages={setupMessages} onOpenWiki={onOpenWiki} wikiPages={wikiPages} />
      {laterMessages.length ? (
        <div className="followup-thread" aria-label="后续追问与方案修订">
          <div className="followup-divider">后续会话</div>
          <MessageList messages={laterMessages} onOpenWiki={onOpenWiki} wikiPages={wikiPages} />
        </div>
      ) : null}
    </div>
  );
}

function ThinkingBubble({ mode, hasPlan }: { mode: "explain" | "solve"; hasPlan: boolean }) {
  const text = mode === "explain"
    ? "正在解释当前方案..."
    : hasPlan
      ? "正在重新评估方案，主流程 Agent 正在辩论..."
      : "正在生成处置方案，主流程 Agent 正在辩论...";
  return (
    <div className="msg msg-assistant">
      <div className="msg-bubble thinking-bubble">
        <span>{text}</span>
        <span className="thinking-dots" aria-hidden="true">
          <i />
          <i />
          <i />
        </span>
      </div>
    </div>
  );
}

function PlanVersionList({
  finalPlan,
  planVersions,
  onOpenWiki,
  wikiPages,
}: {
  finalPlan: string;
  planVersions: PlanVersion[];
  onOpenWiki: (pageOrPath: WikiPage | string) => void;
  wikiPages: WikiPage[];
}) {
  if (planVersions.length) {
    return (
      <div className="plan-version-list">
        <div className="followup-divider">方案版本</div>
        {planVersions.map((plan, index) => {
          const isLatest = index === planVersions.length - 1;
          return (
            <details className="agent-card final-card plan-version-card" key={`${plan.version}-${plan.created_at ?? index}`} open={isLatest}>
              <summary className="agent-card-head plan-version-head">
                <span className="agent-card-title">处置方案 v{plan.version}{isLatest ? "（当前）" : ""}</span>
                <span className="agent-status done">{isLatest ? "当前方案" : "历史版本"}</span>
              </summary>
              <div className="plan-version-meta">
                <span>{plan.created_at || "时间未记录"}</span>
                {typeof plan.confidence_score === "number" ? <span>置信度 {Math.round(plan.confidence_score * 100)}%</span> : null}
              </div>
              <div className="agent-card-body markdown-body compact">
                <MarkdownView content={plan.content} onOpenWiki={onOpenWiki} wikiPages={wikiPages} />
              </div>
            </details>
          );
        })}
      </div>
    );
  }
  if (!finalPlan) return null;
  return (
    <details className="agent-card final-card plan-version-card" open>
      <summary className="agent-card-head plan-version-head">
        <span className="agent-card-title">处置方案 v1（当前）</span>
        <span className="agent-status done">当前方案</span>
      </summary>
      <div className="agent-card-body markdown-body compact">
        <MarkdownView content={finalPlan} onOpenWiki={onOpenWiki} wikiPages={wikiPages} />
      </div>
    </details>
  );
}

function MessageList({
  messages,
  onOpenWiki,
  wikiPages,
}: {
  messages: ChatMessage[];
  onOpenWiki: (pageOrPath: WikiPage | string) => void;
  wikiPages: WikiPage[];
}) {
  return (
    <>
      {messages.map((message) => (
        <div className={`msg msg-${message.role}`} key={message.id}>
          <div className="msg-bubble">
            <MarkdownView content={message.content} onOpenWiki={onOpenWiki} wikiPages={wikiPages} />
          </div>
          <div className="msg-time">{message.createdAt}</div>
        </div>
      ))}
    </>
  );
}

function splitMessages(messages: ChatMessage[], hasPlanSurface: boolean) {
  if (!hasPlanSurface || messages.length <= 2) {
    return { setupMessages: messages, laterMessages: [] };
  }
  const completionIndex = messages.findIndex(
    (message) => message.role === "assistant" && message.content.includes("已完成处置方案生成"),
  );
  if (completionIndex < 0) {
    return { setupMessages: messages.slice(0, 1), laterMessages: messages.slice(1) };
  }
  return {
    setupMessages: messages.slice(0, completionIndex + 1),
    laterMessages: messages.slice(completionIndex + 1),
  };
}

export default ChatThread;
