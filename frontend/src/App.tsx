import { useCallback, useEffect, useMemo, useState } from "react";
import { api, AgentPhase, AccidentFields, EvidenceItem, HealthStatus, LLMConfig, LLMConfigPayload, SessionSummary, SolveResponse, WikiPage } from "./api";
import Shell from "./components/Shell";

const sampleWikiPages: WikiPage[] = [
  { path: "wiki/standards/打捞工具目录.md", title: "打捞工具目录", category: "standards", source_pdf: "SY 5069-2017" },
  { path: "wiki/standards/解卡操作规程.md", title: "解卡操作规程", category: "standards", source_pdf: "SY_T 5587.12-2018" },
  { path: "wiki/standards/水平井特殊工艺.md", title: "水平井特殊工艺", category: "standards", source_pdf: "SYT 6987-2024" },
  { path: "wiki/cases/案例03_直井钻杆断落.md", title: "案例03_直井钻杆断落", category: "cases", source_pdf: "钻具断落事故.pdf" },
  { path: "wiki/cases/案例07_套铣后打捞.md", title: "案例07_套铣后打捞", category: "cases", source_pdf: "钻具断落事故.pdf" },
  { path: "wiki/synthesis/工具选型决策树.md", title: "工具选型决策树", category: "synthesis" },
  { path: "wiki/synthesis/风险评估矩阵.md", title: "风险评估矩阵", category: "synthesis" },
  { path: "wiki/synthesis/常见失败原因.md", title: "常见失败原因", category: "synthesis" },
  { path: "wiki/generated_plans/处置方案_20250312.md", title: "处置方案_20250312", category: "generated_plans" },
];

const sampleAccident: AccidentFields = {
  well_type: "直井",
  depth: "3240 m",
  fish_type: "5寸钻杆",
  fish_description: "约180m",
  fish_top_depth: "3060 m",
  mud_density: "1.35 g/cm3",
  connection_type: undefined,
  inclination: undefined,
  missing_fields: ["地层岩性", "井斜角", "钻具扣型"],
};

const sampleEvidence: EvidenceItem[] = [
  {
    source_type: "standard",
    source_page: "wiki/standards/解卡操作规程.md",
    source_pdf: "SY_T 5587.12-2018",
    page_no: 12,
    clause: "4.2",
    summary: "循环洗井与返砂观察要求",
  },
  {
    source_type: "standard",
    source_page: "wiki/standards/解卡操作规程.md",
    source_pdf: "SY_T 5587.12-2018",
    page_no: 15,
    clause: "5.1",
    summary: "解卡剂浸泡与活动钻具要求",
  },
  {
    source_type: "case",
    source_page: "wiki/cases/案例03_直井钻杆断落.md",
    source_pdf: "钻具断落事故.pdf",
    page_no: 8,
    summary: "深度相近的直井钻杆断落打捞路径",
  },
  {
    source_type: "inference",
    source_page: "engineering-inference",
    summary: "扣型未知时，打捞工具规格需现场复核后确认",
  },
];

const samplePlan = `## 推荐策略
采用由轻到重的阶梯式保守打捞。先稳定井况、循环洗井并确认鱼顶状态，再依据扣型和落鱼内外径选择捞矛或公锥。

## 关键判断
- 若循环后返砂明显减少且鱼顶清楚，可进入打捞工具下入阶段。
- 若鱼顶覆盖或井底沉砂明显，应继续冲洗或考虑套铣前处理。
- 上提力、扭矩、震击参数不得照搬案例，需结合钻具强度、井况和现场设计确认。`;

