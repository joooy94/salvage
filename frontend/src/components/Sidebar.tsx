import { Archive, BookOpen, ChartNoAxesCombined, Database, FileText, Folder, Plus, Search, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { SessionSummary, WikiPage } from "../api";

type SidebarProps = {
  activeSessionId?: string;
  onNewSession: () => void;
  wikiPages: WikiPage[];
  onOpenWiki: (page: WikiPage) => void;
  onDeleteSession: (session: SessionSummary) => void;
  onDeleteGeneratedPlan: (page: WikiPage) => void;
  onSelectSession: (session: SessionSummary) => void;
  archivedPlans: WikiPage[];
  sessions: SessionSummary[];
};

const categoryLabels: Record<string, string> = {
  standards: "行业标准",
  cases: "案例库",
  tools: "工具",
  procedures: "工艺流程",
  synthesis: "综合分析",
  generated_plans: "生成方案",
};

function iconForCategory(category: string) {
  if (category === "standards") return <BookOpen size={13} aria-hidden="true" />;
  if (category === "cases") return <Database size={13} aria-hidden="true" />;
  if (category === "synthesis") return <ChartNoAxesCombined size={13} aria-hidden="true" />;
  return <Folder size={13} aria-hidden="true" />;
}

function Sidebar({ activeSessionId, archivedPlans, onNewSession, wikiPages, onOpenWiki, onDeleteSession, onDeleteGeneratedPlan, onSelectSession, sessions }: SidebarProps) {
  const [tab, setTab] = useState<"session" | "wiki">("session");
  const [query, setQuery] = useState("");

  const groupedPages = useMemo(() => {
    const pages = wikiPages.filter((page) => page.title.toLowerCase().includes(query.trim().toLowerCase()));
    return pages.reduce<Record<string, WikiPage[]>>((groups, page) => {
      const key = page.category ?? "synthesis";
      groups[key] = [...(groups[key] ?? []), page];
      return groups;
    }, {});
  }, [query, wikiPages]);

  return (
    <aside className="sidebar">
      <div className="tab-bar" role="tablist" aria-label="左侧导航">
        <button className={`tab ${tab === "session" ? "active" : ""}`} onClick={() => setTab("session")} type="button">
          会话
        </button>
        <button className={`tab ${tab === "wiki" ? "active" : ""}`} onClick={() => setTab("wiki")} type="button">
          知识库
        </button>
      </div>

      {tab === "session" ? (
        <div className="sidebar-content">
          <button className="sidebar-new-btn" type="button" onClick={onNewSession}>
            <Plus size={14} aria-hidden="true" />
            新建事故分析
          </button>
          <div className="sidebar-section">
            <div className="sidebar-section-title">最近会话</div>
            {(sessions.length ? sessions : [{ id: "demo", title: "示例事故会话", created_at: "" }]).map((item, index) => (
              <div
                className={`sidebar-session-row ${item.id === activeSessionId || (!activeSessionId && index === 0) ? "active" : ""}`}
                key={item.id}
              >
                <button className="sidebar-item session-main" type="button" onClick={() => onSelectSession(item)}>
                  <FileText size={14} aria-hidden="true" />
                  <span className="truncate">{item.title}</span>
                  {item.id === activeSessionId ? <span className="item-badge">当前</span> : null}
                </button>
                {sessions.length ? (
                  <button
                    className="session-delete"
                    type="button"
                    aria-label={`删除会话 ${item.title}`}
                    onClick={() => onDeleteSession(item)}
                  >
                    <Trash2 size={12} aria-hidden="true" />
                  </button>
                ) : null}
              </div>
            ))}
          </div>
          <div className="sidebar-section">
            <div className="sidebar-section-title">已归档方案</div>
            {archivedPlans.length ? (
              archivedPlans.map((page) => (
                <div className="wiki-generated-row" key={page.path}>
                  <button className="sidebar-item session-main" type="button" onClick={() => onOpenWiki(page)}>
                    <Archive size={14} aria-hidden="true" />
                    <span className="truncate">{page.title}</span>
                  </button>
                  <button className="session-delete" type="button" aria-label={`删除归档方案 ${page.title}`} onClick={() => onDeleteGeneratedPlan(page)}>
                    <Trash2 size={12} aria-hidden="true" />
                  </button>
                </div>
              ))
            ) : (
              <div className="sidebar-empty">暂无归档方案</div>
            )}
          </div>
        </div>
      ) : (
        <div className="sidebar-content">
          <label className="sidebar-search">
            <Search size={13} aria-hidden="true" />
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索知识库页面..." />
          </label>

          {Object.entries(groupedPages).map(([category, pages]) => (
            <div className="wiki-group" key={category}>
              <div className="wiki-tree-item group">
                {iconForCategory(category)}
                {categoryLabels[category] ?? category}
                {category === "cases" ? <span className="tree-count">{pages.length}</span> : null}
              </div>
              {pages.map((page) =>
                category === "generated_plans" ? (
                  <div className="wiki-generated-row" key={page.path}>
                    <button className="wiki-tree-item child generated-main" onClick={() => onOpenWiki(page)} type="button">
                      <FileText size={12} aria-hidden="true" />
                      <span className="truncate">{page.title}</span>
                    </button>
                    <button className="session-delete" type="button" aria-label={`删除生成方案 ${page.title}`} onClick={() => onDeleteGeneratedPlan(page)}>
                      <Trash2 size={12} aria-hidden="true" />
                    </button>
                  </div>
                ) : (
                  <button className="wiki-tree-item child" key={page.path} onClick={() => onOpenWiki(page)} type="button">
                    <FileText size={12} aria-hidden="true" />
                    <span className="truncate">{page.title}</span>
                  </button>
                ),
              )}
            </div>
          ))}
        </div>
      )}
    </aside>
  );
}

export default Sidebar;
