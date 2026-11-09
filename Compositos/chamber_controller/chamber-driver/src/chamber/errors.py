"""Exceptions raised by the chamber driver.

Everything derives from ChamberError, so callers that don't care about the
details can catch that one class.
"""


class ChamberError(Exception):
    """Base class for all chamber errors."""


class ChamberConnectionError(ChamberError):
    """The port can't be opened, or the chamber stopped answering."""


class ChamberVersionError(ChamberError):
    """The device answered *IDN? with something this driver doesn't support."""


class ChamberProtocolError(ChamberError):
    """The chamber sent a reply in an unexpected format."""


class ChamberCommandError(ChamberError):
    """The chamber rejected a command with an ERR:... reply."""

    def __init__(self, command: str, code: str):
        self.command = command
        self.code = code  # e.g. "ERR:RANGE"
        super().__init__(f"{command!r} rejected by chamber: {code}")


class ChamberFault(ChamberError):
    """The chamber reports a latched safety fault (TEC is off until cleared)."""

    def __init__(self, status: str):
        self.status = status  # e.g. "FAULT:OVERTEMP"
        super().__init__(f"chamber fault: {status} (fix the cause, then clear_fault())")


class StabilityTimeout(ChamberError):
    """wait_until_stable() gave up before the chamber settled."""
