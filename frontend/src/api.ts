export type HealthStatus = {
  status?: string;
  wiki_ok?: boolean;
  standards_count?: number;
  cases_count?: number;
  message?: string;
};

export type WikiPage = {
  path: string;
  title: string;
  category?: "standards" | "cases" | "tools" | "procedures" | "synthesis" | "generated_plans";
  source_pdf?: string;
  updated_at?: string;
  content?: string;
};

export type DispositionGraphNode = {
  id: string;
  label: string;
  type: "accident" | "feature" | "risk" | "procedure" | "tool" | "standard" | "case" | "synthesis" | "evidence" | "decision";
  level?: number;
  summary?: string;
  source_page?: string;
};

export type DispositionGraphEdge = {
  source: string;
  target: string;
  label: string;
  type?: string;
};

export type DispositionGraph = {
  nodes: DispositionGraphNode[];
  edges: DispositionGraphEdge[];
};

export type SessionSummary = {
  id: string;
  title: string;
  description?: string;
  created_at?: string;
  updated_at?: string;
  accident?: AccidentFields;
  parse_report?: string;
  similar_cases?: string;
  aggressive_plan?: string;
  conservative_plan?: string;
  compliance_report?: string;
  final_plan?: string;
  confidence_score?: number;
  evidence?: EvidenceItem[];
  wiki_pages_used?: string[];
  output_path?: string;
  generated_plan_path?: string;
  current_plan_version?: number;
  plan_versions?: PlanVersion[];
  phases?: AgentPhase[];
  messages?: Array<{ role: "user" | "assistant"; content: string; created_at?: string }>;
  disposition_graph?: DispositionGraph;
};

export type PlanVersion = {
  version: number;
  title?: string;
  content: string;
  created_at?: string;
  output_path?: string;
  generated_plan_path?: string;
  confidence_score?: number;
  mode?: string;
};

export type LLMConfig = {
  provider: string;
  model?: string;
  base_url?: string;
  enabled?: boolean;
  has_api_key?: boolean;
  masked_api_key?: string;
  updated_at?: string;
};

export type LLMConfigPayload = {
  provider: string;
  model?: string;
  base_url?: string;
  api_key?: string;
  enabled?: boolean;
  clear_key?: boolean;
};

export type AccidentFields = {
  well_type?: string;
  depth?: string | number;
  fish_type?: string;
  fish_description?: string;
  fish_top_depth?: string | number;
  mud_density?: string;
  mud_type?: string;
  connection_type?: string;
  thread_type?: string;
  inclination?: string;
  missing_fields?: string[];
};

export type EvidenceItem = {
  source_type: "standard" | "case" | "synthesis" | "inference";
  source_page: string;
  source_pdf?: string;
  page_no?: number | null;
  clause?: string | null;
  quote?: string;
  summary: string;
};

export type AgentPhase = {
  id: string;
  tag: "parse" | "match" | "aggressive" | "conservative" | "plan" | "check" | "final";
  title: string;
  status: "pending" | "running" | "done" | "warning";
  summary: string;
  details?: string;
  citations?: Array<{ label: string; page: string }>;
};

export type SolveResponse = {
  accident?: AccidentFields;
  parse_report?: string;
  similar_cases?: string;
  aggressive_plan?: string;
  conservative_plan?: string;
  compliance_report?: string;
  final_plan?: string;
  confidence_score?: number;
  evidence?: EvidenceItem[];
  wiki_pages_used?: string[];
  output_path?: string;
  generated_plan_path?: string;
  plan_version?: number;
  phases?: AgentPhase[];
  disposition_graph?: DispositionGraph;
};

export type ChatResponse = {
  session_id: string;
  answer: string;
  mode: "explain" | "solve" | "finalize";
  intent?: string;
  route_reason?: string;
  plan_updated?: boolean;
  accident?: AccidentFields;
  parse_report?: string;
  similar_cases?: string;
  aggressive_plan?: string;
  conservative_plan?: string;
  compliance_report?: string;
  final_plan?: string;
  confidence_score?: number;
  evidence?: EvidenceItem[];
  wiki_pages_used?: string[];
  output_path?: string;
  generated_plan_path?: string;
  plan_version?: number;
  debate_rounds?: Array<{ agent: string; title?: string; content: string }>;
  phases?: AgentPhase[];
  updated_at?: string;
  disposition_graph?: DispositionGraph;
};

const jsonHeaders = { "Content-Type": "application/json" };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<HealthStatus>("/api/health"),
  llmConfig: () => request<LLMConfig>("/api/llm/config"),
  saveLLMConfig: (payload: LLMConfigPayload) =>
    request<LLMConfig>("/api/llm/config", {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify(payload),
    }),
  sessions: () => request<SessionSummary[]>("/api/sessions"),
  createSession: (payload: { title?: string; description?: string }) =>
    request<SessionSummary>("/api/sessions", {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify(payload),
    }),
  deleteSession: (sessionId: string) =>
    request<{ deleted: boolean; id: string }>(`/api/sessions/${encodeURIComponent(sessionId)}`, {
      method: "DELETE",
    }),
  dispositionGraph: (sessionId: string) => request<DispositionGraph>(`/api/sessions/${encodeURIComponent(sessionId)}/disposition-graph`),
  wikiPages: () => request<WikiPage[]>("/api/wiki/pages"),
  wikiPage: (path: string) => request<WikiPage>(`/api/wiki/pages/${encodeURIComponent(path)}`),
  deleteGeneratedPlan: (path: string) =>
    request<{ deleted: boolean; path: string }>(`/api/wiki/generated-plans/${encodeURIComponent(path)}`, {
      method: "DELETE",
    }),
  wikiSearch: (q: string) => request<WikiPage[]>(`/api/wiki/search?q=${encodeURIComponent(q)}`),
  solve: (description: string, sessionId?: string) =>
    request<SolveResponse>("/api/solve", {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify({ description, raw_description: description, session_id: sessionId }),
    }),
  chat: (question: string, sessionId: string, mode?: "explain" | "solve") =>
    request<ChatResponse>("/api/chat", {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify({ question, session_id: sessionId, mode }),
    }),
};
