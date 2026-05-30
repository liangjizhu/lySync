import { useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useLyricStore } from "../store";

interface Props {
  send: (msg: object) => void;
}

export function LyricsOverlay({ send }: Props): JSX.Element {
  const { lines, currentIndex, showTranslation, track, linesVisible, audioSyncStatus } =
    useLyricStore();
  const activeRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    activeRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [currentIndex]);

  if (!track) {
    return (
      <div className="overlay-container idle">
        <span className="idle-text">No music playing</span>
      </div>
    );
  }

  if (audioSyncStatus) {
    const isRecording = audioSyncStatus.status === "recording";
    const isTranscribing = audioSyncStatus.status === "transcribing";
    return (
      <div className="overlay-container idle">
        <div className="sync-status">
          <span className={`sync-spinner ${isRecording ? "pulse-red" : "pulse-white"}`}>
            {isRecording ? "🎙" : "⚙"}
          </span>
          <span className="sync-status-text">{audioSyncStatus.message}</span>
          {isRecording && (
            <div className="sync-progress-bar">
              <div className="sync-progress-fill" />
            </div>
          )}
        </div>
      </div>
    );
  }

  if (lines.length === 0) {
    return (
      <div className="overlay-container idle">
        <span className="idle-text">No lyrics found</span>
        <button
          className="sync-audio-btn"
          onClick={() => send({ type: "start_audio_sync" })}
        >
          🎙 Sync with Audio
        </button>
        <span className="sync-audio-hint">
          Restarts song · records {30}s · Whisper required
        </span>
      </div>
    );
  }

  const idx = currentIndex < 0 ? 0 : currentIndex;
  const before = Math.floor((linesVisible - 1) / 2);
  const after = linesVisible - 1 - before;
  const start = Math.max(0, idx - before);
  const end = Math.min(lines.length, idx + after + 1);
  const visible = lines.slice(start, end);

  return (
    <div className="overlay-container">
      <div className="lyrics-scroll">
        <AnimatePresence mode="popLayout">
          {visible.map((line, vi) => {
            const i = start + vi;
            const isActive = i === idx && currentIndex >= 0;
            const isPrev = i < idx;
            const original = line.text;
            const translation = line.translated_text;

            return (
              <motion.div
                key={`${i}-${line.time_ms}`}
                ref={isActive ? activeRef : null}
                className="lyrics-line-wrapper"
                initial={{ opacity: 0, y: 10 }}
                animate={{
                  opacity: isActive ? 1 : isPrev ? 0.3 : 0.55,
                  scale: isActive ? 1.06 : 1,
                  y: 0,
                  filter: isActive ? "brightness(1.4)" : "brightness(0.9)",
                }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.2, ease: "easeOut" }}
              >
                <div className="lyrics-line">
                  {original || <span className="interlude">♪</span>}
                </div>
                {showTranslation && translation && (
                  <div className="lyrics-translation">{translation}</div>
                )}
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </div>
  );
}
