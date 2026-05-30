import React, { useEffect } from "react";
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
  const {
    showSettings,
    toggleSettings,
    fontSize,
    activeColor,
    translationColor,
    verticalPosition,
    bgDim,
  } = useLyricStore();
  const { send } = useWebSocket();

  // Apply CSS variables to root
  useEffect(() => {
    const root = document.documentElement;
    root.style.setProperty("--lyrics-font-size", `${fontSize}px`);
    root.style.setProperty("--active-color", activeColor);
    root.style.setProperty("--translation-color", translationColor);
  }, [fontSize, activeColor, translationColor]);

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

  const positionStyle: React.CSSProperties =
    verticalPosition === "top"
      ? { alignItems: "flex-start", paddingTop: 12, paddingBottom: 0 }
      : verticalPosition === "center"
      ? { alignItems: "center", paddingBottom: 0 }
      : { alignItems: "flex-end", paddingBottom: 12 };

  return (
    <div
      className="app-root"
      style={positionStyle}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
    >
      {bgDim && <div className="bg-dim" />}
      {showSettings ? (
        <Settings send={send} />
      ) : (
        <>
          <LyricsOverlay send={send} />
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
