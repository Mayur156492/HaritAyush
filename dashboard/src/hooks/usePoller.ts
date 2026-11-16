import { useCallback, useEffect, useRef, useState } from 'react';

export interface PollState<T> { data: T | undefined; error: Error | null; loading: boolean; lastSuccess: number | null; refetch: () => Promise<void> }

/** Poll only after the preceding request settles; retain the last good response on failure. */
export function usePoller<T>(load: () => Promise<T>, intervalMs: number): PollState<T> {
  const loader = useRef(load);
  loader.current = load;
  const [data, setData] = useState<T>();
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastSuccess, setLastSuccess] = useState<number | null>(null);
  const inFlight = useRef(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const run = useCallback(async () => {
    if (inFlight.current) return;
    inFlight.current = true;
    try { const next = await loader.current(); setData(next); setError(null); setLastSuccess(Date.now()); }
    catch (caught) { setError(caught instanceof Error ? caught : new Error('Request failed.')); }
    finally { inFlight.current = false; setLoading(false); }
  }, []);
  useEffect(() => {
    let active = true;
    const cycle = async () => {
      await run();
      if (active) timer.current = setTimeout(cycle, intervalMs);
    };
    void cycle();
    return () => { active = false; if (timer.current) clearTimeout(timer.current); };
  }, [intervalMs, run]);
  return { data, error, loading, lastSuccess, refetch: run };
}
