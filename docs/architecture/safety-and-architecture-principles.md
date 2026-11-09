# Architecture and safety principles

These constraints apply to every part of HaritAyush. They are not aspirational
guidance; they define what the platform is allowed to do and what it must say
about what it knows. Any implementation that conflicts with them is wrong, even
if it appears to work.

## Sensors and measurement

1. **Windows 11 does not universally expose temperature and fan sensors.** Some
   laptops expose usable sensors; others expose none, or expose values through
   vendor-specific paths. The platform must work with what is actually
   available and must state when a measurement is unavailable.

2. **Capabilities are discovered, never assumed.** The agent determines which
   sensors, counters and features a device really provides, and reports that
   discovery result. Device model names and marketing specifications are not
   evidence of sensor availability.

3. **Sensor readings are never fabricated.** No placeholder temperature, fan
   speed, power draw, utilisation or derived metric may be presented as a
   measurement. Missing data is reported as missing, and any interpolation or
   estimate is labelled as such wherever it is shown.

## Thermal control and hardware safety

4. **Firmware thermal protection is never bypassed.** HaritAyush reduces and
   forecasts thermal load; it does not override, disable or race against
   firmware throttling and shutdown protections.

5. **Undocumented embedded-controller registers are never written.** No
   direct EC or low-level hardware manipulation is part of this platform.

6. **Local safety validation is independent of backend connectivity.** The
   agent enforces its own safety rules locally, and those rules remain in force
   when the backend is unreachable, slow or compromised. A backend decision
   cannot talk the agent past its own checks.

## Devices, workloads and commands

7. **Only enrolled devices and authorised workloads may be managed.** There is
   no open discovery, auto-adoption or anonymous execution. If a device is not
   enrolled or a workload is not authorised, the platform does not act on it.

8. **No unrestricted remote shell execution.** Commands are specific,
   validated actions against known workloads. The platform does not expose a
   general-purpose remote command channel.

9. **Generic running Windows applications cannot simply be copied live to
   another computer.** Process memory, handles, open files and driver state do
   not transfer between machines that way. Migration is not offered for
   arbitrary software.

10. **Initial migration is limited to purpose-built checkpointable workloads.**
    A workload that can save a consistent checkpoint and resume from it may be
    migrated to a compatible enrolled device. Everything else is out of scope,
    and the UI must not imply otherwise.

## Prediction, verification and risk

11. **Forecasts are verified against observations.** A prediction is compared
    with the temperature actually measured at its target time. Unverifiable
    forecasts are recorded as unverified, never as correct.

12. **SARIMAX future exogenous variables must be handled explicitly.** Future
    CPU utilisation, GPU utilisation, power draw and workload intensity are not
    automatically known at forecast time. Each must be forecast separately,
    supplied from a known schedule, or produced by a documented fallback. The
    choice and its assumptions must be visible wherever the forecast is used.

13. **Model comparisons use identical chronological test periods.** No random
    splits, no temporal leakage, and no metric claims without a reproducible
    evaluation over real recorded telemetry. MAE and RMSE are the supported
    error metrics.

14. **Forecast horizon support is reported honestly.** The planned horizons are
    5 and 15 minutes. If the telemetry frequency or history length cannot
    support a horizon, that limit is stated rather than hidden behind a
    confident-looking number.

## Sustainability claims

15. **Energy, carbon and water figures distinguish measured from estimated.**
    A reading from a platform counter and a model-derived value are different
    things. Every figure carries its provenance, period and assumptions, and
    totals do not blend the two without showing the split. Grid emission
    factors are documented external assumptions, not measurements from this
    platform.

16. **Device lifespan extension is not claimed from temperature reduction
    alone.** Lower operating temperature is not proof of longer hardware life.
    HaritAyush may report thermal conditions, but it does not promise lifespan
    outcomes on that basis.

## Demonstration environment

17. **Simulated devices are labelled as simulated.** The initial demonstration
    uses a Windows 11 laptop and additional real devices where available. When a
    simulated device, reading or workload is necessary, it is explicitly
    identified as simulated everywhere it appears — in the API, the database and
    the dashboard.

## Consequences for the current scaffold

The repository contains no telemetry collection, command execution, model
training or prediction. Every placeholder module in `apps/backend/app/intelligence/`
states the constraint it must satisfy when implemented, and the local agent
package contains no behaviour at all. Nothing in this repository should be read
as evidence that these capabilities already exist.
