import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ApiError, approveAction as liveApprove, dismissAction as liveDismiss, getAudit as liveAudit, getForecastLatest as liveForecast, getHealth as liveHealth, getReadingsRecent as liveReadings, postCommand as liveCommand, postMode as liveMode } from './api/client';
import { formatAge, formatPercent, formatTemperature, RISK_STYLE, timeToDangerText } from './api/format';
import type { Action, CommandType, Forecast, Mode } from './api/types';
import { usePoller } from './hooks/usePoller';
import { mockClient } from './mock/client';
import { scenarioNames, scenarios, type Scenario } from './mock/scenarios';
import { ForecastChart } from './ForecastChart';
import { canDecide, missionFor, plainReason } from './viewModel';
import { holdConfirmed, holdProgress } from './hold';
import './styles.css';

const mockMode = import.meta.env.VITE_USE_MOCK === 'true';
const api = mockMode ? mockClient : { getForecastLatest: liveForecast, getReadingsRecent: liveReadings, getAudit: liveAudit, getHealth: liveHealth, approveAction: liveApprove, dismissAction: liveDismiss, postCommand: liveCommand, postMode: liveMode };
const readSaved = (key: string, fallback = ''): string => { try { return globalThis.localStorage?.getItem(key) ?? fallback; } catch { return fallback; } };
const save = (key: string, value: string): void => { try { globalThis.localStorage?.setItem(key, value); } catch { /* Preferences are optional. */ } };

function RiskMark({ risk }: { risk: Forecast['risk'] }) { return <span className={`risk-shape shape-${RISK_STYLE[risk].shape}`} aria-hidden="true" />; }
function SensorChip({ status }: { status: string }) { return <span className={`sensor-chip sensor-${status.replaceAll(' ', '-')}`}><i aria-hidden="true" />{status}</span>; }

