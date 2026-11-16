import { afterEach, describe, expect, it, vi } from 'vitest';
import { holdConfirmed, holdProgress } from '../src/hold';

afterEach(() => vi.useRealTimers());

describe('press and hold confirmation timing', () => {
  it('cancels an early release and confirms at 700 ms', () => {
    vi.useFakeTimers();
    const started = Date.now();
    vi.advanceTimersByTime(699);
    expect(holdConfirmed(started, Date.now())).toBe(false);
    expect(holdProgress(started, Date.now())).toBeLessThan(100);
    vi.advanceTimersByTime(1);
    expect(holdConfirmed(started, Date.now())).toBe(true);
    expect(holdProgress(started, Date.now())).toBe(100);
  });
});
