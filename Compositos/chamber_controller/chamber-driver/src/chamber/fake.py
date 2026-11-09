"""A simulated chamber that speaks the same protocol as the real firmware.

It answers the exact command set of FW0.3 (same replies, same errors, same
faults), and behind it runs a crude thermal and humidity model, so code using
it behaves as it would on the hardware. Use it to develop scripts and the
suite without the chamber connected.

The model is only qualitative:
- box air relaxes toward room temperature and is pushed by the TEC drive;
- the jar follows the box air slowly;
- jar RH relaxes toward the saturated-salt value with a ~1 h time constant.

speedup > 1 runs simulated time faster than real time (60 = one simulated
minute per real second), handy for testing wait_until_stable().
"""

from __future__ import annotations

import math
import random
import time

from .base import ChamberBase

# Firmware constants (keep in sync with chamber_controller.ino)
MAX_DUTY = 0.60
DEADBAND = 0.02
T_MAX, T_MIN = 55.0, 5.0
SETP_MIN, SETP_MAX = 10.0, 50.0
IDN = "PANI-CHAMBER,DUE,FW0.3"

# Model constants
TAU_AIR = 400.0     # s, box air toward room temperature
HEAT_GAIN = 0.08    # degC/s per unit of (drive * MAX_DUTY)
TAU_JAR = 1500.0    # s, jar toward box air
TAU_RH = 3600.0     # s, jar RH toward the salt's value
MAX_STEPS = 200_000  # cap on simulated seconds per call (about 2.3 days)


def _fmt(v: float, decimals: int) -> str:
    return "NAN" if math.isnan(v) else f"{v:.{decimals}f}"


