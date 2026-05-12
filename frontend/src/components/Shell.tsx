import { AgentPhase, AccidentFields, EvidenceItem, LLMConfig, LLMConfigPayload, SessionSummary, WikiPage } from "../api";
import { ChatMessage } from "../App";
import AccidentPanel from "./AccidentPanel";
import ChatThread from "./ChatThread";
import Composer from "./Composer";
import EvidencePanel from "./EvidencePanel";
import LLMSettingsDialog from "./LLMSettingsDialog";
import Sidebar from "./Sidebar";
import Topbar from "./Topbar";
import WikiPane from "./WikiPane";

type ShellProps = {
  accident: AccidentFields;
  activeWikiPage: WikiPage | null;
  confidence: number;
  evidence: EvidenceItem[];
  finalPlan: string;
  isSolving: boolean;
  llmConfig: LLMConfig | null;
  llmSettingsOpen: boolean;
  messages: ChatMessage[];
  onBackToChat: () => void;
  onNewSession: () => void;
  onCloseLLMSettings: () => void;
  onOpenWiki: (page: WikiPage | string) => void;
  onOpenLLMSettings: () => void;
  onSaveLLMSettings: (payload: LLMConfigPayload) => Promise<void>;
  onSelectSession: (session: SessionSummary) => void;
  onSubmit: (description: string) => void;
  phases: AgentPhase[];
  sessions: SessionSummary[];
  activeSessionId?: string;
  statusLabel: string;
  view: "chat" | "wiki";
  wikiPages: WikiPage[];
};

function Shell({
  accident,
  activeWikiPage,
  confidence,
  evidence,
  finalPlan,
  isSolving,
  llmConfig,
  llmSettingsOpen,
  messages,
  onBackToChat,
  onCloseLLMSettings,
  onNewSession,
  onOpenWiki,
  onOpenLLMSettings,
  onSaveLLMSettings,
  onSelectSession,
  onSubmit,
  phases,
  sessions,
  activeSessionId,
  statusLabel,
  view,
  wikiPages,
}: ShellProps) {
  return (
    <div className="app-frame">
      <div className="shell">
        <Topbar
          statusLabel={statusLabel}
          finalPlan={finalPlan}
          llmConfigured={Boolean(llmConfig?.enabled && llmConfig?.has_api_key)}
          onNewSession={onNewSession}
          onOpenLLMSettings={onOpenLLMSettings}
        />
        <Sidebar
          activeSessionId={activeSessionId}
          sessions={sessions}
          wikiPages={wikiPages}
          onNewSession={onNewSession}
          onOpenWiki={onOpenWiki}
          onSelectSession={onSelectSession}
        />

        {view === "wiki" ? (
          <WikiPane page={activeWikiPage} onBack={onBackToChat} onOpenWiki={onOpenWiki} wikiPages={wikiPages} />
        ) : (
          <main className="main">
            <ChatThread messages={messages} phases={phases} onOpenWiki={onOpenWiki} finalPlan={finalPlan} wikiPages={wikiPages} />
            <Composer onSubmit={onSubmit} disabled={isSolving} />
          </main>
        )}

        <EvidencePanel
          accident={<AccidentPanel accident={accident} />}
          confidence={confidence}
          evidence={evidence}
          onOpenWiki={onOpenWiki}
        />
        <LLMSettingsDialog config={llmConfig} open={llmSettingsOpen} onClose={onCloseLLMSettings} onSave={onSaveLLMSettings} />
      </div>
    </div>
  );
}

export default Shell;
