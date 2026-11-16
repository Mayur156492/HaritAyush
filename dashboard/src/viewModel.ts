import type { Action, ActionStatus, AuditEvent, Forecast } from './api/types';

export function canDecide(status: ActionStatus | null | undefined): boolean { return status === 'pending'; }

export type Mission = { label: string; stage: number; terminal: boolean };
export function missionFor(action: Action | null, events: AuditEvent[]): Mission {
  if (!action) return { label: 'Waiting for recommendation', stage: 0, terminal: false };
  if (action.status === 'rejected') return { label: `Rejected · ${plainReason(action.reject_reason)}`, stage: -1, terminal: true };
  if (action.status === 'rolled_back' || events.some((event) => event.action_id === action.id && (event.event === 'rollback' || event.event === 'cap_removed'))) return { label: 'Rolled back', stage: -1, terminal: true };
  if (action.status === 'dismissed') return { label: 'Dismissed', stage: -1, terminal: true };
  if (action.status === 'expired') return { label: 'Expired', stage: -1, terminal: true };
  if (action.after) return { label: 'Result recorded', stage: 4, terminal: false };
  if (action.status === 'applied') return { label: 'Settling · waiting for the measured result', stage: 3, terminal: false };
  if (events.some((event) => event.action_id === action.id && event.event === 'cap_applied')) return { label: 'Cap applied', stage: 2, terminal: false };
  if (events.some((event) => event.action_id === action.id && event.event === 'command_received')) return { label: 'Agent checking', stage: 1, terminal: false };
  if (action.status === 'approved') return { label: 'Approved', stage: 0, terminal: false };
  return { label: 'Awaiting operator decision', stage: 0, terminal: false };
}

export function plainReason(reason: Action['reject_reason']): string {
  if (!reason) return 'Reason not supplied';
  return ({ approved: 'approval required', right_target: 'the demo job was not the target', in_bounds: 'requested cap was outside the allowed range', fresh_data: 'temperature reading was not fresh and measured', one_at_a_time: 'another action is active or cooling down', kill_switch: 'local kill switch is active' } as const)[reason];
}

export function freshnessReason(forecast: Forecast | null): string | null {
  if (!forecast) return 'Waiting for a forecast.';
  if (forecast.temp_status !== 'measured') return 'A live cap requires a measured temperature.';
  if (forecast.sensor_age_s > 10) return 'The latest temperature reading is older than 10 seconds.';
  if (forecast.trust === 'low') return 'Trust is low; inspect the listed reasons before deciding.';
  return null;
}
