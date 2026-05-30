import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface LRCLine {
  time_ms: number;
  text: string;
  translated_text: string;
}

export interface TrackInfo {
  title: string;
  artist: string;
  album: string;
  position_ms: number;
  duration_ms: number;
  player_name: string;
}

export type VerticalPosition = "top" | "center" | "bottom";

interface LyricStore {
  // Playback state (not persisted)
  track: TrackInfo | null;
  lines: LRCLine[];
  currentIndex: number;
  detectedLang: string | null;

  // Translation settings (persisted)
  targetLang: string;
  showTranslation: boolean;
  translationProvider: "google" | "libre" | "deepl";

  // Display settings (persisted)
  fontSize: number;
  linesVisible: number;
  verticalPosition: VerticalPosition;
  bgDim: boolean;
  activeColor: string;
  translationColor: string;

  // Sync offset
  syncOffsetMs: number;

  // Audio sync state
  audioSyncStatus: { status: string; message: string } | null;

  // UI state
  showSettings: boolean;

  setSyncOffset: (ms: number) => void;
  setAudioSyncStatus: (s: { status: string; message: string } | null) => void;
  setTrack: (track: TrackInfo | null) => void;
  setLines: (lines: LRCLine[], lang: string | null) => void;
  setCurrentIndex: (index: number, text: string, translated: string) => void;
  setTargetLang: (lang: string) => void;
  setTranslationProvider: (p: "google" | "libre" | "deepl") => void;
  toggleTranslation: () => void;
  toggleSettings: () => void;
  setFontSize: (size: number) => void;
  setLinesVisible: (n: number) => void;
  setVerticalPosition: (p: VerticalPosition) => void;
  toggleBgDim: () => void;
  setActiveColor: (c: string) => void;
  setTranslationColor: (c: string) => void;
}

export const useLyricStore = create<LyricStore>()(
  persist(
    (set) => ({
      track: null,
      lines: [],
      currentIndex: -1,
      detectedLang: null,
      syncOffsetMs: 0,
      audioSyncStatus: null,
      targetLang: "en",
      showTranslation: true,
      translationProvider: "google",
      fontSize: 22,
      linesVisible: 6,
      verticalPosition: "bottom",
      bgDim: false,
      activeColor: "#ffffff",
      translationColor: "#ffdc78",
      showSettings: false,

      setSyncOffset: (ms) => set({ syncOffsetMs: ms }),
      setAudioSyncStatus: (s) => set({ audioSyncStatus: s }),
      setTrack: (track) => set({ track, lines: [], currentIndex: -1 }),
      setLines: (lines, lang) => set({ lines, detectedLang: lang, currentIndex: -1 }),
      setCurrentIndex: (index, text, translated) =>
        set((s) => ({
          currentIndex: index,
          lines: s.lines.map((l, i) =>
            i === index ? { ...l, text, translated_text: translated } : l
          ),
        })),
      setTargetLang: (lang) => set({ targetLang: lang }),
      setTranslationProvider: (p) => set({ translationProvider: p }),
      toggleTranslation: () => set((s) => ({ showTranslation: !s.showTranslation })),
      toggleSettings: () => set((s) => ({ showSettings: !s.showSettings })),
      setFontSize: (size) => set({ fontSize: size }),
      setLinesVisible: (n) => set({ linesVisible: n }),
      setVerticalPosition: (p) => set({ verticalPosition: p }),
      toggleBgDim: () => set((s) => ({ bgDim: !s.bgDim })),
      setActiveColor: (c) => set({ activeColor: c }),
      setTranslationColor: (c) => set({ translationColor: c }),
    }),
    {
      name: "lysync-settings",
      partialize: (s) => ({
        syncOffsetMs: s.syncOffsetMs,
        targetLang: s.targetLang,
        showTranslation: s.showTranslation,
        translationProvider: s.translationProvider,
        fontSize: s.fontSize,
        linesVisible: s.linesVisible,
        verticalPosition: s.verticalPosition,
        bgDim: s.bgDim,
        activeColor: s.activeColor,
        translationColor: s.translationColor,
      }),
    }
  )
);
