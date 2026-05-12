import { ReactNode, useMemo, useState } from "react";
import { EvidenceItem } from "../api";

type EvidencePanelProps = {
  accident: ReactNode;
  confidence: number;
  evidence: EvidenceItem[];
  onOpenWiki: (path: string) => void;
};

const sourceLabels = {
  standard: "标准",
  case: "案例",
  synthesis: "综合",
  inference: "推断",
};

function EvidencePanel({ accident, confidence, evidence, onOpenWiki }: EvidencePanelProps) {
  const [filter, setFilter] = useState<EvidenceItem["source_type"] | "all">("standard");
  const filteredEvidence = useMemo(
    () => evidence.filter((item) => filter === "all" || item.source_type === filter),
    [evidence, filter],
  );
  const percent = Math.round(confidence * 100);

  return (
    <aside className="evidence">
      <div className="evidence-header">
        <span>分析依据</span>
        <span className="evidence-count">本次引用 {evidence.length} 页</span>
      </div>
      <div className="evidence-body">
        <section>
          <div className="ev-section-title">事故结构化</div>
          {accident}
        </section>

        <section>
          <div className="ev-section-title">方案置信度</div>
          <div className="ev-card">
            <div className="progress-bar-wrap">
              <div className="progress-label">
                <span>综合置信度</span>
                <span>{percent}%</span>
              </div>
              <div className="progress-track">
                <div className="progress-fill" style={{ width: `${percent}%` }} />
              </div>
            </div>
            <div className="ev-card-body">缺失现场字段会降低工具选型和参数建议的确定性。</div>
          </div>
        </section>

        <section>
          <div className="ev-section-title">引用来源</div>
          <div className="tabs-small">
            {(["standard", "case", "inference", "all"] as const).map((item) => (
              <button className={`tab-small ${filter === item ? "active" : ""}`} type="button" onClick={() => setFilter(item)} key={item}>
                {item === "all" ? "全部" : sourceLabels[item]}
              </button>
            ))}
          </div>
          <div className="evidence-list">
            {filteredEvidence.map((item, index) => (
              <button
                className="ev-card ev-card-button"
                type="button"
                onClick={() => item.source_type !== "inference" && onOpenWiki(item.source_page)}
                key={`${item.source_page}-${index}`}
              >
                <div className="ev-card-title">
                  {item.clause ? `${item.source_page.split("/").pop()?.replace(".md", "")} §${item.clause}` : item.source_page.split("/").pop()?.replace(".md", "")}
                </div>
                <div className="ev-card-meta">
                  {sourceLabels[item.source_type]} {item.source_pdf ? `· ${item.source_pdf}` : ""}
                  {item.page_no ? ` · 第${item.page_no}页` : ""}
                </div>
                <div className="ev-card-body">{item.summary}</div>
              </button>
            ))}
          </div>
        </section>

        <section>
          <div className="ev-section-title">风险提示</div>
          <div className="ev-card">
            <div className="risk-row">
              <span className="risk-dot risk-high" />
              <span>扣型未知，捞矛规格需现场确认</span>
            </div>
            <div className="risk-row">
              <span className="risk-dot risk-med" />
              <span>上提力参数不可盲目照搬历史案例</span>
            </div>
            <div className="risk-row">
              <span className="risk-dot risk-low" />
              <span>洗井排量充足可减少沉砂风险</span>
            </div>
          </div>
        </section>
      </div>
    </aside>
  );
}

export default EvidencePanel;
