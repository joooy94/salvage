import { Send } from "lucide-react";
import { FormEvent, useState } from "react";

type ComposerProps = {
  disabled: boolean;
  followUpMode: boolean;
  onSubmit: (description: string, mode: "explain" | "solve") => void;
};

function Composer({ disabled, followUpMode, onSubmit }: ComposerProps) {
  const [value, setValue] = useState("");

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const text = value.trim();
    if (!text || disabled) return;
    const submitter = (event.nativeEvent as SubmitEvent).submitter as HTMLButtonElement | null;
    const mode = submitter?.value === "explain" ? "explain" : "solve";
    onSubmit(text, mode);
    setValue("");
  };

  return (
    <form className="composer" onSubmit={handleSubmit}>
      <div className="composer-box">
        <textarea
          className="composer-textarea"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          placeholder={followUpMode ? "输入追问，或补充现场信息后重新评估..." : "输入事故描述..."}
          rows={2}
        />
        <div className="composer-footer">
          <span className="composer-hints">
            {followUpMode ? "解释不会生成新方案；重新评估会触发主流程辩论并生成新版本" : "首次会话将生成处置方案并展示主流程辩论"}
          </span>
          <div className="composer-actions">
            {followUpMode ? (
              <button className="composer-secondary" type="submit" value="explain" disabled={disabled || !value.trim()}>
                解释当前方案
              </button>
            ) : null}
            <button className="composer-send" type="submit" value="solve" disabled={disabled || !value.trim()}>
              <Send size={13} aria-hidden="true" />
              {disabled ? (followUpMode ? "处理中" : "分析中") : followUpMode ? "重新评估方案" : "生成处置方案"}
            </button>
          </div>
        </div>
      </div>
    </form>
  );
}

export default Composer;
