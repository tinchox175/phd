import sys
import os
import csv
import json
import math
import time
import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QHBoxLayout, QVBoxLayout,
    QWidget, QLabel, QGroupBox, QPushButton, QTabWidget,
    QLineEdit, QStatusBar, QFileDialog, QFormLayout,
    QDialogButtonBox, QDialog, QDoubleSpinBox, QComboBox,
    QSpinBox, QCheckBox, QSizePolicy, QGridLayout
)
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt, QTimer

# Importar la Vista (UI) y el Modelo (Hardware)
from IVsuplemento import (
    ParametersPane, InstantPane, ParametrosK224Pane, Lecturas34420APane,
    ParametrosRelajacionPane, TemperaturaTab, ControlEspectroscopiaPane,
    EspectroscopiaTab, PulsosTransientesTab
)
from hardware import (
    HiloMedicionDual, HiloTemperatura, HiloEspectroscopia,
    HiloCorreccionSpot, HiloPulsos
)


class ConfiguracionGeneralDialog(QDialog):
    def __init__(self, config_actual, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuración General")
        self.setModal(True)
        self.resize(420, 360)

        self.config = config_actual
        main_layout = QVBoxLayout(self)
        self.tabs = QTabWidget()

        # --- TAB 1: Seguridad (Governor) ---
        tab_seguridad = QWidget()
        layout_seg = QFormLayout(tab_seguridad)
        self.input_limite = QDoubleSpinBox()
        self.input_limite.setDecimals(3)
        self.input_limite.setRange(0.001, 105.0)
        self.input_limite.setValue(self.config.get("max_current_ma", 105.0))
        self.input_limite.setSuffix(" mA")
        layout_seg.addRow("Corriente Máxima Global:", self.input_limite)
        self.tabs.addTab(tab_seguridad, "Seguridad")

        # --- TAB 2: Valores K224 ---
        tab_k224 = QWidget()
        layout_k224 = QFormLayout(tab_k224)
        k224_conf = self.config.get("k224", {})

        self.def_ancho = QDoubleSpinBox()
        self.def_ancho.setDecimals(3)
        self.def_ancho.setRange(0.001, 100.0)
        self.def_ancho.setValue(k224_conf.get("ancho_pulso", 0.1))
        layout_k224.addRow("Ancho Pulso (s):", self.def_ancho)

        self.def_vlim = QDoubleSpinBox()
        self.def_vlim.setRange(0, 200)
        self.def_vlim.setValue(k224_conf.get("limite_voltaje", 20.0))
        layout_k224.addRow("Límite Voltaje (V):", self.def_vlim)

        self.def_no_off = QCheckBox("Mantener salida encendida (No Output Off)")
        self.def_no_off.setChecked(k224_conf.get("no_output_off", False))
        layout_k224.addRow("Modo Continuo:", self.def_no_off)

        self.def_delta = QCheckBox("Medición Diferencial (±I)")
        self.def_delta.setChecked(k224_conf.get("modo_delta", False))
        layout_k224.addRow("Modo Delta:", self.def_delta)

        self.def_matriz_k224 = QCheckBox("Usar Matriz HP34970A")
        self.def_matriz_k224.setChecked(k224_conf.get("usa_matriz", False))
        layout_k224.addRow("Multicanal Matriz:", self.def_matriz_k224)

        self.def_m_ch1 = QSpinBox()
        self.def_m_ch1.setRange(100, 999)
        self.def_m_ch1.setValue(k224_conf.get("matriz_ch1", 212))
        layout_k224.addRow("Canal Matriz 1:", self.def_m_ch1)

        self.def_m_ch2 = QSpinBox()
        self.def_m_ch2.setRange(100, 999)
        self.def_m_ch2.setValue(k224_conf.get("matriz_ch2", 222))
        layout_k224.addRow("Canal Matriz 2:", self.def_m_ch2)

        self.tabs.addTab(tab_k224, "Keithley 224")

        # --- TAB 3: Valores 34420A ---
        tab_34420a = QWidget()
        layout_34420a = QFormLayout(tab_34420a)
        a34420a_conf = self.config.get("a34420a", {})

        self.def_nplc = QComboBox()
        self.def_nplc.addItems(["0.02", "0.2", "1", "2", "10", "20", "100", "200"])
        self.def_nplc.setCurrentText(a34420a_conf.get("nplc", "2"))
        layout_34420a.addRow("NPLC Default:", self.def_nplc)

        self.def_rango = QComboBox()
        self.def_rango.addItems(["Auto", "1 mV", "10 mV", "100 mV", "1 V", "10 V", "100 V"])
        self.def_rango.setCurrentText(a34420a_conf.get("rango", "10 V"))
        layout_34420a.addRow("Rango Default:", self.def_rango)
        self.tabs.addTab(tab_34420a, "Agilent 34420A")

        # --- TAB 4: Valores TH2832 ---
        tab_th2832 = QWidget()
        layout_th2832 = QFormLayout(tab_th2832)
        th_conf = self.config.get("th2832", {})

        self.th_vac = QDoubleSpinBox()
        self.th_vac.setRange(0.01, 2.0)
        self.th_vac.setValue(th_conf.get("vac", 0.1))
        layout_th2832.addRow("Vac Default (Vrms):", self.th_vac)

        self.th_alc = QCheckBox("ALC Default ON")
        self.th_alc.setChecked(th_conf.get("alc_on", True))
        layout_th2832.addRow("Auto Level Control:", self.th_alc)

        self.th_speed = QComboBox()
        self.th_speed.addItems(["SLOW", "MED", "FAST"])
        self.th_speed.setCurrentText(th_conf.get("speed", "MED"))
        layout_th2832.addRow("Velocidad Default:", self.th_speed)

        self.th_avg = QSpinBox()
        self.th_avg.setRange(1, 255)
        self.th_avg.setValue(th_conf.get("avg", 1))
        layout_th2832.addRow("Promedios Default:", self.th_avg)

        self.th_rsou = QComboBox()
        self.th_rsou.addItems(["100", "30"])
        self.th_rsou.setCurrentText(str(th_conf.get("rsou", "100")))
        layout_th2832.addRow("Rsou Default (Ω):", self.th_rsou)

        self.th_rango = QComboBox()
        self.th_rango.addItems(["AUTO", "3", "10", "30", "100", "300", "1000", "3000", "10000", "30000", "100000"])
        self.th_rango.setCurrentText(th_conf.get("rango", "AUTO"))
        layout_th2832.addRow("Rango Default:", self.th_rango)

        self.th_delay = QDoubleSpinBox()
        self.th_delay.setRange(0.0, 60.0)
        self.th_delay.setValue(th_conf.get("trig_delay", 0.0))
        layout_th2832.addRow("Trigger Delay Default (s):", self.th_delay)

        self.tabs.addTab(tab_th2832, "Tonghui TH2832")

        # --- TAB 5: Valores Pulsos Transientes ---
        tab_pulsos = QWidget()
        layout_pulsos = QFormLayout(tab_pulsos)
        pulsos_conf = self.config.get("pulsos", {})

        self.p_freqs = QLineEdit(pulsos_conf.get("freqs", "1000"))
        layout_pulsos.addRow("Frecuencias (Hz):", self.p_freqs)

        self.p_amps = QLineEdit(pulsos_conf.get("amps", "0.15"))
        layout_pulsos.addRow("Amplitudes (V):", self.p_amps)

        self.p_r_limit = QDoubleSpinBox()
        self.p_r_limit.setRange(1.0, 10000000.0)
        self.p_r_limit.setValue(pulsos_conf.get("r_limit", 10000000.0))
        layout_pulsos.addRow("Resistor Límite (Ω):", self.p_r_limit)

        self.p_v_max = QDoubleSpinBox()
        self.p_v_max.setRange(0.01, 10.0)
        self.p_v_max.setValue(pulsos_conf.get("v_max", 0.4))
        layout_pulsos.addRow("Max Voltaje Seguro (V):", self.p_v_max)

        self.p_forma = QComboBox()
        self.p_forma.addItems(["SQU", "PULS", "RAMP", "SIN"])
        self.p_forma.setCurrentText(pulsos_conf.get("forma", "SQU"))
        layout_pulsos.addRow("Forma de Onda:", self.p_forma)

        self.p_ciclos = QSpinBox()
        self.p_ciclos.setRange(1, 1000)
        self.p_ciclos.setValue(pulsos_conf.get("ciclos", 1))
        layout_pulsos.addRow("Ciclos (Burst):", self.p_ciclos)

        self.p_ancho = QDoubleSpinBox()
        self.p_ancho.setDecimals(9)
        self.p_ancho.setRange(8e-9, 1999.9)
        self.p_ancho.setValue(pulsos_conf.get("ancho", 2000e-9))
        layout_pulsos.addRow("Ancho (s):", self.p_ancho)

        self.p_flanco = QDoubleSpinBox()
        self.p_flanco.setDecimals(9)
        self.p_flanco.setRange(5e-9, 1e-3)
        self.p_flanco.setValue(pulsos_conf.get("flanco", 50e-9))
        layout_pulsos.addRow("Flanco (s):", self.p_flanco)

        self.p_sync = QCheckBox("Cable SYNC Externo")
        self.p_sync.setChecked(pulsos_conf.get("sync", False))
        layout_pulsos.addRow("Sincronización:", self.p_sync)

        self.p_high_res = QCheckBox("Alta Resolución (Osciloscopio)")
        self.p_high_res.setChecked(pulsos_conf.get("high_res", True))
        layout_pulsos.addRow("High Res:", self.p_high_res)

        self.tabs.addTab(tab_pulsos, "Pulsos (Osc+AFG)")

        main_layout.addWidget(self.tabs)

        # --- Botones OK/Cancel ---
        botones = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        main_layout.addWidget(botones)

    def get_config_actualizada(self):
        nueva_config = self.config.copy()
        nueva_config["max_current_ma"] = self.input_limite.value()
        nueva_config["k224"] = {
            "ancho_pulso": self.def_ancho.value(),
            "limite_voltaje": self.def_vlim.value(),
            "no_output_off": self.def_no_off.isChecked(),
            "modo_delta": self.def_delta.isChecked(),
            "usa_matriz": self.def_matriz_k224.isChecked(),
            "matriz_ch1": self.def_m_ch1.value(),
            "matriz_ch2": self.def_m_ch2.value()
        }
        nueva_config["a34420a"] = {
            "nplc": self.def_nplc.currentText(),
            "rango": self.def_rango.currentText()
        }
        nueva_config["th2832"] = {
            "vac": self.th_vac.value(),
            "alc_on": self.th_alc.isChecked(),
            "speed": self.th_speed.currentText(),
            "avg": self.th_avg.value(),
            "rsou": self.th_rsou.currentText(),
            "rango": self.th_rango.currentText(),
            "trig_delay": self.th_delay.value()
        }
        nueva_config["pulsos"] = {
            "freqs": self.p_freqs.text(),
            "amps": self.p_amps.text(),
            "r_limit": self.p_r_limit.value(),
            "v_max": self.p_v_max.value(),
            "forma": self.p_forma.currentText(),
            "ciclos": self.p_ciclos.value(),
            "ancho": self.p_ancho.value(),
            "flanco": self.p_flanco.value(),
            "sync": self.p_sync.isChecked(),
            "high_res": self.p_high_res.isChecked()
        }
        return nueva_config


class SMUControlTab(QWidget):
    """Wrapper para la pestaña del SMU B2902A."""
    def __init__(self):
        super().__init__()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        self.params_pane = ParametersPane()
        self.instant_pane = InstantPane()

        layout.addWidget(self.params_pane, alignment=Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.instant_pane, alignment=Qt.AlignmentFlag.AlignTop)
        self.setLayout(layout)


class DualInstrumentControlTab(QWidget):
    """Wrapper para el setup K224 + A34420A."""
    def __init__(self):
        super().__init__()
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)

        panes_layout = QHBoxLayout()
        self.params_pane = ParametrosK224Pane()
        self.instant_pane = Lecturas34420APane()

        panes_layout.addWidget(self.params_pane, stretch=3, alignment=Qt.AlignmentFlag.AlignTop)
        panes_layout.addWidget(self.instant_pane, stretch=2, alignment=Qt.AlignmentFlag.AlignTop)

        main_layout.addLayout(panes_layout)
        self.setLayout(main_layout)


