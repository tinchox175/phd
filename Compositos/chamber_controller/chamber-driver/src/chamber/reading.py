"""One snapshot of the chamber state, as returned by MEAS?."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import ClassVar

from .errors import ChamberProtocolError


@dataclass(frozen=True)
class Reading:
    """Chamber state at one moment.

    Temperatures and RH are NaN when the sensor had no valid value.
    `time` is the PC's clock (Unix seconds) when the reply arrived, so chamber
    data can be lined up with other instruments read by the same PC.
    """

    time: float      # Unix time on the PC, seconds
    t_air: float     # box-air temperature, degC (DS18B20, the controlled one)
    t_jar: float     # jar temperature, degC (SHT30)
    rh: float        # jar relative humidity, % (SHT30)
    output: float    # TEC drive, -1 (full cooling) .. +1 (full heating)
    setpoint: float  # box-air target, degC
    control: bool    # automatic temperature control running
    fan: bool        # jar fan on
    status: str      # "OK" or "FAULT:..."

    FIELDS: ClassVar[tuple[str, ...]] = (
        "time", "t_air", "t_jar", "rh", "output", "setpoint", "control", "fan", "status",
    )

    @property
    def ok(self) -> bool:
        """True when no fault is latched."""
        return self.status == "OK"

    @property
    def has_climate(self) -> bool:
        """True when jar temperature and RH are both valid numbers."""
        return not (math.isnan(self.t_jar) or math.isnan(self.rh))

    def as_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def parse(cls, line: str, time: float) -> Reading:
        """Build a Reading from a MEAS? reply line."""
        parts = line.strip().split(",")
        if len(parts) != 8:
            raise ChamberProtocolError(f"MEAS? reply should have 8 fields, got {len(parts)}: {line!r}")
        try:
            return cls(
                time=time,
                t_air=float(parts[0]),     # float("NAN") gives nan
                t_jar=float(parts[1]),
                rh=float(parts[2]),
                output=float(parts[3]),
                setpoint=float(parts[4]),
                control=parts[5] == "1",
                fan=parts[6] == "1",
                status=parts[7],
            )
        except ValueError as e:
            raise ChamberProtocolError(f"Unreadable MEAS? reply: {line!r}") from e
