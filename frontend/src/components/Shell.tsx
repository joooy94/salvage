import { AgentPhase, AccidentFields, DispositionGraph, EvidenceItem, LLMConfig, LLMConfigPayload, PlanVersion, SessionSummary, WikiPage } from "../api";
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
  dispositionGraph?: DispositionGraph | null;
  evidence: EvidenceItem[];
  finalPlan: string;
  planVersions: PlanVersion[];
  followUpMode: boolean;
  isSolving: boolean;
  pendingMode: "explain" | "solve" | null;
  llmConfig: LLMConfig | null;
  llmSettingsOpen: boolean;
  messages: ChatMessage[];
  onBackToChat: () => void;
  onNewSession: () => void;
  onCloseLLMSettings: () => void;
  onOpenWiki: (page: WikiPage | string) => void;
  onOpenLLMSettings: () => void;
  onSaveLLMSettings: (payload: LLMConfigPayload) => Promise<void>;
  onDeleteSession: (session: SessionSummary) => void;
  onDeleteGeneratedPlan: (page: WikiPage) => void;
  onSelectSession: (session: SessionSummary) => void;
  onSubmit: (description: string, mode: "explain" | "solve") => void;
  phases: AgentPhase[];
  sessions: SessionSummary[];
  archivedPlans: WikiPage[];
  activeSessionId?: string;
  statusLabel: string;
  view: "chat" | "wiki";
  wikiPages: WikiPage[];
};

function Shell({
  accident,
  activeWikiPage,
  confidence,
  dispositionGraph,
  evidence,
  finalPlan,
  planVersions,
  followUpMode,
  isSolving,
  pendingMode,
  llmConfig,
  llmSettingsOpen,
  messages,
  onBackToChat,
  onCloseLLMSettings,
  onNewSession,
  onOpenWiki,
  onOpenLLMSettings,
  onSaveLLMSettings,
  onDeleteSession,
  onDeleteGeneratedPlan,
  onSelectSession,
  onSubmit,
  phases,
  sessions,
  archivedPlans,
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
          archivedPlans={archivedPlans}
          sessions={sessions}
          wikiPages={wikiPages}
          onNewSession={onNewSession}
          onOpenWiki={onOpenWiki}
          onDeleteSession={onDeleteSession}
          onDeleteGeneratedPlan={onDeleteGeneratedPlan}
          onSelectSession={onSelectSession}
        />

        {view === "wiki" ? (
          <WikiPane page={activeWikiPage} onBack={onBackToChat} onOpenWiki={onOpenWiki} wikiPages={wikiPages} />
        ) : (
          <main className="main">
            <ChatThread
              messages={messages}
              phases={phases}
              dispositionGraph={dispositionGraph}
              onOpenWiki={onOpenWiki}
              finalPlan={finalPlan}
              planVersions={planVersions}
              pendingMode={pendingMode}
              wikiPages={wikiPages}
            />
            <Composer onSubmit={onSubmit} disabled={isSolving} followUpMode={followUpMode} />
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