class FakeChamber(ChamberBase):
    """Simulated chamber. Same methods as Chamber.

    Extra knobs for tests: .ambient, .salt_rh, and the state variables
    (.t_air, .t_jar, .rh) can be changed at any time; .air_sensor_ok = False
    simulates a dead DS18B20.
    """

    def __init__(
        self,
        speedup: float = 1.0,
        ambient: float = 24.0,
        salt_rh: float = 75.3,
        start_rh: float = 50.0,
        noise: bool = True,
        seed: int | None = None,
        off_on_close: bool = False,
    ):
        super().__init__(off_on_close=off_on_close)
        self.speedup = speedup
        self.ambient = ambient
        self.salt_rh = salt_rh
        self.noise = noise
        self._rng = random.Random(seed)
        # Physical state
        self.t_air = ambient
        self.t_jar = ambient
        self.rh = start_rh
        self.air_sensor_ok = True
        # Firmware state (boot defaults)
        self.setpoint = 25.0
        self.drive = 0.0
        self.ctrl_on = False
        self.fan_on = False
        self.heater_on = False
        self.kp, self.ki, self.kd = 0.15, 0.002, 0.0
        self._integ = 0.0
        self._prev_meas = math.nan
        self.fault = "OK"
        self._last = None
        self._carry = 0.0
        self._t0 = time.time()   # simulated clock = start time + simulated seconds
        self._sim_s = 0.0

    # ----- transport -------------------------------------------------------------

    def _open(self) -> None:
        self._last = time.monotonic()

    def _close(self) -> None:
        pass

    def _transact(self, line: str) -> str:
        self._advance()
        return self._handle(line)

    # ----- simulation ------------------------------------------------------------

    def advance(self, seconds: float) -> None:
        """Jump simulated time forward (tests)."""
        self._step(int(seconds))

    def _advance(self) -> None:
        now = time.monotonic()
        self._carry += (now - self._last) * self.speedup
        self._last = now
        steps = int(self._carry)
        self._carry -= steps
        self._step(min(steps, MAX_STEPS))

    def _clock(self) -> float:
        return self._t0 + self._sim_s

    def _step(self, n: int) -> None:
        self._sim_s += n
        for _ in range(n):
            # 1 s of physics
            heat = HEAT_GAIN * self.drive * MAX_DUTY
            self.t_air += (self.ambient - self.t_air) / TAU_AIR + heat
            self.t_jar += (self.t_air - self.t_jar) / TAU_JAR
            self.rh += (self.salt_rh - self.rh) / TAU_RH
            # 1 s of firmware: safety, then PID (same order as loop())
            self._check_faults()
            if self.ctrl_on and self.fault == "OK":
                self._apply(self._pid(self.setpoint, self._meas_air(), 1.0))

    def _meas_air(self) -> float:
        if not self.air_sensor_ok:
            return math.nan
        t = self.t_air + (self._rng.gauss(0, 0.02) if self.noise else 0.0)
        return round(t / 0.0625) * 0.0625  # DS18B20 12-bit steps

    def _meas_jar(self) -> tuple[float, float]:
        n = self.noise
        t = self.t_jar + (self._rng.gauss(0, 0.02) if n else 0.0)
        rh = self.rh + (self._rng.gauss(0, 0.1) if n else 0.0)
        return t, max(0.0, min(100.0, rh))

    def _check_faults(self) -> None:
        if self.fault != "OK":
            return
        t = self.t_air if self.air_sensor_ok else math.nan
        if self.ctrl_on and math.isnan(t):
            self.fault = "FAULT:SENSOR"
        elif not math.isnan(t) and t > T_MAX:
            self.fault = "FAULT:OVERTEMP"
        elif not math.isnan(t) and t < T_MIN:
            self.fault = "FAULT:UNDERTEMP"
        if self.fault != "OK":
            self.ctrl_on = False
            self.drive = 0.0

    def _apply(self, u: float) -> None:
        if self.fault != "OK":
            self.drive = 0.0
            return
        u = max(-1.0, min(1.0, u))
        self.drive = 0.0 if abs(u) < DEADBAND else u

    def _pid(self, sp: float, meas: float, dt: float) -> float:
        err = sp - meas
        deriv = 0.0 if math.isnan(self._prev_meas) else -(meas - self._prev_meas) / dt
        self._prev_meas = meas
        u_no_i = self.kp * err + self.kd * deriv
        cand = self._integ + self.ki * err * dt
        u = u_no_i + cand
        if (u > 1 and err > 0) or (u < -1 and err < 0):
            u = u_no_i + self._integ
        else:
            self._integ = cand
        return max(-1.0, min(1.0, u))

    def _pid_reset(self) -> None:
        self._integ = 0.0
        self._prev_meas = math.nan

    # ----- protocol (mirrors handleCommand() in the firmware) ----------------------

    @staticmethod
    def _floats(text: str, n: int) -> list[float] | None:
        parts = text.split()
        if len(parts) != n:
            return None
        try:
            return [float(p) for p in parts]
        except ValueError:
            return None

    @staticmethod
    def _onoff(arg: str) -> bool | None:
        return {"ON": True, "1": True, "OFF": False, "0": False}.get(arg)

    def _handle(self, line: str) -> str:
        line = line.strip().upper()
        cmd, _, arg = line.partition(" ")
        arg = arg.strip()

        if cmd == "*IDN?":
            return IDN
        if cmd == "MEAS?":
            t_jar, rh = self._meas_jar()
            return ",".join([
                _fmt(self._meas_air(), 4), _fmt(t_jar, 2), _fmt(rh, 2),
                f"{self.drive:.3f}", f"{self.setpoint:.2f}",
                "1" if self.ctrl_on else "0", "1" if self.fan_on else "0", self.fault,
            ])
        if cmd == "MEAS:TAIR?":
            return _fmt(self._meas_air(), 4)
        if cmd == "MEAS:TJAR?":
            return _fmt(self._meas_jar()[0], 2)
        if cmd == "MEAS:RH?":
            return _fmt(self._meas_jar()[1], 2)

        if cmd == "TEMP:SET?":
            return f"{self.setpoint:.2f}"
        if cmd == "TEMP:SET":
            v = self._floats(arg, 1)
            if v is None or not SETP_MIN <= v[0] <= SETP_MAX:
                return "ERR:RANGE"
            self.setpoint = v[0]
            return "OK"

        if cmd == "CTRL?":
            return "1" if self.ctrl_on else "0"
        if cmd == "CTRL":
            v = self._onoff(arg)
            if v is None:
                return "ERR:ARG"
            if v and self.fault != "OK":
                return "ERR:FAULT_ACTIVE"
            if v and not self.air_sensor_ok:
                return "ERR:NO_AIR_SENSOR"
            self.ctrl_on = v
            self._pid_reset()
            if not v:
                self._apply(0.0)
            return "OK"

        if cmd == "OUT?":
            return f"{self.drive:.3f}"
        if cmd == "OUT:SET":
            if self.ctrl_on:
                return "ERR:CTRL_ON"
            if self.fault != "OK":
                return "ERR:FAULT_ACTIVE"
            v = self._floats(arg, 1)
            if v is None:
                return "ERR:ARG"
            self._apply(v[0])
            return "OK"

        if cmd == "FAN?":
            return "1" if self.fan_on else "0"
        if cmd == "FAN":
            v = self._onoff(arg)
            if v is None:
                return "ERR:ARG"
            self.fan_on = v
            return "OK"

        if cmd == "PID?":
            return f"{self.kp:.5f},{self.ki:.5f},{self.kd:.5f}"
        if cmd == "PID":
            g = self._floats(arg, 3)
            if g is None or min(g) < 0:
                return "ERR:ARG"
            self.kp, self.ki, self.kd = g
            self._pid_reset()
            return "OK"

        if cmd == "SHT:HEAT":
            v = self._onoff(arg)
            if v is None:
                return "ERR:ARG"
            self.heater_on = v
            return "OK"

        if cmd == "STAT?":
            return self.fault
        if cmd == "*CLS":
            self.fault = "OK"
            return "OK"

        return "ERR:UNKNOWN"
