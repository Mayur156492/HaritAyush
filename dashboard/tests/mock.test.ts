import { afterEach, describe, expect, it } from 'vitest';
import { mockClient } from '../src/mock/client';

afterEach(() => mockClient.setScenario('happy_path'));

describe('mock action decision', () => {
  it('returns 409 when the same action is approved twice', async () => {
    mockClient.setScenario('happy_path');
    const action = (await mockClient.getForecastLatest())?.action;
    expect(action?.status).toBe('pending');
    if (!action) throw new Error('Mock action missing');
    await mockClient.approveAction(action.id, 'Test operator');
    await expect(mockClient.approveAction(action.id, 'Test operator')).rejects.toMatchObject({ status: 409, code: 'invalid_state' });
  });
});
