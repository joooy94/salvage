import { AccidentFields } from "../api";

type AccidentPanelProps = {
  accident: AccidentFields;
};

const rows: Array<[string, keyof AccidentFields, keyof AccidentFields?]> = [
  ["井型", "well_type"],
  ["落鱼类型", "fish_type"],
  ["落鱼描述", "fish_description"],
  ["鱼顶深度", "fish_top_depth", "depth"],
  ["井液密度", "mud_density", "mud_type"],
  ["扣型", "connection_type", "thread_type"],
  ["井斜角", "inclination"],
];

function AccidentPanel({ accident }: AccidentPanelProps) {
  return (
    <div className="ev-card">
      {rows.map(([label, key, fallbackKey]) => {
        const value = accident[key] || (fallbackKey ? accident[fallbackKey] : "");
        return (
          <div className="ev-field-row" key={`${key}-${fallbackKey ?? ""}`}>
            <span className="ev-field-label">{label}</span>
            {value ? <span className="ev-field-value">{String(value)}</span> : <span className="ev-field-missing">未提供</span>}
          </div>
        );
      })}
    </div>
  );
}

export default AccidentPanel;
