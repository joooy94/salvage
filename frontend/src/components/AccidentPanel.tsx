import { AccidentFields } from "../api";

type AccidentPanelProps = {
  accident: AccidentFields;
};

const rows: Array<[string, keyof AccidentFields]> = [
  ["井型", "well_type"],
  ["落鱼类型", "fish_type"],
  ["落鱼描述", "fish_description"],
  ["鱼顶深度", "fish_top_depth"],
  ["井液密度", "mud_density"],
  ["扣型", "connection_type"],
  ["井斜角", "inclination"],
];

function AccidentPanel({ accident }: AccidentPanelProps) {
  return (
    <div className="ev-card">
      {rows.map(([label, key]) => {
        const value = accident[key];
        return (
          <div className="ev-field-row" key={key}>
            <span className="ev-field-label">{label}</span>
            {value ? <span className="ev-field-value">{String(value)}</span> : <span className="ev-field-missing">未提供</span>}
          </div>
        );
      })}
    </div>
  );
}

export default AccidentPanel;
