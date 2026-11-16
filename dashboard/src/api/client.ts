import type { Action, AuditResponse, CommandCreated, CommandType, Forecast, Health, Mode, ModeResponse, RecentReadings } from './types';

const base = (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, '') ?? 'http://localhost:8000';

export class ApiError extends Error {
  constructor(readonly status: number, readonly code: string, message: string) { super(message); this.name = 'ApiError'; }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try { response = await fetch(`${base}${path}`, { ...init, headers: { 'Content-Type': 'application/json', ...init?.headers } }); }
  catch { throw new ApiError(0, 'offline', 'The backend could not be reached.'); }
  if (!response.ok) {
    let error: { error?: { code?: string; message?: string } } = {};
    try { error = await response.json() as typeof error; } catch { /* Keep generic HTTP error. */ }
    throw new ApiError(response.status, error.error?.code ?? 'http_error', error.error?.message ?? `Request failed (${response.status}).`);
  }
  return await response.json() as T;
}

export async function getForecastLatest(): Promise<Forecast | null> {
  try { return await request<Forecast>('/forecast/latest'); }
  catch (error) { if (error instanceof ApiError && error.status === 404 && error.code === 'no_data') return null; throw error; }
}
export const getReadingsRecent = (n = 300): Promise<RecentReadings> => request(`/readings/recent?n=${n}`);
export const approveAction = (id: string, operator: string): Promise<Action> => request(`/actions/${encodeURIComponent(id)}/approve`, { method: 'POST', body: JSON.stringify({ operator }) });
export const dismissAction = (id: string, operator: string): Promise<Action> => request(`/actions/${encodeURIComponent(id)}/dismiss`, { method: 'POST', body: JSON.stringify({ operator }) });
export const getAudit = (limit = 100): Promise<AuditResponse> => request(`/audit?limit=${limit}`);
export const postCommand = (type: CommandType): Promise<CommandCreated> => request('/commands', { method: 'POST', body: JSON.stringify({ type }) });
export const postMode = (mode: Mode): Promise<ModeResponse> => request('/mode', { method: 'POST', body: JSON.stringify({ mode }) });
export const getHealth = (): Promise<Health> => request('/health');