export default function App() {
  const forecastPoll = usePoller(() => api.getForecastLatest(), 2000);
  const readingsPoll = usePoller(() => api.getReadingsRecent(300), 3000);
  const auditPoll = usePoller(() => api.getAudit(100), 4000);
  const healthPoll = usePoller(() => api.getHealth(), 5000);
  const forecast = forecastPoll.data ?? null;
  const readings = readingsPoll.data?.readings ?? [];
  const events = auditPoll.data?.events ?? [];
  const action: Action | null = forecast?.action ?? null;
  const [ageNow, setAgeNow] = useState(Date.now());
  const [theme, setTheme] = useState<'dark' | 'light'>(() => readSaved('haritayush-theme', 'dark') === 'light' ? 'light' : 'dark');
  const [operator, setOperator] = useState(() => readSaved('haritayush-operator'));
  const [toast, setToast] = useState('');
  const [confirmArmed, setConfirmArmed] = useState<'approve' | 'dismiss' | null>(null);
  const [progress, setProgress] = useState(0);
  const [scenario, setScenario] = useState<Scenario>(() => mockMode ? mockClient.getScenario() : 'happy_path');
  const [expandedAudit, setExpandedAudit] = useState<string | null>(null);
  const holdRef = useRef<{ started: number; decision: 'approve' | 'dismiss'; interval: ReturnType<typeof setInterval> } | null>(null);
  const pointerAction = useRef(false);

  const refresh = useCallback(async () => {
    await Promise.all([forecastPoll.refetch(), readingsPoll.refetch(), auditPoll.refetch(), healthPoll.refetch()]);
  }, [forecastPoll.refetch, readingsPoll.refetch, auditPoll.refetch, healthPoll.refetch]);
  useEffect(() => { const timer = setInterval(() => setAgeNow(Date.now()), 1000); return () => clearInterval(timer); }, []);
  useEffect(() => { document.documentElement.dataset.theme = theme; save('haritayush-theme', theme); }, [theme]);
  useEffect(() => { save('haritayush-operator', operator); }, [operator]);

  const anyError = Boolean(forecastPoll.error || readingsPoll.error || auditPoll.error || healthPoll.error || healthPoll.data?.status === 'offline');
  const latestReading = readings[readings.length - 1] ?? null;
  const lastGoodResponseAt = [forecastPoll.lastSuccess, readingsPoll.lastSuccess, auditPoll.lastSuccess, healthPoll.lastSuccess].filter((time): time is number => time !== null).reduce((latest, time) => Math.max(latest, time), 0);
  const sensorAgeSeconds = forecast ? forecast.sensor_age_s + (forecastPoll.lastSuccess === null ? 0 : Math.max(0, (ageNow - forecastPoll.lastSuccess) / 1000)) : null;
  const sourceAge = sensorAgeSeconds !== null ? formatAge(sensorAgeSeconds) : readingsPoll.lastSuccess === null ? '–' : formatAge((ageNow - readingsPoll.lastSuccess) / 1000);
  const dangerText = forecast ? timeToDangerText(forecast.time_to_danger_min, forecast.limit_c) : 'Waiting for the first forecast.';
  const mission = useMemo(() => missionFor(action, events), [action, events]);
  const liveSafetyReason = !forecast ? 'Waiting for a forecast.' : forecast.temp_status !== 'measured' ? 'A live cap requires a measured temperature.' : (sensorAgeSeconds ?? 0) > 10 ? 'The latest temperature reading is older than 10 seconds.' : forecast.trust === 'low' ? 'Trust is low; inspect the listed reasons before deciding.' : null;
  const approveReady = canDecide(action?.status) && Boolean(operator.trim()) && (mockMode ? Boolean(latestReading?.demo_job.running) : (!liveSafetyReason && Boolean(latestReading?.demo_job.running)));
  const dismissReady = canDecide(action?.status) && Boolean(operator.trim());

  const doDecision = useCallback(async (decision: 'approve' | 'dismiss') => {
    if (!action || action.status !== 'pending' || !operator.trim()) return;
    if (decision === 'approve' && !approveReady) { setToast(liveSafetyReason ?? 'Start the demo job before approving the CPU cap.'); return; }
    setToast(''); setConfirmArmed(null);
    try {
      if (decision === 'approve') await api.approveAction(action.id, operator.trim());
      else await api.dismissAction(action.id, operator.trim());
      await refresh();
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        const latest = await api.getForecastLatest().catch(() => null);
        const who = latest?.action?.decided_by ?? action.decided_by ?? 'another operator';
        setToast(`Already decided by ${who}. The latest status was refreshed.`);
        await refresh();
      } else setToast(error instanceof Error ? error.message : 'The action could not be completed.');
    }
  }, [action, approveReady, liveSafetyReason, operator, refresh]);

  function beginHold(decision: 'approve' | 'dismiss') {
    if (holdRef.current) clearInterval(holdRef.current.interval);
    const started = Date.now();
    const interval = setInterval(() => setProgress(holdProgress(started, Date.now())), 20);
    holdRef.current = { started, decision, interval };
  }
  function endHold() {
    const hold = holdRef.current;
    if (!hold) return;
    clearInterval(hold.interval); holdRef.current = null; setProgress(0); pointerAction.current = true;
    if (holdConfirmed(hold.started, Date.now())) void doDecision(hold.decision);
    else setToast('Confirmation cancelled.');
  }
  function keyboardDecision(decision: 'approve' | 'dismiss') {
    if (confirmArmed === decision) { void doDecision(decision); return; }
    setConfirmArmed(decision); setToast(`Click ${decision === 'approve' ? 'Approve' : 'Dismiss'} again to confirm.`);
  }
  async function sendCommand(type: CommandType) { try { await api.postCommand(type); await refresh(); } catch (error) { setToast(error instanceof Error ? error.message : 'Command could not be sent.'); } }
  async function toggleReplay() {
    try {
      const next: Mode = forecast?.data_source === 'replay' ? 'live' : 'replay';
      await api.postMode(next);
      if (mockMode) { const nextScenario = next === 'replay' ? 'replay' : 'happy_path'; mockClient.setScenario(nextScenario); setScenario(nextScenario); }
      await refresh();
    } catch (error) { setToast(error instanceof Error ? error.message : 'Mode could not be changed.'); }
  }
  async function changeScenario(next: Scenario) { mockClient.setScenario(next); setScenario(next); await refresh(); }

  const dataLabel = !forecast ? (mockMode ? 'MOCK DATA' : 'WAITING FOR DATA') : forecast.data_source === 'replay' ? 'DEMO DATA: REPLAY' : forecast.data_source === 'simulated' ? 'SIMULATED' : 'LIVE';
  const sourceClass = forecast?.data_source === 'live' ? 'badge-live' : forecast ? 'badge-demo' : 'badge-waiting';
  const offlineAge = lastGoodResponseAt === 0 ? 'No successful response yet' : `Last good response ${formatAge((ageNow - lastGoodResponseAt) / 1000)} ago`;

  return <main className="dashboard">
    <header className="topbar">
      <div className="brand"><span className="brand-mark" aria-hidden="true"><i /><i /><i /></span><div><strong>HaritAyush</strong><small>Thermal watch</small></div></div>
      <div className="site"><span>SITE</span><b>laptop-01</b></div>
      <div className="top-state">{mockMode && <span className="data-badge badge-mock">MOCK DATA</span>}<span className={`data-badge ${sourceClass}`}>{dataLabel}</span><span className={`connection ${anyError ? 'offline' : ''}`}><i />{anyError ? 'Offline' : 'Connected'} <span>· {sourceAge}</span></span></div>
      <button className="quiet-button theme-button" onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')} aria-label="Toggle theme">{theme === 'dark' ? 'Light mode' : 'Dark mode'}</button>
    </header>

    {mockMode && <div className="scenario-row"><span>Development scenario</span><select value={scenario} onChange={(event) => void changeScenario(event.target.value as Scenario)}>{scenarios.map((item) => <option key={item} value={item}>{scenarioNames[item]}</option>)}</select><b>MOCK DATA · no hardware command is sent</b></div>}
    {anyError && <div className="banner offline-banner" role="status"><b>Backend offline.</b> Showing the last good data. {offlineAge}</div>}
    {forecast && forecast.data_source !== 'live' && <div className="banner source-banner"><b>{dataLabel}</b> · This view is not live sensor telemetry.</div>}
    {forecast && (sensorAgeSeconds ?? 0) > 10 && <div className="banner stale-banner" role="status">Sensor data is stale ({formatAge(sensorAgeSeconds)}). Live approval is disabled.</div>}
    {forecast?.trust === 'low' && <div className="banner trust-banner"><b>LOW TRUST</b> {forecast.trust_reasons.join(' ')}</div>}
    {forecast?.temp_status === 'estimated' && <div className="banner safety-banner">Temperature is estimated; a live CPU cap cannot be approved.</div>}
    {forecast?.temp_status === 'unavailable' && <div className="banner safety-banner">CPU temperature is unavailable; a live CPU cap cannot be approved.</div>}

    {mockMode && <div className="mock-stamp" aria-label="Mock data">MOCK DATA</div>}
    <div className="workspace">
      <div className="left-column">
        <section className={`panel risk-panel ${forecast ? `risk-${forecast.risk.toLowerCase()}` : ''}`} aria-live="polite" aria-label="Thermal risk">
          <div className="panel-heading"><div><p className="eyebrow">CURRENT THERMAL RISK</p><h1>{forecast ? <><RiskMark risk={forecast.risk} />{forecast.risk}</> : 'Waiting'}</h1></div>{forecast?.trust === 'low' && <span className="trust-flag">LOW TRUST</span>}</div>
          <p className="danger-statement">{dangerText}</p>
          {forecast ? <>
            <div className="temperature-block"><span className="temp-label">CPU temperature</span><strong>{formatTemperature(forecast.now_temp_c)}</strong><SensorChip status={forecast.temp_status === 'measured' ? 'measured' : forecast.temp_status} /></div>
            <div className="limit-meta"><span>Configured limit</span><strong>{formatTemperature(forecast.limit_c)}</strong><span className="dot-sep">·</span><span>Sensor age {sourceAge}</span></div>
          </> : <p className="muted">Waiting for readings from laptop-01.</p>}
          {forecast?.trust === 'low' && <div className="trust-reasons"><b>Why trust is low</b>{forecast.trust_reasons.map((reason) => <span key={reason}>• {reason}</span>)}</div>}
        </section>

        <section className="panel reliability-panel">
          <div className="panel-heading compact"><div><p className="eyebrow">INPUTS</p><h2>Data reliability</h2></div><span className="sensor-age">Age {sourceAge}</span></div>
          <div className="sensor-grid">
            <div className="sensor-row"><span>CPU temperature</span><SensorChip status={forecast?.temp_status ?? 'unavailable'} /><b>{latestReading ? formatTemperature(latestReading.cpu_temp_c) : formatTemperature(forecast?.now_temp_c ?? null)}</b></div>
            <div className="sensor-row"><span>CPU load</span><SensorChip status={latestReading ? 'available' : 'unavailable'} /><b>{formatPercent(latestReading?.cpu_pct)}</b></div>
            <div className="sensor-row"><span>Memory</span><SensorChip status={latestReading ? 'available' : 'unavailable'} /><b>{formatPercent(latestReading?.mem_pct)}</b></div>
          </div>
          <p className="unavailable-line"><b>Not measured on this laptop:</b> {latestReading?.unavailable.map((item) => item.replaceAll('_', ' ')).join(', ') || 'GPU temperature, fan speed, inlet temperature, humidity, power'}</p>
          <div className="job-row"><span>Demo job <b>{latestReading?.demo_job.running ? 'running' : 'stopped'}</b>{latestReading ? ` · cap ${formatPercent(latestReading.demo_job.cap_pct)}` : ''}</span><div><button className="control-button" onClick={() => void sendCommand('start_job')} disabled={Boolean(latestReading?.demo_job.running)}>Start job</button><button className="control-button" onClick={() => void sendCommand('stop_job')} disabled={!latestReading?.demo_job.running}>Stop job</button><button className="control-button" onClick={() => void toggleReplay()}>{forecast?.data_source === 'replay' ? 'Replay on' : 'Replay off'}</button></div></div>
        </section>
      </div>

      <div className="right-column">
        <ForecastChart forecast={forecast} readings={readings} events={events} />
        <section className="panel why-panel">
          <div className="panel-heading compact"><div><p className="eyebrow">EXPLANATION</p><h2>Why this warning?</h2></div></div>
          {forecast?.why.length ? <ol className="causes">{[...forecast.why].sort((a, b) => b.weight - a.weight).map((cause, index) => <li key={`${cause.cause}-${index}`}><span className="cause-rank">0{index + 1}</span><div className="cause-body"><span>{cause.cause}</span><div className="weight-track"><i style={{ width: `${Math.max(0, Math.min(100, cause.weight * 100))}%` }} /></div></div><b>{Math.round(cause.weight * 100)}%</b></li>)}</ol> : <p className="muted">No causes are available yet.</p>}
          <div className="checks"><h3>Verification checks</h3>{forecast?.checks.length ? forecast.checks.map((check) => <div className="check-row" key={check.name}><span className={`check-icon ${check.passed ? 'pass' : 'fail'}`}>{check.passed ? '✓' : '!'}</span><span>{check.detail}</span><b>{check.passed ? 'PASS' : 'REVIEW'}</b></div>) : <p className="muted">Waiting for checks.</p>}</div>
        </section>

        <section className="panel action-panel">
          <div className="panel-heading compact"><div><p className="eyebrow">OPERATOR ACTION</p><h2>{action ? action.status.replaceAll('_', ' ') : 'No action available'}</h2></div>{action && <span className={`status-pill status-${action.status}`}>{action.status}</span>}</div>
          {action ? <>
            <p className="action-copy">Cap the demo job's CPU at <strong>{formatPercent(action.cap_pct)}</strong>.</p>
            <p className="action-reason">{action.reason}</p>
            {action.status === 'pending' && <>
              <label className="operator-field">Operator name<input value={operator} onChange={(event) => setOperator(event.target.value)} placeholder="Name for audit record" autoComplete="name" /></label>
              {liveSafetyReason && !mockMode && <p className="blocked-reason">{liveSafetyReason}</p>}
              {!latestReading?.demo_job.running && <p className="blocked-reason">Start the demo job before approving the CPU cap.</p>}
              <div className="decision-row">
                <button className="approve-button" disabled={!approveReady} style={{ ['--hold-progress' as string]: `${progress}%` }} onPointerDown={() => { if (approveReady) beginHold('approve'); }} onPointerUp={endHold} onPointerLeave={() => { if (holdRef.current) endHold(); }} onClick={() => { if (pointerAction.current) { pointerAction.current = false; return; } if (approveReady) keyboardDecision('approve'); }} aria-label="Hold to approve this cap">{confirmArmed === 'approve' ? 'Click again to approve' : 'Hold 0.7 s · Approve'}</button>
                <button className="dismiss-button" disabled={!dismissReady} onPointerDown={() => { if (dismissReady) beginHold('dismiss'); }} onPointerUp={endHold} onPointerLeave={() => { if (holdRef.current) endHold(); }} onClick={() => { if (pointerAction.current) { pointerAction.current = false; return; } if (dismissReady) keyboardDecision('dismiss'); }}>{confirmArmed === 'dismiss' ? 'Click again to dismiss' : 'Dismiss'}</button>
              </div>
              {!operator.trim() && <p className="hint">Enter an operator name to enable a decision.</p>}
            </>}
            {toast && <p className="toast" role="status">{toast}</p>}
            <div className="mission"><div className="mission-head"><h3>Action progress</h3><b>{mission.label}</b></div>{mission.terminal ? <p className="terminal-message">{action.status === 'rejected' ? plainReason(action.reject_reason) : mission.label}</p> : <ol>{['Approved', 'Agent checking', 'Cap applied', 'Settling', 'Result'].map((label, index) => <li className={mission.stage >= index + 1 ? 'done' : mission.stage === index ? 'current' : ''} key={label}><i />{label}</li>)}</ol>}</div>
            {action.status === 'applied' && !action.after && <p className="settling-copy">Settling, waiting for the measured result.</p>}
            {action.before && <div className="result-box"><div className="result-head"><h3>Before / after</h3><span>{mockMode ? 'MOCK DATA' : `Updated ${action.applied_at ? formatAge(Math.max(0, (Date.now() - Date.parse(action.applied_at)) / 1000)) : '–'} ago`}</span></div><div className="result-values"><div><small>BEFORE</small><b>{formatTemperature(action.before.cpu_temp_c)}</b><SensorChip status={mockMode ? forecast?.temp_status ?? 'unavailable' : 'not supplied'} /><span>CPU {formatPercent(action.before.cpu_pct)}</span></div><i>→</i><div><small>AFTER</small><b>{formatTemperature(action.after?.cpu_temp_c ?? null)}</b>{action.after && <SensorChip status={mockMode ? forecast?.temp_status ?? 'unavailable' : 'not supplied'} />}<span>CPU {formatPercent(action.after?.cpu_pct)}</span></div></div>{action.after && <p className="result-disclaimer">{mockMode ? 'Mock action cycle. No measured laptop result.' : forecast?.temp_status === 'measured' && action.before.cpu_temp_c !== null && action.after.cpu_temp_c !== null ? 'One measured run on one laptop. Not a savings claim.' : 'Temperature status for these action samples is not supplied.'}</p>}</div>}
          </> : <p className="muted">There is no current recommendation.</p>}
        </section>

        <section className="panel audit-panel">
          <div className="panel-heading compact"><div><p className="eyebrow">RECORD</p><h2>Audit timeline</h2></div><span>{events.length} events</span></div>
          {events.length ? <ul className="audit-list">{events.slice(0, 12).map((event) => <li key={event.id}><button onClick={() => setExpandedAudit(expandedAudit === event.id ? null : event.id)} aria-expanded={expandedAudit === event.id}><time>{new Date(event.ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</time><b>{event.event.replaceAll('_', ' ')}</b><span>{event.actor}</span></button>{expandedAudit === event.id && <div className="audit-detail"><p>{event.detail ?? event.reason ?? 'No detail supplied.'}</p>{event.before && <span>Before: {formatTemperature(event.before.cpu_temp_c)} · status not supplied · CPU {formatPercent(event.before.cpu_pct)}</span>}{event.after && <span>After: {formatTemperature(event.after.cpu_temp_c)} · status not supplied · CPU {formatPercent(event.after.cpu_pct)}</span>}</div>}</li>)}</ul> : <p className="muted">No audit events returned yet.</p>}
        </section>
      </div>
    </div>
    <footer className="footer"><span>{forecast?.model ?? 'Waiting for backend forecast'}</span><span>Sensor status shown with temperature. {healthPoll.data?.contract_version ?? ''}</span></footer>
  </main>;
}