const samplePhases: AgentPhase[] = [
  {
    id: "parse",
    tag: "parse",
    title: "事故信息提取",
    status: "done",
    summary: "井型：直井 · 深度：3240m · 落鱼：5寸钻杆约180m · 鱼顶：3060m · 井液密度：1.35 g/cm3。缺失：地层岩性、井斜角、钻具扣型。",
    details: "原始描述已被结构化为井型、鱼顶、落鱼类型、井液密度等字段；当前仍缺少地层岩性、井斜角、钻具扣型，影响工具选型与参数确认。",
  },
  {
    id: "match",
    tag: "match",
    title: "历史案例参考",
    status: "done",
    summary: "找到 2 个相似案例：案例03 为深度相近的直井钻杆断落，案例07 强调套铣前应先循环洗井并确认鱼顶状态。",
    details: "相似案例通常优先参考井型、落鱼类型、深度和是否伴随砂埋/卡阻。本次案例匹配偏向直井钻杆断落路径，提示先循环清洁再决定是否下捞矛或公锥。",
    citations: [
      { label: "案例03", page: "wiki/cases/案例03_直井钻杆断落.md" },
      { label: "案例07", page: "wiki/cases/案例07_套铣后打捞.md" },
    ],
  },
  {
    id: "aggressive",
    tag: "aggressive",
    title: "激进方案",
    status: "done",
    summary: "先复核井筒稳定和循环通道，再恢复循环、洗井或冲砂，之后依据扣型和鱼顶形态快速切换捞矛、公锥或震击路径。",
    details: "激进路径强调尽快恢复作业窗口，但所有扭矩、拉力、震击参数都必须现场设计确认。若出现井控风险、循环失效或工具通过性不足，应立即切回保守路径。",
    citations: [{ label: "打捞工具目录", page: "wiki/standards/打捞工具目录.md" }],
  },
  {
    id: "conservative",
    tag: "conservative",
    title: "保守方案",
    status: "done",
    summary: "推荐阶梯式保守打捞：先循环洗井并复核返砂，再评估解卡剂浸泡和活动钻具，确认鱼顶后下入捞矛或公锥。上提力、扭矩等参数需结合钻具强度和现场设计确认。",
    details: "保守路径优先级为井控安全、井筒完整和防止事故扩大。建议按井况复核、循环清洁、低扰动解卡、震击、打捞、套铣/磨铣逐级推进，直到满足升级或终止条件。",
    citations: [{ label: "解卡操作规程 §4.2", page: "wiki/standards/解卡操作规程.md" }],
  },
  {
    id: "check",
    tag: "check",
    title: "合规审核",
    status: "warning",
    summary: "工具选型可按 SY 5069-2017 范围复核；当前缺少扣型、井斜角和地层岩性，不能直接给出精确打捞参数。",
    details: "合规审核重点核验工具选型、作业程序和水平井特殊要求。当前方案中缺失的扣型和井斜角，意味着部分工具组合和参数只能作为待确认项，不能写成确定值。",
    citations: [{ label: "打捞工具目录", page: "wiki/standards/打捞工具目录.md" }],
  },
  {
    id: "final",
    tag: "final",
    title: "最终决策",
    status: "done",
    summary: "最终采用保守为主、激进为辅的阶梯式方案：先循环洗井和确认鱼顶，再决定捞矛、公锥、震击或套铣路径。",
    details: samplePlan,
  },
];

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: string;
};

