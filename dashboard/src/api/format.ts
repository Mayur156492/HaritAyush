import type { Risk, TemperatureStatus } from './types';

export const RISK_STYLE: Record<Risk, { shape: 'circle' | 'triangle' | 'square'; word: Risk }> = {
  Normal: { shape: 'circle', word: 'Normal' },
  Elevated: { shape: 'triangle', word: 'Elevated' },
  High: { shape: 'square', word: 'High' },
};

export function tempBadge(status: TemperatureStatus): string | null {
  if (status === 'measured') return null;
  return status === 'estimated' ? 'Estimated' : 'Unavailable';
}

export function timeToDangerText(minutes: number | null, limitC: number): string {
  if (minutes === null) return 'Not expected to reach the limit within 15 minutes';
  const limit = Number.isInteger(limitC) ? limitC.toFixed(0) : limitC.toFixed(1);
  return `May reach the limit of ${limit} °C in about ${Math.max(0, Math.round(minutes))} minutes`;
}

export function formatTemperature(value: number | null): string { return value === null ? '–' : `${value.toFixed(1)} °C`; }
export function formatPercent(value: number | null | undefined): string { return value == null ? '–' : `${Math.round(value)}%`; }
export function formatAge(seconds: number | null): string {
  if (seconds === null || !Number.isFinite(seconds)) return 'Age unavailable';
  const rounded = Math.max(0, Math.floor(seconds));
  return rounded < 60 ? `${rounded} s` : `${Math.floor(rounded / 60)} min ${rounded % 60} s`;
}
