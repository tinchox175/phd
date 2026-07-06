import sys
import math
from PySide6.QtWidgets import (QApplication, QMainWindow, QHBoxLayout, QVBoxLayout, 
                               QWidget, QLabel, QGroupBox, QPushButton, QTabWidget, 
                               QLineEdit, QMessageBox, QStatusBar, QFileDialog)
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt
import pyqtgraph as pg

# Import the View (UI) and Model (Hardware)
from IVsuplemento import ParametersPane, InstantPane, ParametrosK224Pane, Lecturas34420APane
from hardware import HiloMedicionDual

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

        # Paneles principales (Eliminada la barra superior de nombre de muestra)
        panes_layout = QHBoxLayout()
        self.params_pane = ParametrosK224Pane()
        self.instant_pane = Lecturas34420APane()
        
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
        
        # Diccionario de estado compartido con el Worker
        self.estado_compartido = {}
        
        # Inicializar el hilo de hardware
        self.worker = HiloMedicionDual(self.estado_compartido)
        
        # Variables para almacenar datos de gráficos
        self._limpiar_datos_graficos()

        self._setup_menu()
        self._setup_ui()
        self._setup_connections()

    def _setup_menu(self):
        """Crea la barra de herramientas superior."""
        menu_bar = self.menuBar()
        
        # Menú Archivo
        archivo_menu = menu_bar.addMenu("Archivo")
        
        self.action_abrir = QAction("Abrir Mediciones Anteriores...", self)
        self.action_abrir.triggered.connect(lambda: print("Abrir presionado (Pendiente)"))
        archivo_menu.addAction(self.action_abrir)
        
        # Menú Opciones
        opciones_menu = menu_bar.addMenu("Opciones")
        
        self.action_configurar_ruta = QAction("Configurar Ruta por Defecto...", self)
        self.action_configurar_ruta.triggered.connect(lambda: print("Configurar Ruta presionado (Pendiente)"))
        opciones_menu.addAction(self.action_configurar_ruta)

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
        
        self.setup_tabs.addTab(self.dual_inst_tab, "Setup: K224 + 34420A")
        self.setup_tabs.addTab(self.smu_tab, "Setup: B2902A SMU")
        
        main_layout.addWidget(self.setup_tabs)

        # ==========================================
        # BOTTOM ROW: The Global Plots 
        # ==========================================
        # Configuraciones globales de pyqtgraph
        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')
        pg.setConfigOptions(antialias=True)
        
        bottom_row_layout = QHBoxLayout()

        # I-V Plot Pane
        self.iv_plot_pane = QGroupBox("Gráfico I-V")
        iv_layout = QVBoxLayout()
        self.iv_plot = pg.PlotWidget(title="Voltaje vs Corriente")
        self._style_plot(self.iv_plot, "Voltaje (V)", "Corriente (mA)")
        self.iv_curve = self.iv_plot.plot(pen=None, symbol='o', symbolSize=6, symbolBrush=pg.mkBrush('#0055ff')) 
        iv_layout.addWidget(self.iv_plot)
        self.iv_plot_pane.setLayout(iv_layout)
        bottom_row_layout.addWidget(self.iv_plot_pane)

        # Resistance Plot Pane
        self.res_plot_pane = QGroupBox("Gráfico Resistencia")
        res_layout = QVBoxLayout()
        self.res_plot = pg.PlotWidget(title="Resistencia Temporal")
        self._style_plot(self.res_plot, "Tiempo (min)", "Resistencia (Ω)")
        self.res_curve = self.res_plot.plot(pen=pg.mkPen(color='#ff5500', width=2))
        res_layout.addWidget(self.res_plot)
        self.res_plot_pane.setLayout(res_layout)
        bottom_row_layout.addWidget(self.res_plot_pane)

        # Voltage vs Time Plot Pane
        self.vt_plot_pane = QGroupBox("Monitoreo Temporal")
        vt_layout = QVBoxLayout()
        self.vt_plot = pg.PlotWidget(title="Voltaje vs Tiempo")
        self._style_plot(self.vt_plot, "Tiempo (min)", "Voltaje (V)")
        self.vt_curve = self.vt_plot.plot(pen=pg.mkPen(color='#00aa00', width=2))
        vt_layout.addWidget(self.vt_plot)
        self.vt_plot_pane.setLayout(vt_layout)
        bottom_row_layout.addWidget(self.vt_plot_pane)

        main_layout.addLayout(bottom_row_layout)
        
        # Status Bar para errores y mensajes
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Listo para medir.")

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
        
        # Botones UI -> Funciones del Controlador
        p_pane.btn_aplicar.clicked.connect(self._sincronizar_parametros)
        p_pane.btn_medir.clicked.connect(self._iniciar_medicion)
        p_pane.btn_detencion.clicked.connect(self._detener_medicion)
        p_pane.btn_pausa_cbias.clicked.connect(self._toggle_pausa_cbias)
        p_pane.btn_pausa_sbias.clicked.connect(self._toggle_pausa_sbias)

        # Señales del Worker -> Funciones del Controlador
        self.worker.datos_actualizados.connect(self._actualizar_datos)
        self.worker.paso_invertido.connect(self._invertir_paso)
        self.worker.error_detectado.connect(self._mostrar_error)

        # Validaciones en vivo (NPLC vs Ancho Pulso)
        p_pane.ancho_pulso.valueChanged.connect(self._validar_tiempos)
        i_pane.combo_nplc.currentTextChanged.connect(self._validar_tiempos)
        i_pane.btn_ch2_toggle.toggled.connect(self._validar_tiempos)

    def _limpiar_datos_graficos(self):
        self.data_t = []
        self.data_v = []
        self.data_i = []
        
        self.data_t_res = []
        self.data_r = []

    # ==========================================
    # LÓGICA DE CONTROL (SLOTS)
    # ==========================================

    def _sincronizar_parametros(self):
        """Lee la UI y actualiza el diccionario del hilo de forma segura."""
        p_pane = self.dual_inst_tab.params_pane
        i_pane = self.dual_inst_tab.instant_pane

        nuevo_estado = {
            'nombre_muestra': self.dual_inst_tab.input_nombre_muestra.text(),
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
            'filtro': i_pane.combo_filtro.currentText(),
            'ch2_activado': i_pane.btn_ch2_toggle.isChecked()
        }
        self.estado_compartido.update(nuevo_estado)
        
        # Limpiar el color rojo antes de mostrar el mensaje normal
        self.status_bar.setStyleSheet("") 
        self.status_bar.showMessage("Parámetros actualizados y aplicados al hardware.", 3000)

    def _iniciar_medicion(self):
        if self.worker.corriendo:
            self.status_bar.showMessage("La medición ya está en curso.", 3000)
            return

        # 1. Solicitar ruta y nombre de archivo al usuario
        ruta_archivo, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar Medición",
            "", 
            "CSV Files (*.csv);;Todos los archivos (*)"
        )

        # Si el usuario cancela la ventana de guardado
        if not ruta_archivo:
            self.status_bar.showMessage("Medición cancelada (no se seleccionó archivo de destino).", 4000)
            return

        # 2. Asegurar que los últimos números tipeados estén cargados
        self._sincronizar_parametros()
        
        # 3. Guardar la ruta en el estado para que el hilo la use
        self.estado_compartido['ruta_archivo'] = ruta_archivo

        # 4. Limpiar los gráficos para una nueva muestra
        self._limpiar_datos_graficos()
        self.iv_curve.setData([], [])
        self.res_curve.setData([], [])
        self.vt_curve.setData([], [])

        # 5. Arrancar el motor
        self.status_bar.setStyleSheet("") # Resetear color en caso de error previo
        self.status_bar.showMessage(f"Iniciando medición... Guardando en {ruta_archivo}")
        self.worker.iniciar_medicion()

    def _detener_medicion(self):
        if not self.worker.corriendo: return # Ignorar si ya está detenido
        self.worker.detener_medicion()
        self.status_bar.setStyleSheet("")
        self.status_bar.showMessage("Medición detenida por el usuario.", 5000)

    def _toggle_pausa_cbias(self):
        estado_actual = self.worker.pausado_cbias
        self.worker.pausado_cbias = not estado_actual
        self.worker.pausado_sbias = False # Mutual exclusion
        msg = "Pausado (CON Bias)" if self.worker.pausado_cbias else "Reanudando..."
        
        # Limpiar el color rojo antes de mostrar el mensaje normal
        self.status_bar.setStyleSheet("") 
        self.status_bar.showMessage(msg, 3000)

    def _toggle_pausa_sbias(self):
        estado_actual = self.worker.pausado_sbias
        self.worker.pausado_sbias = not estado_actual
        self.worker.pausado_cbias = False # Mutual exclusion
        msg = "Pausado (SIN Bias)" if self.worker.pausado_sbias else "Reanudando..."
        
        # Limpiar el color rojo antes de mostrar el mensaje normal
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

    def _validar_tiempos(self, *args):
            """Revisa si el Ancho de Pulso es suficiente para el NPLC seleccionado."""
            p_pane = self.dual_inst_tab.params_pane
            i_pane = self.dual_inst_tab.instant_pane
            
            ancho = p_pane.ancho_pulso.value()
            try:
                nplc = float(i_pane.combo_nplc.currentText())
            except ValueError:
                return

            usa_ch2 = i_pane.btn_ch2_toggle.isChecked()
            
            # Cálculo del tiempo mínimo físico (Integración + Relay + Overhead)
            multiplicador = 2 if usa_ch2 else 1
            tiempo_integracion = (nplc * 0.02) * multiplicador
            delay_relay = 0.015 if usa_ch2 else 0.0
            overhead = 0.015 * multiplicador + delay_relay
            tiempo_minimo = tiempo_integracion + overhead + 0.05 # 50ms margen seguridad
            
            if ancho < tiempo_minimo:
                p_pane.lbl_warning_tiempo.setText(f"⚠ PELIGRO: Ancho de pulso ({ancho}s) es muy corto para NPLC {nplc}. Mínimo sugerido: {tiempo_minimo:.3f}s")
            else:
                p_pane.lbl_warning_tiempo.setText(" ")

    def _actualizar_datos(self, t_min, v1, r1, v2, r2, i_app, es_bias):
        """Actualiza la Interfaz y los Gráficos con los datos recibidos."""
        p_pane = self.dual_inst_tab.params_pane
        i_pane = self.dual_inst_tab.instant_pane

        p_pane.corr_actual_ro.setText(f"{i_app:.3f}")
        
        def safe_format(val):
            return "NaN" if math.isnan(val) else f"{val:.4f}"

        if not es_bias:
            i_pane.ip_1_ro.setText(f"{i_app:.3f}")
            i_pane.vp_1_ro.setText(safe_format(v1))
            i_pane.rinst_1_ro.setText(safe_format(r1))
            
            # --- NUEVO: Advertencia Visual de Límite de Voltaje ---
            limite = self.estado_compartido.get('limite_voltaje', 200.0)
            if not math.isnan(v1) and abs(v1) > (0.85 * limite):
                # Cambia el fondo a naranja si superamos el 85% del límite
                i_pane.vp_1_ro.setStyleSheet("background-color: #ffb74d; color: black; font-weight: bold;")
            else:
                # Fondo gris normal
                i_pane.vp_1_ro.setStyleSheet("background-color: #f0f0f0; color: #333; font-weight: bold;")

            if self.estado_compartido.get('ch2_activado', False):
                i_pane.ip_2_ro.setText(f"{i_app:.3f}")
                i_pane.vp_2_ro.setText(safe_format(v2))
                i_pane.rinst_2_ro.setText(safe_format(r2))

        if not es_bias:
            self.data_t.append(t_min)
            self.data_v.append(v1)
            self.data_i.append(i_app)
            
            if not math.isnan(r1):
                self.data_t_res.append(t_min)
                self.data_r.append(r1)

            self.iv_curve.setData(self.data_v, self.data_i)
            self.vt_curve.setData(self.data_t, self.data_v)
            self.res_curve.setData(self.data_t_res, self.data_r)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = IVMeasurementApp()
    window.show()
    sys.exit(app.exec())