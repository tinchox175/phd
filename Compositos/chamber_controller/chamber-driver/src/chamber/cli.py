"""Command-line tool for quick checks and logging.

    chamber status                 one-line summary of the chamber
    chamber set 25                 set the box-air target (degC)
    chamber ctrl on|off            start/stop temperature control
    chamber fan on|off             jar fan
    chamber clear                  clear a latched fault
    chamber raw "MEAS?"            send any command, print the reply
    chamber log run1.csv           log every second to CSV until Ctrl-C
    chamber wait                   block until RH and temperature have settled

Global options: --port PATH (else CHAMBER_PORT or auto-detect),
--fake (simulated chamber, --speedup N to run it faster).
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
import time
from datetime import datetime

from .base import ChamberBase
from .driver import Chamber
from .errors import ChamberError
from .fake import FakeChamber
from .reading import Reading


def _num(v: float, fmt: str) -> str:
    return "  --  " if math.isnan(v) else format(v, fmt)


def summary(r: Reading) -> str:
    return (
        f"air {_num(r.t_air, '6.2f')} C | jar {_num(r.t_jar, '6.2f')} C | RH {_num(r.rh, '5.1f')} % | "
        f"set {r.setpoint:5.2f} C | ctrl {'ON ' if r.control else 'OFF'} | "
        f"drive {r.output:+.3f} | fan {'ON ' if r.fan else 'OFF'} | {r.status}"
    )


def _onoff(text: str) -> bool:
    return text.lower() == "on"


def cmd_log(ch: ChamberBase, path: str, interval: float, duration: float | None) -> None:
    start = time.monotonic()
    next_t = start
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["iso_time", *Reading.FIELDS])
        print(f"Logging to {path} every {interval:g} s, Ctrl-C to stop")
        try:
            while duration is None or time.monotonic() - start < duration:
                r = ch.read()
                iso = datetime.fromtimestamp(r.time).isoformat(timespec="seconds")
                writer.writerow([iso, *(getattr(r, k) for k in Reading.FIELDS)])
                f.flush()  # data is on disk even if the program is killed
                print(f"{iso}  {summary(r)}")
                next_t += interval
                time.sleep(max(0.0, next_t - time.monotonic()))
        except KeyboardInterrupt:
            print("\nStopped.")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="chamber", description="PANI humidity chamber tool")
    p.add_argument("--port", help="device path or VISA name (default: CHAMBER_PORT or auto-detect)")
    p.add_argument("--fake", action="store_true", help="use the simulated chamber")
    p.add_argument("--speedup", type=float, default=60.0, help="simulated-time speedup for --fake")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="print the current state")
    s = sub.add_parser("set", help="set box-air target temperature")
    s.add_argument("temperature", type=float)
    c = sub.add_parser("ctrl", help="temperature control on/off")
    c.add_argument("state", choices=["on", "off"])
    f = sub.add_parser("fan", help="jar fan on/off")
    f.add_argument("state", choices=["on", "off"])
    sub.add_parser("clear", help="clear a latched fault")
    r = sub.add_parser("raw", help="send a raw command and print the reply")
    r.add_argument("command")
    lg = sub.add_parser("log", help="log readings to a CSV file")
    lg.add_argument("file")
    lg.add_argument("--interval", type=float, default=1.0, help="seconds between readings")
    lg.add_argument("--duration", type=float, default=None, help="stop after this many seconds")
    w = sub.add_parser("wait", help="wait until RH and temperature have settled")
    w.add_argument("--window", type=float, default=600.0, help="seconds that must be stable")
    w.add_argument("--rh-tol", type=float, default=0.5, help="max RH drift across the window, %%")
    w.add_argument("--t-tol", type=float, default=0.1, help="max jar-temperature drift across the window, degC")
    w.add_argument("--timeout", type=float, default=None, help="give up after this many seconds")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        ch: ChamberBase = FakeChamber(speedup=args.speedup) if args.fake else Chamber(port=args.port)
        with ch:
            if args.cmd == "status":
                print(summary(ch.read()))
            elif args.cmd == "set":
                ch.set_temperature(args.temperature)
                print(f"setpoint {args.temperature:.2f} C")
            elif args.cmd == "ctrl":
                ch.control(_onoff(args.state))
                print(f"control {args.state}")
            elif args.cmd == "fan":
                ch.fan(_onoff(args.state))
                print(f"fan {args.state}")
            elif args.cmd == "clear":
                ch.clear_fault()
                print("fault cleared")
            elif args.cmd == "raw":
                print(ch.raw(args.command))
            elif args.cmd == "log":
                cmd_log(ch, args.file, args.interval, args.duration)
            elif args.cmd == "wait":
                r = ch.wait_until_stable(
                    window_s=args.window, rh_tol=args.rh_tol, t_tol=args.t_tol,
                    timeout_s=args.timeout, poll_s=1.0 if args.fake else 5.0,
                    on_reading=lambda r: print(summary(r)),
                )
                print(f"Stable: {summary(r)}")
    except ChamberError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
