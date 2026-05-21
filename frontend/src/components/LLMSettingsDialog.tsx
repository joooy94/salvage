import { FormEvent, useEffect, useState } from "react";
import { LLMConfig, LLMConfigPayload } from "../api";

type LLMSettingsDialogProps = {
  config: LLMConfig | null;
  open: boolean;
  onClose: () => void;
  onSave: (payload: LLMConfigPayload) => Promise<void>;
};

const providerDefaults: Record<string, { model: string; base_url: string }> = {
  openai: { model: "gpt-4o-mini", base_url: "" },
  anthropic: { model: "claude-3-5-sonnet-latest", base_url: "" },
  zai: { model: "glm-5.1", base_url: "https://api.z.ai/api/paas/v4/" },
  custom: { model: "", base_url: "" },
};

function LLMSettingsDialog({ config, open, onClose, onSave }: LLMSettingsDialogProps) {
  const [provider, setProvider] = useState("openai");
  const [model, setModel] = useState(providerDefaults.openai.model);
  const [baseUrl, setBaseUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [enabled, setEnabled] = useState(true);
  const [clearKey, setClearKey] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    const nextProvider = config?.provider || "openai";
    setProvider(nextProvider);
    setModel(config?.model || providerDefaults[nextProvider]?.model || "");
    setBaseUrl(config?.base_url || providerDefaults[nextProvider]?.base_url || "");
    setEnabled(config?.enabled ?? true);
    setApiKey("");
    setClearKey(false);
  }, [config, open]);

  if (!open) return null;

  const handleProviderChange = (nextProvider: string) => {
    setProvider(nextProvider);
    if (!model || model === providerDefaults[provider]?.model) {
      setModel(providerDefaults[nextProvider]?.model || "");
    }
    if (!baseUrl || baseUrl === providerDefaults[provider]?.base_url) {
      setBaseUrl(providerDefaults[nextProvider]?.base_url || "");
    }
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setSaving(true);
    try {
      await onSave({
        provider,
        model,
        base_url: baseUrl,
        api_key: apiKey.trim() || undefined,
        enabled,
        clear_key: clearKey,
      });
      onClose();
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section className="llm-modal" role="dialog" aria-modal="true" aria-labelledby="llm-settings-title" onMouseDown={(event) => event.stopPropagation()}>
        <form onSubmit={handleSubmit}>
          <div className="modal-head">
            <div>
              <h2 id="llm-settings-title">LLM 设置</h2>
              <p>{config?.has_api_key ? `已保存：${config.masked_api_key}` : "尚未保存 API Key"}</p>
            </div>
            <button className="modal-close" type="button" onClick={onClose}>
              关闭
            </button>
          </div>

          <label className="form-field">
            <span>供应商</span>
            <select value={provider} onChange={(event) => handleProviderChange(event.target.value)}>
              <option value="openai">OpenAI</option>
              <option value="anthropic">Anthropic</option>
              <option value="zai">Z.ai</option>
              <option value="custom">OpenAI 兼容接口</option>
            </select>
          </label>

          <label className="form-field">
            <span>模型</span>
            <input value={model} onChange={(event) => setModel(event.target.value)} placeholder="例如 gpt-4o-mini / claude-3-5-sonnet-latest / glm-5.1" />
          </label>

          <label className="form-field">
            <span>Base URL</span>
            <input value={baseUrl} onChange={(event) => setBaseUrl(event.target.value)} placeholder="官方接口可留空，自定义接口填写完整地址" />
          </label>

          <label className="form-field">
            <span>API Key</span>
            <input value={apiKey} onChange={(event) => setApiKey(event.target.value)} placeholder={config?.has_api_key ? "留空则保留已保存 Key" : "输入 API Key"} type="password" />
          </label>

          <div className="form-inline">
            <label>
              <input checked={enabled} onChange={(event) => setEnabled(event.target.checked)} type="checkbox" />
              启用大模型
            </label>
            <label>
              <input checked={clearKey} onChange={(event) => setClearKey(event.target.checked)} type="checkbox" />
              清除已保存 Key
            </label>
          </div>

          <div className="modal-note">配置保存在本机后端的 outputs/llm_config.json，接口返回时只显示脱敏状态。</div>

          <div className="modal-actions">
            <button className="topbar-btn" type="button" onClick={onClose}>
              取消
            </button>
            <button className="composer-send" type="submit" disabled={saving}>
              {saving ? "保存中" : "保存设置"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

export default LLMSettingsDialog;
