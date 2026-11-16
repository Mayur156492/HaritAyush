/**
 * Minimal application shell for the frontend scaffold.
 *
 * This file intentionally contains no dashboard, device view, chart or 3D
 * scene. It exists so that the React + TypeScript + Vite toolchain can be
 * verified end to end before feature work begins.
 */
export default function App() {
  return (
    <main className="app-shell">
      <h1 className="app-shell__title">THERMOS</h1>
      <p className="app-shell__subtitle">
        Thermal Heuristic Engine for Reasoning, Monitoring, Optimisation and Safety
      </p>
      <p className="app-shell__notice">
        Implementation: HaritAyush. Repository scaffold only. Telemetry views, forecasting panels, the 3D
        command centre and alerts are not implemented yet.
      </p>
    </main>
  );
}
