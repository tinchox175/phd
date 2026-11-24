import os
import sys
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from main import IVMeasurementApp


@pytest.fixture(scope="module")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication.instance() or QApplication([])
    yield app


def test_channel2_updates_are_recorded_for_plots_and_text_boxes(qapp):
    window = IVMeasurementApp()
    window._limpiar_datos_graficos()

    window._actualizar_datos(1.0, 0.35, 12.5, 0.65, 18.5, 1.25, False)

    assert window.dual_inst_tab.instant_pane.ip_2_ro.text() == "1.25000"
    assert window.dual_inst_tab.instant_pane.vp_2_ro.text() == "0.65000"
    assert window.dual_inst_tab.instant_pane.rinst_2_ro.text() == "18.50000"
    assert window.data_v_ch2 == [0.65]
    assert window.data_i_ch2 == [1.25]
    assert window.data_t == [1.0]
