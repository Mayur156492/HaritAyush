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
      <h1 className="app-shell__title">HaritAyush</h1>
      <p className="app-shell__subtitle">
        Distributed Thermal Intelligence and Resource Optimisation Platform
      </p>
      <p className="app-shell__notice">
        Repository scaffold only. Telemetry views, forecasting panels, the 3D
        command centre and alerts are not implemented yet.
      </p>
    </main>
  );
}
