import { useLyricStore } from "../store";
import { useWebSocket } from "../hooks/useWebSocket";

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

export function Settings(): JSX.Element {
  const {
    targetLang,
    setTargetLang,
    translationProvider,
    setTranslationProvider,
    showTranslation,
    toggleTranslation,
    toggleSettings,
  } = useLyricStore();
  const { send } = useWebSocket();

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

      <label className="settings-label">
        <input
          type="checkbox"
          checked={showTranslation}
          onChange={toggleTranslation}
        />
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
            <option key={l.code} value={l.code}>
              {l.label}
            </option>
          ))}
        </select>
      </div>

      <div className="settings-field">
        <label className="settings-label">Translation provider</label>
        <select
          value={translationProvider}
          onChange={(e) =>
            handleProviderChange(e.target.value as "google" | "libre" | "deepl")
          }
          className="settings-select"
        >
          <option value="google">Google Translate</option>
          <option value="libre">LibreTranslate</option>
          <option value="deepl">DeepL</option>
        </select>
      </div>
    </div>
  );
}
