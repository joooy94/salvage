import ReactMarkdown from "react-markdown";
import { WikiPage } from "../api";

type MarkdownViewProps = {
  className?: string;
  content: string;
  onOpenWiki: (pageOrPath: WikiPage | string) => void;
  wikiPages: WikiPage[];
};

function MarkdownView({ className, content, onOpenWiki, wikiPages }: MarkdownViewProps) {
  const linkedContent = linkifyWikiRefs(content);

  return (
    <div className={className}>
      <ReactMarkdown
        components={{
          a: ({ href, children }) => {
            if (href?.startsWith("#wiki/")) {
              return (
                <a className="markdown-wiki-link" href={href}>
                  {children}
                </a>
              );
            }
            if (href && isWikiPath(href)) {
              const target = resolveWikiTarget(href, wikiPages);
              const targetPath = typeof target === "string" ? target : target.path;
              return (
                <a className="markdown-wiki-link" href={`#wiki/${encodeURIComponent(targetPath)}`}>
                  {children}
                </a>
              );
            }
            return (
              <a href={href} target="_blank" rel="noreferrer">
                {children}
              </a>
            );
          },
        }}
      >
        {linkedContent}
      </ReactMarkdown>
    </div>
  );
}

function linkifyWikiRefs(markdown: string) {
  return markdown.replace(/\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|([^\]]+))?\]\]/g, (_match, target: string, label?: string) => {
    const cleanTarget = target.trim();
    const cleanLabel = (label || cleanTarget).trim();
    return `[${cleanLabel}](#wiki/${encodeURIComponent(cleanTarget)})`;
  });
}

function isWikiPath(href: string) {
  return href.endsWith(".md") && /^(wiki\/)?(standards|cases|synthesis|generated_plans|tools|procedures)\//.test(href);
}

function resolveWikiTarget(target: string, pages: WikiPage[]) {
  const normalized = target.replace(/^wiki\//, "");
  const byPath = pages.find((page) => page.path.replace(/^wiki\//, "") === normalized);
  if (byPath) return byPath;

  const byTitle = pages.find((page) => page.title === normalized || page.path.split("/").pop()?.replace(/\.md$/, "") === normalized);
  if (byTitle) return byTitle;

  const bySuffix = pages.find((page) => page.path.endsWith(`/${normalized}.md`) || page.path.endsWith(`/${normalized}`));
  return bySuffix ?? normalized;
}

export default MarkdownView;
