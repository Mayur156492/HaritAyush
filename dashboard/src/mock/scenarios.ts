export const scenarios = ['happy_path', 'temperature_unavailable', 'temperature_estimated', 'stale_data', 'backend_offline', 'safety_check_rejection', 'rolled_back', 'low_trust', 'replay'] as const;
export type Scenario = (typeof scenarios)[number];
export const scenarioNames: Record<Scenario, string> = {
  happy_path: 'Happy path', temperature_unavailable: 'Temperature unavailable', temperature_estimated: 'Temperature estimated',
  stale_data: 'Stale data', backend_offline: 'Backend offline', safety_check_rejection: 'Safety check rejection',
  rolled_back: 'Rolled back', low_trust: 'Low trust', replay: 'Replay',
};
