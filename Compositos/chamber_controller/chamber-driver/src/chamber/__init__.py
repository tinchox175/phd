"""Driver for the PANI humidity chamber (Arduino Due, firmware FW0.3).

    from chamber import Chamber
    with Chamber() as ch:
        print(ch.read())

See chamber_commands.txt (next to the firmware) for the underlying protocol.
"""

from .base import SUPPORTED_FIRMWARE, ChamberBase
from .driver import Chamber, find_port
from .errors import (
    ChamberCommandError,
    ChamberConnectionError,
    ChamberError,
    ChamberFault,
    ChamberProtocolError,
    ChamberVersionError,
    StabilityTimeout,
)
from .fake import FakeChamber
from .reading import Reading
from .stability import StabilityMonitor, is_stable

__all__ = [
    "Chamber", "ChamberBase", "FakeChamber", "Reading", "StabilityMonitor", "is_stable",
    "find_port", "SUPPORTED_FIRMWARE",
    "ChamberError", "ChamberConnectionError", "ChamberVersionError", "ChamberProtocolError",
    "ChamberCommandError", "ChamberFault", "StabilityTimeout",
]
__version__ = "0.1.0"
