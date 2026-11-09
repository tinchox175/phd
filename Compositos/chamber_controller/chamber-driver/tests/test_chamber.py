"""Tests run against FakeChamber, which mirrors the firmware protocol."""

import math

import pytest

from chamber import (
    ChamberCommandError,
    ChamberFault,
    FakeChamber,
    Reading,
    StabilityMonitor,
)
from chamber.cli import main
from chamber.driver import to_resource


@pytest.fixture
def ch():
    with FakeChamber(speedup=0, noise=False, seed=1) as c:   # speedup=0: time moves only via advance()
        yield c


def test_connect_reads_idn(ch):
    assert ch.firmware == "FW0.3"


def test_read_parses_all_fields(ch):
    r = ch.read()
    assert isinstance(r, Reading)
    assert r.ok and not r.control and not r.fan
    assert r.setpoint == 25.0
    assert not math.isnan(r.t_air) and not math.isnan(r.rh)


def test_setpoint_and_range_error(ch):
    ch.set_temperature(30)
    assert ch.temperature_setpoint() == 30.0
    with pytest.raises(ChamberCommandError) as e:
        ch.set_temperature(80)
    assert e.value.code == "ERR:RANGE"


def test_control_reaches_setpoint(ch):
    ch.set_temperature(30)
    ch.control(True)
    ch.advance(3 * 3600)
    r = ch.read()
    assert r.control and abs(r.t_air - 30) < 0.3


def test_manual_output_refused_while_controlling(ch):
    ch.control(True)
    with pytest.raises(ChamberCommandError) as e:
        ch.set_output(0.5)
    assert e.value.code == "ERR:CTRL_ON"
    ch.control(False)
    ch.set_output(0.5)
    assert ch.output() == 0.5


def test_overtemp_fault_latches_and_clears(ch):
    ch.control(True)
    ch.t_air = 60.0
    ch.advance(1)
    r = ch.read()
    assert r.status == "FAULT:OVERTEMP" and not r.control and r.output == 0
    with pytest.raises(ChamberFault):
        ch.read(raise_on_fault=True)
    with pytest.raises(ChamberCommandError):
        ch.control(True)                 # refused while latched
    ch.t_air = 25.0
    ch.clear_fault()
    ch.advance(1)
    assert ch.status() == "OK"


def test_sensor_fault(ch):
    ch.control(True)
    ch.air_sensor_ok = False
    ch.advance(1)
    assert ch.status() == "FAULT:SENSOR"


def test_unknown_command_raises(ch):
    with pytest.raises(ChamberCommandError):
        ch.query("NOPE?")
    assert ch.raw("NOPE?") == "ERR:UNKNOWN"


def test_pid_roundtrip(ch):
    ch.set_pid(0.2, 0.003, 0.0)
    assert ch.pid() == (0.2, 0.003, 0.0)


def test_stability_monitor():
    def rd(t, rh):
        return Reading(t, 25.0, 25.0, rh, 0.0, 25.0, True, True, "OK")

    m = StabilityMonitor(window_s=600, rh_tol=0.5, t_tol=0.1)
    for t in range(0, 300, 5):
        m.add(rd(t, 60.0))
    assert not m.stable                  # not enough history yet
    for t in range(300, 700, 5):
        m.add(rd(t, 60.2))
    assert m.stable
    for t in range(705, 900, 5):
        m.add(rd(t, 60.2 + (t - 700) * 0.01))   # starts drifting 0.6 %/min
    assert not m.stable


def test_stability_ignores_noise():
    import random
    rng = random.Random(0)
    m = StabilityMonitor(window_s=600, rh_tol=0.5, t_tol=0.1)
    for t in range(0, 900, 1):
        m.add(Reading(t, 25.0, 25.0 + rng.gauss(0, 0.02), 60 + rng.gauss(0, 0.15),
                      0.0, 25.0, True, True, "OK"))
    assert m.stable                      # noisy but flat


def test_rh_settles_to_salt_value():
    with FakeChamber(speedup=0, noise=False, salt_rh=75.3, start_rh=40.0) as c:
        c.advance(6 * 3600)
        assert abs(c.read().rh - 75.3) < 0.5


def test_resource_names():
    assert to_resource("/dev/ttyACM0") == "ASRL/dev/ttyACM0::INSTR"
    assert to_resource("COM5") == "ASRL5::INSTR"
    assert to_resource("ASRL3::INSTR") == "ASRL3::INSTR"


def test_cli_status_with_fake(capsys):
    assert main(["--fake", "status"]) == 0
    assert "RH" in capsys.readouterr().out


def test_cli_reports_errors(capsys):
    assert main(["--fake", "set", "99"]) == 1
    assert "ERR:RANGE" in capsys.readouterr().err
