import { ArrowLeft } from "lucide-react";
import { WikiPage } from "../api";
import MarkdownView from "./MarkdownView";

type WikiPaneProps = {
  page: WikiPage | null;
  onBack: () => void;
  onOpenWiki: (pageOrPath: WikiPage | string) => void;
  wikiPages: WikiPage[];
};

function WikiPane({ page, onBack, onOpenWiki, wikiPages }: WikiPaneProps) {
  const title = page?.title ?? "知识库页面";
  const content = stripFrontMatter(
    page?.content ??
      "## 页面预览\n\n知识库服务暂未返回正文。点击左侧知识库页面或 Agent 引用后，会在此处显示对应内容。",
  );

  return (
    <main className="main wiki-pane visible">
      <div className="wiki-header">
        <button className="wiki-header-back" type="button" onClick={onBack} aria-label="返回聊天视图">
          <ArrowLeft size={18} aria-hidden="true" />
        </button>
        <span className="wiki-header-title">{title}</span>
      </div>
      <div className="wiki-body markdown-body">
        <div className="wiki-meta">
          <span>路径：{page?.path ?? "未选择"}</span>
          {page?.source_pdf ? <span>来源：{page.source_pdf}</span> : null}
          {page?.updated_at ? <span>更新：{page.updated_at}</span> : null}
        </div>
        <MarkdownView content={content} onOpenWiki={onOpenWiki} wikiPages={wikiPages} />
      </div>
    </main>
  );
}

function stripFrontMatter(markdown: string) {
  return markdown.replace(/^---\n[\s\S]*?\n---\n+/, "");
}

export default WikiPane;
