import { useEffect, useRef } from "react";
import { useLyricStore } from "../store";

const WS_URL = "ws://127.0.0.1:7314/ws";
const RECONNECT_DELAY_MS = 2000;

export function useWebSocket(): { send: (msg: object) => void } {
  const ws = useRef<WebSocket | null>(null);
  const store = useLyricStore();
  const sendQueue = useRef<string[]>([]);

  function send(msg: object): void {
    const raw = JSON.stringify(msg);
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(raw);
    } else {
      sendQueue.current.push(raw);
    }
  }

  useEffect(() => {
    let destroyed = false;
    let retryTimer: ReturnType<typeof setTimeout>;

    function connect(): void {
      const socket = new WebSocket(WS_URL);
      ws.current = socket;

      socket.onopen = () => {
        // Flush queued messages
        while (sendQueue.current.length) {
          socket.send(sendQueue.current.shift()!);
        }
      };

      socket.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          dispatch(msg);
        } catch {
          // ignore malformed
        }
      };

      socket.onclose = () => {
        if (!destroyed) {
          retryTimer = setTimeout(connect, RECONNECT_DELAY_MS);
        }
      };

      socket.onerror = () => socket.close();
    }

    function dispatch(msg: { type: string; payload: unknown }): void {
      switch (msg.type) {
        case "track_changed":
          store.setTrack(msg.payload as never);
          break;
        case "lyrics_loaded": {
          const p = msg.payload as { lines: never[]; lang: string | null };
          store.setLines(p.lines, p.lang);
          break;
        }
        case "line_changed": {
          const p = msg.payload as {
            index: number;
            text: string;
            translated_text: string;
          };
          store.setCurrentIndex(p.index, p.text, p.translated_text);
          break;
        }
      }
    }

    connect();
    return () => {
      destroyed = true;
      clearTimeout(retryTimer);
      ws.current?.close();
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return { send };
}