class RelajacionTab(QWidget):
    """Wrapper para la pestaña de Relajación (K224 + 34420A)."""
    def __init__(self):
        super().__init__()
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)

        panes_layout = QHBoxLayout()
        self.params_pane = ParametrosRelajacionPane()
        self.instant_pane = Lecturas34420APane()

        panes_layout.addWidget(self.params_pane, stretch=3, alignment=Qt.AlignmentFlag.AlignTop)
        panes_layout.addWidget(self.instant_pane, stretch=2, alignment=Qt.AlignmentFlag.AlignTop)

        main_layout.addLayout(panes_layout)
        self.setLayout(main_layout)


class IVMeasurementApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Suite de Medición I-V")
        self.resize(1280, 840)

        self.estado_compartido = {}
        self.archivo_config = "config.json"

        self.config_app = {
            "directorio_defecto": "",
            "max_current_ma": 105.0,
            "k224": {
                "ancho_pulso": 0.1,
                "limite_voltaje": 20.0,
                "no_output_off": False,
                "modo_delta": False,
                "usa_matriz": False,
                "matriz_ch1": 212,
                "matriz_ch2": 222
            },
            "a34420a": {"nplc": "2", "rango": "10 V"},
            "th2832": {
                "vac": 0.1, "alc_on": True, "speed": "MED", "avg": 1,
                "rsou": "100", "rango": "AUTO", "trig_delay": 0.0
            },
            "pulsos": {
                "freqs": "1000", "amps": "0.15", "r_limit": 1000.0, "v_max": 0.4,
                "forma": "SQU", "ciclos": 1, "ancho": 2000e-9, "flanco": 50e-9,
                "sync": False, "high_res": True
            }
        }
        self._cargar_configuracion()
        self.directorio_defecto = self.config_app.get("directorio_defecto", "")

        self.worker = HiloMedicionDual(self.estado_compartido)
        self.worker_temp = HiloTemperatura(self.estado_compartido)
        self.worker_is = HiloEspectroscopia(self.estado_compartido)
        self.worker_pulsos = HiloPulsos(self.estado_compartido)

        self.i_inst = 0.0
        self._limpiar_datos_graficos()
        self._setup_menu()
        self._setup_ui()
        self._setup_connections()

        self._aplicar_gobernador(self.config_app["max_current_ma"])
        self._aplicar_defaults_a_ui()

        QTimer.singleShot(10, lambda: self._al_cambiar_pestana(self.setup_tabs.currentIndex()))

    def _cargar_configuracion(self):
        if os.path.exists(self.archivo_config):
            try:
                with open(self.archivo_config, 'r') as f:
                    cargado = json.load(f)
                    for k, v in cargado.items():
                        if isinstance(v, dict) and k in self.config_app and isinstance(self.config_app[k], dict):
                            self.config_app[k].update(v)
                        else:
                            self.config_app[k] = v
            except Exception as e:
                print(f"Error leyendo config.json: {e}")

    def _guardar_configuracion(self):
        with open(self.archivo_config, 'w') as f:
            json.dump(self.config_app, f, indent=4)

    def _setup_menu(self):
        menu_bar = self.menuBar()
        archivo_menu = menu_bar.addMenu("Archivo")

        self.action_abrir = QAction("Cargar...", self)
        self.action_abrir.triggered.connect(self._cargar_medicion)
        archivo_menu.addAction(self.action_abrir)

        opciones_menu = menu_bar.addMenu("Opciones")
        self.action_configurar_ruta = QAction("Carpeta por Defecto...", self)
        self.action_configurar_ruta.triggered.connect(self._configurar_ruta_defecto)
        opciones_menu.addAction(self.action_configurar_ruta)

        self.action_config = QAction("Configuración General...", self)
        self.action_config.triggered.connect(self._abrir_configuracion)
        opciones_menu.addAction(self.action_config)

    def _abrir_configuracion(self):
        dialog = ConfiguracionGeneralDialog(self.config_app, self)
        if dialog.exec():
            self.config_app = dialog.get_config_actualizada()
            self._guardar_configuracion()

            self._aplicar_gobernador(self.config_app["max_current_ma"])
            self._aplicar_defaults_a_ui()

            self.status_bar.setStyleSheet("color: #2e7d32; font-weight: bold;")
            self.status_bar.showMessage("Configuración guardada y aplicada.", 4000)

    def _aplicar_defaults_a_ui(self):
        p_k224 = self.dual_inst_tab.params_pane
        i_34420 = self.dual_inst_tab.instant_pane
        p_th = self.espectroscopia_tab.params_pane
        p_pulsos = self.pulsos_tab.params_pane

        k224_conf = self.config_app.get("k224", {})
        a34420_conf = self.config_app.get("a34420a", {})
        th_conf = self.config_app.get("th2832", {})
        pulsos_conf = self.config_app.get("pulsos", {})

        p_k224.ancho_pulso.setValue(k224_conf.get("ancho_pulso", 0.1))
        p_k224.limite_voltaje.setValue(k224_conf.get("limite_voltaje", 20.0))
        p_k224.btn_no_off.setChecked(k224_conf.get("no_output_off", False))
        p_k224.btn_delta.setChecked(k224_conf.get("modo_delta", False))
        p_k224.btn_matriz.setChecked(k224_conf.get("usa_matriz", False))
        p_k224.matriz_ch1.setValue(k224_conf.get("matriz_ch1", 212))
        p_k224.matriz_ch2.setValue(k224_conf.get("matriz_ch2", 222))

        i_34420.combo_nplc.setCurrentText(a34420_conf.get("nplc", "2"))
        i_34420.combo_rango.setCurrentText(a34420_conf.get("rango", "10 V"))

        p_th.vac.setValue(th_conf.get("vac", 0.1))
        p_th.chk_alc.setChecked(th_conf.get("alc_on", True))
        p_th.combo_speed.setCurrentText(th_conf.get("speed", "MED"))
        p_th.avg_pts.setValue(th_conf.get("avg", 1))
        p_th.combo_rsou.setCurrentText(str(th_conf.get("rsou", "100")))
        p_th.combo_rango.setCurrentText(th_conf.get("rango", "AUTO"))
        p_th.trig_delay.setValue(th_conf.get("trig_delay", 0.0))

        p_pulsos.freqs.setText(pulsos_conf.get("freqs", "1000"))
        p_pulsos.amps.setText(pulsos_conf.get("amps", "0.15"))
        p_pulsos.r_limit.setValue(pulsos_conf.get("r_limit", 1100000.0))
        p_pulsos.v_max.setValue(pulsos_conf.get("v_max", 0.4))
        p_pulsos.forma.setCurrentText(pulsos_conf.get("forma", "PULS"))
        p_pulsos.ciclos.setValue(pulsos_conf.get("ciclos", 1))
        p_pulsos.ancho.setValue(pulsos_conf.get("ancho", 2000e-9))
        p_pulsos.flanco.setValue(pulsos_conf.get("flanco", 50e-9))
        p_pulsos.chk_sync.setChecked(pulsos_conf.get("sync", False))
        p_pulsos.chk_high_res.setChecked(pulsos_conf.get("high_res", True))

    def _aplicar_gobernador(self, max_ma):
        p_k224 = self.dual_inst_tab.params_pane
        cajas_corriente = [
            p_k224.corr_maxima, p_k224.corr_minima,
            p_k224.corr_inicial, p_k224.corr_bias, p_k224.paso_corr,
            p_k224.offset_ramp
        ]
        for caja in cajas_corriente:
            caja.blockSignals(True)
            caja.setRange(-max_ma, max_ma)
            caja.blockSignals(False)

    def _configurar_ruta_defecto(self):
        directorio = QFileDialog.getExistingDirectory(
            self,
            "Seleccionar Carpeta por Defecto",
            self.directorio_defecto,
            QFileDialog.Option.ShowDirsOnly
        )
        if directorio:
            self.directorio_defecto = directorio
            self.config_app["directorio_defecto"] = directorio
            self._guardar_configuracion()

            self.status_bar.setStyleSheet("color: #0055ff; font-weight: bold;")
            self.status_bar.showMessage(f"Ruta por defecto configurada: {self.directorio_defecto}", 5000)

    def _setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(6)

        # ==========================================
        # FILA SUPERIOR: Pestañas de Control
        # ==========================================
        self.setup_tabs = QTabWidget()
        self.setup_tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

        self.smu_tab = SMUControlTab()
        self.dual_inst_tab = DualInstrumentControlTab()
        self.relajacion_tab = RelajacionTab()
        self.temperatura_tab = TemperaturaTab()
        self.espectroscopia_tab = EspectroscopiaTab()
        self.pulsos_tab = PulsosTransientesTab()

        self.setup_tabs.addTab(self.dual_inst_tab, "Setup: K224 + 34420A")
        self.setup_tabs.addTab(self.pulsos_tab, "Transientes (Osc + AFG)")
        self.setup_tabs.addTab(self.espectroscopia_tab, "Espectroscopía (TH2832)")
        self.setup_tabs.addTab(self.relajacion_tab, "Relajación")
        self.setup_tabs.addTab(self.temperatura_tab, "Temperatura (LakeShore)")
        self.setup_tabs.addTab(self.smu_tab, "Setup: B2902A SMU")

        # ==========================================
        # FILA INFERIOR: Gráficos Globales Expandidos
        # ==========================================
        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')
        pg.setConfigOptions(antialias=True)

        bottom_row_layout = QHBoxLayout()
        bottom_row_layout.setSpacing(6)

        # --- PANELES I-V, RESISTENCIA Y MONITOREO ---
        self.iv_plot_pane = QGroupBox("Gráfico I-V")
        self.iv_plot_pane.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        iv_layout = QVBoxLayout()
        iv_layout.setContentsMargins(4, 6, 4, 4)
        self.iv_plot = pg.PlotWidget(title="Voltaje vs Corriente")
        self._style_plot(self.iv_plot, "Voltaje (V)", "Corriente (mA)")
        self.iv_plot.addLegend()
        self.iv_curve = self.iv_plot.plot(
            symbol='o', width=1, symbolSize=6, symbolBrush=pg.mkBrush('#0055ff'), name="Canal 1"
        )
        self.iv_curve_ch2 = self.iv_plot.plot(
            symbol='s', width=1, symbolSize=6, symbolBrush=pg.mkBrush('#ff5500'), name="Canal 2"
        )
        self.iv_last = self.iv_plot.plot(pen=None, symbol='o', symbolSize=10, symbolBrush='g', symbolPen='k')
        self.iv_last_ch2 = self.iv_plot.plot(pen=None, symbol='s', symbolSize=10, symbolBrush='g', symbolPen='k')
        iv_layout.addWidget(self.iv_plot)
        self.iv_plot_pane.setLayout(iv_layout)
        bottom_row_layout.addWidget(self.iv_plot_pane)

        self.res_plot_pane = QGroupBox("Gráfico Resistencia")
        self.res_plot_pane.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        res_layout = QVBoxLayout()
        res_layout.setContentsMargins(4, 6, 4, 4)
        self.res_plot = pg.PlotWidget(title="Resistencia vs Corriente")
        self._style_plot(self.res_plot, "Corriente (mA)", "Resistencia (Ω)")
        self.res_plot.addLegend()
        self.rinst_curve = self.res_plot.plot(
            pen=pg.mkPen(color='#0055ff', width=1), symbol='o', symbolSize=5, symbolBrush='#0055ff', name="Rinst Ch1"
        )
        self.rinst_curve_ch2 = self.res_plot.plot(
            pen=pg.mkPen(color='#ff5500', width=1), symbol='s', symbolSize=5, symbolBrush='#ff5500', name="Rinst Ch2"
        )
        self.rrem_curve = self.res_plot.plot(
            pen=pg.mkPen(color='#0055ff', width=1, style=Qt.PenStyle.DashLine),
            symbol='o', symbolSize=5, symbolBrush='#0055ff', name="Rrem Ch1"
        )
        self.rrem_curve_ch2 = self.res_plot.plot(
            pen=pg.mkPen(color='#ff5500', width=1, style=Qt.PenStyle.DashLine),
            symbol='s', symbolSize=5, symbolBrush='#ff5500', name="Rrem Ch2"
        )
        self.rinst_last = self.res_plot.plot(pen=None, symbol='o', symbolSize=10, symbolBrush='r', symbolPen='k')
        self.rinst_last_ch2 = self.res_plot.plot(pen=None, symbol='s', symbolSize=10, symbolBrush='r', symbolPen='k')
        self.rrem_last = self.res_plot.plot(pen=None, symbol='o', symbolSize=10, symbolBrush='r', symbolPen='k')
        self.rrem_last_ch2 = self.res_plot.plot(pen=None, symbol='s', symbolSize=10, symbolBrush='r', symbolPen='k')
        res_layout.addWidget(self.res_plot)
        self.res_plot_pane.setLayout(res_layout)
        bottom_row_layout.addWidget(self.res_plot_pane)

        self.vt_plot_pane = QGroupBox("Monitoreo Temporal")
        self.vt_plot_pane.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        vt_layout = QVBoxLayout()
        vt_layout.setContentsMargins(4, 6, 4, 4)
        self.vt_plot = pg.PlotWidget(title="Voltaje vs Tiempo")
        self._style_plot(self.vt_plot, "Tiempo (min)", "Voltaje (V)")
        self.vt_plot.addLegend()
        self.vt_curve = self.vt_plot.plot(pen=pg.mkPen(color='#00aa00', width=2), name="Canal 1")
        self.vt_curve_ch2 = self.vt_plot.plot(pen=pg.mkPen(color='#ff5500', width=2), name="Canal 2")
        vt_layout.addWidget(self.vt_plot)
        self.vt_plot_pane.setLayout(vt_layout)
        bottom_row_layout.addWidget(self.vt_plot_pane)

        # --- PANELES ESPECTROSCOPÍA ---
        self.nyquist_pane = QGroupBox("Gráfico de Nyquist")
        self.nyquist_pane.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        nyq_layout = QVBoxLayout()
        self.nyquist_plot = pg.PlotWidget()
        self.nyquist_plot.setLabel('bottom', "Z' (Real) [Ω]")
        self.nyquist_plot.setLabel('left', "-Z'' (Imaginario) [Ω]")
        self.nyquist_plot.showGrid(x=True, y=True, alpha=0.3)
        self.nyquist_plot.setAspectLocked(True, ratio=1)
        self.nyquist_plot.addLegend()
        nyq_layout.addWidget(self.nyquist_plot)
        self.nyquist_pane.setLayout(nyq_layout)
        bottom_row_layout.addWidget(self.nyquist_pane)
        self.nyquist_pane.hide()

        self.bode_pane = QGroupBox("Gráficos R y X")
        self.bode_pane.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        bode_layout = QVBoxLayout()
        self.bode_widget = pg.GraphicsLayoutWidget()

        self.bode_r_plot = self.bode_widget.addPlot(row=0, col=0)
        self.bode_r_plot.setLogMode(x=True, y=False)
        self.bode_r_plot.setLabel('left', "R [Ω]")
        self.bode_r_plot.showGrid(x=True, y=True, alpha=0.3)
        self.bode_r_plot.addLegend()

        self.bode_x_plot = self.bode_widget.addPlot(row=1, col=0)
        self.bode_x_plot.setLogMode(x=True, y=False)
        self.bode_x_plot.setLabel('left', "X [Ω]")
        self.bode_x_plot.setLabel('bottom', "Frequency [Hz]")
        self.bode_x_plot.showGrid(x=True, y=True, alpha=0.3)
        self.bode_x_plot.addLegend()
        self.bode_x_plot.setXLink(self.bode_r_plot)

        bode_layout.addWidget(self.bode_widget)
        self.bode_pane.setLayout(bode_layout)
        bottom_row_layout.addWidget(self.bode_pane)
        self.bode_pane.hide()

        # --- PANELES TRANSIENTES (PULSOS) ---
        self.pulsos_pane = QWidget()
        self.pulsos_pane.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        pulsos_layout = QGridLayout(self.pulsos_pane)
        pulsos_layout.setContentsMargins(0, 0, 0, 0)
        pulsos_layout.setColumnStretch(0, 10)
        pulsos_layout.setColumnStretch(1, 10)
        pulsos_layout.setRowStretch(0, 10)
        pulsos_layout.setRowStretch(1, 10)
        pulsos_layout.setRowStretch(2, 12)

        self.pt_drive_plot = pg.PlotWidget()
        self._style_plot(self.pt_drive_plot, "Tiempo (ms)", "Amplitud (V)")
        self.pt_drive_plot.addLegend()
        self.pt_ch1_curve = self.pt_drive_plot.plot(pen=pg.mkPen('#1f77b4', width=2), name="CH1 Supply")
        self.pt_ch2_curve = self.pt_drive_plot.plot(pen=pg.mkPen('#ff7f0e', width=2), name="CH2 Resistor")
        pulsos_layout.addWidget(self.pt_drive_plot, 0, 0)

        self.pt_sense_plot = pg.PlotWidget()
        self._style_plot(self.pt_sense_plot, "Tiempo (ms)", "Amplitud (mV)")
        self.pt_sense_plot.addLegend()
        self.pt_ch3_curve = self.pt_sense_plot.plot(pen=pg.mkPen('#2ca02c', width=2), name="CH3 Sense+")
        self.pt_ch4_curve = self.pt_sense_plot.plot(pen=pg.mkPen('#d62728', width=2), name="CH4 Sense-")
        self.pt_sense_plot.setXLink(self.pt_drive_plot)
        pulsos_layout.addWidget(self.pt_sense_plot, 1, 0)

        self.pt_over_plot = pg.PlotWidget()
        self._style_plot(self.pt_over_plot, "Tiempo (ms)", "Drive (V)")
        self.pt_over_plot.setXLink(self.pt_drive_plot)

        self.pt_over_plot.showAxis('right')
        self.pt_over_vb = pg.ViewBox()
        self.pt_over_plot.scene().addItem(self.pt_over_vb)
        self.pt_over_plot.getAxis('right').linkToView(self.pt_over_vb)
        self.pt_over_vb.setXLink(self.pt_over_plot)
        self.pt_over_plot.getAxis('right').setLabel('Sense (mV)')

        def update_views():
            try:
                self.pt_over_vb.setGeometry(self.pt_over_plot.getViewBox().sceneBoundingRect())
                self.pt_over_vb.linkedViewChanged(self.pt_over_plot.getViewBox(), self.pt_over_vb.XAxis)
            except Exception:
                pass

        self.pt_over_plot.getViewBox().sigResized.connect(update_views)

        self.pt_over_plot.addLegend()
        self.pt_over_ch1 = self.pt_over_plot.plot(
            pen=pg.mkPen('#1f77b4', width=2, style=Qt.PenStyle.SolidLine), name="CH1 (V)"
        )
        self.pt_over_ch2 = self.pt_over_plot.plot(
            pen=pg.mkPen('#ff7f0e', width=2, style=Qt.PenStyle.SolidLine), name="CH2 (V)"
        )
        self.pt_over_ch3 = pg.PlotCurveItem(
            pen=pg.mkPen('#2ca02c', width=2, style=Qt.PenStyle.DashLine), name="CH3 (mV)"
        )
        self.pt_over_ch4 = pg.PlotCurveItem(
            pen=pg.mkPen('#d62728', width=2, style=Qt.PenStyle.DashLine), name="CH4 (mV)"
        )
        self.pt_over_vb.addItem(self.pt_over_ch3)
        self.pt_over_vb.addItem(self.pt_over_ch4)

        pulsos_layout.addWidget(self.pt_over_plot, 2, 0)

        self.pt_iv_plot = pg.PlotWidget()
        self._style_plot(self.pt_iv_plot, "4-Wire Voltage Drop (mV)", "Sample Current (µA)")
        self.pt_iv_plot.addLegend()

        self.pt_iv_curve_raw = self.pt_iv_plot.plot(
            pen=pg.mkPen(color=(128, 128, 128, 100), width=1), name="RAW"
        )
        self.pt_iv_curve_filt = self.pt_iv_plot.plot(
            pen=pg.mkPen('#9467bd', width=2), name="Filtered"
        )

        self.pt_iv_plot.addLine(x=0, pen=pg.mkPen('k', width=1))
        self.pt_iv_plot.addLine(y=0, pen=pg.mkPen('k', width=1))

        pulsos_layout.addWidget(self.pt_iv_plot, 0, 1, 3, 1)

        bottom_row_layout.addWidget(self.pulsos_pane)
        self.pulsos_pane.hide()

        # Añadir las dos filas principales (una sola vez) dando stretch=1 a los gráficos
        main_layout.addWidget(self.setup_tabs, stretch=0)
        main_layout.addLayout(bottom_row_layout, stretch=1)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Listo para medir.")

    def _al_cambiar_pestana(self, index):
        """Ajusta dinámicamente la altura superior para maximizar el espacio de gráficos."""
        nombre_pestana = self.setup_tabs.tabText(index)
        es_is = "Espectroscopía" in nombre_pestana
        es_pulsos = "Transientes" in nombre_pestana

        if "K224" in nombre_pestana:
            self.setup_tabs.setMaximumHeight(280)
        elif es_pulsos:
            self.setup_tabs.setMaximumHeight(255)
        elif "Relajación" in nombre_pestana or "B2902A" in nombre_pestana:
            self.setup_tabs.setMaximumHeight(250)
        else:
            # Liberar el límite de altura en Espectroscopía y Temperatura para no aplastar las cajas
            self.setup_tabs.setMaximumHeight(16777215)

        if es_is or es_pulsos:
            self.iv_plot_pane.hide()
            self.res_plot_pane.hide()
            self.vt_plot_pane.hide()
        else:
            self.iv_plot_pane.show()
            self.res_plot_pane.show()
            self.vt_plot_pane.show()

        if es_is:
            self.nyquist_pane.show()
            self.bode_pane.show()
        else:
            self.nyquist_pane.hide()
            self.bode_pane.hide()

        if es_pulsos:
            self.pulsos_pane.show()
        else:
            self.pulsos_pane.hide()

        if nombre_pestana == "Relajación":
            self.res_plot.setLabel('bottom', "Tiempo (min)")
            self.vt_plot.setLabel('left', "Voltaje (V)")
        elif "K224" in nombre_pestana:
            self.res_plot.setLabel('bottom', "Corriente (mA)")
            self.vt_plot.setLabel('left', "Voltaje (V)")
        elif "Temperatura" in nombre_pestana:
            self.res_plot.setLabel('bottom', "Temperatura (K)")
            self.vt_plot.setLabel('left', "Temperatura (K)")

    def _style_plot(self, plot_widget, x_label, y_label):
        plot_widget.setLabel('left', y_label)
        plot_widget.setLabel('bottom', x_label)
        plot_widget.showGrid(x=True, y=True, alpha=0.3)
        plot_widget.setMouseEnabled(x=True, y=True)

    def _setup_connections(self):
        p_pane = self.dual_inst_tab.params_pane
        i_pane = self.dual_inst_tab.instant_pane

        # Botones UI -> Controlador (Modo Triangular K224)
        p_pane.btn_aplicar.clicked.connect(self._sincronizar_parametros)
        p_pane.btn_medir.clicked.connect(self._iniciar_medicion)
        p_pane.btn_detencion.clicked.connect(self._detener_medicion)
        p_pane.btn_pausa_cbias.clicked.connect(self._toggle_pausa_cbias)
        p_pane.btn_pausa_sbias.clicked.connect(self._toggle_pausa_sbias)

        # Coordinación entre Matriz HP34970A y CH2 FRON2 del 34420A
        p_pane.btn_matriz.toggled.connect(self._on_k224_matriz_toggled)
        i_pane.btn_ch2_toggle.toggled.connect(self._on_k224_fron2_toggled)

        # Botones UI -> Controlador (Modo Relajación)
        r_pane = self.relajacion_tab.params_pane
        r_pane.btn_aplicar.clicked.connect(self._sincronizar_parametros)
        r_pane.btn_medir.clicked.connect(self._iniciar_medicion)
        r_pane.btn_detencion.clicked.connect(self._detener_medicion)

        # Señales del Worker Dual -> Controlador
        self.worker.nueva_secuencia.connect(self._preparar_nueva_secuencia)
        self.worker.datos_actualizados.connect(self._actualizar_datos)
        self.worker.paso_invertido.connect(self._invertir_paso)
        self.worker.error_detectado.connect(self._mostrar_error)

        # Validaciones de tiempo (Pestaña K224 + 34420A)
        p_pane.ancho_pulso.valueChanged.connect(self._validar_tiempos)
        i_pane.combo_nplc.currentTextChanged.connect(self._validar_tiempos)
        i_pane.btn_ch2_toggle.toggled.connect(self._validar_tiempos)
        p_pane.btn_delta.toggled.connect(self._validar_tiempos)
        p_pane.btn_matriz.toggled.connect(self._validar_tiempos)
        p_pane.btn_no_off.toggled.connect(self._validar_tiempos)

        # Validaciones de tiempo (Pestaña Relajación)
        r_i_pane = self.relajacion_tab.instant_pane
        r_pane.ancho_lectura.valueChanged.connect(self._validar_tiempos)
        r_i_pane.combo_nplc.currentTextChanged.connect(self._validar_tiempos)
        r_i_pane.btn_ch2_toggle.toggled.connect(self._validar_tiempos)

        # Cambio de pestaña
        self.setup_tabs.currentChanged.connect(self._validar_tiempos)
        self.setup_tabs.currentChanged.connect(self._al_cambiar_pestana)

        # Conexiones de los demás módulos (sin duplicados)
        self._setup_conexiones_temp()
        self._setup_conexiones_is()
        self._setup_conexiones_pulsos()

    def _on_k224_matriz_toggled(self, checked):
        """Habilita las lecturas del Canal 2 al activar la Matriz y evita conflicto con FRON2."""
        i_pane = self.dual_inst_tab.instant_pane
        if checked and i_pane.btn_ch2_toggle.isChecked():
            i_pane.btn_ch2_toggle.blockSignals(True)
            i_pane.btn_ch2_toggle.setChecked(False)
            i_pane._on_ch2_toggle(False)
            i_pane.btn_ch2_toggle.blockSignals(False)
        i_pane.set_ch2_readouts_enabled(checked or i_pane.btn_ch2_toggle.isChecked())

    def _on_k224_fron2_toggled(self, checked):
        """Si se activa FRON2 en el 34420A, desactiva la Matriz para evitar doble ruteo."""
        p_pane = self.dual_inst_tab.params_pane
        i_pane = self.dual_inst_tab.instant_pane
        if checked and p_pane.btn_matriz.isChecked():
            p_pane.btn_matriz.blockSignals(True)
            p_pane.btn_matriz.setChecked(False)
            p_pane._on_matriz_toggle(False)
            p_pane.btn_matriz.blockSignals(False)
        i_pane.set_ch2_readouts_enabled(checked or p_pane.btn_matriz.isChecked())

    # ==========================================
    # MÓDULO: TRANSIENTES (PULSOS)
    # ==========================================
    def _setup_conexiones_pulsos(self):
        p_pane = self.pulsos_tab.params_pane
        p_pane.btn_medir.clicked.connect(self._iniciar_medicion_pulsos)
        p_pane.btn_detencion.clicked.connect(self.worker_pulsos.detener_medicion)
        self.worker_pulsos.datos_pulso.connect(self._actualizar_graficos_pulsos)
        self.worker_pulsos.estado_msg.connect(lambda msg: self.status_bar.showMessage(msg))
        self.worker_pulsos.error_detectado.connect(self._mostrar_error)

        p_pane.ancho.valueChanged.connect(self._validar_limites_pulso)
        p_pane.flanco.valueChanged.connect(self._validar_limites_pulso)
        p_pane.forma.currentTextChanged.connect(self._validar_limites_pulso)
        p_pane.freqs.textChanged.connect(self._validar_limites_pulso)

    def _validar_limites_pulso(self, *args):
        p_pane = self.pulsos_tab.params_pane
        if p_pane.forma.currentText() != "PULS":
            p_pane.lbl_warning_pulsos.setText("")
            return

        ancho = p_pane.ancho.value()
        flanco = p_pane.flanco.value()
        warning_msg = ""

        max_flanco = 0.625 * ancho
        if flanco > max_flanco:
            warning_msg += f"⚠ ALERTA: Flanco supera 62.5% del ancho (Máx: {max_flanco*1e9:.1f} ns). "

        try:
            freqs = [float(x.strip()) for x in p_pane.freqs.text().split(',') if x.strip()]
            if freqs:
                max_freq = max(freqs)
                min_period = 1.0 / max_freq
                if ancho >= min_period:
                    warning_msg += f"⚠ ALERTA: Ancho ({ancho*1000:.1f} ms) supera el período de {max_freq}Hz ({min_period*1000:.2f} ms)."
        except ValueError:
            pass

        p_pane.lbl_warning_pulsos.setText(warning_msg)

    def _iniciar_medicion_pulsos(self):
        if self.worker_pulsos.corriendo:
            return
        p_pane = self.pulsos_tab.params_pane

        try:
            freqs = [float(x.strip()) for x in p_pane.freqs.text().split(',')]
            amps = [float(x.strip()) for x in p_pane.amps.text().split(',')]
        except ValueError:
            self._mostrar_error("Frecuencias o amplitudes inválidas. Use números separados por comas.")
            return

        ruta_inicial = self.directorio_defecto if self.directorio_defecto else ""
        directorio_destino = QFileDialog.getExistingDirectory(
            self, "Seleccionar Directorio Raíz para el Lote", ruta_inicial
        )
        if not directorio_destino:
            return

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        directorio_lote = os.path.join(directorio_destino, f"lote_pulsos_{timestamp}")
        os.makedirs(directorio_lote, exist_ok=True)

        self.estado_compartido.update({
            'frecuencias_pulsos': freqs,
            'amplitudes_pulsos': amps,
            'r_limit': p_pane.r_limit.value(),
            'max_voltage_pulse': p_pane.v_max.value(),
            'wave_shape': p_pane.forma.currentText(),
            'num_cycles': p_pane.ciclos.value(),
            'pulse_width': p_pane.ancho.value(),
            'edge_time': p_pane.flanco.value(),
            'use_sync_cable': p_pane.chk_sync.isChecked(),
            'high_res': p_pane.chk_high_res.isChecked(),
            'ruta_archivo_pulsos': directorio_lote
        })

        for curva in [
            self.pt_ch1_curve, self.pt_ch2_curve, self.pt_ch3_curve, self.pt_ch4_curve,
            self.pt_over_ch1, self.pt_over_ch2, self.pt_over_ch3, self.pt_over_ch4,
            self.pt_iv_curve_raw, self.pt_iv_curve_filt
        ]:
            curva.setData([], [])

        self.worker_pulsos.iniciar_medicion()

    def _actualizar_graficos_pulsos(self, freq, amp, time_axis, v1, v2, v3, v4, v_dut_filt, current_filt):
        time_ms = time_axis * 1e3
        v3_mv = v3 * 1e3
        v4_mv = v4 * 1e3

        self.pt_ch1_curve.setData(time_ms, v1)
        self.pt_ch2_curve.setData(time_ms, v2)
        self.pt_ch3_curve.setData(time_ms, v3_mv)
        self.pt_ch4_curve.setData(time_ms, v4_mv)

        self.pt_over_ch1.setData(time_ms, v1)
        self.pt_over_ch2.setData(time_ms, v2)
        self.pt_over_ch3.setData(time_ms, v3_mv)
        self.pt_over_ch4.setData(time_ms, v4_mv)

        v_dut_raw = (v3 - v4) * 1e3
        r_limit = self.pulsos_tab.params_pane.r_limit.value()
        r_scope = 1e6

        i_total = (v1 - v2) / r_limit
        i_leak2 = v2 / r_scope
        i_leak3 = v3 / r_scope
        current_raw = (i_total - i_leak2 - i_leak3) * 1e6

        self.pt_iv_curve_raw.setData(v_dut_raw, current_raw)
        self.pt_iv_curve_filt.setData(v_dut_filt * 1e3, current_filt * 1e6)

    # ==========================================
    # MÓDULO: TEMPERATURA (LAKESHORE)
    # ==========================================
    def _setup_conexiones_temp(self):
        t_pane = self.temperatura_tab.params_pane
        t_pane.btn_medir.clicked.connect(self._iniciar_medicion_temp)
        t_pane.btn_detencion.clicked.connect(self.worker_temp.detener_medicion)
        t_pane.btn_aplicar.clicked.connect(self._sincronizar_parametros_temp)

        self.worker_temp.datos_temp.connect(self._actualizar_graficos_termodinamicos)
        self.worker_temp.datos_res.connect(self._actualizar_graficos_res_temp)
        self.worker_temp.estado_msg.connect(lambda msg: self.status_bar.showMessage(msg))
        self.worker_temp.error_detectado.connect(self._mostrar_error)

    def _iniciar_medicion_temp(self):
        if self.worker_temp.corriendo:
            return

        t_pane = self.temperatura_tab.params_pane
        i_pane = self.temperatura_tab.instant_pane

        tabla_T = []
        for row in range(t_pane.tabla_pasos.rowCount()):
            tabla_T.append({
                'setpoint': t_pane.tabla_pasos.item(row, 0).text(),
                'rate': t_pane.tabla_pasos.item(row, 1).text(),
                'estable': t_pane.tabla_pasos.item(row, 2).text()
            })

        if not tabla_T:
            self._mostrar_error("La tabla de rampas está vacía.")
            return

        ruta_inicial = self.directorio_defecto
        if ruta_inicial:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            ruta_inicial = os.path.join(ruta_inicial, f"temperatura_{timestamp}")

        ruta_archivo, _ = QFileDialog.getSaveFileName(
            self, "Guardar Rampa de Temperatura", ruta_inicial, "CSV Files (*.csv)"
        )
        if not ruta_archivo:
            return
        if not ruta_archivo.lower().endswith('.csv'):
            ruta_archivo += '.csv'

        self.estado_compartido.update({
            'tabla_T': tabla_T,
            'mhi': t_pane.motor_max.value(),
            'mlo': t_pane.motor_min.value(),
            'tiempo_estabilidad': t_pane.tiempo_estabilidad.value(),
            'i_bias': t_pane.i_bias.value(),
            'vlim': t_pane.vlim.value(),
            'N_stat': t_pane.n_stat.value(),
            'auto_rango_i': t_pane.chk_auto_rango.isChecked(),
            'v_scale_max': t_pane.v_max.value(),
            'v_scale_min': t_pane.v_min.value(),
            'motor_manual': t_pane.chk_motor_manual.isChecked(),
            'motor_v_manual': t_pane.v_motor_manual.value(),
            'ch2_activado': i_pane.btn_ch2_toggle.isChecked(),
            'nplc': i_pane.combo_nplc.currentText(),
            'rango': i_pane.combo_rango.currentText(),
            'ruta_archivo': ruta_archivo
        })

        self.data_t_temp = []
        self.data_T_act = []
        self.data_T_set = []

        self.worker_temp.iniciar_medicion()

    def _sincronizar_parametros_temp(self):
        t_pane = self.temperatura_tab.params_pane
        i_pane = self.temperatura_tab.instant_pane

        nuevo_estado = {
            'mhi': t_pane.motor_max.value(),
            'mlo': t_pane.motor_min.value(),
            'tiempo_estabilidad': t_pane.tiempo_estabilidad.value(),
            'i_bias': t_pane.i_bias.value(),
            'vlim': t_pane.vlim.value(),
            'N_stat': t_pane.n_stat.value(),
            'auto_rango_i': t_pane.chk_auto_rango.isChecked(),
            'v_scale_max': t_pane.v_max.value(),
            'v_scale_min': t_pane.v_min.value(),
            'motor_manual': t_pane.chk_motor_manual.isChecked(),
            'motor_v_manual': t_pane.v_motor_manual.value(),
            'ch2_activado': i_pane.btn_ch2_toggle.isChecked()
        }

        try:
            pid_vals = [float(x.strip()) for x in t_pane.pid_input.text().split(',')]
            if len(pid_vals) == 3:
                nuevo_estado['pid_p'] = pid_vals[0]
                nuevo_estado['pid_i'] = pid_vals[1]
                nuevo_estado['pid_d'] = pid_vals[2]

                if self.worker_temp.corriendo and self.worker_temp.lakeshore.inst:
                    self.worker_temp.lakeshore.set_pid(pid_vals[0], pid_vals[1], pid_vals[2])
        except ValueError:
            pass

        self.estado_compartido.update(nuevo_estado)
        self.status_bar.setStyleSheet("")
        self.status_bar.showMessage("Parámetros de Temperatura actualizados en vivo.", 3000)

    def _actualizar_graficos_termodinamicos(self, t_min, T_act, T_set, pot, v_motor):
        self.data_t_temp.append(t_min)
        self.data_T_act.append(T_act)
        self.data_T_set.append(T_set)

        if "Temperatura" in self.setup_tabs.tabText(self.setup_tabs.currentIndex()):
            self.vt_curve.setData(self.data_t_temp, self.data_T_act)
            self.vt_curve_ch2.setData(self.data_t_temp, self.data_T_set)
            self.vt_plot.setLabel('left', "Temperatura (K)")

    def _actualizar_graficos_res_temp(self, T_act, r1, r2, t_min):
        i_pane = self.temperatura_tab.instant_pane
        i_pane.vp_1_ro.setText(f"{T_act:.2f} K")
        i_pane.rinst_1_ro.setText(f"{r1:.3e}")
        if not math.isnan(r2):
            i_pane.rinst_2_ro.setText(f"{r2:.3e}")
            self.data_rinst_ch2.append(r2)
            self.data_i_rinst_ch2.append(T_act)
            self.rinst_curve_ch2.setData(self.data_i_rinst_ch2, self.data_rinst_ch2)

        self.data_rinst.append(r1)
        self.data_i_rinst.append(T_act)
        self.rinst_curve.setData(self.data_i_rinst, self.data_rinst)
        self.res_plot.setLabel('bottom', "Temperatura (K)")

    # ==========================================
    # MÓDULO: ESPECTROSCOPÍA DE IMPEDANCIA (TH2832)
    # ==========================================
    def _setup_conexiones_is(self):
        pane = self.espectroscopia_tab.params_pane
        pane.btn_medir.clicked.connect(self._iniciar_medicion_is)
        pane.btn_detencion.clicked.connect(self.worker_is.detener_medicion)

        pane.btn_corr_open.clicked.connect(lambda: self._iniciar_correccion("OPEN"))
        pane.btn_corr_short.clicked.connect(lambda: self._iniciar_correccion("SHOR"))

        self.worker_is.datos_is.connect(self._actualizar_graficos_is)
        self.worker_is.estado_msg.connect(lambda msg: self.status_bar.showMessage(msg))
        self.worker_is.error_detectado.connect(self._mostrar_error)

    def _iniciar_correccion(self, tipo):
        pane = self.espectroscopia_tab.params_pane

        lista_freq = []
        for row in range(pane.tabla_freq.rowCount()):
            try:
                f = float(pane.tabla_freq.item(row, 0).text())
                lista_freq.append(f)
            except ValueError:
                pass

        if not lista_freq:
            self._mostrar_error("La tabla de frecuencias está vacía.")
            return

        if len(lista_freq) > 201:
            self.status_bar.showMessage("⚠ Advertencia: El LCR solo soporta 201 puntos. Se truncará la lista.", 5000)

        self.estado_compartido['frecuencias_corr'] = lista_freq

        self.worker_corr = HiloCorreccionSpot(self.estado_compartido, tipo)
        self.worker_corr.progreso.connect(self._actualizar_progreso_corr)
        self.worker_corr.estado_msg.connect(lambda msg: self.status_bar.showMessage(msg))
        self.worker_corr.finalizado.connect(self._finalizar_correccion)
        self.worker_corr.error_detectado.connect(self._mostrar_error)

        pane.btn_corr_open.setEnabled(False)
        pane.btn_corr_short.setEnabled(False)
        pane.btn_medir.setEnabled(False)

        self.worker_corr.start()

    def _actualizar_progreso_corr(self, actual, total, freq):
        self.status_bar.setStyleSheet("color: #0055ff; font-weight: bold;")
        self.status_bar.showMessage(f"Corrigiendo Punto {actual}/{total} ({freq} Hz)... Por favor espere.")

    def _finalizar_correccion(self, mensaje):
        self.status_bar.setStyleSheet("color: #2e7d32; font-weight: bold;")
        self.status_bar.showMessage(mensaje, 6000)

        pane = self.espectroscopia_tab.params_pane
        pane.btn_corr_open.setEnabled(True)
        pane.btn_corr_short.setEnabled(True)
        pane.btn_medir.setEnabled(True)

    def _iniciar_medicion_is(self):
        if self.worker_is.corriendo:
            return

        pane = self.espectroscopia_tab.params_pane

        if pane.chk_vdc_sweep.isChecked():
            lista_vdc = []
            if pane.tabla_vdc.rowCount() == 0:
                self._mostrar_error("La tabla de Vdc está vacía para el barrido.")
                return
            for row in range(pane.tabla_vdc.rowCount()):
                try:
                    v = float(pane.tabla_vdc.item(row, 0).text())
                    lista_vdc.append(v)
                except ValueError:
                    pass
        else:
            lista_vdc = [pane.vdc_fijo.value()]

        lista_freq = []
        if pane.tabla_freq.rowCount() == 0:
            self._mostrar_error("La tabla de frecuencias está vacía.")
            return

        for row in range(pane.tabla_freq.rowCount()):
            try:
                f = float(pane.tabla_freq.item(row, 0).text())
                lista_freq.append(f)
            except ValueError:
                pass

        ruta_inicial = self.directorio_defecto
        if ruta_inicial:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            ruta_inicial = os.path.join(ruta_inicial, f"espectroscopia_{timestamp}")

        ruta_archivo, _ = QFileDialog.getSaveFileName(
            self, "Guardar Espectroscopía", ruta_inicial, "CSV Files (*.csv)"
        )
        if not ruta_archivo:
            return
        if not ruta_archivo.lower().endswith('.csv'):
            ruta_archivo += '.csv'

        self.estado_compartido.update({
            'lista_vdc': lista_vdc,
            'frecuencias': lista_freq,
            'vac': pane.vac.value(),
            'alc_on': pane.chk_alc.isChecked(),
            'speed': pane.combo_speed.currentText(),
            'avg': pane.avg_pts.value(),
            'rsou': int(pane.combo_rsou.currentText()),
            'rango': pane.combo_rango.currentText(),
            'trig_delay': pane.trig_delay.value(),
            'usa_matriz': pane.chk_matriz.isChecked(),
            'matriz_ch1': pane.matriz_ch1.value(),
            'matriz_ch2': pane.matriz_ch2.value(),
            'ruta_archivo_is': ruta_archivo
        })

        self._limpiar_datos_graficos()
        self.worker_is.iniciar_medicion()

    def _actualizar_graficos_is(self, vdc, freq, r1, x1, z1, theta1, r2, x2, z2, theta2, t_min, status):
        if status != 0 and status != -1:
            msg = f"Error Status {status}"
            self.status_bar.setStyleSheet("background-color: #ff9800; color: black; font-weight: bold;")
            self.status_bar.showMessage(f"⚠ ALERTA LCR (Freq: {freq}Hz): {msg}", 4000)
        else:
            self.status_bar.setStyleSheet("")
            self.status_bar.showMessage(f"IS Corriendo: {vdc} Vdc | {freq:.1f} Hz")

        if vdc not in self.data_is:
            self.data_is[vdc] = {'f': [], 'r1': [], 'x1': [], 'r2': [], 'x2': [], 'dr': [], 'dx': []}

            idx = len(self.curvas_is)
            color_base = pg.intColor(idx, hues=9)

            pen_ch1 = pg.mkPen(color=color_base, width=2)
            pen_ch2 = pg.mkPen(color=color_base, width=2, style=Qt.PenStyle.DashLine)
            pen_diff = pg.mkPen(color=color_base, width=2, style=Qt.PenStyle.DotLine)

            self.curvas_is[vdc] = {
                'nyq1': self.nyquist_plot.plot(pen=pen_ch1, symbol='o', symbolSize=5, symbolBrush=color_base, name=f"CH1 {vdc}V"),
                'nyq2': self.nyquist_plot.plot(pen=pen_ch2, symbol='s', symbolSize=5, symbolBrush=color_base, name=f"CH2 {vdc}V"),
                'nyq_diff': self.nyquist_plot.plot(pen=pen_diff, symbol='t', symbolSize=6, symbolBrush=color_base, name=f"ΔZ {vdc}V"),
                'r1': self.bode_r_plot.plot(pen=pen_ch1, name=f"CH1 {vdc}V"),
                'r2': self.bode_r_plot.plot(pen=pen_ch2, name=f"CH2 {vdc}V"),
                'r_diff': self.bode_r_plot.plot(pen=pen_diff, name=f"ΔZ {vdc}V"),
                'x1': self.bode_x_plot.plot(pen=pen_ch1, name=f"CH1 {vdc}V"),
                'x2': self.bode_x_plot.plot(pen=pen_ch2, name=f"CH2 {vdc}V"),
                'x_diff': self.bode_x_plot.plot(pen=pen_diff, name=f"ΔZ {vdc}V"),
            }

        d = self.data_is[vdc]
        d['f'].append(freq)
        d['r1'].append(r1)
        d['x1'].append(x1)

        if not math.isnan(r2):
            d['r2'].append(r2)
            d['x2'].append(x2)
            d['dr'].append(r1 - r2)
            d['dx'].append(x1 - x2)

        c = self.curvas_is[vdc]
        c['nyq1'].setData(d['r1'], [-x for x in d['x1']])
        c['r1'].setData(d['f'], d['r1'])
        c['x1'].setData(d['f'], d['x1'])

        if len(d['r2']) > 0:
            c['nyq2'].setData(d['r2'], [-x for x in d['x2']])
            c['r2'].setData(d['f'], d['r2'])
            c['x2'].setData(d['f'], d['x2'])
            c['nyq_diff'].setData(d['dr'], [-x for x in d['dx']])
            c['r_diff'].setData(d['f'], d['dr'])
            c['x_diff'].setData(d['f'], d['dx'])

    def _limpiar_datos_graficos(self):
        self.data_t, self.data_v, self.data_i = [], [], []
        self.data_t_ch2, self.data_v_ch2, self.data_i_ch2 = [], [], []

        self.data_i_rinst, self.data_rinst, self.data_t_rinst = [], [], []
        self.data_i_rrem, self.data_rrem, self.data_t_rrem = [], [], []

        self.data_i_rinst_ch2, self.data_rinst_ch2, self.data_t_rinst_ch2 = [], [], []
        self.data_i_rrem_ch2, self.data_rrem_ch2, self.data_t_rrem_ch2 = [], [], []

        self.data_t_temp, self.data_T_act, self.data_T_set = [], [], []

        if hasattr(self, 'nyquist_plot'):
            self.nyquist_plot.clear()
            self.bode_r_plot.clear()
            self.bode_x_plot.clear()

        self.data_is = {}
        self.curvas_is = {}

        self.data_pt_t = []
        self.data_pt_v1, self.data_pt_v2 = [], []
        self.data_pt_v3, self.data_pt_v4 = [], []
        self.data_pt_vdut, self.data_pt_idut = [], []

    # ==========================================
    # LÓGICA DE CONTROL I-V Y RELAJACIÓN (K224 + 34420A)
    # ==========================================
    def _validar_tiempos(self, *args):
        """Calcula el límite físico del hardware según NPLC y los modos activos (Delta, Matriz, CH2)."""
        nombre_pestana = self.setup_tabs.tabText(self.setup_tabs.currentIndex())
        es_relajacion = (nombre_pestana == "Relajación")

        if es_relajacion:
            p_pane = self.relajacion_tab.params_pane
            i_pane = self.relajacion_tab.instant_pane
            ancho_input = p_pane.ancho_lectura
            periodo_input = p_pane.periodo
            lbl_warning = p_pane.lbl_warning_tiempo
            modo_delta = False
            usa_matriz = False
        elif "K224" in nombre_pestana:
            p_pane = self.dual_inst_tab.params_pane
            i_pane = self.dual_inst_tab.instant_pane
            ancho_input = p_pane.ancho_pulso
            periodo_input = p_pane.periodo_pulso
            lbl_warning = p_pane.lbl_warning_tiempo
            modo_delta = p_pane.btn_delta.isChecked()
            usa_matriz = p_pane.btn_matriz.isChecked()
        else:
            return

        try:
            nplc = float(i_pane.combo_nplc.currentText())
        except ValueError:
            return

        usa_ch2_fron = i_pane.btn_ch2_toggle.isChecked()
        tiempo_integracion = nplc * 0.02

        # 1. Ancho mínimo por cada sub-pulso de polaridad
        if usa_ch2_fron and not usa_matriz:
            tiempo_minimo_ancho = (tiempo_integracion * 2) + 0.20
        else:
            tiempo_minimo_ancho = tiempo_integracion + 0.10

        ancho_input.blockSignals(True)
        periodo_input.blockSignals(True)

        ancho_input.setMinimum(tiempo_minimo_ancho)
        if ancho_input.value() < tiempo_minimo_ancho:
            ancho_input.setValue(tiempo_minimo_ancho)

        # 2. Período mínimo según cantidad de polaridades (Delta) y canales de Matriz
        ancho_efectivo = ancho_input.value()
        factor_polaridad = 2 if modo_delta else 1
        factor_matriz = 2 if usa_matriz else 1
        overhead_matriz = 0.35 if usa_matriz else 0.05

        tiempo_minimo_periodo = (ancho_efectivo * factor_polaridad * factor_matriz) + overhead_matriz

        periodo_input.setMinimum(tiempo_minimo_periodo)
        if periodo_input.value() < tiempo_minimo_periodo:
            periodo_input.setValue(tiempo_minimo_periodo)

        ancho_input.blockSignals(False)
        periodo_input.blockSignals(False)

        etiquetas_activas = []
        if not es_relajacion and p_pane.btn_no_off.isChecked():
            etiquetas_activas.append("NO-OFF")
        if modo_delta:
            etiquetas_activas.append("DELTA (±I)")
        if usa_matriz:
            etiquetas_activas.append(f"MATRIZ ({p_pane.matriz_ch1.value()}/{p_pane.matriz_ch2.value()})")
        elif usa_ch2_fron:
            etiquetas_activas.append("CH2 (FRON2)")

        if etiquetas_activas:
            modos_str = " + ".join(etiquetas_activas)
            lbl_warning.setText(
                f"⚙ Modos [{modos_str}] -> Ancho mín: {tiempo_minimo_ancho:.2f}s | Período mín: {tiempo_minimo_periodo:.2f}s"
            )
        else:
            lbl_warning.setText(" ")

    def _sincronizar_parametros(self):
        """Lee la UI activa y actualiza el diccionario del hilo."""
        nombre_pestana = self.setup_tabs.tabText(self.setup_tabs.currentIndex())
        es_relajacion = (nombre_pestana == "Relajación")

        if es_relajacion:
            p_pane = self.relajacion_tab.params_pane
            i_pane = self.relajacion_tab.instant_pane

            try:
                lista_pulsos = [float(x.strip()) for x in p_pane.corr_pulso.text().split(',') if x.strip()]
                lista_bias = [float(x.strip()) for x in p_pane.corr_bias.text().split(',') if x.strip()]
            except ValueError:
                self.status_bar.setStyleSheet("background-color: #d32f2f; color: white; font-weight: bold;")
                self.status_bar.showMessage("ERROR: Las matrices deben contener solo números separados por comas.", 5000)
                return False

            nuevo_estado = {
                'modo_relajacion': True,
                'lista_pulsos': lista_pulsos,
                'lista_bias': lista_bias,
                'tiempo_pulso': p_pane.tiempo_pulso.value(),
                'tiempo_descarga': p_pane.tiempo_descarga.value(),
                'relajacion_pulsada': p_pane.btn_pulsado.isChecked(),
                'periodo_relajacion': p_pane.periodo.value(),
                'ancho_lectura': p_pane.ancho_lectura.value(),
                'limite_voltaje': p_pane.limite_voltaje.value(),
                'nplc': i_pane.combo_nplc.currentText(),
                'rango': i_pane.combo_rango.currentText(),
                'ch2_activado': i_pane.btn_ch2_toggle.isChecked(),
                'usa_matriz': False
            }
        else:
            p_pane = self.dual_inst_tab.params_pane
            i_pane = self.dual_inst_tab.instant_pane
            nuevo_estado = {
                'modo_relajacion': False,
                'ancho_pulso': p_pane.ancho_pulso.value(),
                'corr_maxima': p_pane.corr_maxima.value(),
                'corr_inicial': p_pane.corr_inicial.value(),
                'num_mediciones_bias': p_pane.num_mediciones.value(),
                'corr_bias': p_pane.corr_bias.value(),
                'periodo_pulso': p_pane.periodo_pulso.value(),
                'corr_minima': p_pane.corr_minima.value(),
                'paso_corr': p_pane.paso_corr.value(),
                'offset_ramp': p_pane.offset_ramp.value(),
                'limite_voltaje': p_pane.limite_voltaje.value(),
                'no_output_off': p_pane.btn_no_off.isChecked(),
                'modo_delta': p_pane.btn_delta.isChecked(),
                'usa_matriz': p_pane.btn_matriz.isChecked(),
                'matriz_ch1': p_pane.matriz_ch1.value(),
                'matriz_ch2': p_pane.matriz_ch2.value(),
                'nplc': i_pane.combo_nplc.currentText(),
                'rango': i_pane.combo_rango.currentText(),
                'ch2_activado': i_pane.btn_ch2_toggle.isChecked()
            }

        self.estado_compartido.update(nuevo_estado)
        self.status_bar.setStyleSheet("")
        self.status_bar.showMessage(f"Parámetros ({nombre_pestana}) actualizados.", 3000)
        return True

    def _iniciar_medicion(self):
        if self.worker.corriendo:
            self.status_bar.showMessage("La medición ya está en curso.", 3000)
            return

        if not self._sincronizar_parametros():
            return

        ruta_inicial = self.directorio_defecto
        if ruta_inicial:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            ruta_inicial = os.path.join(ruta_inicial, f"medicion_{timestamp}")

        ruta_archivo, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar Medición",
            ruta_inicial,
            "CSV Files (*.csv);;Todos los archivos (*)"
        )

        if not ruta_archivo:
            self.status_bar.showMessage("Medición cancelada (no se seleccionó archivo de destino).", 4000)
            return

        if not ruta_archivo.lower().endswith('.csv'):
            ruta_archivo += '.csv'

        self.estado_compartido['ruta_archivo'] = ruta_archivo

        self._limpiar_datos_graficos()
        for curva in [
            self.iv_curve, self.iv_curve_ch2, self.rinst_curve, self.rinst_curve_ch2,
            self.rrem_curve, self.rrem_curve_ch2, self.vt_curve, self.vt_curve_ch2,
            self.iv_last, self.iv_last_ch2, self.rinst_last, self.rinst_last_ch2,
            self.rrem_last, self.rrem_last_ch2
        ]:
            curva.setData([], [])

        self.status_bar.setStyleSheet("")
        self.status_bar.showMessage(f"Iniciando medición... Guardando en {ruta_archivo}")
        self.worker.iniciar_medicion()

    def _preparar_nueva_secuencia(self, corr_bias, corr_pulso, nombre_archivo):
        self._limpiar_datos_graficos()
        for curva in [
            self.iv_curve, self.iv_curve_ch2, self.rinst_curve, self.rinst_curve_ch2,
            self.rrem_curve, self.rrem_curve_ch2, self.vt_curve, self.vt_curve_ch2
        ]:
            curva.setData([], [])
        self.status_bar.setStyleSheet("")
        self.status_bar.showMessage(
            f"Matriz: Bias {corr_bias}mA | Pulso {corr_pulso}mA -> Guardando en {os.path.basename(nombre_archivo)}"
        )

    def _cargar_medicion(self):
        if self.worker.corriendo or self.worker_is.corriendo or self.worker_temp.corriendo:
            self.status_bar.showMessage("No se puede cargar un archivo mientras se está midiendo.", 4000)
            return

        ruta_archivo, _ = QFileDialog.getOpenFileName(
            self,
            "Cargar Medición",
            self.directorio_defecto,
            "CSV Files (*.csv);;Todos los archivos (*)"
        )

        if not ruta_archivo:
            return

        try:
            self._limpiar_datos_graficos()

            with open(ruta_archivo, 'r', encoding='utf-8') as f:
                lineas_limpias = (line for line in f if not line.startswith('#'))
                reader = csv.DictReader(lineas_limpias)

                for fila in reader:
                    # 1. TRANSIENTES
                    if "Time_s" in fila:
                        self.data_pt_t.append(float(fila["Time_s"]))
                        self.data_pt_v1.append(float(fila["CH1_V_Supply"]))
                        self.data_pt_v2.append(float(fila["CH2_V_Resistor"]))
                        self.data_pt_v3.append(float(fila["CH3_V_SenseP"]))
                        self.data_pt_v4.append(float(fila["CH4_V_SenseN"]))
                        self.data_pt_vdut.append(float(fila["V_Sample_Filt"]))
                        self.data_pt_idut.append(float(fila["I_Sample_Filt"]))
                        continue

                    try:
                        t = float(fila.get("Tiempo (min)", float('nan')))
                        is_smu = False

                        # 2. ESPECTROSCOPÍA DE IMPEDANCIA
                        if "Freq (Hz)" in fila:
                            f_val = float(fila["Freq (Hz)"])
                            vdc = float(fila.get("Vdc (V)", 0.0))

                            if vdc not in self.data_is:
                                self.data_is[vdc] = {
                                    'f': [], 'r1': [], 'x1': [], 'r2': [], 'x2': [], 'dr': [], 'dx': []
                                }

                            d = self.data_is[vdc]

                            if "R_ch1 (Ohm)" in fila:
                                r1 = float(fila["R_ch1 (Ohm)"])
                                x1 = float(fila["X_ch1 (Ohm)"])

                                if not math.isnan(r1):
                                    d['f'].append(f_val)
                                    d['r1'].append(r1)
                                    d['x1'].append(x1)

                                r2_str = fila.get("R_ch2 (Ohm)", "nan")
                                if r2_str.strip() and r2_str.strip().lower() != 'nan':
                                    r2 = float(r2_str)
                                    x2 = float(fila["X_ch2 (Ohm)"])
                                    d['r2'].append(r2)
                                    d['x2'].append(x2)
                                    d['dr'].append(r1 - r2)
                                    d['dx'].append(x1 - x2)

                            elif "R (Ohm)" in fila:
                                r1 = float(fila["R (Ohm)"])
                                x1 = float(fila["X (Ohm)"])
                                if not math.isnan(r1):
                                    d['f'].append(f_val)
                                    d['r1'].append(r1)
                                    d['x1'].append(x1)

                            continue

                        # 3. I-V / RELAJACIÓN (K224 + 34420A)
                        elif "I pulso (mA)" in fila:
                            i_inst = float(fila["I pulso (mA)"])
                            r1_inst = float(fila["Rinst 1 (Ohm)"])
                            r2_inst = float(fila.get("Rinst 2 (Ohm)", float('nan')))

                        # 4. I-V (Formato B2902A SMU)
                        elif "I pulso(mA)" in fila:
                            is_smu = True
                            i_inst = float(fila["Iinst 1 (mA)"])
                            r1_inst = float(fila["Rinst 1(Ohm)"])
                            r2_inst = float(fila.get("Rinst 2(Ohm)", float('nan')))

                        else:
                            continue

                        v1_inst = float(fila.get("Vinst 1 (V)", float('nan')))
                        r1_bias = float(fila.get("Rrem 1 (Ohm)", float('nan')))
                        v2_inst = float(fila.get("Vinst 2 (V)", float('nan')))
                        r2_bias = float(fila.get("Rrem 2 (Ohm)", float('nan')))

                        if is_smu:
                            if abs(v2_inst) > 1e30:
                                v2_inst = float('nan')
                            if abs(r2_inst) > 1e30:
                                r2_inst = float('nan')
                            if abs(r2_bias) > 1e30:
                                r2_bias = float('nan')

                    except ValueError:
                        continue

                    if not math.isnan(t) and not math.isnan(i_inst):
                        self.data_t.append(t)
                        self.data_i.append(i_inst)
                        self.data_v.append(v1_inst)

                    if not math.isnan(r1_inst):
                        self.data_i_rinst.append(i_inst)
                        self.data_rinst.append(r1_inst)

                    if not math.isnan(r1_bias):
                        self.data_i_rrem.append(i_inst)
                        self.data_rrem.append(r1_bias)

                    if not math.isnan(v2_inst):
                        self.data_t_ch2.append(t)
                        self.data_v_ch2.append(v2_inst)
                        self.data_i_ch2.append(i_inst)

                    if not math.isnan(r2_inst):
                        self.data_i_rinst_ch2.append(i_inst)
                        self.data_rinst_ch2.append(r2_inst)

                    if not math.isnan(r2_bias):
                        self.data_i_rrem_ch2.append(i_inst)
                        self.data_rrem_ch2.append(r2_bias)

            # Renderizar Gráficos I-V
            self.iv_curve.setData(self.data_v, self.data_i)
            self.vt_curve.setData(self.data_t, self.data_v)
            self.rinst_curve.setData(self.data_i_rinst, self.data_rinst)
            self.rrem_curve.setData(self.data_i_rrem, self.data_rrem)

            self.iv_curve_ch2.setData(self.data_v_ch2, self.data_i_ch2)
            self.vt_curve_ch2.setData(self.data_t_ch2, self.data_v_ch2)
            self.rinst_curve_ch2.setData(self.data_i_rinst_ch2, self.data_rinst_ch2)
            self.rrem_curve_ch2.setData(self.data_i_rrem_ch2, self.data_rrem_ch2)

            # Renderizar Gráficos de Espectroscopía
            for i, (vdc, d) in enumerate(self.data_is.items()):
                color_base = pg.intColor(i, hues=9)
                pen_ch1 = pg.mkPen(color=color_base, width=2)
                pen_ch2 = pg.mkPen(color=color_base, width=2, style=Qt.PenStyle.DashLine)
                pen_diff = pg.mkPen(color=color_base, width=2, style=Qt.PenStyle.DotLine)

                self.curvas_is[vdc] = {
                    'nyq1': self.nyquist_plot.plot(pen=pen_ch1, symbol='o', symbolSize=5, symbolBrush=color_base, name=f"CH1 {vdc}V"),
                    'nyq2': self.nyquist_plot.plot(pen=pen_ch2, symbol='s', symbolSize=5, symbolBrush=color_base, name=f"CH2 {vdc}V"),
                    'nyq_diff': self.nyquist_plot.plot(pen=pen_diff, symbol='t', symbolSize=6, symbolBrush=color_base, name=f"ΔZ {vdc}V"),
                    'r1': self.bode_r_plot.plot(pen=pen_ch1, name=f"CH1 {vdc}V"),
                    'r2': self.bode_r_plot.plot(pen=pen_ch2, name=f"CH2 {vdc}V"),
                    'r_diff': self.bode_r_plot.plot(pen=pen_diff, name=f"ΔZ {vdc}V"),
                    'x1': self.bode_x_plot.plot(pen=pen_ch1, name=f"CH1 {vdc}V"),
                    'x2': self.bode_x_plot.plot(pen=pen_ch2, name=f"CH2 {vdc}V"),
                    'x_diff': self.bode_x_plot.plot(pen=pen_diff, name=f"ΔZ {vdc}V"),
                }

                c = self.curvas_is[vdc]
                c['nyq1'].setData(d['r1'], [-x for x in d['x1']])
                c['r1'].setData(d['f'], d['r1'])
                c['x1'].setData(d['f'], d['x1'])

                if len(d['r2']) > 0:
                    c['nyq2'].setData(d['r2'], [-x for x in d['x2']])
                    c['r2'].setData(d['f'], d['r2'])
                    c['x2'].setData(d['f'], d['x2'])
                    c['nyq_diff'].setData(d['dr'], [-x for x in d['dx']])
                    c['r_diff'].setData(d['f'], d['dr'])
                    c['x_diff'].setData(d['f'], d['dx'])

            # Renderizar Gráficos de Transientes
            if self.data_pt_t:
                t_ms = np.array(self.data_pt_t) * 1e3
                v1_arr = np.array(self.data_pt_v1)
                v2_arr = np.array(self.data_pt_v2)
                v3_mv = np.array(self.data_pt_v3) * 1e3
                v4_mv = np.array(self.data_pt_v4) * 1e3

                self.pt_ch1_curve.setData(t_ms, v1_arr)
                self.pt_ch2_curve.setData(t_ms, v2_arr)
                self.pt_ch3_curve.setData(t_ms, v3_mv)
                self.pt_ch4_curve.setData(t_ms, v4_mv)

                self.pt_over_ch1.setData(t_ms, v1_arr)
                self.pt_over_ch2.setData(t_ms, v2_arr)
                self.pt_over_ch3.setData(t_ms, v3_mv)
                self.pt_over_ch4.setData(t_ms, v4_mv)

                self.pt_iv_curve_filt.setData(
                    np.array(self.data_pt_vdut) * 1e3, np.array(self.data_pt_idut) * 1e6
                )

                v3_raw = np.array(self.data_pt_v3)
                v4_raw = np.array(self.data_pt_v4)
                v_dut_raw = (v3_raw - v4_raw) * 1e3

                r_limit = self.pulsos_tab.params_pane.r_limit.value()
                r_scope = 1e6

                i_total = (v1_arr - v2_arr) / r_limit
                i_leak2 = v2_arr / r_scope
                i_leak3 = v3_raw / r_scope
                i_dut_raw = (i_total - i_leak2 - i_leak3) * 1e6

                self.pt_iv_curve_raw.setData(v_dut_raw, i_dut_raw)
                self.setup_tabs.setCurrentWidget(self.pulsos_tab)

            for marcador in [
                self.iv_last, self.iv_last_ch2, self.rinst_last,
                self.rinst_last_ch2, self.rrem_last, self.rrem_last_ch2
            ]:
                marcador.setData([], [])

            self.status_bar.setStyleSheet("color: #2e7d32; font-weight: bold;")
            self.status_bar.showMessage(f"Archivo cargado exitosamente: {ruta_archivo}", 5000)

        except Exception as e:
            self._mostrar_error(f"Error al leer el archivo: {str(e)}")

    def _detener_medicion(self):
        if not self.worker.corriendo:
            return
        self.worker.detener_medicion()
        self.status_bar.setStyleSheet("")
        self.status_bar.showMessage("Medición detenida por el usuario.", 5000)

    def _toggle_pausa_cbias(self):
        if not self.worker.corriendo:
            return
        self.worker.pausado_cbias = not self.worker.pausado_cbias
        self.worker.pausado_sbias = False
        msg = "Pausado (CON Bias)" if self.worker.pausado_cbias else "Reanudando..."
        self.status_bar.setStyleSheet("")
        self.status_bar.showMessage(msg, 3000)

    def _toggle_pausa_sbias(self):
        if not self.worker.corriendo:
            return
        self.worker.pausado_sbias = not self.worker.pausado_sbias
        self.worker.pausado_cbias = False
        msg = "Pausado (SIN Bias)" if self.worker.pausado_sbias else "Reanudando..."
        self.status_bar.setStyleSheet("")
        self.status_bar.showMessage(msg, 3000)

    def _invertir_paso(self, nuevo_paso):
        self.dual_inst_tab.params_pane.paso_corr.blockSignals(True)
        self.dual_inst_tab.params_pane.paso_corr.setValue(nuevo_paso)
        self.dual_inst_tab.params_pane.paso_corr.blockSignals(False)

    def _mostrar_error(self, mensaje):
        self.status_bar.setStyleSheet("background-color: #d32f2f; color: white; font-weight: bold;")
        self.status_bar.showMessage(f"ERROR: {mensaje}")

    def _actualizar_datos(self, t_min, v1, r1, v2, r2, i_app, es_bias):
        """Actualiza los indicadores numéricos y los gráficos en tiempo real."""
        es_relajacion = self.estado_compartido.get('modo_relajacion', False)

        p_pane = self.dual_inst_tab.params_pane
        i_pane = self.relajacion_tab.instant_pane if es_relajacion else self.dual_inst_tab.instant_pane

        if not es_relajacion:
            p_pane.corr_actual_ro.setText(f"{i_app:.5f}")

        def safe_format(val):
            return "NaN" if math.isnan(val) else f"{val:.5f}"

        # 1. Actualizar Cajas de Lectura Instantánea
        if not es_bias:
            i_pane.ip_1_ro.setText(f"{i_app:.5f}")
            i_pane.vp_1_ro.setText(safe_format(v1))
            i_pane.rinst_1_ro.setText(safe_format(r1))
            i_pane.ip_2_ro.setText(f"{i_app:.5f}")
            i_pane.vp_2_ro.setText(safe_format(v2))
            i_pane.rinst_2_ro.setText(safe_format(r2))
        else:
            i_pane.ib_1_ro.setText(f"{i_app:.5f}")
            i_pane.vb_1_ro.setText(safe_format(v1))
            i_pane.rrem_1_ro.setText(safe_format(r1))
            i_pane.ib_2_ro.setText(f"{i_app:.5f}")
            i_pane.vb_2_ro.setText(safe_format(v2))
            i_pane.rrem_2_ro.setText(safe_format(r2))

        # 2. Actualizar Gráficos
        if not es_bias:
            self.data_t.append(t_min)
            self.data_v.append(v1)
            self.data_i.append(i_app)
            self.iv_curve.setData(self.data_v, self.data_i)
            self.vt_curve.setData(self.data_t, self.data_v)

            self.iv_last.setData([v1], [i_app])
            self.i_inst = i_app

            if not math.isnan(r1):
                self.data_i_rinst.append(i_app)
                self.data_t_rinst.append(t_min)
                self.data_rinst.append(r1)

                x_data = self.data_t_rinst if es_relajacion else self.data_i_rinst
                self.rinst_curve.setData(x_data, self.data_rinst)
                self.rinst_last.setData([x_data[-1]], [r1])

            if not math.isnan(v2):
                self.data_t_ch2.append(t_min)
                self.data_v_ch2.append(v2)
                self.data_i_ch2.append(i_app)
                self.iv_curve_ch2.setData(self.data_v_ch2, self.data_i_ch2)
                self.vt_curve_ch2.setData(self.data_t_ch2, self.data_v_ch2)
                self.iv_last_ch2.setData([v2], [i_app])

            if not math.isnan(r2):
                self.data_i_rinst_ch2.append(i_app)
                self.data_t_rinst_ch2.append(t_min)
                self.data_rinst_ch2.append(r2)

                x_data_ch2 = self.data_t_rinst_ch2 if es_relajacion else self.data_i_rinst_ch2
                self.rinst_curve_ch2.setData(x_data_ch2, self.data_rinst_ch2)
                self.rinst_last_ch2.setData([x_data_ch2[-1]], [r2])

        else:
            if not math.isnan(r1):
                self.data_i_rrem.append(self.i_inst)
                self.data_t_rrem.append(t_min)
                self.data_rrem.append(r1)

                x_data_bias = self.data_t_rrem if es_relajacion else self.data_i_rrem
                self.rrem_curve.setData(x_data_bias, self.data_rrem)
                self.rrem_last.setData([x_data_bias[-1]], [r1])

            if not math.isnan(r2):
                self.data_i_rrem_ch2.append(self.i_inst)
                self.data_t_rrem_ch2.append(t_min)
                self.data_rrem_ch2.append(r2)

                x_data_bias_ch2 = self.data_t_rrem_ch2 if es_relajacion else self.data_i_rrem_ch2
                self.rrem_curve_ch2.setData(x_data_bias_ch2, self.data_rrem_ch2)
                self.rrem_last_ch2.setData([x_data_bias_ch2[-1]], [r2])


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = IVMeasurementApp()
    window.show()
    sys.exit(app.exec())