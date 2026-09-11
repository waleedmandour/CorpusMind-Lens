import { useEffect, useState } from "react";
import { useShell } from "../shell";
import { api } from "../lib/api";

export function SettingsView() {
  const { t, theme, setTheme } = useShell();
  const [settings, setSettings] = useState<any>(null);
  const [ethics, setEthics] = useState<any>(null);
  const [providers, setProviders] = useState<any>(null);
  const [companion, setCompanion] = useState<any>(null);

  useEffect(() => {
    api.settings().then(setSettings).catch(() => undefined);
    api.ethics().then(setEthics).catch(() => undefined);
    api.providersStatus().then(setProviders).catch(() => undefined);
    api.companionStatus().then(setCompanion).catch(() => undefined);
  }, []);

  return (
    <div>
      <h2>{t.nav.settings}</h2>

      <div className="card">
        <h3>{t.settings.aiProviders}</h3>
        {providers && (
          <dl className="kv">
            <dt>Ollama</dt>
            <dd>
              <span className={`chip ${providers.ollama.reachable ? "grounded" : ""}`}>
                {providers.ollama.reachable ? "reachable" : "not found"}
              </span>
              <span className="evidence">{providers.ollama.models.slice(0, 5).join(", ")}</span>
            </dd>
            <dt>LM Studio</dt>
            <dd>
              <span className={`chip ${providers.lmstudio.reachable ? "grounded" : ""}`}>
                {providers.lmstudio.reachable ? "reachable" : "not found"}
              </span>
            </dd>
            <dt>{t.settings.cloud}</dt>
            <dd>
              <span className={`chip ${settings?.cloud_enabled ? "ungrounded" : ""}`}>
                {settings?.cloud_enabled ? "enabled" : "off by default"}
              </span>
              <span className="muted" style={{ fontSize: 12 }}> — {t.settings.cloudNote}</span>
            </dd>
          </dl>
        )}
      </div>

      <div className="card">
        <h3>{t.settings.ethics}</h3>
        <dl className="kv">
          <dt>{t.settings.facial}</dt>
          <dd>
            <span className={`chip ${settings?.facial_analysis ? "ungrounded" : "grounded"}`}>
              {settings?.facial_analysis ? "opted in" : "off (default)"}
            </span>
            <p className="muted" style={{ fontSize: 12 }}>{settings?.facial_analysis_notice || t.settings.facialNote}</p>
          </dd>
          <dt>GPS</dt>
          <dd>{ethics?.gps_extraction?.reason}</dd>
          <dt>Identity recognition</dt>
          <dd>{ethics?.identity_recognition?.reason}</dd>
        </dl>
      </div>

      <div className="card">
        <h3>{t.settings.companion}</h3>
        <p className="muted" style={{ fontSize: 12 }}>{t.settings.companionNote}</p>
        <dl className="kv">
          <dt>Status</dt>
          <dd>
            <span className={`chip ${companion?.enabled ? "grounded" : ""}`}>
              {companion?.enabled ? (companion.reachable ? "reachable" : "enabled, unreachable") : "off"}
            </span>
            {companion?.base_url && <span className="evidence"> {companion.base_url}</span>}
          </dd>
        </dl>
      </div>

      <div className="card">
        <h3>{t.settings.appearance}</h3>
        <div className="row">
          <span>{t.settings.theme}:</span>
          <button className="btn secondary" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}>
            {theme === "dark" ? "☀ light" : "☾ dark"}
          </button>
          <span className="chip">{t.settings.language}: EN / العربية (RTL mirror)</span>
        </div>
      </div>

      {settings && (
        <div className="card">
          <h3>{t.common.engine}</h3>
          <dl className="kv">
            <dt>{t.common.version}</dt>
            <dd>{settings.version}</dd>
            <dt>Encryption</dt>
            <dd>{settings.encryption ? `on (${settings.encryption_fingerprint})` : "off"}</dd>
            <dt>Upload caps</dt>
            <dd>{settings.max_file_mb} MB/file · {settings.max_batch_images}/batch</dd>
          </dl>
        </div>
      )}
    </div>
  );
}
