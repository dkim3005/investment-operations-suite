"use client";

import { useEffect, useState } from "react";

/** Poll a JSON endpoint on an interval; returns the latest data and error. */
export function usePoll<T>(url: string, ms = 4000) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let stopped = false;
    const tick = async () => {
      try {
        const r = await fetch(url);
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        const json = await r.json();
        if (!stopped) {
          setData(json);
          setError(null);
        }
      } catch (e) {
        if (!stopped) setError(e instanceof Error ? e.message : "request failed");
      }
    };
    tick();
    const id = setInterval(tick, ms);
    return () => {
      stopped = true;
      clearInterval(id);
    };
  }, [url, ms]);

  return { data, error };
}
