import { create } from "zustand";

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

interface LyricStore {
  track: TrackInfo | null;
  lines: LRCLine[];
  currentIndex: number;
  detectedLang: string | null;
  targetLang: string;
  showTranslation: boolean;
  showSettings: boolean;
  translationProvider: "google" | "libre" | "deepl";

  setTrack: (track: TrackInfo | null) => void;
  setLines: (lines: LRCLine[], lang: string | null) => void;
  setCurrentIndex: (index: number, text: string, translated: string) => void;
  setTargetLang: (lang: string) => void;
  setTranslationProvider: (p: "google" | "libre" | "deepl") => void;
  toggleTranslation: () => void;
  toggleSettings: () => void;
}

export const useLyricStore = create<LyricStore>((set) => ({
  track: null,
  lines: [],
  currentIndex: -1,
  detectedLang: null,
  targetLang: "en",
  showTranslation: true,
  showSettings: false,
  translationProvider: "google",

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
}));
