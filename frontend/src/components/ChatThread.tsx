import { Check, Link2 } from "lucide-react";
import { AgentPhase, WikiPage } from "../api";
import { ChatMessage } from "../App";
import MarkdownView from "./MarkdownView";

type ChatThreadProps = {
  finalPlan: string;
  messages: ChatMessage[];
  phases: AgentPhase[];
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

function ChatThread({ finalPlan, messages, phases, onOpenWiki, wikiPages }: ChatThreadProps) {
  const isEmpty = messages.length === 0 && phases.length === 0 && !finalPlan;

  return (
    <section className="chat-area" aria-label="事故处置分析">
      {isEmpty ? (
        <article className="agent-card empty-session-card">
          <div className="agent-card-head">
            <span className="agent-card-title">新建事故会话</span>
            <span className="agent-status done">待输入</span>
          </div>
          <div className="agent-card-body">
            输入事故描述后，系统会依次展示事故解析、案例匹配、激进方案、保守方案、合规审核和最终决策。
          </div>
        </article>
      ) : null}

      {messages.map((message) => (
        <div className={`msg msg-${message.role}`} key={message.id}>
          <div className="msg-bubble">{message.content}</div>
          <div className="msg-time">{message.createdAt}</div>
        </div>
      ))}

      {phases.map((phase) => (
        <div className="agent-step" key={phase.id}>
          <div className="agent-step-header">
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

      {finalPlan ? <article className="agent-card final-card">
        <div className="agent-card-head">
          <span className="agent-card-title">最终处置方案 Markdown</span>
          <span className="agent-status done">可导出</span>
        </div>
        <div className="agent-card-body markdown-body compact">
          <MarkdownView content={finalPlan} onOpenWiki={onOpenWiki} wikiPages={wikiPages} />
        </div>
      </article> : null}
    </section>
  );
}

export default ChatThread;
