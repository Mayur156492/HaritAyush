# Dashboard report

## Works

- Responsive dark and light dashboard with risk shape and word, temperature status, trust reasons, forecast chart and upper-band note.
- Why causes and verification checks appear before the action.
- Pending action can be approved or dismissed with a 700 ms hold or a two-click keyboard confirmation. Real approvals also require fresh measured temperature, high trust and a running demo job. A 409 refreshes the action and identifies the deciding operator when the backend returns that name.
- Action progress is derived from the contract action status and audit events. Before/after values come from `action.before` and `action.after`; missing fields display a dash. Action measurement status is identified as unavailable when the API does not supply it.
- Data reliability, sensor age, audit expansion, CPU chart overlay, demo job/replay controls, theme preference and operator-name preference.
- Polling uses recursive timers, so each endpoint is polled only after its prior request settles. Failed requests retain the last good result and show an offline state with the age of the last successful response.
- Tests cover formatting, pending-only action decisions, mock 409 behavior and the 700 ms hold threshold.

## Mock and live boundaries

`npm run dev` uses an in-memory mock API. Its values and action loop are development examples only, marked MOCK DATA; its temperature status is estimated or unavailable and it never reports a mock sample as a measured laptop reading. It does not apply a real CPU cap. `npm run dev:live` calls the HTTP endpoints in `src/api/client.ts`; a live backend/device loop was not exercised for this delivery.

## Contract issues

- The repository has no `contract/` directory or `docs/CONTRACT.md`. The six files under `contracts/` are explicitly marked initial placeholders and declare no API fields. The API contract embedded in the task was used as the source of truth.
- The `Action.before` and `Action.after` shapes do not include `temp_status` or a sample timestamp. The UI therefore labels action temperatures as estimated in mock mode and “status not supplied” in live mode; it does not claim those values were measured from these fields alone.
- The project does not include an API schema/runtime validator for these endpoint payloads. The live client is typed at compile time; it assumes the backend returns the specified shapes.

## Not verified / missing

- No real backend connection, Windows agent, or real cap application was tested. The live endpoint compatibility and exact backend result timing need verification with the team backend and a Windows laptop.
- `npm audit` reported zero vulnerabilities after updating Recharts and Vitest.
- The chart currently shows forecast points only when the backend supplies those horizons; it does not generate missing forecast values.

## Verification

- `npm test`: 4 test files, 7 tests passed.
- `npm run build`: passed. Vite reports a large uncompressed JavaScript chunk (645 KB); the generated JavaScript is approximately 192 KB gzip.
