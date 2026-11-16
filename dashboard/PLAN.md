# THERMOS dashboard plan

```text
┌ THERMOS · laptop-01 · DATA SOURCE · connection age ──────────────────┐
│ Risk + current temperature             │ Forecast chart              │
│ Risk shape, sentence, trust             │ History, forecast band,      │
│                                         │ limit and elevated lines     │
├ Why this warning? + checks              │ CPU overlay / chart note     │
├ Suggested action + operator + decisions │ Mission tracker + result     │
├ Reliability + job/replay controls        │ Audit timeline               │
└─────────────────────────────────────────┴─────────────────────────────┘
```

Files: `src/api/` contract types, fetch client and formatters; `src/mock/` in-memory API; `src/hooks/` non-overlapping polling; `src/App.tsx` dashboard and interactions; `src/styles.css`; `src/viewModel.ts`; `tests/` pure behavior tests.

States: waiting, live, replay, simulated/mock, offline with last-good data age, stale, low trust, estimated/unavailable temperature, pending, approved/checking/applied/settling/result, rejected, rolled back, dismissed, expired, 409 conflict.
