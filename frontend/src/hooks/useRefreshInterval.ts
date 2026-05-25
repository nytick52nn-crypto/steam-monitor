import { useEffect } from "react";

export type RefreshOption = 15 | 30 | 60 | 0;

export function useRefreshInterval(
  seconds: RefreshOption,
  onTick: () => void
) {
  useEffect(() => {
    if (!seconds) return;
    const id = setInterval(onTick, seconds * 1000);
    return () => clearInterval(id);
  }, [seconds, onTick]);
}
