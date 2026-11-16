import type { Action, AuditEvent, AuditResponse, CommandCreated, CommandType, DataSource, Forecast, Health, Mode, ModeResponse, RecentReadings } from '../api/types';
import type { Scenario } from './scenarios';
import { ApiError } from '../api/client';

let scenario: Scenario = 'happy_path';
let jobRunning = false;
let temperature = 72.4;
let tick = 0;
let action: Action = makeAction();
let events: AuditEvent[] = [];
let timers: ReturnType<typeof setTimeout>[] = [];

function isoAgo(seconds: number): string { return new Date(Date.now() - seconds * 1000).toISOString().replace('.000Z', 'Z'); }
function makeAction(): Action {
  return { id: 'mock-action-001', type: 'cpu_cap', cap_pct: 50, status: 'pending', reason: 'The upper forecast band approaches the configured temperature limit.', created_at: isoAgo(35), decided_by: null, decided_at: null, applied_at: null, ended_at: null, before: null, after: null, reject_reason: null };
}
function source(): DataSource { return scenario === 'replay' ? 'replay' : 'simulated'; }
function tempStatus(): Forecast['temp_status'] { return scenario === 'temperature_unavailable' ? 'unavailable' : 'estimated'; }
function addEvent(event: AuditEvent['event'], detail: string, actor: AuditEvent['actor'] = 'agent'): void {
  events.unshift({ id: `mock-event-${Date.now()}-${events.length}`, ts: isoAgo(0), site_id: 'laptop-01', actor, event, action_id: action.id, command_id: null, approved_by: action.decided_by, cap_pct: action.cap_pct, reason: detail, before: action.before, after: action.after, detail });
}
function wait(ms = 70): Promise<void> { return new Promise((resolve) => setTimeout(resolve, ms)); }