function App() {
  const [health, setHealth] = useState<HealthStatus>({ wiki_ok: true, standards_count: 3, cases_count: 15 });
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | undefined>();
  const [llmConfig, setLLMConfig] = useState<LLMConfig | null>(null);
  const [llmSettingsOpen, setLLMSettingsOpen] = useState(false);
  const [wikiPages, setWikiPages] = useState<WikiPage[]>(sampleWikiPages);
  const [activeWikiPage, setActiveWikiPage] = useState<WikiPage | null>(null);
  const [view, setView] = useState<"chat" | "wiki">("chat");
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "m1",
      role: "user",
      content: "某井钻进至3240m时，钻具发生断落，落鱼为5寸钻杆约180m，鱼顶深度3060m，目前井液密度1.35g/cm3，已尝试上提未能活动，请给出处置方案。",
      createdAt: "2025-03-12 14:32",
    },
  ]);
  const [phases, setPhases] = useState<AgentPhase[]>(samplePhases);
  const [accident, setAccident] = useState<AccidentFields>(sampleAccident);
  const [evidence, setEvidence] = useState<EvidenceItem[]>(sampleEvidence);
  const [confidence, setConfidence] = useState(0.78);
  const [finalPlan, setFinalPlan] = useState(samplePlan);
  const [isSolving, setIsSolving] = useState(false);

  useEffect(() => {
    api.health().then(setHealth).catch(() => undefined);
    api.llmConfig().then(setLLMConfig).catch(() => undefined);
    api.sessions().then((items) => {
      setSessions(items);
      setActiveSessionId((current) => current ?? items[0]?.id);
    }).catch(() => undefined);
    api.wikiPages().then((pages) => pages.length && setWikiPages(pages)).catch(() => undefined);
  }, []);

  const resetWorkspaceForSession = useCallback((sessionId?: string) => {
    setActiveSessionId(sessionId);
    setActiveWikiPage(null);
    setView("chat");
    setMessages([]);
    setPhases([]);
    setAccident({});
    setEvidence([]);
    setConfidence(0);
    setFinalPlan("");
  }, []);

  const handleNewSession = useCallback(async () => {
    const fallbackSession: SessionSummary = {
      id: `local-${Date.now()}`,
      title: `新建事故会话 ${new Date().toLocaleTimeString("zh-CN", { hour12: false })}`,
      created_at: new Date().toISOString(),
    };

    try {
      const session = await api.createSession({ title: fallbackSession.title });
      setSessions((items) => [session, ...items.filter((item) => item.id !== session.id)]);
      resetWorkspaceForSession(session.id);
    } catch {
      setSessions((items) => [fallbackSession, ...items]);
      resetWorkspaceForSession(fallbackSession.id);
    }
  }, [resetWorkspaceForSession]);

  const handleSelectSession = useCallback((session: SessionSummary) => {
    resetWorkspaceForSession(session.id);
  }, [resetWorkspaceForSession]);

  const handleSaveLLMSettings = useCallback(async (payload: LLMConfigPayload) => {
    const saved = await api.saveLLMConfig(payload);
    setLLMConfig(saved);
  }, []);

  const openWikiPage = useCallback(async (pageOrPath: WikiPage | string) => {
    const fallback = typeof pageOrPath === "string" ? wikiPages.find((page) => page.path === pageOrPath) : pageOrPath;
    const path = typeof pageOrPath === "string" ? pageOrPath : pageOrPath.path;
    setActiveWikiPage(
      fallback ?? {
        path,
        title: path.split("/").pop()?.replace(".md", "") ?? "Wiki 页面",
        content: "",
      },
    );
    setView("wiki");
    try {
      const page = await api.wikiPage(path);
      setActiveWikiPage(page);
    } catch {
      setActiveWikiPage((current) => ({
        ...(current ?? fallback),
        path,
        title: (current ?? fallback)?.title ?? "Wiki 页面",
        source_pdf: (current ?? fallback)?.source_pdf,
        content:
          (current ?? fallback)?.content ??
          "## 页面预览\n\n后端 Wiki 服务暂未返回正文。当前视图已按接口边界保留，服务可用后会显示 Markdown 内容。",
      }));
    }
  }, [wikiPages]);

  useEffect(() => {
    const openHashWikiPage = () => {
      const hash = window.location.hash;
      if (!hash.startsWith("#wiki/")) return;
      const target = decodeURIComponent(hash.slice("#wiki/".length)).replace(/^wiki\//, "");
      void openWikiPage(resolveWikiPageTarget(target, wikiPages));
      window.history.replaceState(null, "", window.location.pathname + window.location.search);
    };

    const openClickedWikiPage = (event: MouseEvent) => {
      const link = (event.target as Element | null)?.closest?.('a[href^="#wiki/"]') as HTMLAnchorElement | null;
      if (!link) return;
      event.preventDefault();
      const target = decodeURIComponent(link.getAttribute("href")?.slice("#wiki/".length) ?? "").replace(/^wiki\//, "");
      void openWikiPage(resolveWikiPageTarget(target, wikiPages));
    };

    window.addEventListener("hashchange", openHashWikiPage);
    document.addEventListener("click", openClickedWikiPage);
    openHashWikiPage();
    return () => {
      window.removeEventListener("hashchange", openHashWikiPage);
      document.removeEventListener("click", openClickedWikiPage);
    };
  }, [openWikiPage, wikiPages]);

  const handleSubmit = async (description: string) => {
    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: description,
      createdAt: new Date().toLocaleString("zh-CN", { hour12: false }),
    };
    setMessages((items) => [...items, userMessage]);
    setIsSolving(true);

    try {
      let sessionId = activeSessionId;
      if (!sessionId) {
        const title = description.slice(0, 18) || "事故会话";
        const session = await api.createSession({ title, description });
        sessionId = session.id;
        setSessions((items) => [session, ...items.filter((item) => item.id !== session.id)]);
        setActiveSessionId(session.id);
      }
      const result: SolveResponse = await api.solve(description, sessionId);
      setAccident(result.accident ?? sampleAccident);
      setEvidence(result.evidence?.length ? result.evidence : sampleEvidence);
      setPhases(buildPhasesFromResult(result));
      setConfidence(result.confidence_score ?? 0.72);
      setFinalPlan(result.final_plan ?? samplePlan);
      setMessages((items) => [
        ...items,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: "已完成处置方案生成，详见下方 Agent 阶段卡片与最终方案 Markdown。",
          createdAt: new Date().toLocaleString("zh-CN", { hour12: false }),
        },
      ]);
    } catch {
      setPhases(samplePhases);
      setMessages((items) => [
        ...items,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: "后端服务暂不可用，当前显示本地演示流程。接口边界已保留，可直接接入 /api/solve。",
          createdAt: new Date().toLocaleString("zh-CN", { hour12: false }),
        },
      ]);
    } finally {
      setIsSolving(false);
    }
  };

  const statusLabel = useMemo(() => {
    const cases = health.cases_count ?? 15;
    const standards = health.standards_count ?? 3;
    return health.wiki_ok === false ? "Wiki 待检查" : `Wiki 健康 · ${cases} 案例 · ${standards} 行标`;
  }, [health]);

  return (
    <Shell
      activeSessionId={activeSessionId}
      accident={accident}
      activeWikiPage={activeWikiPage}
      confidence={confidence}
      evidence={evidence}
      finalPlan={finalPlan}
      isSolving={isSolving}
      llmConfig={llmConfig}
      llmSettingsOpen={llmSettingsOpen}
      messages={messages}
      onBackToChat={() => setView("chat")}
      onCloseLLMSettings={() => setLLMSettingsOpen(false)}
      onNewSession={handleNewSession}
      onOpenLLMSettings={() => setLLMSettingsOpen(true)}
      onOpenWiki={openWikiPage}
      onSaveLLMSettings={handleSaveLLMSettings}
      onSelectSession={handleSelectSession}
      onSubmit={handleSubmit}
      phases={phases}
      sessions={sessions}
      statusLabel={statusLabel}
      view={view}
      wikiPages={wikiPages}
    />
  );
}

