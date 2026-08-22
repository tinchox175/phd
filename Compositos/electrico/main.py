import sys
import math
import csv
import os
from PySide6.QtWidgets import (QApplication, QMainWindow, QHBoxLayout, QVBoxLayout, 
                               QWidget, QLabel, QGroupBox, QPushButton, QTabWidget, 
                               QLineEdit, QMessageBox, QStatusBar, QFileDialog)
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt
import pyqtgraph as pg

# Import the View (UI) and Model (Hardware)
from IVsuplemento import ParametersPane, InstantPane, ParametrosK224Pane, Lecturas34420APane, ParametrosRelajacionPane
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
        
        # Diccionario de estado compartido con el Worker
        self.estado_compartido = {}
        
        # Variable para almacenar la ruta por defecto de guardado/carga
        self.directorio_defecto = ""

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
        
        self.action_abrir = QAction("Cargar...", self)
        self.action_abrir.triggered.connect(self._cargar_medicion) # <-- Conectado aquí
        archivo_menu.addAction(self.action_abrir)
        
        # Menú Opciones
        opciones_menu = menu_bar.addMenu("Opciones")
        
        self.action_configurar_ruta = QAction("Configurar Ruta por Defecto...", self)
        self.action_configurar_ruta.triggered.connect(self._configurar_ruta_defecto) # <-- Actualizado
        opciones_menu.addAction(self.action_configurar_ruta)

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
        self.relajacion_tab = RelajacionTab() # <-- NUEVO
        
        self.setup_tabs.addTab(self.dual_inst_tab, "Setup: K224 + 34420A")
        self.setup_tabs.addTab(self.relajacion_tab, "Relajación") # <-- NUEVO
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
        self.iv_plot.addLegend()
        self.iv_curve = self.iv_plot.plot(symbol='o', width=1,
                                           symbolSize=6, symbolBrush=pg.mkBrush('#0055ff'), name="Canal 1")
        self.iv_curve_ch2 = self.iv_plot.plot(symbol='s', width=1,
                                               symbolSize=6, symbolBrush=pg.mkBrush('#ff5500'), name="Canal 2")
        self.iv_last = self.iv_plot.plot(pen=None, symbol='o', symbolSize=10, symbolBrush='g', symbolPen='k')
        self.iv_last_ch2 = self.iv_plot.plot(pen=None, symbol='s', symbolSize=10, symbolBrush='g', symbolPen='k')
        iv_layout.addWidget(self.iv_plot)
        self.iv_plot_pane.setLayout(iv_layout)
        bottom_row_layout.addWidget(self.iv_plot_pane)

        # Resistance Plot Pane
        self.res_plot_pane = QGroupBox("Gráfico Resistencia")
        res_layout = QVBoxLayout()
        self.res_plot = pg.PlotWidget(title="Resistencia vs Corriente")
        self._style_plot(self.res_plot, "Corriente (mA)", "Resistencia (Ω)")
        self.res_plot.addLegend()
        
        # Curvas para canal 1 y canal 2
        self.rinst_curve = self.res_plot.plot(pen=pg.mkPen(color='#0055ff', width=1), 
                                              symbol='o', symbolSize=5, symbolBrush='#0055ff', name="Rinst Ch1")
        self.rinst_curve_ch2 = self.res_plot.plot(pen=pg.mkPen(color='#ff5500', width=1), 
                                                  symbol='s', symbolSize=5, symbolBrush='#ff5500', name="Rinst Ch2")
        self.rrem_curve = self.res_plot.plot(pen=pg.mkPen(color='#0055ff', width=1, style=Qt.PenStyle.DashLine), 
                                             symbol='o', symbolSize=5, symbolBrush='#0055ff', name="Rrem Ch1")
        self.rrem_curve_ch2 = self.res_plot.plot(pen=pg.mkPen(color='#ff5500', width=1, style=Qt.PenStyle.DashLine), 
                                                 symbol='s', symbolSize=5, symbolBrush='#ff5500', name="Rrem Ch2")
        self.rinst_last = self.res_plot.plot(pen=None, symbol='o', symbolSize=10, symbolBrush='r', symbolPen='k')
        self.rinst_last_ch2 = self.res_plot.plot(pen=None, symbol='s', symbolSize=10, symbolBrush='r', symbolPen='k')
        
        self.rrem_last = self.res_plot.plot(pen=None, symbol='o', symbolSize=10, symbolBrush='r', symbolPen='k')
        self.rrem_last_ch2 = self.res_plot.plot(pen=None, symbol='s', symbolSize=10, symbolBrush='r', symbolPen='k')
        res_layout.addWidget(self.res_plot)
        self.res_plot_pane.setLayout(res_layout)
        bottom_row_layout.addWidget(self.res_plot_pane)

        # Voltage vs Time Plot Pane
        self.vt_plot_pane = QGroupBox("Monitoreo Temporal")
        vt_layout = QVBoxLayout()
        self.vt_plot = pg.PlotWidget(title="Voltaje vs Tiempo")
        self._style_plot(self.vt_plot, "Tiempo (min)", "Voltaje (V)")
        self.vt_plot.addLegend()
        self.vt_curve = self.vt_plot.plot(pen=pg.mkPen(color='#00aa00', width=2), name="Canal 1")
        self.vt_curve_ch2 = self.vt_plot.plot(pen=pg.mkPen(color='#ff5500', width=2), name="Canal 2")
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
        
        # Botones UI -> Funciones del Controlador (Modo Triangular)
        p_pane.btn_aplicar.clicked.connect(self._sincronizar_parametros)
        p_pane.btn_medir.clicked.connect(self._iniciar_medicion)
        p_pane.btn_detencion.clicked.connect(self._detener_medicion)
        p_pane.btn_pausa_cbias.clicked.connect(self._toggle_pausa_cbias)
        p_pane.btn_pausa_sbias.clicked.connect(self._toggle_pausa_sbias)

        # NUEVO: Botones UI -> Funciones del Controlador (Modo Relajación)
        r_pane = self.relajacion_tab.params_pane
        r_pane.btn_aplicar.clicked.connect(self._sincronizar_parametros)
        r_pane.btn_medir.clicked.connect(self._iniciar_medicion)
        r_pane.btn_detencion.clicked.connect(self._detener_medicion)

        # Señales del Worker -> Funciones del Controlador
        self.worker.nueva_secuencia.connect(self._preparar_nueva_secuencia)
        self.worker.datos_actualizados.connect(self._actualizar_datos)
        self.worker.paso_invertido.connect(self._invertir_paso)
        self.worker.error_detectado.connect(self._mostrar_error)

        # Validaciones en vivo (NPLC vs Ancho Pulso)
        p_pane.ancho_pulso.valueChanged.connect(self._validar_tiempos)
        i_pane.combo_nplc.currentTextChanged.connect(self._validar_tiempos)
        i_pane.btn_ch2_toggle.toggled.connect(self._validar_tiempos)

        # NUEVO: Detectar cambio de pestaña para cambiar el eje del gráfico
        self.setup_tabs.currentChanged.connect(self._al_cambiar_pestana)
        

    def _al_cambiar_pestana(self, index):
        """Cambia dinámicamente el eje X del gráfico de resistencia según el modo."""
        nombre_pestana = self.setup_tabs.tabText(index)
        if nombre_pestana == "Relajación":
            self.res_plot.setLabel('bottom', "Tiempo (min)")
        elif "K224" in nombre_pestana:
            self.res_plot.setLabel('bottom', "Corriente (mA)")

    def _limpiar_datos_graficos(self):
        self.data_t = []
        self.data_v = []
        self.data_i = []
        self.data_t_ch2 = []
        self.data_v_ch2 = []
        self.data_i_ch2 = []
        
        # Reset de las listas de datos
        self.data_i_rinst = []
        self.data_rinst = []
        self.data_t_rinst = [] # NUEVO Eje X de Tiempo

        self.data_i_rrem = []
        self.data_rrem = []
        self.data_t_rrem = []  # NUEVO Eje X de Tiempo

        self.data_i_rinst_ch2 = []
        self.data_rinst_ch2 = []
        self.data_t_rinst_ch2 = [] # NUEVO Eje X de Tiempo

        self.data_i_rrem_ch2 = []
        self.data_rrem_ch2 = []
        self.data_t_rrem_ch2 = []  # NUEVO Eje X de Tiempo

    # ==========================================
    # LÓGICA DE CONTROL (SLOTS)
    # ==========================================

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
        if self.worker.corriendo:
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
                        is_smu = False # NUEVO: Bandera para identificar el archivo
                        
                        # ---------------------------------------------------------
                        # DETECCIÓN DE FORMATO (Nuevo vs SMU Viejo)
                        # ---------------------------------------------------------
                        if "I pulso (mA)" in fila:
                            # FORMATO NUEVO (K224 + 34420A)
                            i_inst = float(fila["I pulso (mA)"])
                            r1_inst = float(fila["Rinst 1 (Ohm)"])
                            r2_inst = float(fila.get("Rinst 2 (Ohm)", float('nan')))
                            
                        elif "I pulso(mA)" in fila:
                            # FORMATO VIEJO (B2902A SMU)
                            is_smu = True # Activamos la bandera
                            i_inst = float(fila["Iinst 1 (mA)"]) 
                            r1_inst = float(fila["Rinst 1(Ohm)"])
                            r2_inst = float(fila.get("Rinst 2(Ohm)", float('nan')))
                            
                        else:
                            # Fila irreconocible
                            continue

                        # Columnas compartidas
                        v1_inst = float(fila.get("Vinst 1 (V)", float('nan')))
                        r1_bias = float(fila.get("Rrem 1 (Ohm)", float('nan')))
                        v2_inst = float(fila.get("Vinst 2 (V)", float('nan')))
                        r2_bias = float(fila.get("Rrem 2 (Ohm)", float('nan')))
                        
                        # ---------------------------------------------------------
                        # NUEVO: FILTRO DE BASURA (Solo para archivos SMU)
                        # Si el valor absoluto supera 1e30, lo convertimos en NaN
                        # ---------------------------------------------------------
                        if is_smu:
                            if abs(v2_inst) > 1e30: v2_inst = float('nan')
                            if abs(r2_inst) > 1e30: r2_inst = float('nan')
                            if abs(r2_bias) > 1e30: r2_bias = float('nan')
                            
                    except ValueError:
                        continue # Ignorar si hay texto corrupto
                    
                    # Poblar datos del pulso principal
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
                        
                    # Poblar datos del Canal 2 si existen (y si no fueron limpiados por el filtro)
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

            # Actualizar todos los gráficos con los arrays completos
            self.iv_curve.setData(self.data_v, self.data_i)
            self.vt_curve.setData(self.data_t, self.data_v)
            self.rinst_curve.setData(self.data_i_rinst, self.data_rinst)
            self.rrem_curve.setData(self.data_i_rrem, self.data_rrem)
            
            self.iv_curve_ch2.setData(self.data_v_ch2, self.data_i_ch2)
            self.vt_curve_ch2.setData(self.data_t_ch2, self.data_v_ch2)
            self.rinst_curve_ch2.setData(self.data_i_rinst_ch2, self.data_rinst_ch2)
            self.rrem_curve_ch2.setData(self.data_i_rrem_ch2, self.data_rrem_ch2)
            
            # Limpiar los puntos rojos de rastreo al cargar datos históricos
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