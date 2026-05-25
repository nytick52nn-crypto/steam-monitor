import { useEffect, useRef, useState } from "react";

export function useWebSocket(onMessage?: (data: unknown) => void) {
  const [connected, setConnected] = useState(false);
  const [lastSnapshot, setLastSnapshot] = useState<unknown>(null);
  const cb = useRef(onMessage);
  cb.current = onMessage;

  useEffect(() => {
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const ws = new WebSocket(`${proto}//${host}/ws`);

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data);
        if (data.type === "snapshot") setLastSnapshot(data);
        cb.current?.(data);
      } catch {
        /* ignore */
      }
    };

    const ping = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) ws.send("ping");
    }, 30000);

    return () => {
      clearInterval(ping);
      ws.close();
    };
  }, []);

  return { connected, lastSnapshot };
}
