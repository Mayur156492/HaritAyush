import { describe, expect, it } from 'vitest';
import { RISK_STYLE, tempBadge, timeToDangerText } from '../src/api/format';

describe('temperature and risk formatting', () => {
  it('never labels a non-measured temperature as measured', () => {
    expect(tempBadge('measured')).toBeNull();
    expect(tempBadge('estimated')).toBe('Estimated');
    expect(tempBadge('unavailable')).toBe('Unavailable');
  });
  it('uses distinct word and shape for every risk', () => {
    expect(RISK_STYLE.Normal).toEqual({ shape: 'circle', word: 'Normal' });
    expect(RISK_STYLE.Elevated).toEqual({ shape: 'triangle', word: 'Elevated' });
    expect(RISK_STYLE.High).toEqual({ shape: 'square', word: 'High' });
  });
  it('formats the two documented danger states', () => {
    expect(timeToDangerText(8, 80)).toBe('May reach the limit of 80 °C in about 8 minutes');
    expect(timeToDangerText(null, 80)).toBe('Not expected to reach the limit within 15 minutes');
  });
});