export const mockClient = {
  setScenario(next: Scenario): void {
    scenario = next;
    temperature = 72.4;
    tick = 0;
    jobRunning = false;
    action = makeAction();
    events = [];
    for (const timer of timers) clearTimeout(timer);
    timers = [];
    if (next === 'rolled_back') {
      action = { ...action, status: 'rolled_back', decided_by: 'Mock operator', decided_at: isoAgo(70), applied_at: isoAgo(60), ended_at: isoAgo(8), before: { cpu_pct: 90, mem_pct: 62, cpu_temp_c: 78.1 }, after: { cpu_pct: 74, mem_pct: 62, cpu_temp_c: 76.9 } };
      addEvent('rollback', 'The mock cap was removed after the rollback condition.');
    }
  },
  getScenario(): Scenario { return scenario; },
  async getForecastLatest(): Promise<Forecast | null> {
    await wait();
    if (scenario === 'backend_offline') throw new ApiError(0, 'offline', 'Mock backend is offline.');
    if (scenario === 'happy_path' || scenario === 'temperature_estimated' || scenario === 'temperature_unavailable' || scenario === 'stale_data') {
      temperature = Math.min(79.3, temperature + 0.12);
      tick++;
    }
    const status = tempStatus();
    const age = scenario === 'stale_data' ? 24 : 3;
    const hi = temperature + 3.2;
    const data: Forecast = {
      site_id: 'laptop-01', ts: isoAgo(age), now_temp_c: status === 'unavailable' ? null : Number(temperature.toFixed(1)), temp_status: status,
      limit_c: 80, pred: { '5': { lo: temperature + 0.7, mid: temperature + 1.8, hi: hi }, '15': { lo: temperature + 1.2, mid: temperature + 3.2, hi: temperature + 5.4 } },
      risk: temperature > 76 ? 'High' : temperature > 73 ? 'Elevated' : 'Normal', time_to_danger_min: temperature > 76 ? 8 : null,
      trust: scenario === 'low_trust' ? 'low' : 'high', trust_reasons: scenario === 'low_trust' ? ['Limited recent temperature history.', 'Forecast band is wider than usual.'] : [],
      why: [{ cause: 'CPU load has risen over recent readings', weight: 0.62 }, { cause: 'Temperature is trending upward', weight: 0.38 }],
      checks: [
        { name: 'data_fresh', passed: age <= 10, detail: age <= 10 ? 'Latest reading is within 10 seconds.' : 'Latest reading is older than 10 seconds.' },
        { name: 'enough_history', passed: true, detail: 'Recent history is available.' },
        { name: 'band_narrow', passed: true, detail: 'Forecast uncertainty is within the current check.' },
        { name: 'physics_ok', passed: true, detail: 'Forecast passes the plausibility check.' },
      ],
      sensor_age_s: age, data_source: source(), model: 'Mock forecast (development only)', action: scenario === 'safety_check_rejection' ? action : action,
    };
    return data;
  },
  async getReadingsRecent(n = 300): Promise<RecentReadings> {
    await wait();
    if (scenario === 'backend_offline') throw new ApiError(0, 'offline', 'Mock backend is offline.');
    const status = tempStatus();
    const readings = Array.from({ length: Math.min(n, 12) }, (_, i) => {
      const age = scenario === 'stale_data' ? 180 - i * 15 : 36 - i * 3;
      return { ts: isoAgo(age), cpu_pct: Math.max(30, 65 + i * 2), mem_pct: 62 + (i % 4) * 0.4,
        cpu_temp_c: status === 'unavailable' ? null : Number((temperature - (11 - i) * 0.16).toFixed(1)), temp_status: status,
        unavailable: ['gpu_temp', 'fan_rpm', 'inlet_temp', 'humidity', 'power_w'],
        demo_job: { running: jobRunning, cap_pct: action.status === 'applied' ? action.cap_pct : 100, pid: null }, data_source: source() };
    });
    return { site_id: 'laptop-01', readings };
  },
  async getAudit(limit = 100): Promise<AuditResponse> { await wait(); if (scenario === 'backend_offline') throw new ApiError(0, 'offline', 'Mock backend is offline.'); return { events: events.slice(0, limit) }; },
  async getHealth(): Promise<Health> { await wait(); return { status: scenario === 'backend_offline' ? 'offline' : 'ok', contract_version: 'mock-development', time: isoAgo(0), mode: scenario === 'replay' ? 'replay' : 'live', limit_c: 80 }; },
  async approveAction(id: string, operator: string): Promise<Action> {
    await wait();
    if (id !== action.id || action.status !== 'pending') throw new ApiError(409, 'invalid_state', `Already decided by ${action.decided_by ?? 'another operator'}.`);
    const now = isoAgo(0);
    if (scenario === 'safety_check_rejection') {
      action = { ...action, status: 'rejected', decided_by: operator, decided_at: now, ended_at: now, reject_reason: 'fresh_data' };
      addEvent('check_failed', 'Fresh-data check failed.', 'agent');
      return structuredClone(action);
    }
    action = { ...action, status: 'approved', decided_by: operator, decided_at: now, before: { cpu_pct: 91, mem_pct: 62.4, cpu_temp_c: tempStatus() === 'unavailable' ? null : Number(temperature.toFixed(1)) } };
    addEvent('action_approved', 'Operator approved the demo CPU cap.', 'operator');
    timers.push(setTimeout(() => addEvent('command_received', 'Agent received the approved command.'), 650));
    timers.push(setTimeout(() => {
      action = { ...action, status: 'applied', applied_at: isoAgo(0) };
      addEvent('cap_applied', 'Mock agent applied the cap to the demo job.');
      timers.push(setTimeout(() => {
        action = { ...action, after: { cpu_pct: 49, mem_pct: 62.3, cpu_temp_c: tempStatus() === 'unavailable' ? null : Number((temperature - 1.8).toFixed(1)) } };
        addEvent('result_recorded', 'Mock settling period completed.');
      }, 2100));
    }, 1450));
    return structuredClone(action);
  },
  async dismissAction(id: string, operator: string): Promise<Action> {
    await wait();
    if (id !== action.id || action.status !== 'pending') throw new ApiError(409, 'invalid_state', `Already decided by ${action.decided_by ?? 'another operator'}.`);
    action = { ...action, status: 'dismissed', decided_by: operator, decided_at: isoAgo(0), ended_at: isoAgo(0) };
    addEvent('action_dismissed', 'Operator dismissed the action.', 'operator');
    return structuredClone(action);
  },
  async postCommand(type: CommandType): Promise<CommandCreated> {
    await wait(); jobRunning = type === 'start_job'; addEvent(type === 'start_job' ? 'job_started' : 'job_stopped', `Mock demo job ${type === 'start_job' ? 'started' : 'stopped'}.`); return { id: `mock-command-${Date.now()}`, type };
  },
  async postMode(mode: Mode): Promise<ModeResponse> { await wait(); if (mode === 'replay') scenario = 'replay'; else if (scenario === 'replay') scenario = 'happy_path'; return { mode }; },
};
