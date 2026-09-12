import sys
import math
import csv
import os
from PySide6.QtWidgets import (QApplication, QMainWindow, QHBoxLayout, QVBoxLayout, 
                               QWidget, QLabel, QGroupBox, QPushButton, QTabWidget, 
                               QLineEdit, QMessageBox, QStatusBar, QFileDialog,
                               QFormLayout, QDialogButtonBox, QDialog, QDoubleSpinBox,
                               QComboBox, QSpinBox, QCheckBox, QSizePolicy, QGridLayout)
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt, QTimer
import pyqtgraph as pg
import json

# Import the View (UI) and Model (Hardware)
from IVsuplemento import (ParametersPane, InstantPane, ParametrosK224Pane, Lecturas34420APane, 
                          ParametrosRelajacionPane, TemperaturaTab, ControlEspectroscopiaPane, 
                          EspectroscopiaTab, PulsosTransientesTab)

from hardware import HiloMedicionDual, HiloTemperatura, HiloEspectroscopia, HiloCorreccionSpot, HiloPulsos
class ConfiguracionGeneralDialog(QDialog):
    def __init__(self, config_actual, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuración General")
        self.setModal(True)
        self.resize(400, 300)
        
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
        self.def_ancho.setValue(k224_conf.get("ancho_pulso", 0.1))
        layout_k224.addRow("Ancho Pulso (s):", self.def_ancho)
        
        self.def_vlim = QDoubleSpinBox()
        self.def_vlim.setRange(0, 200)
        self.def_vlim.setValue(k224_conf.get("limite_voltaje", 20.0))
        layout_k224.addRow("Límite Voltaje (V):", self.def_vlim)
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
        
        main_layout.addWidget(self.tabs)
        
        # --- Botones OK/Cancel ---
        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        main_layout.addWidget(botones)
        
    def get_config_actualizada(self):
        nueva_config = self.config.copy()
        nueva_config["max_current_ma"] = self.input_limite.value()
        nueva_config["k224"] = {
            "ancho_pulso": self.def_ancho.value(),
            "limite_voltaje": self.def_vlim.value()
        }
        nueva_config["a34420a"] = {
            "nplc": self.def_nplc.currentText(),
            "rango": self.def_rango.currentText()
        }
        # <-- AÑADIR ESTO -->
        nueva_config["th2832"] = {
            "vac": self.th_vac.value(),
            "alc_on": self.th_alc.isChecked(),
            "speed": self.th_speed.currentText(),
            "avg": self.th_avg.value(),
            "rsou": self.th_rsou.currentText(),
            "rango": self.th_rango.currentText(),
            "trig_delay": self.th_delay.value()
        }
        return nueva_config

class SMUControlTab(QWidget):
    """Wrapper for the B2902A SMU layout."""
    def __init__(self):
        super().__init__()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.params_pane = ParametersPane()
        self.instant_pane = InstantPane()
        
        layout.addWidget(self.params_pane)
        layout.addWidget(self.instant_pane)
        layout.addStretch()
        self.setLayout(layout)

class DualInstrumentControlTab(QWidget):
    """Wrapper for the K224 + A34420A layout."""
    def __init__(self):
        super().__init__()
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)

        # Paneles principales
        panes_layout = QHBoxLayout()
        self.params_pane = ParametrosK224Pane()
        self.instant_pane = Lecturas34420APane()
        
        panes_layout.addWidget(self.params_pane, alignment=Qt.AlignmentFlag.AlignTop)
        panes_layout.addWidget(self.instant_pane, alignment=Qt.AlignmentFlag.AlignTop)
        panes_layout.addStretch()
        
        main_layout.addLayout(panes_layout)
        self.setLayout(main_layout)

class RelajacionTab(QWidget):
    """Wrapper para la pestaña de prueba de Relajación (K224 + 34420A)."""
    def __init__(self):
        super().__init__()
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)

        panes_layout = QHBoxLayout()
        self.params_pane = ParametrosRelajacionPane()
        self.instant_pane = Lecturas34420APane() # Reutilizamos el panel del voltímetro
        
        panes_layout.addWidget(self.params_pane, alignment=Qt.AlignmentFlag.AlignTop)
        panes_layout.addWidget(self.instant_pane, alignment=Qt.AlignmentFlag.AlignTop)
        panes_layout.addStretch()
        
        main_layout.addLayout(panes_layout)
        self.setLayout(main_layout)

class IVMeasurementApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Suite de Medición I-V")
        self.resize(1200, 800)
        
        self.estado_compartido = {}
        self.archivo_config = "config.json"
        
        # Diccionario base por si el JSON no existe
        # Diccionario base por si el JSON no existe
        self.config_app = {
            "directorio_defecto": "",
            "max_current_ma": 105.0,
            "k224": {"ancho_pulso": 0.1, "limite_voltaje": 20.0},
            "a34420a": {"nplc": "2", "rango": "10 V"},
            "th2832": {"vac": 0.1, "alc_on": True, "speed": "MED", "avg": 1, "rsou": "100", "rango": "AUTO", "trig_delay": 0.0} 
        }
        self._cargar_configuracion()
        
        # --- AÑADIR ESTA LÍNEA AQUÍ ---
        self.directorio_defecto = self.config_app.get("directorio_defecto", "")

        self.worker = HiloMedicionDual(self.estado_compartido)
        self.worker_temp = HiloTemperatura(self.estado_compartido) 
        self.worker_is = HiloEspectroscopia(self.estado_compartido) # <-- NUEVO
        self.worker_pulsos = HiloPulsos(self.estado_compartido)

        self._limpiar_datos_graficos()
        self._setup_menu()
        self._setup_ui()
        self._setup_connections()
        
        # Aplicar los defaults a la UI inmediatamente al arrancar
        self._aplicar_gobernador(self.config_app["max_current_ma"])
        self._aplicar_defaults_a_ui()
        # SOLUCIÓN BUG DE INICIO: Esperar a que la ventana exista físicamente 
        # antes de intentar ocultar los gráficos base.
        QTimer.singleShot(10, lambda: self._al_cambiar_pestana(self.setup_tabs.currentIndex()))

    def _cargar_configuracion(self):
        if os.path.exists(self.archivo_config):
            try:
                with open(self.archivo_config, 'r') as f:
                    # Actualiza el diccionario base con lo que encuentre en el archivo
                    self.config_app.update(json.load(f)) 
            except Exception as e:
                print(f"Error leyendo config.json: {e}")

    def _guardar_configuracion(self):
        with open(self.archivo_config, 'w') as f:
            json.dump(self.config_app, f, indent=4)

    # Reemplaza tu _setup_menu() existente
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
        """Despliega la ventana modal de ajustes."""
        dialog = ConfiguracionGeneralDialog(self.config_app, self)
        if dialog.exec(): # Si el usuario presiona OK
            self.config_app = dialog.get_config_actualizada()
            self._guardar_configuracion()
            
            # Forzar actualización inmediata en la UI
            self._aplicar_gobernador(self.config_app["max_current_ma"])
            self._aplicar_defaults_a_ui()
            
            self.status_bar.setStyleSheet("color: #2e7d32; font-weight: bold;")
            self.status_bar.showMessage("Configuración guardada y aplicada.", 4000)

    def _aplicar_defaults_a_ui(self):
        p_k224 = self.dual_inst_tab.params_pane
        i_34420 = self.dual_inst_tab.instant_pane
        p_th = self.espectroscopia_tab.params_pane # <-- Referencia a TH2832
        
        k224_conf = self.config_app.get("k224", {})
        a34420_conf = self.config_app.get("a34420a", {})
        th_conf = self.config_app.get("th2832", {}) # <-- Recuperar
        
        p_k224.ancho_pulso.setValue(k224_conf.get("ancho_pulso", 0.1))
        p_k224.limite_voltaje.setValue(k224_conf.get("limite_voltaje", 20.0))
        
        i_34420.combo_nplc.setCurrentText(a34420_conf.get("nplc", "2"))
        i_34420.combo_rango.setCurrentText(a34420_conf.get("rango", "10 V"))

        # <-- APLICAR TH2832 -->
        p_th.vac.setValue(th_conf.get("vac", 0.1))
        p_th.chk_alc.setChecked(th_conf.get("alc_on", True))
        p_th.combo_speed.setCurrentText(th_conf.get("speed", "MED"))
        p_th.avg_pts.setValue(th_conf.get("avg", 1))
        p_th.combo_rsou.setCurrentText(str(th_conf.get("rsou", "100")))
        p_th.combo_rango.setCurrentText(th_conf.get("rango", "AUTO"))
        p_th.trig_delay.setValue(th_conf.get("trig_delay", 0.0))

    def _aplicar_gobernador(self, max_ma):
        """Bloquea los rangos máximos de las cajas de corriente."""
        p_k224 = self.dual_inst_tab.params_pane
        cajas_corriente = [
            p_k224.corr_maxima, p_k224.corr_minima, 
            p_k224.corr_inicial, p_k224.corr_bias, p_k224.paso_corr
        ]
        
        for caja in cajas_corriente:
            caja.blockSignals(True)
            caja.setRange(-max_ma, max_ma)
            caja.blockSignals(False)

    def _configurar_ruta_defecto(self):
        """Abre un diálogo para seleccionar la carpeta por defecto para guardar archivos."""
        directorio = QFileDialog.getExistingDirectory(
            self,
            "Seleccionar Carpeta por Defecto",
            self.directorio_defecto,
            QFileDialog.Option.ShowDirsOnly
        )
        
        if directorio:
            self.directorio_defecto = directorio
            
            # --- AÑADIR ESTAS DOS LÍNEAS ---
            self.config_app["directorio_defecto"] = directorio
            self._guardar_configuracion()
            # -------------------------------
            
            self.status_bar.setStyleSheet("color: #0055ff; font-weight: bold;")
            self.status_bar.showMessage(f"Ruta por defecto configurada: {self.directorio_defecto}", 5000)

    def _setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # ==========================================
        # TOP ROW: The Setup Tabs
        # ==========================================
        self.setup_tabs = QTabWidget()
        self.smu_tab = SMUControlTab()
        self.dual_inst_tab = DualInstrumentControlTab()
        self.relajacion_tab = RelajacionTab() 
        self.temperatura_tab = TemperaturaTab()
        self.espectroscopia_tab = EspectroscopiaTab() 
        self.pulsos_tab = PulsosTransientesTab()

        self.setup_tabs.addTab(self.pulsos_tab, "Transientes (Osc + AFG)")
        self.setup_tabs.addTab(self.espectroscopia_tab, "Espectroscopía (TH2832)")
        self.setup_tabs.addTab(self.dual_inst_tab, "Setup: K224 + 34420A")
        self.setup_tabs.addTab(self.relajacion_tab, "Relajación") 
        self.setup_tabs.addTab(self.temperatura_tab, "Temperatura (LakeShore)")
        self.setup_tabs.addTab(self.smu_tab, "Setup: B2902A SMU")
        
        main_layout.addWidget(self.setup_tabs)

        # ==========================================
        # BOTTOM ROW: The Global Plots 
        # ==========================================
        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')
        pg.setConfigOptions(antialias=True)
        
        bottom_row_layout = QHBoxLayout()
        
        # --- PANELES NORMALES (I-V, Res, Monitoreo) ---
        self.iv_plot_pane = QGroupBox("Gráfico I-V")
        self.iv_plot_pane.setMinimumHeight(350) # <-- FORZAR ALTURA
        iv_layout = QVBoxLayout()
        self.iv_plot = pg.PlotWidget(title="Voltaje vs Corriente")
        self._style_plot(self.iv_plot, "Voltaje (V)", "Corriente (mA)")
        self.iv_plot.addLegend()
        self.iv_curve = self.iv_plot.plot(symbol='o', width=1, symbolSize=6, symbolBrush=pg.mkBrush('#0055ff'), name="Canal 1")
        self.iv_curve_ch2 = self.iv_plot.plot(symbol='s', width=1, symbolSize=6, symbolBrush=pg.mkBrush('#ff5500'), name="Canal 2")
        self.iv_last = self.iv_plot.plot(pen=None, symbol='o', symbolSize=10, symbolBrush='g', symbolPen='k')
        self.iv_last_ch2 = self.iv_plot.plot(pen=None, symbol='s', symbolSize=10, symbolBrush='g', symbolPen='k')
        iv_layout.addWidget(self.iv_plot)
        self.iv_plot_pane.setLayout(iv_layout)
        bottom_row_layout.addWidget(self.iv_plot_pane)

        self.res_plot_pane = QGroupBox("Gráfico Resistencia")
        self.res_plot_pane.setMinimumHeight(350) # <-- FORZAR ALTURA
        res_layout = QVBoxLayout()
        self.res_plot = pg.PlotWidget(title="Resistencia vs Corriente")
        self._style_plot(self.res_plot, "Corriente (mA)", "Resistencia (Ω)")
        self.res_plot.addLegend()
        self.rinst_curve = self.res_plot.plot(pen=pg.mkPen(color='#0055ff', width=1), symbol='o', symbolSize=5, symbolBrush='#0055ff', name="Rinst Ch1")
        self.rinst_curve_ch2 = self.res_plot.plot(pen=pg.mkPen(color='#ff5500', width=1), symbol='s', symbolSize=5, symbolBrush='#ff5500', name="Rinst Ch2")
        self.rrem_curve = self.res_plot.plot(pen=pg.mkPen(color='#0055ff', width=1, style=Qt.PenStyle.DashLine), symbol='o', symbolSize=5, symbolBrush='#0055ff', name="Rrem Ch1")
        self.rrem_curve_ch2 = self.res_plot.plot(pen=pg.mkPen(color='#ff5500', width=1, style=Qt.PenStyle.DashLine), symbol='s', symbolSize=5, symbolBrush='#ff5500', name="Rrem Ch2")
        self.rinst_last = self.res_plot.plot(pen=None, symbol='o', symbolSize=10, symbolBrush='r', symbolPen='k')
        self.rinst_last_ch2 = self.res_plot.plot(pen=None, symbol='s', symbolSize=10, symbolBrush='r', symbolPen='k')
        self.rrem_last = self.res_plot.plot(pen=None, symbol='o', symbolSize=10, symbolBrush='r', symbolPen='k')
        self.rrem_last_ch2 = self.res_plot.plot(pen=None, symbol='s', symbolSize=10, symbolBrush='r', symbolPen='k')
        res_layout.addWidget(self.res_plot)
        self.res_plot_pane.setLayout(res_layout)
        bottom_row_layout.addWidget(self.res_plot_pane)

        self.vt_plot_pane = QGroupBox("Monitoreo Temporal")
        self.vt_plot_pane.setMinimumHeight(350) # <-- FORZAR ALTURA
        vt_layout = QVBoxLayout()
        self.vt_plot = pg.PlotWidget(title="Voltaje vs Tiempo")
        self._style_plot(self.vt_plot, "Tiempo (min)", "Voltaje (V)")
        self.vt_plot.addLegend()
        self.vt_curve = self.vt_plot.plot(pen=pg.mkPen(color='#00aa00', width=2), name="Canal 1")
        self.vt_curve_ch2 = self.vt_plot.plot(pen=pg.mkPen(color='#ff5500', width=2), name="Canal 2")
        vt_layout.addWidget(self.vt_plot)
        self.vt_plot_pane.setLayout(vt_layout)
        bottom_row_layout.addWidget(self.vt_plot_pane)

        # --- PANELES ESPECTROSCOPÍA (Ocultos por defecto) ---
        self.nyquist_pane = QGroupBox("Gráfico de Nyquist")
        self.nyquist_pane.setMinimumHeight(350)
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
        self.bode_pane.setMinimumHeight(350)
        bode_layout = QVBoxLayout()
        self.bode_widget = pg.GraphicsLayoutWidget()
        
        self.bode_r_plot = self.bode_widget.addPlot(row=0, col=0)
        self.bode_r_plot.setLogMode(x=True, y=False) # X log, Y lineal
        self.bode_r_plot.setLabel('left', "R [Ω]")
        self.bode_r_plot.showGrid(x=True, y=True, alpha=0.3)
        self.bode_r_plot.addLegend()
        
        self.bode_x_plot = self.bode_widget.addPlot(row=1, col=0)
        self.bode_x_plot.setLogMode(x=True, y=False) # X log, Y lineal
        self.bode_x_plot.setLabel('left', "X [Ω]")
        self.bode_x_plot.setLabel('bottom', "Frequency [Hz]")
        self.bode_x_plot.showGrid(x=True, y=True, alpha=0.3)
        self.bode_x_plot.addLegend()
        self.bode_x_plot.setXLink(self.bode_r_plot)
        
        bode_layout.addWidget(self.bode_widget)
        self.bode_pane.setLayout(bode_layout)
        bottom_row_layout.addWidget(self.bode_pane)
        self.bode_pane.hide()

        # --- PANELES TRANSIENTES (PULSOS) RE-ESTRUCTURADOS EN GRID ---
        self.pulsos_pane = QWidget()
        self.pulsos_pane.setMinimumHeight(350) 
        pulsos_layout = QGridLayout(self.pulsos_pane)
        pulsos_layout.setContentsMargins(0,0,0,0)
        
        # 1. Señales Drive
        self.pt_drive_pane = QGroupBox("Señales de Excitación (Drive)")
        pt_drive_lay = QVBoxLayout()
        self.pt_drive_plot = pg.PlotWidget()
        self._style_plot(self.pt_drive_plot, "Tiempo (ms)", "Amplitud (V)") 
        self.pt_drive_plot.addLegend()
        self.pt_ch1_curve = self.pt_drive_plot.plot(pen=pg.mkPen('#1f77b4', width=2), name="CH1 Supply")
        self.pt_ch2_curve = self.pt_drive_plot.plot(pen=pg.mkPen('#ff7f0e', width=2), name="CH2 Resistor")
        pt_drive_lay.addWidget(self.pt_drive_plot)
        self.pt_drive_pane.setLayout(pt_drive_lay)
        pulsos_layout.addWidget(self.pt_drive_pane, 0, 0)

        # 2. Señales Sense
        self.pt_sense_pane = QGroupBox("Señales Sensadas (Sense)")
        pt_sense_lay = QVBoxLayout()
        self.pt_sense_plot = pg.PlotWidget()
        self._style_plot(self.pt_sense_plot, "Tiempo (ms)", "Amplitud (mV)") 
        self.pt_sense_plot.addLegend()
        self.pt_ch3_curve = self.pt_sense_plot.plot(pen=pg.mkPen('#2ca02c', width=2), name="CH3 Sense+")
        self.pt_ch4_curve = self.pt_sense_plot.plot(pen=pg.mkPen('#d62728', width=2), name="CH4 Sense-")
        self.pt_sense_plot.setXLink(self.pt_drive_plot) # Sincronizar zoom X
        pt_sense_lay.addWidget(self.pt_sense_plot)
        self.pt_sense_pane.setLayout(pt_sense_lay)
        pulsos_layout.addWidget(self.pt_sense_pane, 1, 0)

        # 3. All Channels Overlay (Twin Y-Axis)
        self.pt_over_pane = QGroupBox("All Channels Overlay")
        pt_over_lay = QVBoxLayout()
        self.pt_over_plot = pg.PlotWidget()
        self._style_plot(self.pt_over_plot, "Tiempo (ms)", "Drive (V)")
        self.pt_over_plot.setXLink(self.pt_drive_plot)
        
        # Crear eje Y derecho para Sense (mV)
        self.pt_over_plot.showAxis('right') # <-- Comando nativo correcto
        self.pt_over_vb = pg.ViewBox()
        self.pt_over_plot.scene().addItem(self.pt_over_vb)
        self.pt_over_plot.getAxis('right').linkToView(self.pt_over_vb)
        self.pt_over_vb.setXLink(self.pt_over_plot)
        self.pt_over_plot.getAxis('right').setLabel('Sense (mV)')

        # Mantener el ViewBox alineado al redimensionar
        def update_views():
            self.pt_over_vb.setGeometry(self.pt_over_plot.getViewBox().sceneBoundingRect())
            self.pt_over_vb.linkedViewChanged(self.pt_over_plot.getViewBox(), self.pt_over_vb.XAxis)
            
        self.pt_over_plot.getViewBox().sigResized.connect(update_views)
        update_views() # <-- CRÍTICO: Forzar la geometría inicial antes del primer resize

        self.pt_over_plot.addLegend()
        self.pt_over_ch1 = self.pt_over_plot.plot(pen=pg.mkPen('#1f77b4', width=2, style=Qt.PenStyle.SolidLine), name="CH1")
        self.pt_over_ch2 = self.pt_over_plot.plot(pen=pg.mkPen('#ff7f0e', width=2, style=Qt.PenStyle.SolidLine), name="CH2")
        self.pt_over_ch3 = pg.PlotCurveItem(pen=pg.mkPen('#2ca02c', width=2, style=Qt.PenStyle.DashLine), name="CH3")
        self.pt_over_ch4 = pg.PlotCurveItem(pen=pg.mkPen('#d62728', width=2, style=Qt.PenStyle.DashLine), name="CH4")
        self.pt_over_vb.addItem(self.pt_over_ch3)
        self.pt_over_vb.addItem(self.pt_over_ch4)
        
        pt_over_lay.addWidget(self.pt_over_plot)
        self.pt_over_pane.setLayout(pt_over_lay)
        pulsos_layout.addWidget(self.pt_over_pane, 2, 0)

        # 4. Curva I-V (RAW + Filtrada)
        self.pt_iv_pane = QGroupBox("Curva I-V (Raw + Filtered)")
        pt_iv_lay = QVBoxLayout()
        self.pt_iv_plot = pg.PlotWidget()
        self._style_plot(self.pt_iv_plot, "Voltaje Muestra (mV)", "Corriente Muestra (µA)") 
        self.pt_iv_plot.addLegend()
        self.pt_iv_curve_raw = self.pt_iv_plot.plot(pen=pg.mkPen(color=(128,128,128,100), width=1), name="RAW")
        self.pt_iv_curve_filt = self.pt_iv_plot.plot(pen=pg.mkPen('#9467bd', width=2), name="Filtrado")
        
        self.pt_iv_plot.addLine(x=0, pen=pg.mkPen('k', width=1))
        self.pt_iv_plot.addLine(y=0, pen=pg.mkPen('k', width=1))
        
        pt_iv_lay.addWidget(self.pt_iv_plot)
        self.pt_iv_pane.setLayout(pt_iv_lay)
        pulsos_layout.addWidget(self.pt_iv_pane, 0, 1, 3, 1) # Abarca las 3 filas
        
        bottom_row_layout.addWidget(self.pulsos_pane)
        self.pulsos_pane.hide()

        # ==========================================
        # CRÍTICO: EXPANDIR LOS GRÁFICOS
        # ==========================================
        # Se añade 'stretch=0' a las pestañas y 'stretch=1' a los gráficos. 
        # Esto le ordena a Qt que todos los pixeles libres de la pantalla vayan a los gráficos.
        self.iv_plot_pane.setMinimumHeight(350)
        self.res_plot_pane.setMinimumHeight(350)
        self.vt_plot_pane.setMinimumHeight(350)
        self.nyquist_pane.setMinimumHeight(350)
        self.bode_pane.setMinimumHeight(350)
        main_layout.addWidget(self.setup_tabs, stretch=0)
        main_layout.addLayout(bottom_row_layout, stretch=1)
        
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Listo para medir.")

    def _al_cambiar_pestana(self, index):
        """Muestra u oculta los gráficos dependiendo del modo activo."""
        nombre_pestana = self.setup_tabs.tabText(index)
        es_is = "Espectroscopía" in nombre_pestana
        es_pulsos = "Transientes" in nombre_pestana
        
        # 1. Paneles Estándar (I-V, Resistencia)
        if es_is or es_pulsos:
            self.iv_plot_pane.hide()
            self.res_plot_pane.hide()
            self.vt_plot_pane.hide()
        else:
            self.iv_plot_pane.show()
            self.res_plot_pane.show()
            self.vt_plot_pane.show()
            
        # 2. Paneles de Espectroscopía
        if es_is:
            self.nyquist_pane.show()
            self.bode_pane.show()
        else:
            self.nyquist_pane.hide()
            self.bode_pane.hide()
            
        # 3. Paneles de Pulsos Transientes
        if es_pulsos:
            self.pulsos_pane.show()
        else:
            self.pulsos_pane.hide()
        
        # 4. Ajustes de Eje X dinámicos
        if nombre_pestana == "Relajación":
            self.res_plot.setLabel('bottom', "Tiempo (min)")
        elif "K224" in nombre_pestana:
            self.res_plot.setLabel('bottom', "Corriente (mA)")

    def _style_plot(self, plot_widget, x_label, y_label):
        """Aplica estilos consistentes a los gráficos."""
        plot_widget.setLabel('left', y_label)
        plot_widget.setLabel('bottom', x_label)
        plot_widget.showGrid(x=True, y=True, alpha=0.3)
        plot_widget.setMouseEnabled(x=True, y=True)

    def _setup_connections(self):
        """Conecta todos los botones y señales."""
        p_pane = self.dual_inst_tab.params_pane
        i_pane = self.dual_inst_tab.instant_pane 
        
        # Botones UI -> Funciones del Controlador (Modo Triangular)
        p_pane.btn_aplicar.clicked.connect(self._sincronizar_parametros)
        p_pane.btn_medir.clicked.connect(self._iniciar_medicion)
        p_pane.btn_detencion.clicked.connect(self._detener_medicion)
        p_pane.btn_pausa_cbias.clicked.connect(self._toggle_pausa_cbias)
        p_pane.btn_pausa_sbias.clicked.connect(self._toggle_pausa_sbias)

        # Botones UI -> Funciones del Controlador (Modo Relajación)
        r_pane = self.relajacion_tab.params_pane
        r_pane.btn_aplicar.clicked.connect(self._sincronizar_parametros)
        r_pane.btn_medir.clicked.connect(self._iniciar_medicion)
        r_pane.btn_detencion.clicked.connect(self._detener_medicion)

        # Señales del Worker -> Funciones del Controlador
        self.worker.nueva_secuencia.connect(self._preparar_nueva_secuencia)
        self.worker.datos_actualizados.connect(self._actualizar_datos)
        self.worker.paso_invertido.connect(self._invertir_paso)
        self.worker.error_detectado.connect(self._mostrar_error)

        # AUTOMATIZACIÓN: Conectar validaciones inteligentes (Pestaña I-V)
        p_pane.ancho_pulso.valueChanged.connect(self._validar_tiempos)
        i_pane.combo_nplc.currentTextChanged.connect(self._validar_tiempos)
        i_pane.btn_ch2_toggle.toggled.connect(self._validar_tiempos)

        # AUTOMATIZACIÓN: Conectar validaciones inteligentes (Pestaña Relajación)
        r_i_pane = self.relajacion_tab.instant_pane
        r_pane.ancho_lectura.valueChanged.connect(self._validar_tiempos)
        r_i_pane.combo_nplc.currentTextChanged.connect(self._validar_tiempos)
        r_i_pane.btn_ch2_toggle.toggled.connect(self._validar_tiempos)

        # Re-validar y ajustar gráficos al cambiar de pestaña
        self.setup_tabs.currentChanged.connect(self._validar_tiempos)
        self.setup_tabs.currentChanged.connect(self._al_cambiar_pestana)
        self._setup_conexiones_temp()
        self._setup_conexiones_is() # <--- ¡ESTA ES LA LÍNEA QUE FALTABA!
        self._setup_conexiones_pulsos()

        t_pane = self.temperatura_tab.params_pane
        t_pane.btn_medir.clicked.connect(self._iniciar_medicion_temp)
        t_pane.btn_detencion.clicked.connect(self.worker_temp.detener_medicion)
        
        # NUEVA CONEXIÓN PARA CAMBIOS EN VIVO
        t_pane.btn_aplicar.clicked.connect(self._sincronizar_parametros_temp) 
        
        self.worker_temp.datos_temp.connect(self._actualizar_graficos_termodinamicos)

    def _setup_conexiones_pulsos(self):
        p_pane = self.pulsos_tab.params_pane
        p_pane.btn_medir.clicked.connect(self._iniciar_medicion_pulsos)
        p_pane.btn_detencion.clicked.connect(self.worker_pulsos.detener_medicion)
        self.worker_pulsos.datos_pulso.connect(self._actualizar_graficos_pulsos)
        self.worker_pulsos.estado_msg.connect(lambda msg: self.status_bar.showMessage(msg))
        self.worker_pulsos.error_detectado.connect(self._mostrar_error)

    def _iniciar_medicion_pulsos(self):
        if self.worker_pulsos.corriendo: return
        p_pane = self.pulsos_tab.params_pane
        
        try:
            freqs = [float(x.strip()) for x in p_pane.freqs.text().split(',')]
            amps = [float(x.strip()) for x in p_pane.amps.text().split(',')]
        except ValueError:
            self._mostrar_error("Frecuencias o amplitudes inválidas. Use números separados por comas.")
            return

        ruta_inicial = self.directorio_defecto
        if ruta_inicial:
            import time
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            # AÑADIR .csv AQUÍ fuerza al OS a pre-seleccionar el filtro correctamente
            ruta_inicial = os.path.join(ruta_inicial, f"transientes_{timestamp}.csv") 
            
        ruta_archivo, _ = QFileDialog.getSaveFileName(self, "Guardar Transientes", ruta_inicial, "CSV Files (*.csv);;Todos los archivos (*)")
        if not ruta_archivo: return
        if not ruta_archivo.lower().endswith('.csv'): ruta_archivo += '.csv'

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
            'ruta_archivo_pulsos': ruta_archivo
        })
        
        self.pt_ch1_curve.setData([], [])
        self.pt_ch2_curve.setData([], [])
        self.pt_ch3_curve.setData([], [])
        self.pt_ch4_curve.setData([], [])
        self.pt_iv_curve.setData([], [])
        
        self.worker_pulsos.iniciar_medicion()

    def _actualizar_graficos_pulsos(self, freq, amp, time_axis, v1, v2, v3, v4, v_dut_filt, current_filt):
        time_ms = time_axis * 1e3
        v3_mv = v3 * 1e3
        v4_mv = v4 * 1e3
        
        # 1. Drive
        self.pt_ch1_curve.setData(time_ms, v1)
        self.pt_ch2_curve.setData(time_ms, v2)
        
        # 2. Sense
        self.pt_ch3_curve.setData(time_ms, v3_mv) 
        self.pt_ch4_curve.setData(time_ms, v4_mv) 
        
        # 3. Overlay
        self.pt_over_ch1.setData(time_ms, v1)
        self.pt_over_ch2.setData(time_ms, v2)
        self.pt_over_ch3.setData(time_ms, v3_mv)
        self.pt_over_ch4.setData(time_ms, v4_mv)
        
        # 4. I-V Curve (Raw calculation + Filtered)
        v_dut_raw = (v4 - v3) * 1e3
        r_limit = self.pulsos_tab.params_pane.r_limit.value()
        current_raw = ((v1 - v2) / r_limit) * 1e6
        
        self.pt_iv_curve_raw.setData(v_dut_raw, current_raw)
        self.pt_iv_curve_filt.setData(v_dut_filt * 1e3, current_filt * 1e6)

    # Añadir a _setup_connections(self):
    def _setup_conexiones_temp(self):
        t_pane = self.temperatura_tab.params_pane
        t_pane.btn_medir.clicked.connect(self._iniciar_medicion_temp)
        t_pane.btn_detencion.clicked.connect(self.worker_temp.detener_medicion)
        
        self.worker_temp.datos_temp.connect(self._actualizar_graficos_termodinamicos)
        self.worker_temp.datos_res.connect(self._actualizar_graficos_res_temp)
        self.worker_temp.estado_msg.connect(lambda msg: self.status_bar.showMessage(msg))
        self.worker_temp.error_detectado.connect(self._mostrar_error)

    def _iniciar_medicion_temp(self):
        if self.worker_temp.corriendo: return
        
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

        # --- Reemplazo del TODO: Lógica de Guardado de Archivo ---
        ruta_inicial = self.directorio_defecto
        if ruta_inicial:
            import time
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            ruta_inicial = os.path.join(ruta_inicial, f"temperatura_{timestamp}")

        ruta_archivo, _ = QFileDialog.getSaveFileName(self, "Guardar Rampa de Temperatura", ruta_inicial, "CSV Files (*.csv)")
        if not ruta_archivo: return
        if not ruta_archivo.lower().endswith('.csv'): ruta_archivo += '.csv'
        # ---------------------------------------------------------
            
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
            'ch2_activado': i_pane.btn_ch2_toggle.isChecked(),
            'nplc': i_pane.combo_nplc.currentText(),
            'rango': i_pane.combo_rango.currentText(),
            'ruta_archivo': ruta_archivo
        })
        
        self.data_t_temp = []
        self.data_T_act = []
        self.data_T_set = []
        
        self.worker_temp.iniciar_medicion()

    def _actualizar_graficos_termodinamicos(self, t_min, T_act, T_set, pot, v_motor):
        """Actualiza laUI durante la rampa/estabilización (sin medir resistencia aún)."""
        self.data_t_temp.append(t_min)
        self.data_T_act.append(T_act)
        self.data_T_set.append(T_set)
        
        # Si estás en la pestaña de Temperatura, puedes re-usar vt_curve temporalmente 
        # o crear un panel dedicado de gráficos en el futuro.
        if self.setup_tabs.tabText(self.setup_tabs.currentIndex()) == "Temperatura (LakeShore)":
            self.vt_curve.setData(self.data_t_temp, self.data_T_act)
            self.vt_curve_ch2.setData(self.data_t_temp, self.data_T_set)
            self.vt_plot.setLabel('left', "Temperatura (K)")

    def _actualizar_graficos_res_temp(self, T_act, r1, r2, t_min):
        """Actualiza la UI cuando se completa un N_stat_msr."""
        # Mostrar en los QLineEdit de Lectura Instantánea
        i_pane = self.temperatura_tab.instant_pane
        i_pane.vp_1_ro.setText(f"{T_act:.2f} K") # Usamos V_pos visualmente para T
        i_pane.rinst_1_ro.setText(f"{r1:.3e}")
        if not math.isnan(r2):
            i_pane.rinst_2_ro.setText(f"{r2:.3e}")
            
        # Actualizar gráfico principal R(T)
        self.data_rinst.append(r1)
        self.data_i_rinst.append(T_act) # Usamos el eje X (Corriente) para guardar Temperatura
        self.rinst_curve.setData(self.data_i_rinst, self.data_rinst)
        self.res_plot.setLabel('bottom', "Temperatura (K)")

    def _al_cambiar_pestana(self, index):
        """Muestra u oculta los gráficos dependiendo del modo activo."""
        nombre_pestana = self.setup_tabs.tabText(index)
        es_is = "Espectroscopía" in nombre_pestana
        
        self.iv_plot_pane.setVisible(not es_is)
        self.res_plot_pane.setVisible(not es_is)
        self.vt_plot_pane.setVisible(not es_is)
        
        self.nyquist_pane.setVisible(es_is)
        self.bode_pane.setVisible(es_is)
        
        if nombre_pestana == "Relajación":
            self.res_plot.setLabel('bottom', "Tiempo (min)")
        elif "K224" in nombre_pestana:
            self.res_plot.setLabel('bottom', "Corriente (mA)")

    # Llama a esto desde tu _setup_connections original
    def _setup_conexiones_is(self):
        pane = self.espectroscopia_tab.params_pane
        pane.btn_medir.clicked.connect(self._iniciar_medicion_is)
        pane.btn_detencion.clicked.connect(self.worker_is.detener_medicion)
        
        # --- NUEVAS CONEXIONES DE CORRECCIÓN ---
        pane.btn_corr_open.clicked.connect(lambda: self._iniciar_correccion("OPEN"))
        pane.btn_corr_short.clicked.connect(lambda: self._iniciar_correccion("SHOR"))
        
        self.worker_is.datos_is.connect(self._actualizar_graficos_is)
        self.worker_is.estado_msg.connect(lambda msg: self.status_bar.showMessage(msg))
        self.worker_is.error_detectado.connect(self._mostrar_error)

    def _iniciar_correccion(self, tipo):
        """Inicia el hilo de corrección para las frecuencias actualmente en la tabla."""
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

        # Configurar estado compartido para el hilo
        self.estado_compartido['frecuencias_corr'] = lista_freq
        
        # Crear y conectar el hilo de corrección
        self.worker_corr = HiloCorreccionSpot(self.estado_compartido, tipo)
        self.worker_corr.progreso.connect(self._actualizar_progreso_corr)
        self.worker_corr.estado_msg.connect(lambda msg: self.status_bar.showMessage(msg))
        self.worker_corr.finalizado.connect(self._finalizar_correccion)
        self.worker_corr.error_detectado.connect(self._mostrar_error)
        
        # Bloquear botones para evitar dobles clicks
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
        
        # Restaurar botones
        pane = self.espectroscopia_tab.params_pane
        pane.btn_corr_open.setEnabled(True)
        pane.btn_corr_short.setEnabled(True)
        pane.btn_medir.setEnabled(True)

    def _iniciar_medicion_is(self):
        if self.worker_is.corriendo: return
        
        pane = self.espectroscopia_tab.params_pane
        
        # 1. Parsear Lógica de Vdc (Fijo vs Barrido)
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
            # Si no se usa la lista, se envía el valor fijo ingresado
            lista_vdc = [pane.vdc_fijo.value()]

        # 2. Parsear Frecuencias
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

        # 3. Guardar Archivo
        ruta_inicial = self.directorio_defecto
        if ruta_inicial:
            import time
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            ruta_inicial = os.path.join(ruta_inicial, f"espectroscopia_{timestamp}")

        ruta_archivo, _ = QFileDialog.getSaveFileName(self, "Guardar Espectroscopía", ruta_inicial, "CSV Files (*.csv)")
        if not ruta_archivo: return
        if not ruta_archivo.lower().endswith('.csv'): ruta_archivo += '.csv'

        # 4. Actualizar el estado con TODO lo necesario
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
        
        # Limpiar gráficos para la nueva corrida
        self._limpiar_datos_graficos()
        self.worker_is.iniciar_medicion()

    # Actualizar la firma para recibir el status
    def _actualizar_graficos_is(self, vdc, freq, r1, x1, z1, theta1, r2, x2, z2, theta2, t_min, status):
        if status != 0 and status != -1:
            msg = f"Error Status {status}"
            self.status_bar.setStyleSheet("background-color: #ff9800; color: black; font-weight: bold;")
            self.status_bar.showMessage(f"⚠ ALERTA LCR (Freq: {freq}Hz): {msg}", 4000)
        else:
            self.status_bar.setStyleSheet("")
            self.status_bar.showMessage(f"IS Corriendo: {vdc} Vdc | {freq:.1f} Hz")

        # 1. Si el Vdc es nuevo, inicializamos su memoria y sus curvas
        if vdc not in self.data_is:
            self.data_is[vdc] = {'f':[], 'r1':[], 'x1':[], 'r2':[], 'x2':[], 'dr':[], 'dx':[]}
            
            # Asignar un color único y brillante para este barrido Vdc
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

        # 2. Extraer el diccionario correspondiente y guardar los datos
        d = self.data_is[vdc]
        d['f'].append(freq)
        d['r1'].append(r1)
        d['x1'].append(x1)
        
        if not math.isnan(r2):
            d['r2'].append(r2)
            d['x2'].append(x2)
            d['dr'].append(r1 - r2)
            d['dx'].append(x1 - x2)
        
        # 3. Renderizar las curvas específicas de este Vdc
        c = self.curvas_is[vdc]
        c['nyq1'].setData(d['r1'], [-x for x in d['x1']]) # Convención: -Imaginario en Nyquist
        c['r1'].setData(d['f'], d['r1'])
        c['x1'].setData(d['f'], d['x1']) # Bode X en Y real
        
        if len(d['r2']) > 0:
            c['nyq2'].setData(d['r2'], [-x for x in d['x2']])
            c['r2'].setData(d['f'], d['r2'])
            c['x2'].setData(d['f'], d['x2'])
            
            c['nyq_diff'].setData(d['dr'], [-x for x in d['dx']])
            c['r_diff'].setData(d['f'], d['dr'])
            c['x_diff'].setData(d['f'], d['dx'])

    def _limpiar_datos_graficos(self):
        # Arrays I-V y Termodinámicos
        self.data_t, self.data_v, self.data_i = [], [], []
        self.data_t_ch2, self.data_v_ch2, self.data_i_ch2 = [], [], []
        
        self.data_i_rinst, self.data_rinst, self.data_t_rinst = [], [], []
        self.data_i_rrem, self.data_rrem, self.data_t_rrem = [], [], []
        
        self.data_i_rinst_ch2, self.data_rinst_ch2, self.data_t_rinst_ch2 = [], [], []
        self.data_i_rrem_ch2, self.data_rrem_ch2, self.data_t_rrem_ch2 = [], [], []

        # Limpiar gráficos de Espectroscopía (si ya fueron inicializados)
        if hasattr(self, 'nyquist_plot'):
            self.nyquist_plot.clear()
            self.bode_r_plot.clear()
            self.bode_x_plot.clear()

        # Diccionarios dinámicos para agrupar barridos múltiples (Vdc)
        self.data_is = {}
        self.curvas_is = {}

    # ==========================================
    # LÓGICA DE CONTROL (SLOTS)
    # ==========================================

    def _validar_tiempos(self, *args):
        """Calcula el límite físico del hardware y ajusta la UI automáticamente para prevenir bloqueos."""
        nombre_pestana = self.setup_tabs.tabText(self.setup_tabs.currentIndex())
        es_relajacion = (nombre_pestana == "Relajación")
        
        if es_relajacion:
            p_pane = self.relajacion_tab.params_pane
            i_pane = self.relajacion_tab.instant_pane
            ancho_input = p_pane.ancho_lectura
            periodo_input = p_pane.periodo
            lbl_warning = p_pane.lbl_warning_tiempo
        elif "K224" in nombre_pestana:
            p_pane = self.dual_inst_tab.params_pane
            i_pane = self.dual_inst_tab.instant_pane
            ancho_input = p_pane.ancho_pulso
            periodo_input = p_pane.periodo_pulso
            lbl_warning = p_pane.lbl_warning_tiempo
        else:
            return # Ignorar si estamos en la pestaña del B2902A

        try:
            nplc = float(i_pane.combo_nplc.currentText())
        except ValueError:
            return

        usa_ch2 = i_pane.btn_ch2_toggle.isChecked()
        
        # Matemática dura de los límites del Agilent 34420A
        tiempo_integracion = nplc * 0.02
        
        if usa_ch2:
            # Integración CH1 + 1.5s relay (ida) + Integración CH2 + 1.5s relay (vuelta) + 100ms procesador
            tiempo_minimo_ancho = (tiempo_integracion * 2) + 0.25 
        else:
            # Solo CH1
            tiempo_minimo_ancho = tiempo_integracion + 0.05 
            
        # El periodo SIEMPRE debe alojar el ancho + un descanso mínimo de 50ms para limpieza de buffer
        tiempo_minimo_periodo = tiempo_minimo_ancho + 0.05 
        
        # Bloquear temporalmente las señales para evitar un bucle infinito en PyQt
        ancho_input.blockSignals(True)
        periodo_input.blockSignals(True)
        
        # AUTOMATIZACIÓN: Restringir los valores mínimos permitidos en las cajas de la interfaz
        ancho_input.setMinimum(tiempo_minimo_ancho)
        periodo_input.setMinimum(tiempo_minimo_periodo)
        
        # Si el usuario tenía puesto 0.5s y encendió el CH2, el valor salta automáticamente a ~3.15s
        if ancho_input.value() < tiempo_minimo_ancho:
            ancho_input.setValue(tiempo_minimo_ancho)
        if periodo_input.value() < tiempo_minimo_periodo:
            periodo_input.setValue(tiempo_minimo_periodo)
            
        ancho_input.blockSignals(False)
        periodo_input.blockSignals(False)
        
        # Mensaje visual para informar por qué saltaron los números
        if usa_ch2:
            lbl_warning.setText(f"⚠ CH2 ACTIVO: Tiempos limitados por relays mecánicos (Mínimo {tiempo_minimo_periodo:.2f}s).")
        else:
            lbl_warning.setText(" ")

    def _sincronizar_parametros(self):
        """Lee la UI activa y actualiza el diccionario del hilo de forma segura."""
        nombre_pestana = self.setup_tabs.tabText(self.setup_tabs.currentIndex())
        es_relajacion = (nombre_pestana == "Relajación")
        
        if es_relajacion:
            p_pane = self.relajacion_tab.params_pane
            i_pane = self.relajacion_tab.instant_pane
            
            # Convertir el texto separado por comas a listas de Python
            try:
                lista_pulsos = [float(x.strip()) for x in p_pane.corr_pulso.text().split(',')]
                lista_bias = [float(x.strip()) for x in p_pane.corr_bias.text().split(',')]
            except ValueError:
                self.status_bar.setStyleSheet("background-color: #d32f2f; color: white; font-weight: bold;")
                self.status_bar.showMessage("ERROR: Las matrices deben contener solo números separados por comas.", 5000)
                return
                
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
                'ch2_activado': i_pane.btn_ch2_toggle.isChecked()
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
                'limite_voltaje': p_pane.limite_voltaje.value(),
                'nplc': i_pane.combo_nplc.currentText(),
                'rango': i_pane.combo_rango.currentText(),
                'ch2_activado': i_pane.btn_ch2_toggle.isChecked()
            }
            
        self.estado_compartido.update(nuevo_estado)
        self.status_bar.setStyleSheet("") 
        self.status_bar.showMessage(f"Parámetros ({nombre_pestana}) actualizados.", 3000)

    # NUEVA FUNCIÓN DE SINCRONIZACIÓN
    def _sincronizar_parametros_temp(self):
        """Actualiza los parámetros del hilo de temperatura en vivo sin interrumpirlo."""
        t_pane = self.temperatura_tab.params_pane
        i_pane = self.temperatura_tab.instant_pane
        
        nuevo_estado = {
            'mhi': t_pane.motor_max.value(),
            'mlo': t_pane.motor_min.value(),
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
        
        # Extraer PID si el usuario lo tipeó correctamente
        try:
            pid_vals = [float(x.strip()) for x in t_pane.pid_input.text().split(',')]
            if len(pid_vals) == 3:
                nuevo_estado['pid_p'] = pid_vals[0]
                nuevo_estado['pid_i'] = pid_vals[1]
                nuevo_estado['pid_d'] = pid_vals[2]
                
                # Si el hilo está corriendo, enviar el comando SCPI inmediatamente al LakeShore
                if self.worker_temp.corriendo and self.worker_temp.lakeshore.inst:
                    self.worker_temp.lakeshore.set_pid(pid_vals[0], pid_vals[1], pid_vals[2])
        except ValueError:
            pass # Si escriben mal el PID, lo ignoramos para no crashear
            
        self.estado_compartido.update(nuevo_estado)
        self.status_bar.setStyleSheet("")
        self.status_bar.showMessage("Parámetros de Temperatura actualizados en vivo.", 3000)

    def _iniciar_medicion(self):
        if self.worker.corriendo:
            self.status_bar.showMessage("La medición ya está en curso.", 3000)
            return

        # 1. Solicitar ruta y nombre de archivo al usuario, empezando en la ruta por defecto
        ruta_inicial = self.directorio_defecto
        if ruta_inicial:
            import time
            # Generar un timestamp único (Ej: 20260821_163629)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            ruta_inicial = os.path.join(ruta_inicial, f"medicion_{timestamp}")

        ruta_archivo, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar Medición",
            ruta_inicial, 
            "CSV Files (*.csv);;Todos los archivos (*)"
        )

        # Si el usuario cancela la ventana de guardado
        if not ruta_archivo:
            self.status_bar.showMessage("Medición cancelada (no se seleccionó archivo de destino).", 4000)
            return

        # NUEVO: Asegurar que el archivo tenga la extensión .csv automáticamente
        if not ruta_archivo.lower().endswith('.csv'):
            ruta_archivo += '.csv'

        # 2. Asegurar que los últimos números tipeados estén cargados
        self._sincronizar_parametros()
        
        # 3. Guardar la ruta en el estado para que el hilo la use
        self.estado_compartido['ruta_archivo'] = ruta_archivo

        # 4. Limpiar los gráficos correctamente
        self._limpiar_datos_graficos()
        self.iv_curve.setData([], [])
        self.iv_curve_ch2.setData([], [])
        self.rinst_curve.setData([], [])
        self.rinst_curve_ch2.setData([], [])
        self.rrem_curve.setData([], [])
        self.rrem_curve_ch2.setData([], [])
        self.vt_curve.setData([], [])
        self.vt_curve_ch2.setData([], [])
        
        # Limpiar los puntos rojos de ambos canales
        self.iv_last.setData([], [])
        self.iv_last_ch2.setData([], [])
        self.rinst_last.setData([], [])
        self.rinst_last_ch2.setData([], [])
        self.rrem_last.setData([], [])
        self.rrem_last_ch2.setData([], [])

        # 5. Arrancar el motor
        self.status_bar.setStyleSheet("") # Resetear color en caso de error previo
        self.status_bar.showMessage(f"Iniciando medición... Guardando en {ruta_archivo}")
        self.worker.iniciar_medicion()

    def _preparar_nueva_secuencia(self, corr_bias, corr_pulso, nombre_archivo):
        """Limpia los gráficos antes de iniciar la siguiente combinación de la matriz."""
        self._limpiar_datos_graficos()
        self.iv_curve.setData([], [])
        self.iv_curve_ch2.setData([], [])
        self.rinst_curve.setData([], [])
        self.rinst_curve_ch2.setData([], [])
        self.rrem_curve.setData([], [])
        self.rrem_curve_ch2.setData([], [])
        self.vt_curve.setData([], [])
        self.vt_curve_ch2.setData([], [])
        self.status_bar.setStyleSheet("")
        import os
        self.status_bar.showMessage(f"Matriz: Bias {corr_bias}mA | Pulso {corr_pulso}mA -> Guardando en {os.path.basename(nombre_archivo)}")

    def _cargar_medicion(self):
        """Abre un diálogo, lee un CSV previo y puebla los gráficos soportando múltiples formatos."""
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
                reader = csv.DictReader(f)
                
                for fila in reader:
                    try:
                        t = float(fila.get("Tiempo (min)", float('nan')))
                        is_smu = False
                        
                        # ---------------------------------------------------------
                        # 1. ESPECTROSCOPÍA DE IMPEDANCIA (IS)
                        # ---------------------------------------------------------
                        if "Freq (Hz)" in fila:
                            f_val = float(fila["Freq (Hz)"])
                            vdc = float(fila.get("Vdc (V)", 0.0)) # Compatibilidad hacia atrás
                            
                            if vdc not in self.data_is:
                                self.data_is[vdc] = {'f':[], 'r1':[], 'x1':[], 'r2':[], 'x2':[], 'dr':[], 'dx':[]}
                                
                            d = self.data_is[vdc]
                            
                            if "R_ch1 (Ohm)" in fila: # Formato Matriz
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
                                    
                            elif "R (Ohm)" in fila: # Formato Viejo
                                r1 = float(fila["R (Ohm)"])
                                x1 = float(fila["X (Ohm)"])
                                if not math.isnan(r1):
                                    d['f'].append(f_val)
                                    d['r1'].append(r1)
                                    d['x1'].append(x1)
                            
                            continue # CRÍTICO: Salta al siguiente loop
                            
                        # ---------------------------------------------------------
                        # 2. I-V / RELAJACIÓN (Formato Nuevo K224 + 34420A)
                        # ---------------------------------------------------------
                        elif "I pulso (mA)" in fila:
                            i_inst = float(fila["I pulso (mA)"])
                            r1_inst = float(fila["Rinst 1 (Ohm)"])
                            r2_inst = float(fila.get("Rinst 2 (Ohm)", float('nan')))
                            
                        # ---------------------------------------------------------
                        # 3. I-V (Formato Viejo B2902A SMU)
                        # ---------------------------------------------------------
                        elif "I pulso(mA)" in fila:
                            is_smu = True 
                            i_inst = float(fila["Iinst 1 (mA)"]) 
                            r1_inst = float(fila["Rinst 1(Ohm)"])
                            r2_inst = float(fila.get("Rinst 2(Ohm)", float('nan')))
                            
                        else:
                            continue # Ignorar si la fila no coincide con nada

                        # Variables I-V compartidas
                        v1_inst = float(fila.get("Vinst 1 (V)", float('nan')))
                        r1_bias = float(fila.get("Rrem 1 (Ohm)", float('nan')))
                        v2_inst = float(fila.get("Vinst 2 (V)", float('nan')))
                        r2_bias = float(fila.get("Rrem 2 (Ohm)", float('nan')))
                        
                        if is_smu:
                            if abs(v2_inst) > 1e30: v2_inst = float('nan')
                            if abs(r2_inst) > 1e30: r2_inst = float('nan')
                            if abs(r2_bias) > 1e30: r2_bias = float('nan')
                            
                    except ValueError:
                        continue 
                    
                    # Carga de datos I-V
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

            # --- RENDER: Actualizar todos los gráficos I-V ---
            self.iv_curve.setData(self.data_v, self.data_i)
            self.vt_curve.setData(self.data_t, self.data_v)
            self.rinst_curve.setData(self.data_i_rinst, self.data_rinst)
            self.rrem_curve.setData(self.data_i_rrem, self.data_rrem)
            
            self.iv_curve_ch2.setData(self.data_v_ch2, self.data_i_ch2)
            self.vt_curve_ch2.setData(self.data_t_ch2, self.data_v_ch2)
            self.rinst_curve_ch2.setData(self.data_i_rinst_ch2, self.data_rinst_ch2)
            self.rrem_curve_ch2.setData(self.data_i_rrem_ch2, self.data_rrem_ch2)
            
            # --- RENDER: Actualizar Gráficos de Espectroscopía ---
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
                else:
                    c['nyq2'].setData([], [])
                    c['r2'].setData([], [])
                    c['x2'].setData([], [])
                    c['nyq_diff'].setData([], [])
                    c['r_diff'].setData([], [])
                    c['x_diff'].setData([], [])
            
            # Limpiar cursores
            self.iv_last.setData([], [])
            self.iv_last_ch2.setData([], [])
            self.rinst_last.setData([], [])
            self.rinst_last_ch2.setData([], [])
            self.rrem_last.setData([], [])
            self.rrem_last_ch2.setData([], [])
            
            self.status_bar.setStyleSheet("color: #2e7d32; font-weight: bold;")
            self.status_bar.showMessage(f"Archivo cargado exitosamente: {ruta_archivo}", 5000)

        except Exception as e:
            self._mostrar_error(f"Error al leer el archivo: {str(e)}")

    def _detener_medicion(self):
        if not self.worker.corriendo: return 
        self.worker.detener_medicion()
        self.status_bar.setStyleSheet("")
        self.status_bar.showMessage("Medición detenida por el usuario.", 5000)

    def _toggle_pausa_cbias(self):
        if not self.worker.corriendo: return 
        estado_actual = self.worker.pausado_cbias
        self.worker.pausado_cbias = not estado_actual
        self.worker.pausado_sbias = False 
        msg = "Pausado (CON Bias)" if self.worker.pausado_cbias else "Reanudando..."
        
        self.status_bar.setStyleSheet("") 
        self.status_bar.showMessage(msg, 3000)

    def _toggle_pausa_sbias(self):
        if not self.worker.corriendo: return 
        estado_actual = self.worker.pausado_sbias
        self.worker.pausado_sbias = not estado_actual
        self.worker.pausado_cbias = False 
        msg = "Pausado (SIN Bias)" if self.worker.pausado_sbias else "Reanudando..."
        
        self.status_bar.setStyleSheet("") 
        self.status_bar.showMessage(msg, 3000)

    def _invertir_paso(self, nuevo_paso):
        """Actualiza la UI visualmente cuando la máquina de estados rebota en un límite."""
        self.dual_inst_tab.params_pane.paso_corr.blockSignals(True)
        self.dual_inst_tab.params_pane.paso_corr.setValue(nuevo_paso)
        self.dual_inst_tab.params_pane.paso_corr.blockSignals(False)

    def _mostrar_error(self, mensaje):
        """Muestra errores críticos del hardware en rojo en la barra inferior."""
        self.status_bar.setStyleSheet("background-color: #d32f2f; color: white; font-weight: bold;")
        self.status_bar.showMessage(f"ERROR: {mensaje}")

    def _actualizar_datos(self, t_min, v1, r1, v2, r2, i_app, es_bias):
        """Actualiza la Interfaz y los Gráficos con los datos recibidos."""
        p_pane = self.dual_inst_tab.params_pane
        i_pane = self.dual_inst_tab.instant_pane

        p_pane.corr_actual_ro.setText(f"{i_app:.5f}")
        
        def safe_format(val):
            return "NaN" if math.isnan(val) else f"{val:.5f}"

        # 1. Update UI Labels
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

        # 2. Update Plots
        es_relajacion = self.estado_compartido.get('modo_relajacion', False)

        if not es_bias:
            self.data_t.append(t_min)
            self.data_v.append(v1)
            self.data_i.append(i_app)
            self.iv_curve.setData(self.data_v, self.data_i)
            self.vt_curve.setData(self.data_t, self.data_v)
            
            self.iv_last.setData([v1], [i_app])
            self.i_inst = i_app # Guardamos para alinear el Rrem si aplica

            if not math.isnan(r1):
                self.data_i_rinst.append(i_app)
                self.data_t_rinst.append(t_min)
                self.data_rinst.append(r1)
                
                # Elegir Eje X dinámico
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
                self.data_i_rrem.append(self.i_inst) # Corriente origen del pulso
                self.data_t_rrem.append(t_min)
                self.data_rrem.append(r1)
                
                # Elegir Eje X dinámico
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