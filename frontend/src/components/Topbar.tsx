import { Download, KeyRound, Plus, Wrench } from "lucide-react";
import PlanActions from "./PlanActions";

type TopbarProps = {
  statusLabel: string;
  finalPlan: string;
  llmConfigured: boolean;
  onNewSession: () => void;
  onOpenLLMSettings: () => void;
};

function Topbar({ statusLabel, finalPlan, llmConfigured, onNewSession, onOpenLLMSettings }: TopbarProps) {
  return (
    <header className="topbar">
      <div className="topbar-left">
        <Wrench size={16} className="muted-icon" aria-hidden="true" />
        <span className="topbar-title">钻具落断事故处置系统</span>
        <span className="topbar-separator">|</span>
        <span className="status-dot" aria-hidden="true" />
        <span className="status-label">{statusLabel}</span>
      </div>
      <div className="topbar-right">
        <button className={`topbar-btn ${llmConfigured ? "active" : ""}`} type="button" onClick={onOpenLLMSettings}>
          <KeyRound size={14} aria-hidden="true" />
          {llmConfigured ? "LLM 已配置" : "LLM 设置"}
        </button>
        <button className="topbar-btn" type="button" onClick={onNewSession}>
          <Plus size={14} aria-hidden="true" />
          新建会话
        </button>
        <PlanActions
          plan={finalPlan}
          trigger={
            <button className="topbar-btn" type="button">
              <Download size={14} aria-hidden="true" />
              导出
            </button>
          }
        />
      </div>
    </header>
  );
}

export default Topbar;
