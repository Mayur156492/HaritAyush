import { describe, expect, it } from 'vitest';
import { canDecide, missionFor } from '../src/viewModel';

describe('operator view rules', () => {
  it('allows a decision only while the action is pending', () => {
    for (const status of ['approved', 'dismissed', 'applied', 'rolled_back', 'rejected', 'expired'] as const) expect(canDecide(status)).toBe(false);
    expect(canDecide('pending')).toBe(true);
    expect(canDecide(null)).toBe(false);
  });
  it('shows settling only when applied and no result is supplied', () => {
    const action = { id: 'a', type: 'cpu_cap' as const, cap_pct: 50, status: 'applied' as const, reason: '', created_at: '', decided_by: null, decided_at: null, applied_at: '2026-11-16T10:00:00Z', ended_at: null, before: null, after: null, reject_reason: null };
    expect(missionFor(action, []).label).toContain('Settling');
  });
});
