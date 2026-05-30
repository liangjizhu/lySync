import { useLyricStore, VerticalPosition } from "../store";

const OFFSET_STEP_MS = 500;

const LANGUAGES = [
  { code: "en", label: "English" },
  { code: "es", label: "Spanish" },
  { code: "fr", label: "French" },
  { code: "de", label: "German" },
  { code: "pt", label: "Portuguese" },
  { code: "ja", label: "Japanese" },
  { code: "ko", label: "Korean" },
  { code: "zh", label: "Chinese" },
  { code: "ar", label: "Arabic" },
  { code: "ru", label: "Russian" },
  { code: "it", label: "Italian" },
];

const ACTIVE_COLORS = [
  { value: "#ffffff", label: "White" },
  { value: "#ffe066", label: "Yellow" },
  { value: "#66e0ff", label: "Cyan" },
  { value: "#ff8c66", label: "Coral" },
  { value: "#a3ff66", label: "Green" },
];

const TRANSLATION_COLORS = [
  { value: "#ffdc78", label: "Gold" },
  { value: "#aaaaaa", label: "Gray" },
  { value: "#66e0ff", label: "Cyan" },
  { value: "#ff8c66", label: "Coral" },
  { value: "#ffffff", label: "White" },
];

interface Props {
  send: (msg: object) => void;
}

export function Settings({ send }: Props): JSX.Element {
  const {
    targetLang,
    setTargetLang,
    translationProvider,
    setTranslationProvider,
    showTranslation,
    toggleTranslation,
    toggleSettings,
    fontSize,
    setFontSize,
    linesVisible,
    setLinesVisible,
    verticalPosition,
    setVerticalPosition,
    bgDim,
    toggleBgDim,
    activeColor,
    setActiveColor,
    translationColor,
    setTranslationColor,
    syncOffsetMs,
    setSyncOffset,
  } = useLyricStore();

  function handleOffsetChange(delta: number): void {
    const next = syncOffsetMs + delta;
    setSyncOffset(next);
    send({ type: "set_sync_offset", payload: { offset_ms: next } });
  }

  function handleOffsetReset(): void {
    setSyncOffset(0);
    send({ type: "set_sync_offset", payload: { offset_ms: 0 } });
  }

  function handleLangChange(lang: string): void {
    setTargetLang(lang);
    send({ type: "set_target_lang", payload: { lang } });
  }

  function handleProviderChange(provider: "google" | "libre" | "deepl"): void {
    setTranslationProvider(provider);
    send({ type: "set_translation_provider", payload: { provider } });
  }

  return (
    <div className="settings-panel">
      <button className="close-btn" onClick={toggleSettings}>✕</button>
      <h2 className="settings-title">lySync Settings</h2>

      {/* ── Translation ─────────────────────────────── */}
      <div className="settings-section">
        <div className="settings-section-title">Translation</div>

        <label className="settings-label">
          <input type="checkbox" checked={showTranslation} onChange={toggleTranslation} />
          Show translation
        </label>

        <div className="settings-field">
          <label className="settings-label">Target language</label>
          <select
            value={targetLang}
            onChange={(e) => handleLangChange(e.target.value)}
            className="settings-select"
          >
            {LANGUAGES.map((l) => (
              <option key={l.code} value={l.code}>{l.label}</option>
            ))}
          </select>
        </div>

        <div className="settings-field">
          <label className="settings-label">Provider</label>
          <select
            value={translationProvider}
            onChange={(e) => handleProviderChange(e.target.value as "google" | "libre" | "deepl")}
            className="settings-select"
          >
            <option value="google">Google Translate</option>
            <option value="libre">LibreTranslate</option>
            <option value="deepl">DeepL</option>
          </select>
        </div>
      </div>

      {/* ── Display ─────────────────────────────────── */}
      <div className="settings-section">
        <div className="settings-section-title">Display</div>

        <div className="settings-field">
          <label className="settings-label">
            Font size — {fontSize}px
          </label>
          <input
            type="range"
            min={14}
            max={40}
            value={fontSize}
            onChange={(e) => setFontSize(Number(e.target.value))}
            className="settings-slider"
          />
        </div>

        <div className="settings-field">
          <label className="settings-label">Lines visible</label>
          <select
            value={linesVisible}
            onChange={(e) => setLinesVisible(Number(e.target.value))}
            className="settings-select"
          >
            <option value={3}>3 lines</option>
            <option value={5}>5 lines</option>
            <option value={7}>7 lines</option>
            <option value={9}>9 lines</option>
          </select>
        </div>

        <div className="settings-field">
          <label className="settings-label">Position</label>
          <div className="settings-btn-group">
            {(["top", "center", "bottom"] as VerticalPosition[]).map((p) => (
              <button
                key={p}
                className={`settings-btn ${verticalPosition === p ? "active" : ""}`}
                onClick={() => setVerticalPosition(p)}
              >
                {p.charAt(0).toUpperCase() + p.slice(1)}
              </button>
            ))}
          </div>
        </div>

        <label className="settings-label">
          <input type="checkbox" checked={bgDim} onChange={toggleBgDim} />
          Background dim
        </label>

        <div className="settings-field">
          <label className="settings-label">
            Lyrics sync offset&nbsp;
            <span className="offset-value">
              {syncOffsetMs === 0
                ? "0s"
                : `${syncOffsetMs > 0 ? "+" : ""}${(syncOffsetMs / 1000).toFixed(1)}s`}
            </span>
          </label>
          <div className="offset-controls">
            <button className="offset-btn" onClick={() => handleOffsetChange(-OFFSET_STEP_MS * 2)} title="-1s">−1s</button>
            <button className="offset-btn" onClick={() => handleOffsetChange(-OFFSET_STEP_MS)} title="-0.5s">−½s</button>
            <button className="offset-btn reset" onClick={handleOffsetReset} title="Reset">0</button>
            <button className="offset-btn" onClick={() => handleOffsetChange(+OFFSET_STEP_MS)} title="+0.5s">+½s</button>
            <button className="offset-btn" onClick={() => handleOffsetChange(+OFFSET_STEP_MS * 2)} title="+1s">+1s</button>
          </div>
        </div>
      </div>

      {/* ── Colors ──────────────────────────────────── */}
      <div className="settings-section">
        <div className="settings-section-title">Colors</div>

        <div className="settings-field">
          <label className="settings-label">Lyrics color</label>
          <div className="color-swatches">
            {ACTIVE_COLORS.map((c) => (
              <button
                key={c.value}
                className={`color-swatch ${activeColor === c.value ? "selected" : ""}`}
                style={{ background: c.value }}
                title={c.label}
                onClick={() => setActiveColor(c.value)}
              />
            ))}
          </div>
        </div>

        <div className="settings-field">
          <label className="settings-label">Translation color</label>
          <div className="color-swatches">
            {TRANSLATION_COLORS.map((c) => (
              <button
                key={c.value}
                className={`color-swatch ${translationColor === c.value ? "selected" : ""}`}
                style={{ background: c.value }}
                title={c.label}
                onClick={() => setTranslationColor(c.value)}
              />
            ))}
          </div>
        </div>
      </div>

      <button className="settings-quit-btn" onClick={() => window.electronAPI?.quit()}>
        Quit lySync
      </button>
    </div>
  );
}
