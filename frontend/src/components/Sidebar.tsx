import { Archive, BookOpen, ChartNoAxesCombined, Database, FileText, Folder, Plus, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { SessionSummary, WikiPage } from "../api";

type SidebarProps = {
  activeSessionId?: string;
  onNewSession: () => void;
  wikiPages: WikiPage[];
  onOpenWiki: (page: WikiPage) => void;
  onSelectSession: (session: SessionSummary) => void;
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

function Sidebar({ activeSessionId, onNewSession, wikiPages, onOpenWiki, onSelectSession, sessions }: SidebarProps) {
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
          Wiki
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
              <button
                className={`sidebar-item ${item.id === activeSessionId || (!activeSessionId && index === 0) ? "active" : ""}`}
                type="button"
                key={item.id}
                onClick={() => onSelectSession(item)}
              >
                <FileText size={14} aria-hidden="true" />
                <span className="truncate">{item.title}</span>
                {item.id === activeSessionId ? <span className="item-badge">当前</span> : null}
              </button>
            ))}
          </div>
          <div className="sidebar-section">
            <div className="sidebar-section-title">已归档方案</div>
            {["处置方案_20250312", "处置方案_20250228"].map((item) => (
              <button className="sidebar-item" type="button" key={item}>
                <Archive size={14} aria-hidden="true" />
                <span className="truncate">{item}</span>
              </button>
            ))}
          </div>
        </div>
      ) : (
        <div className="sidebar-content">
          <label className="sidebar-search">
            <Search size={13} aria-hidden="true" />
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索 Wiki 页面..." />
          </label>

          {Object.entries(groupedPages).map(([category, pages]) => (
            <div className="wiki-group" key={category}>
              <div className="wiki-tree-item group">
                {iconForCategory(category)}
                {categoryLabels[category] ?? category}
                {category === "cases" ? <span className="tree-count">{pages.length}</span> : null}
              </div>
              {pages.map((page) => (
                <button className="wiki-tree-item child" key={page.path} onClick={() => onOpenWiki(page)} type="button">
                  <FileText size={12} aria-hidden="true" />
                  <span className="truncate">{page.title}</span>
                </button>
              ))}
            </div>
          ))}
        </div>
      )}
    </aside>
  );
}

export default Sidebar;
