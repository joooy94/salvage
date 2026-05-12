import { Send } from "lucide-react";
import { FormEvent, useState } from "react";

type ComposerProps = {
  disabled: boolean;
  onSubmit: (description: string) => void;
};

function Composer({ disabled, onSubmit }: ComposerProps) {
  const [value, setValue] = useState("");

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    const text = value.trim();
    if (!text || disabled) return;
    onSubmit(text);
    setValue("");
  };

  return (
    <form className="composer" onSubmit={handleSubmit}>
      <div className="composer-box">
        <textarea
          className="composer-textarea"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          placeholder="补充现场信息，或询问处置细节..."
          rows={2}
        />
        <div className="composer-footer">
          <span className="composer-hints">可补充：地层岩性 · 钻具扣型 · 井斜角</span>
          <button className="composer-send" type="submit" disabled={disabled || !value.trim()}>
            <Send size={13} aria-hidden="true" />
            {disabled ? "分析中" : "发送"}
          </button>
        </div>
      </div>
    </form>
  );
}

export default Composer;
