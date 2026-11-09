"""The chamber's high-level interface, shared by the real and the fake chamber.

ChamberBase turns method calls into protocol commands (chamber_commands.txt)
and checks every reply. Subclasses only provide the transport: how to open,
close, and exchange one line (send a command, get one reply line back).
"""

from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Callable

from .errors import (
    ChamberCommandError,
    ChamberConnectionError,
    ChamberFault,
    ChamberProtocolError,
    ChamberVersionError,
    StabilityTimeout,
)
from .reading import Reading
from .stability import StabilityMonitor

IDN_PREFIX = "PANI-CHAMBER,DUE,"
SUPPORTED_FIRMWARE = ("FW0.3",)


class ChamberBase(ABC):
    """Common chamber API. Use as a context manager:

        with Chamber() as ch:
            print(ch.read())
    """

    def __init__(self, off_on_close: bool = False):
        # off_on_close: switch temperature control off when the program closes
        # the connection. Default False: the chamber keeps holding temperature
        # between scripts, which is usually what you want.
        self.off_on_close = off_on_close
        self.idn: str | None = None
        self.firmware: str | None = None
        self._connected = False
        # One lock so several threads (e.g. a GUI and a poller) can share one
        # Chamber object without their commands and replies getting mixed up.
        self._lock = threading.RLock()

    # ----- transport, provided by subclasses -----------------------------------

    @abstractmethod
    def _open(self) -> None: ...

    @abstractmethod
    def _close(self) -> None: ...

    @abstractmethod
    def _transact(self, line: str) -> str:
        """Send one command line and return the single reply line, stripped."""

    def _clock(self) -> float:
        """Timestamp for readings (Unix seconds). The fake uses simulated time."""
        return time.time()

    # ----- connection ----------------------------------------------------------

    def connect(self) -> ChamberBase:
        """Open the connection and verify the firmware version."""
        with self._lock:
            self._open()
            self._connected = True
            try:
                idn = self._transact("*IDN?")
                if not idn.startswith(IDN_PREFIX):
                    raise ChamberVersionError(f"Not a PANI chamber: *IDN? returned {idn!r}")
                fw = idn[len(IDN_PREFIX):]
                if fw not in SUPPORTED_FIRMWARE:
                    raise ChamberVersionError(
                        f"Firmware {fw} not supported by this driver (supports {', '.join(SUPPORTED_FIRMWARE)})"
                    )
                self.idn, self.firmware = idn, fw
            except Exception:
                self._connected = False
                self._close()
                raise
        return self

    def close(self) -> None:
        with self._lock:
            if not self._connected:
                return
            try:
                if self.off_on_close:
                    self.control(False)
            finally:
                self._connected = False
                self._close()

    @property
    def connected(self) -> bool:
        return self._connected

    def __enter__(self) -> ChamberBase:
        return self.connect()

    def __exit__(self, *exc) -> None:
        self.close()

    # ----- low-level access ----------------------------------------------------

    def raw(self, line: str) -> str:
        """Send any command and return the reply unchecked (for debugging)."""
        with self._lock:
            if not self._connected:
                raise ChamberConnectionError("Not connected (call connect() or use 'with')")
            return self._transact(line)

    def query(self, command: str) -> str:
        """Send a command; return the reply, raising ChamberCommandError on ERR:..."""
        reply = self.raw(command)
        if reply.startswith("ERR:"):
            raise ChamberCommandError(command, reply)
        return reply

    def command(self, command: str) -> None:
        """Send an action command that must be answered with OK."""
        reply = self.query(command)
        if reply != "OK":
            raise ChamberProtocolError(f"Expected OK to {command!r}, got {reply!r}")

    def _query_float(self, command: str) -> float:
        reply = self.query(command)
        try:
            return float(reply)
        except ValueError as e:
            raise ChamberProtocolError(f"Expected a number from {command!r}, got {reply!r}") from e

    def _query_bool(self, command: str) -> bool:
        reply = self.query(command)
        if reply not in ("0", "1"):
            raise ChamberProtocolError(f"Expected 0/1 from {command!r}, got {reply!r}")
        return reply == "1"

    # ----- measurements --------------------------------------------------------

    def read(self, raise_on_fault: bool = False) -> Reading:
        """Read everything at once (MEAS?).

        By default a fault is reported in reading.status rather than raised, so
        loggers keep recording. Pass raise_on_fault=True to get ChamberFault.
        """
        reading = Reading.parse(self.query("MEAS?"), time=self._clock())
        if raise_on_fault and not reading.ok:
            raise ChamberFault(reading.status)
        return reading

    # ----- temperature control -------------------------------------------------

    def set_temperature(self, celsius: float) -> None:
        """Box-air target, 10-50 degC (the firmware enforces the range)."""
        self.command(f"TEMP:SET {celsius:.2f}")

    def temperature_setpoint(self) -> float:
        return self._query_float("TEMP:SET?")

    def control(self, on: bool) -> None:
        """Start or stop automatic temperature control."""
        self.command(f"CTRL {'ON' if on else 'OFF'}")

    def control_enabled(self) -> bool:
        return self._query_bool("CTRL?")

    def set_pid(self, kp: float, ki: float, kd: float) -> None:
        self.command(f"PID {kp:.6g} {ki:.6g} {kd:.6g}")

    def pid(self) -> tuple[float, float, float]:
        parts = self.query("PID?").split(",")
        if len(parts) != 3:
            raise ChamberProtocolError(f"Unexpected PID? reply: {parts!r}")
        kp, ki, kd = (float(p) for p in parts)
        return kp, ki, kd

    # ----- manual output (testing only, control must be off) -----------------

    def set_output(self, drive: float) -> None:
        """Manual TEC drive, -1 (full cooling) .. +1 (full heating)."""
        self.command(f"OUT:SET {drive:.3f}")

    def output(self) -> float:
        return self._query_float("OUT?")

    # ----- fan, sensor heater, faults ------------------------------------------

    def fan(self, on: bool) -> None:
        self.command(f"FAN {'ON' if on else 'OFF'}")

    def fan_enabled(self) -> bool:
        return self._query_bool("FAN?")

    def sht_heater(self, on: bool) -> None:
        """SHT30 heater: only for sensor recovery after long high-RH exposure."""
        self.command(f"SHT:HEAT {'ON' if on else 'OFF'}")

    def status(self) -> str:
        """'OK' or 'FAULT:...'."""
        return self.query("STAT?")

    def clear_fault(self) -> None:
        """Clear a latched fault (*CLS). It returns within 1 s if the cause persists."""
        self.command("*CLS")

    # ----- waiting for equilibrium -----------------------------------------------

    def wait_until_stable(
        self,
        window_s: float = 600.0,
        rh_tol: float = 0.5,
        t_tol: float = 0.1,
        poll_s: float = 5.0,
        timeout_s: float | None = None,
        on_reading: Callable[[Reading], None] | None = None,
    ) -> Reading:
        """Block until jar RH and temperature have settled; return the last reading.

        Settled = over the last window_s seconds, the fitted trend of jar RH
        changes by at most rh_tol (%) and of jar temperature by at most t_tol
        (degC); see stability.py. on_reading, if given, is called with
        every reading (use it to log or print progress). Raises ChamberFault on a
        fault and StabilityTimeout if timeout_s passes first.
        """
        monitor = StabilityMonitor(window_s, rh_tol, t_tol)
        start = time.monotonic()
        while True:
            reading = self.read(raise_on_fault=True)
            monitor.add(reading)
            if on_reading is not None:
                on_reading(reading)
            if monitor.stable:
                return reading
            if timeout_s is not None and time.monotonic() - start > timeout_s:
                raise StabilityTimeout(f"Not stable after {timeout_s:.0f} s")
            time.sleep(poll_s)