function buildPhasesFromResult(result: SolveResponse): AgentPhase[] {
  return [
    {
      id: "parse",
      tag: "parse",
      title: "事故信息提取",
      status: "done",
      summary: result.parse_report ?? "已完成事故信息结构化。",
      details: result.parse_report ?? "已完成事故信息结构化。",
    },
    {
      id: "match",
      tag: "match",
      title: "历史案例参考",
      status: "done",
      summary: result.similar_cases?.split("\n").slice(0, 2).join(" ") || "已完成案例匹配。",
      details: result.similar_cases ?? "",
    },
    {
      id: "aggressive",
      tag: "aggressive",
      title: "激进方案",
      status: "done",
      summary: firstSentence(result.aggressive_plan) || "已形成激进方案。",
      details: result.aggressive_plan ?? "",
    },
    {
      id: "conservative",
      tag: "conservative",
      title: "保守方案",
      status: "done",
      summary: firstSentence(result.conservative_plan) || "已形成保守方案。",
      details: result.conservative_plan ?? "",
    },
    {
      id: "check",
      tag: "check",
      title: "合规审核",
      status: result.confidence_score && result.confidence_score < 0.6 ? "warning" : "done",
      summary: firstSentence(result.compliance_report) || "已完成合规审核。",
      details: result.compliance_report ?? "",
    },
    {
      id: "final",
      tag: "final",
      title: "最终决策",
      status: "done",
      summary: firstSentence(result.final_plan) || "已生成最终决策。",
      details: result.final_plan ?? "",
    },
  ];
}

function firstSentence(text?: string | null) {
  if (!text) return "";
  const cleaned = text.replace(/^#+\s*/gm, "").trim();
  const match = cleaned.match(/[^。！？!?]+[。！？!?]?/);
  return match?.[0].trim() ?? cleaned.slice(0, 80);
}

function resolveWikiPageTarget(target: string, pages: WikiPage[]) {
  const normalized = target.replace(/^wiki\//, "");
  return (
    pages.find((item) => item.path.replace(/^wiki\//, "") === normalized) ??
    pages.find((item) => item.title === normalized || item.path.split("/").pop()?.replace(/\.md$/, "") === normalized) ??
    normalized
  );
}

export default App;
