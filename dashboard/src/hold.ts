export const HOLD_DURATION_MS = 700;
export function holdProgress(startedAt: number, now: number): number { return Math.min(100, Math.max(0, ((now - startedAt) / HOLD_DURATION_MS) * 100)); }
export function holdConfirmed(startedAt: number, endedAt: number): boolean { return endedAt - startedAt >= HOLD_DURATION_MS; }
