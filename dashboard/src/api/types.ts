export type TemperatureStatus = 'measured' | 'estimated' | 'unavailable';
export type Risk = 'Normal' | 'Elevated' | 'High';
export type Trust = 'high' | 'low';
export type DataSource = 'live' | 'replay' | 'simulated';
export type ActionStatus = 'pending' | 'approved' | 'dismissed' | 'applied' | 'rolled_back' | 'rejected' | 'expired';
export type RejectReason = 'approved' | 'right_target' | 'in_bounds' | 'fresh_data' | 'one_at_a_time' | 'kill_switch';
export type CommandType = 'start_job' | 'stop_job';
export type Mode = 'live' | 'replay';
export type CheckName = 'data_fresh' | 'enough_history' | 'band_narrow' | 'physics_ok';

export interface PredictionPoint { mid: number; lo: number; hi: number }
export interface Measurement { cpu_pct: number; mem_pct: number; cpu_temp_c: number | null }
export interface Action {
  id: string;
  type: 'cpu_cap';
  cap_pct: number;
  status: ActionStatus;
  reason: string;
  created_at: string;
  decided_by: string | null;
  decided_at: string | null;
  applied_at: string | null;
  ended_at: string | null;
  before: Measurement | null;
  after: Measurement | null;
  reject_reason: RejectReason | null;
}
export interface Check { name: CheckName; passed: boolean; detail: string }
export interface Cause { cause: string; weight: number }
export interface Forecast {
  site_id: string;
  ts: string;
  now_temp_c: number | null;
  temp_status: TemperatureStatus;
  limit_c: number;
  pred: { '5'?: PredictionPoint; '15'?: PredictionPoint };
  risk: Risk;
  time_to_danger_min: number | null;
  trust: Trust;
  trust_reasons: string[];
  why: Cause[];
  checks: Check[];
  sensor_age_s: number;
  data_source: DataSource;
  model: string;
  action: Action | null;
}
export interface Reading {
  ts: string;
  cpu_pct: number;
  mem_pct: number;
  cpu_temp_c: number | null;
  temp_status: TemperatureStatus;
  unavailable: string[];
  demo_job: { running: boolean; cap_pct: number; pid: number | null };
  data_source: DataSource;
}
export interface RecentReadings { site_id: string; readings: Reading[] }
export type AuditName = 'action_recommended' | 'action_approved' | 'action_dismissed' | 'command_received' | 'job_started' | 'job_stopped' | 'check_failed' | 'cap_applied' | 'result_recorded' | 'cap_removed' | 'rollback' | 'kill_switch' | 'reading_gap';
export interface AuditEvent {
  id: string; ts: string; site_id: string; actor: 'agent' | 'backend' | 'operator'; event: AuditName;
  action_id: string | null; command_id: string | null; approved_by: string | null; cap_pct: number | null;
  reason: string | null; before: Measurement | null; after: Measurement | null; detail: string | null;
}
export interface AuditResponse { events: AuditEvent[] }
export interface CommandCreated { id: string; type: CommandType }
export interface ModeResponse { mode: Mode }
export interface Health { status: string; contract_version: string; time: string; mode: Mode; limit_c: number }
