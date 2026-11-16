import { useMemo, useState } from 'react';
import { Area, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { AuditEvent, Forecast, Reading } from './api/types';
import { formatTemperature } from './api/format';

interface Props { forecast: Forecast | null; readings: Reading[]; events: AuditEvent[] }
interface Point { time: string; label: string; temp: number | null; low?: number; band?: number; mid?: number; cpu?: number; kind?: string }

export function ForecastChart({ forecast, readings, events }: Props) {
  const [showCpu, setShowCpu] = useState(false);
  const points = useMemo<Point[]>(() => {
    const history = readings.map((reading) => ({ time: reading.ts, label: new Date(reading.ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }), temp: reading.cpu_temp_c, low: reading.cpu_temp_c ?? undefined, band: 0, cpu: reading.cpu_pct, kind: 'history' }));
    if (!forecast) return history;
    const now = new Date(forecast.ts);
    const result: Point[] = [...history, { time: forecast.ts, label: 'Now', temp: forecast.now_temp_c, low: forecast.now_temp_c ?? undefined, band: 0, kind: 'now' }];
    for (const horizon of ['5', '15'] as const) {
      const pred = forecast.pred[horizon];
      if (pred) result.push({ time: new Date(now.getTime() + Number(horizon) * 60_000).toISOString(), label: `+${horizon}m`, temp: null, low: pred.lo, band: Math.max(0, pred.hi - pred.lo), mid: pred.mid, kind: 'forecast' });
    }
    return result;
  }, [forecast, readings]);
  const values = [forecast?.now_temp_c ?? null, forecast?.limit_c ?? null, ...readings.map((reading) => reading.cpu_temp_c ?? null), ...(['5', '15'] as const).flatMap((horizon) => { const point = forecast?.pred[horizon]; return point ? [point.lo, point.hi] : []; })].filter((value): value is number => value !== null && Number.isFinite(value));
  const low = values.length ? Math.floor(Math.min(...values) - 2) : 0;
  const high = values.length ? Math.ceil(Math.max(...values) + 2) : 100;

  return <section className="panel chart-panel" aria-labelledby="chart-title">
    <div className="panel-heading chart-heading"><div><p className="eyebrow">THERMAL HISTORY + FORECAST</p><h2 id="chart-title">Temperature path</h2></div><button className="toggle" aria-pressed={showCpu} onClick={() => setShowCpu((value) => !value)}>CPU overlay <span>{showCpu ? 'On' : 'Off'}</span></button></div>
    {forecast ? <>
      <div className="chart-meta"><span><i className="legend-line" />Temperature</span><span><i className="legend-band" />Forecast range</span><span><i className="legend-dash" />Elevated · {formatTemperature(forecast.limit_c - 5)}</span><span><i className="legend-limit" />Limit · {formatTemperature(forecast.limit_c)}</span></div>
      <div className="chart-wrap" role="img" aria-label="Temperature history and forecast, with elevated and limit lines">
        <ResponsiveContainer width="100%" height="100%"><ComposedChart data={points} margin={{ top: 10, right: 6, bottom: 0, left: 0 }}>
          <CartesianGrid strokeDasharray="2 6" vertical={false} stroke="var(--grid)" />
          <XAxis dataKey="label" tick={{ fill: 'var(--muted)', fontSize: 11 }} axisLine={{ stroke: 'var(--rule)' }} tickLine={false} />
          <YAxis yAxisId="temp" domain={[low, high]} allowDataOverflow tickCount={5} interval="preserveStartEnd" tick={{ fill: 'var(--muted)', fontSize: 11 }} axisLine={false} tickLine={false} width={50} tickFormatter={(v: number) => `${v} °C`} />
          {showCpu && <YAxis yAxisId="cpu" orientation="right" domain={[0, 100]} tick={{ fill: 'var(--muted)', fontSize: 11 }} axisLine={false} tickLine={false} width={32} tickFormatter={(v: number) => `${v}%`} />}
          <Tooltip content={({ active, payload, label }) => { const visible = payload?.filter((item) => ['temp', 'mid', 'cpu'].includes(String(item.dataKey))) ?? []; return active && visible.length ? <div className="chart-tooltip"><b>{String(label)}</b>{visible.map((item) => <span key={String(item.dataKey)}>{item.dataKey === 'cpu' ? `CPU ${Math.round(Number(item.value))}%` : `Temperature ${formatTemperature(Number(item.value))}`}</span>)}<small>{forecast.temp_status === 'measured' ? 'Measured sensor' : `${forecast.temp_status} temperature · mock or estimated source`}</small></div> : null; }} />
          <ReferenceLine yAxisId="temp" y={forecast.limit_c} stroke="var(--high)" strokeDasharray="5 4" />
          <ReferenceLine yAxisId="temp" y={forecast.limit_c - 5} stroke="var(--elevated)" strokeDasharray="3 5" />
          <Area yAxisId="temp" dataKey="low" stackId="band" stroke="none" fill="transparent" isAnimationActive={false} />
          <Area yAxisId="temp" dataKey="band" stackId="band" stroke="none" fill="var(--band)" fillOpacity={0.4} isAnimationActive={false} />
          <Line yAxisId="temp" dataKey="temp" name="Temperature" stroke="var(--ink)" strokeWidth={2.5} dot={false} connectNulls isAnimationActive={false} />
          <Line yAxisId="temp" dataKey="mid" name="Forecast midpoint" stroke="var(--accent)" strokeWidth={2} strokeDasharray="5 5" dot={{ r: 4, fill: 'var(--accent)' }} connectNulls isAnimationActive={false} />
          {showCpu && <Line yAxisId="cpu" dataKey="cpu" name="CPU" stroke="var(--cpu)" strokeWidth={1.5} dot={false} connectNulls isAnimationActive={false} />}
        </ComposedChart></ResponsiveContainer>
      </div>
      <p className="chart-note">Warnings use the upper edge of the band. Forecast values are shown only at the supplied 5 and 15 minute horizons.</p>
      {events.length > 0 && <div className="event-strip" aria-label="Audit events on the timeline">{events.slice(0, 6).map((event) => <span key={event.id} title={`${event.event} · ${new Date(event.ts).toLocaleTimeString()}`}><i />{event.event.replaceAll('_', ' ')}</span>)}</div>}
    </> : <div className="empty-state"><strong>Waiting for readings</strong><span>The backend has not returned a forecast yet.</span></div>}
  </section>;
}
