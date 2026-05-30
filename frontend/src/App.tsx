import { useEffect } from "react";
import { LyricsOverlay } from "./components/LyricsOverlay";
import { Settings } from "./components/Settings";
import { useLyricStore } from "./store";
import { useWebSocket } from "./hooks/useWebSocket";

declare global {
  interface Window {
    electronAPI?: {
      setIgnoreMouse: (ignore: boolean) => void;
      quit: () => void;
    };
  }
}

export default function App(): JSX.Element {
  const { showSettings, toggleSettings } = useLyricStore();
  useWebSocket(); // initializes connection

  // Toggle click-through on hover
  function handleMouseEnter(): void {
    window.electronAPI?.setIgnoreMouse(false);
  }

  function handleMouseLeave(): void {
    if (!showSettings) window.electronAPI?.setIgnoreMouse(true);
  }

  useEffect(() => {
    if (!showSettings) {
      window.electronAPI?.setIgnoreMouse(true);
    }
  }, [showSettings]);

  return (
    <div
      className="app-root"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      {showSettings ? (
        <Settings />
      ) : (
        <>
          <LyricsOverlay />
          <button
            className="settings-trigger"
            onClick={toggleSettings}
            title="Settings"
          >
            ⚙
          </button>
        </>
      )}
    </div>
  );
}
