import { useEffect, useRef, useState } from "react";
import type { TaskEvent } from "../lib/api";

export type SocketStatus = "connecting" | "open" | "reconnecting";

/**
 * Keeps one WebSocket to /ws open. Reconnects with exponential backoff (1s → 30s);
 * `onReconnect` fires after a drop so the caller can refetch what it missed.
 */
export function useTaskSocket(
  onEvent: (event: TaskEvent) => void,
  onReconnect: () => void,
): SocketStatus {
  const [status, setStatus] = useState<SocketStatus>("connecting");
  const handlers = useRef({ onEvent, onReconnect });
  handlers.current = { onEvent, onReconnect };

  useEffect(() => {
    let socket: WebSocket | null = null;
    let timer: number | undefined;
    let delay = 1000;
    let hadConnection = false;
    let closed = false;

    const connect = () => {
      const proto = location.protocol === "https:" ? "wss" : "ws";
      socket = new WebSocket(`${proto}://${location.host}/ws`);
      socket.onopen = () => {
        setStatus("open");
        delay = 1000;
        if (hadConnection) handlers.current.onReconnect();
        hadConnection = true;
      };
      socket.onmessage = (msg) => {
        try {
          handlers.current.onEvent(JSON.parse(msg.data) as TaskEvent);
        } catch {
          /* ignore malformed frames */
        }
      };
      socket.onclose = () => {
        if (closed) return;
        setStatus("reconnecting");
        timer = window.setTimeout(connect, delay);
        delay = Math.min(delay * 2, 30000);
      };
      socket.onerror = () => socket?.close();
    };
    connect();

    return () => {
      closed = true;
      window.clearTimeout(timer);
      socket?.close();
    };
  }, []);

  return status;
}
