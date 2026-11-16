# HaritAyush dashboard

A small React dashboard for the HaritAyush thermal warning loop. It shows the latest risk and readings, a forecast chart, backend explanations and checks, an operator decision, action progress, before/after values and the audit timeline. The dashboard does not send system-wide controls; its commands are limited to the demo job and replay mode defined by the API.

## Run locally with mock data

```sh
cd dashboard
npm install
npm run dev
```

Open the local URL Vite prints. The development scenario selector covers the happy path, temperature unavailable or estimated, stale data, offline, safety-check rejection, rollback, low trust and replay. Every mock screen is marked **MOCK DATA**. Mock temperatures are marked estimated or unavailable; mock actions do not control a laptop.

To try the simulated approval loop, select **Happy path**, click **Start job**, enter an operator name, then hold **Approve** for 0.7 seconds (or click twice using the keyboard). The mock agent progresses through approval, checking, apply, settling and a mock result. A second decision receives a 409 conflict.

## Connect to a backend

```sh
cd dashboard
VITE_API_BASE=http://localhost:8000 npm run dev:live
```

Set `VITE_API_BASE` to the backend base address. In PowerShell, use `$env:VITE_API_BASE="http://localhost:8000"` before `npm run dev:live`. The live backend must implement the API described in the supplied dashboard contract. Real approvals are enabled only for pending actions with a running demo job, high trust, a fresh reading, and measured CPU temperature.

## Checks and production build

```sh
npm test
npm run build
```

`npm run preview` serves the production build locally.
