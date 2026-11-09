"""The real chamber, over USB serial through pyvisa (pyvisa-py backend)."""

from __future__ import annotations

import glob
import os

from .base import ChamberBase
from .errors import ChamberConnectionError

# Linux keeps a stable name for each USB serial device under /dev/serial/by-id/.
BY_ID_PATTERN = "/dev/serial/by-id/*Arduino_Due*"


def find_port() -> str | None:
    """Return the Due's stable /dev/serial/by-id path, if exactly findable."""
    matches = sorted(glob.glob(BY_ID_PATTERN))
    return matches[0] if matches else None


def to_resource(port: str) -> str:
    """Accept a VISA resource name, a Linux device path or a Windows COM name."""
    if port.upper().startswith("ASRL"):
        return port                                   # already a VISA name
    if port.upper().startswith("COM") and port[3:].isdigit():
        return f"ASRL{port[3:]}::INSTR"               # COM5 -> ASRL5::INSTR
    return f"ASRL{port}::INSTR"                       # /dev/... -> ASRL/dev/...::INSTR


class Chamber(ChamberBase):
    """Real chamber.

    Port selection, first match wins: the `port` argument, the CHAMBER_PORT
    environment variable, then auto-detection under /dev/serial/by-id/.
    """

    def __init__(
        self,
        port: str | None = None,
        timeout_s: float = 2.0,
        off_on_close: bool = False,
        visa_library: str = "@py",
    ):
        super().__init__(off_on_close=off_on_close)
        port = port or os.environ.get("CHAMBER_PORT") or find_port()
        if not port:
            raise ChamberConnectionError(
                "No chamber found. Pass port=..., set CHAMBER_PORT, or check the USB cable "
                f"(looked for {BY_ID_PATTERN})."
            )
        self.resource_name = to_resource(port)
        self.timeout_s = timeout_s
        self._visa_library = visa_library
        self._rm = None
        self._inst = None
        self._needs_drain = False

    def _open(self) -> None:
        import pyvisa  # imported here so the fake chamber works without pyvisa

        try:
            self._rm = pyvisa.ResourceManager(self._visa_library)
            self._inst = self._rm.open_resource(
                self.resource_name,
                read_termination="\n",
                write_termination="\n",
                timeout=int(self.timeout_s * 1000),
            )
        except Exception as e:
            self._close()
            raise ChamberConnectionError(f"Can't open {self.resource_name}: {e}") from e
        try:
            self._inst.baud_rate = 115200  # ignored by the Native port, but must not be 1200
        except Exception:
            pass
        self._drain()

    def _close(self) -> None:
        for obj in (self._inst, self._rm):
            if obj is not None:
                try:
                    obj.close()
                except Exception:
                    pass
        self._inst = None
        self._rm = None

    def _drain(self) -> None:
        """Throw away any stale bytes waiting in the input buffer."""
        import pyvisa

        old = self._inst.timeout
        self._inst.timeout = 100  # ms
        try:
            for _ in range(100):
                self._inst.read()
        except pyvisa.errors.VisaIOError:
            pass  # timed out = buffer empty, which is what we want
        finally:
            self._inst.timeout = old
        self._needs_drain = False

    def _transact(self, line: str) -> str:
        import pyvisa

        if self._needs_drain:
            # A previous reply came late; it may still be in the buffer and would
            # otherwise be read as the answer to this command.
            self._drain()
        try:
            return self._inst.query(line).strip()
        except pyvisa.errors.VisaIOError as e:
            self._needs_drain = True
            raise ChamberConnectionError(f"No reply to {line!r} from {self.resource_name}: {e}") from e
