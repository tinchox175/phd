# pani-chamber

PC driver for the PANI humidity chamber: Arduino Due running firmware FW0.3.
The protocol it speaks is documented in `chamber_commands.txt`, next to the firmware.

## Install

As its own project:

```
cd chamber-driver
uv sync
uv run chamber --fake status        # works without hardware
uv run pytest                       # tests run against the simulated chamber
```

Inside another project (the suite, an analysis repo), as an editable dependency,
so edits here show up there immediately:

```
uv add --editable ../chamber-driver
```

## Finding the chamber

First match wins:

1. `Chamber(port=...)` or `chamber --port ...`: a device path
   (`/dev/serial/by-id/...`, `/dev/ttyACM0`), a Windows `COM5`, or a VISA name.
2. The `CHAMBER_PORT` environment variable.
3. Auto-detection of `/dev/serial/by-id/*Arduino_Due*` (Linux).

Only one program can hold the port at a time.

## Command line

```
chamber status                      # one-line summary
chamber set 25                      # box-air target, degC
chamber ctrl on                     # start temperature control
chamber fan on
chamber clear                       # clear a latched fault
chamber raw "PID?"                  # any protocol command, reply printed as-is
chamber log run1.csv                # 1 Hz CSV log until Ctrl-C (--interval, --duration)
chamber wait --window 1800 --rh-tol 0.2
chamber --fake --speedup 120 wait   # try anything on the simulated chamber
```

## Python

```python
from chamber import Chamber, ChamberError

with Chamber() as ch:
    ch.set_temperature(25)
    ch.control(True)
    ch.fan(True)

    r = ch.read()                    # Reading: time, t_air, t_jar, rh, output,
    print(r.rh, r.t_jar, r.status)   #          setpoint, control, fan, status

    final = ch.wait_until_stable(window_s=1800, rh_tol=0.2, t_tol=0.05,
                                 on_reading=print)
```

- Rejected commands raise `ChamberCommandError` (with `.code`, e.g. `ERR:RANGE`).
- `read()` reports faults in `reading.status`; `read(raise_on_fault=True)` raises `ChamberFault`.
- Lost connection or no reply raises `ChamberConnectionError`.
- All of them derive from `ChamberError`.
- By default, closing the connection leaves the chamber running. Use
  `Chamber(off_on_close=True)` to switch control off when the program ends.
- One `Chamber` object can be shared between threads; commands are serialized.

### Equilibration

`wait_until_stable()` fits a straight line to the jar RH (and temperature) over
the last `window_s` seconds and returns when that line changes by less than
`rh_tol` (`t_tol`) across the window. The defaults (10 min, 0.5 %, 0.1 degC)
are placeholders: once you have a few real equilibration curves, pick a window
and tolerances that match how slowly your salts and films actually settle.

For the suite, don't call `wait_until_stable()` (it polls by itself). Have the
single 1 Hz worker that already reads the chamber feed a `StabilityMonitor`:

```python
from chamber import StabilityMonitor
monitor = StabilityMonitor(window_s=1800, rh_tol=0.2, t_tol=0.05)
monitor.add(reading)      # every reading the worker takes
monitor.stable            # check whenever needed
monitor.reset()           # after changing salt or setpoint
```

## Simulated chamber

`FakeChamber` answers the same protocol as the firmware (same replies, errors
and faults) with a rough thermal and humidity model behind it. It has the same
methods as `Chamber`, so code can switch with one line.

```python
from chamber import FakeChamber
with FakeChamber(speedup=60, salt_rh=75.3) as ch:   # 1 real s = 1 simulated min
    ...
```

Readings from the fake carry simulated timestamps. For tests, `speedup=0`
freezes time and `ch.advance(seconds)` steps it by hand; `ch.t_air = 60` or
`ch.air_sensor_ok = False` trigger the firmware's faults.

## Layout

```
src/chamber/
  base.py        ChamberBase: the API, reply checking, wait_until_stable
  driver.py      Chamber: real hardware over pyvisa (pyvisa-py backend)
  fake.py        FakeChamber: simulated firmware + physics
  reading.py     Reading: one MEAS? snapshot
  stability.py   is_stable(), StabilityMonitor
  errors.py      exception classes
  cli.py         the `chamber` command
tests/           pytest, against FakeChamber
```

When the firmware protocol changes: bump its version, update
`chamber_commands.txt`, `SUPPORTED_FIRMWARE` in `base.py` and `fake.py`.
