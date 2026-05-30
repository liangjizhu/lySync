import { useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useLyricStore } from "../store";

export function LyricsOverlay(): JSX.Element {
  const { lines, currentIndex, showTranslation, track } = useLyricStore();
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

  if (lines.length === 0) {
    return (
      <div className="overlay-container idle">
        <span className="idle-text">No lyrics found</span>
      </div>
    );
  }

  const idx = currentIndex < 0 ? 0 : currentIndex;
  const BEFORE = 2;
  const AFTER = 3;
  const start = Math.max(0, idx - BEFORE);
  const end = Math.min(lines.length, idx + AFTER + 1);
  const visible = lines.slice(start, end);

  return (
    <div className="overlay-container">
      <div className="lyrics-scroll">
        <AnimatePresence mode="popLayout">
          {visible.map((line, vi) => {
            const i = start + vi;
            const isActive = i === idx && currentIndex >= 0;
            const isPrev = i < idx;
            const displayText =
              showTranslation && line.translated_text
                ? line.translated_text
                : line.text;

            return (
              <motion.div
                key={`${i}-${line.time_ms}`}
                ref={isActive ? activeRef : null}
                className="lyrics-line"
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
                {displayText || <span className="interlude">♪</span>}
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </div>
  );
}
