import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QHBoxLayout, QVBoxLayout, QWidget, QGridLayout, QLabel, 
                               QDoubleSpinBox, QSpinBox, QLineEdit, QGroupBox, QPushButton, QSizePolicy, QComboBox, QSpacerItem)
from PySide6.QtCore import Qt
import pyqtgraph as pg

class Lecturas34420APane(QGroupBox):
    def __init__(self):
        super().__init__("Lecturas 34420A")
        
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(5, 10, 5, 5)
        self.setLayout(main_layout)

        # ==========================================
        # SUBPANEL 1: Canal 1
        # ==========================================
        self.ch1_panel = QGroupBox("Canal 1")
        ch1_layout = QVBoxLayout()
        self.ch1_panel.setLayout(ch1_layout)

        # --- CH1 Controles Superiores ---
        ch1_top_layout = QHBoxLayout()
        
        # NPLC
        nplc_layout = QVBoxLayout()
        nplc_layout.addWidget(QLabel("NPLC"))
        self.combo_nplc = QComboBox()
        self.combo_nplc.addItems(["0.02", "0.2", "1", "2", "10", "20", "100", "200"]) 
        self.combo_nplc.setCurrentText("2") 
        nplc_layout.addWidget(self.combo_nplc)
        ch1_top_layout.addLayout(nplc_layout)

        # Rango
        rango_layout = QVBoxLayout()
        rango_layout.addWidget(QLabel("Rango"))
        self.combo_rango = QComboBox()
        self.combo_rango.addItems(["Auto", "1 mV", "10 mV", "100 mV", "1 V", "10 V", "100 V"])
        self.combo_rango.setCurrentText("10 V") 
        rango_layout.addWidget(self.combo_rango)
        ch1_top_layout.addLayout(rango_layout)

        ch1_layout.addLayout(ch1_top_layout)

        # --- CH1 Grilla de Lecturas ---
        grid1 = QGridLayout()
        grid1.setVerticalSpacing(5)
        grid1.setHorizontalSpacing(8)

        grid1.addWidget(QLabel("Ip 1 (mA)"), 0, 0)
        self.ip_1_ro = self._create_ro_display()
        grid1.addWidget(self.ip_1_ro, 1, 0)

        grid1.addWidget(QLabel("Vp 1 (V)"), 0, 1)
        self.vp_1_ro = self._create_ro_display()
        grid1.addWidget(self.vp_1_ro, 1, 1)

        grid1.addWidget(QLabel("Rinst 1 (Ω)"), 0, 2)
        self.rinst_1_ro = self._create_ro_display()
        grid1.addWidget(self.rinst_1_ro, 1, 2)

        grid1.addWidget(QLabel("Ib 1 (mA)"), 2, 0)
        self.ib_1_ro = self._create_ro_display()
        grid1.addWidget(self.ib_1_ro, 3, 0)

        grid1.addWidget(QLabel("Vb 1 (V)"), 2, 1)
        self.vb_1_ro = self._create_ro_display()
        grid1.addWidget(self.vb_1_ro, 3, 1)

        grid1.addWidget(QLabel("Rrem 1 (Ω)"), 2, 2)
        self.rrem_1_ro = self._create_ro_display()
        grid1.addWidget(self.rrem_1_ro, 3, 2)

        grid1.setRowStretch(4, 1)
        ch1_layout.addLayout(grid1)


        # ==========================================
        # SUBPANEL 2: Canal 2
        # ==========================================
        self.ch2_panel = QGroupBox("Canal 2")
        ch2_layout = QVBoxLayout()
        self.ch2_panel.setLayout(ch2_layout)

        # --- CH2 Controles Superiores ---
        ch2_top_layout = QHBoxLayout()
        self.btn_ch2_toggle = QPushButton("CH 2: APAGADO")
        self.btn_ch2_toggle.setCheckable(True)
        self.btn_ch2_toggle.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self.btn_ch2_toggle.setMinimumHeight(48) 
        self.btn_ch2_toggle.toggled.connect(self._on_ch2_toggle)
        ch2_top_layout.addWidget(self.btn_ch2_toggle)
        ch2_layout.addLayout(ch2_top_layout)

        # --- CH2 Grilla de Lecturas ---
        grid2 = QGridLayout()
        grid2.setVerticalSpacing(5)
        grid2.setHorizontalSpacing(8)

        grid2.addWidget(QLabel("Ip 2 (mA)"), 0, 0)
        self.ip_2_ro = self._create_ro_display()
        grid2.addWidget(self.ip_2_ro, 1, 0)

        grid2.addWidget(QLabel("Vp 2 (V)"), 0, 1)
        self.vp_2_ro = self._create_ro_display()
        grid2.addWidget(self.vp_2_ro, 1, 1)

        grid2.addWidget(QLabel("Rinst 2 (Ω)"), 0, 2)
        self.rinst_2_ro = self._create_ro_display()
        grid2.addWidget(self.rinst_2_ro, 1, 2)

        grid2.addWidget(QLabel("Ib 2 (mA)"), 2, 0)
        self.ib_2_ro = self._create_ro_display()
        grid2.addWidget(self.ib_2_ro, 3, 0)

        grid2.addWidget(QLabel("Vb 2 (V)"), 2, 1)
        self.vb_2_ro = self._create_ro_display()
        grid2.addWidget(self.vb_2_ro, 3, 1)

        grid2.addWidget(QLabel("Rrem 2 (Ω)"), 2, 2)
        self.rrem_2_ro = self._create_ro_display()
        grid2.addWidget(self.rrem_2_ro, 3, 2)

        grid2.setRowStretch(4, 1)
        ch2_layout.addLayout(grid2)

        # Añadir subpaneles al layout principal
        main_layout.addWidget(self.ch1_panel)
        main_layout.addWidget(self.ch2_panel)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

        self._on_ch2_toggle(False)

    def _create_ro_display(self):
        le = QLineEdit("0.00000") 
        le.setReadOnly(True)
        le.setStyleSheet("background-color: #f0f0f0; color: #333; font-weight: bold;")
        le.setAlignment(Qt.AlignmentFlag.AlignRight)
        return le

    def _on_ch2_toggle(self, checked):
        if checked:
            self.btn_ch2_toggle.setText("CH 2: ENCENDIDO")
            self.btn_ch2_toggle.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold;")
        else:
            self.btn_ch2_toggle.setText("CH 2: APAGADO")
            self.btn_ch2_toggle.setStyleSheet("background-color: #ffcccc; color: black; font-weight: bold;")
            
        widgets_to_toggle = [
            self.ip_2_ro, self.vp_2_ro, self.rinst_2_ro,
            self.ib_2_ro, self.vb_2_ro, self.rrem_2_ro
        ]
        for widget in widgets_to_toggle:
            widget.setEnabled(checked)

    # ==========================================
    # MÉTODOS AUXILIARES
    # ==========================================
    def _create_ro_display(self):
        le = QLineEdit("0.00000") # Aumentado a 5 decimales por default visual
        le.setReadOnly(True)
        le.setStyleSheet("background-color: #f0f0f0; color: #333; font-weight: bold;")
        le.setAlignment(Qt.AlignmentFlag.AlignRight)
        return le

    def _validar_filtros(self):
        filtro = self.combo_filtro.currentText()
        rango = self.combo_rango.currentText()
        
        mensaje = ""
        # 1. Check del Filtro Digital
        if filtro in ["Digital", "Ambos"]:
            mensaje += "⚠ Digital: Distorsiona barridos (usar solo en bias constante).\n"
            
        # 2. Check del Filtro Analógico (Solo en <= 100mV)
        if filtro in ["Analógico", "Ambos"]:
            rangos_invalidos = ["1 V", "10 V", "100 V"]
            if rango in rangos_invalidos:
                mensaje += rf"⚠ Analógico: Rango {rango} incompatible (solo $\le$ 100mV).\n"
                
        self.lbl_advertencia.setText(mensaje)

    def _on_ch2_toggle(self, checked):
        if checked:
            self.btn_ch2_toggle.setText("CH 2: ENCENDIDO")
            self.btn_ch2_toggle.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold;")
        else:
            self.btn_ch2_toggle.setText("CH 2: APAGADO")
            self.btn_ch2_toggle.setStyleSheet("background-color: #ffcccc; color: black; font-weight: bold;")
            
        widgets_to_toggle = [
            self.ip_2_ro, self.vp_2_ro, self.rinst_2_ro,
            self.ib_2_ro, self.vb_2_ro, self.rrem_2_ro
        ]
        for widget in widgets_to_toggle:
            widget.setEnabled(checked)


class ParametrosK224Pane(QGroupBox):
    def __init__(self):
        super().__init__("Parámetros K224")
        
        layout = QGridLayout()
        layout.setVerticalSpacing(5) 
        layout.setHorizontalSpacing(8)
        layout.setContentsMargins(5, 15, 5, 5)
        
        # LÍMITES GLOBALES DE CORRIENTE Y PRECISIÓN
        RANGO_CORRIENTE = (-105.0, 105.0)
        DECIMALES_CORRIENTE = 5
        PASO_UI = 0.001 # Las flechas arriba/abajo sumarán 1 µA en lugar de 1 mA

        # ==========================================
        # FILA 1 (Textos Fila 0, Inputs Fila 1)
        # ==========================================
        layout.addWidget(QLabel("Ancho Pulso (s)"), 0, 0)
        self.ancho_pulso = QDoubleSpinBox()
        self.ancho_pulso.setDecimals(3)
        self.ancho_pulso.setKeyboardTracking(False)
        self.ancho_pulso.setRange(0.001, 100.0)
        self.ancho_pulso.setValue(0.1) # Default: 100 ms
        layout.addWidget(self.ancho_pulso, 1, 0)

        layout.addWidget(QLabel("Corriente Máxima (mA)"), 0, 1)
        self.corr_maxima = QDoubleSpinBox()
        self.corr_maxima.setDecimals(DECIMALES_CORRIENTE)
        self.corr_maxima.setKeyboardTracking(False)
        self.corr_maxima.setRange(*RANGO_CORRIENTE)
        self.corr_maxima.setSingleStep(PASO_UI)
        self.corr_maxima.setValue(0.010) # Default: +10 µA (0.010 mA)
        layout.addWidget(self.corr_maxima, 1, 1)

        layout.addWidget(QLabel("Corriente Inicial (mA)"), 0, 2)
        self.corr_inicial = QDoubleSpinBox()
        self.corr_inicial.setDecimals(DECIMALES_CORRIENTE)
        self.corr_inicial.setKeyboardTracking(False)
        self.corr_inicial.setRange(*RANGO_CORRIENTE)
        self.corr_inicial.setSingleStep(PASO_UI)
        self.corr_inicial.setValue(0.000) # Default: 0 mA
        layout.addWidget(self.corr_inicial, 1, 2)

        layout.addWidget(QLabel("Corriente Actual (mA)"), 0, 3)
        self.corr_actual_ro = QLineEdit("0.00000")
        self.corr_actual_ro.setReadOnly(True)
        self.corr_actual_ro.setStyleSheet("background-color: #f0f0f0; color: #333; font-weight: bold;")
        self.corr_actual_ro.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.corr_actual_ro, 1, 3)

        layout.addWidget(QLabel("# Mediciones Bias"), 0, 4)
        self.num_mediciones = QSpinBox()
        self.num_mediciones.setRange(0, 10000)
        self.num_mediciones.setKeyboardTracking(False)
        self.num_mediciones.setValue(1) 
        layout.addWidget(self.num_mediciones, 1, 4)

        layout.addWidget(QLabel("Corriente Bias (mA)"), 0, 5)
        self.corr_bias = QDoubleSpinBox()
        self.corr_bias.setDecimals(DECIMALES_CORRIENTE)
        self.corr_bias.setKeyboardTracking(False)
        self.corr_bias.setRange(*RANGO_CORRIENTE)
        self.corr_bias.setSingleStep(PASO_UI)
        self.corr_bias.setValue(0.00010) # Default: +0.1 µA (0.0001 mA)
        layout.addWidget(self.corr_bias, 1, 5)

        # ==========================================
        # FILA 2 (Textos Fila 2, Inputs Fila 3)
        # ==========================================
        layout.addWidget(QLabel("Período Pulso (s)"), 2, 0)
        self.periodo_pulso = QDoubleSpinBox()
        self.periodo_pulso.setDecimals(3)
        self.periodo_pulso.setRange(0.01, 1000.0)
        self.periodo_pulso.setValue(1.0) # Default: 1 segundo
        layout.addWidget(self.periodo_pulso, 3, 0)

        layout.addWidget(QLabel("Corriente Mínima (mA)"), 2, 1)
        self.corr_minima = QDoubleSpinBox()
        self.corr_minima.setDecimals(DECIMALES_CORRIENTE)
        self.corr_minima.setKeyboardTracking(False)
        self.corr_minima.setRange(*RANGO_CORRIENTE)
        self.corr_minima.setSingleStep(PASO_UI)
        self.corr_minima.setValue(-0.010) # Default: -10 µA (-0.010 mA)
        layout.addWidget(self.corr_minima, 3, 1)

        layout.addWidget(QLabel("Paso Corriente (mA)"), 2, 2)
        self.paso_corr = QDoubleSpinBox()
        self.paso_corr.setDecimals(DECIMALES_CORRIENTE)
        self.paso_corr.setKeyboardTracking(False)
        self.paso_corr.setRange(*RANGO_CORRIENTE)
        self.paso_corr.setSingleStep(PASO_UI)
        self.paso_corr.setValue(0.001) # Default: +1 µA (0.001 mA)
        layout.addWidget(self.paso_corr, 3, 2)

        layout.addWidget(QLabel("Límite Voltaje (V)"), 2, 3)
        self.limite_voltaje = QDoubleSpinBox()
        self.limite_voltaje.setRange(0.0, 200.0)
        self.limite_voltaje.setValue(20.0) # Default: 20 V
        layout.addWidget(self.limite_voltaje, 3, 3)

        # Label de advertencia de tiempos
        self.lbl_warning_tiempo = QLabel(" ")
        self.lbl_warning_tiempo.setStyleSheet("color: #d32f2f; font-weight: bold; font-size: 11px;")
        layout.addWidget(self.lbl_warning_tiempo, 4, 0, 1, 6)
        
        layout.setRowMinimumHeight(4, 20)
        
        # ==========================================
        # FILA 3: BOTONES (Fila 5 en la grilla)
        # ==========================================
        btn_layout = QHBoxLayout()
        
        self.btn_medir = QPushButton("Medir")
        self.btn_medir.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold;") 
        
        self.btn_pausa_cbias = QPushButton("Pausa c/Bias")
        self.btn_pausa_sbias = QPushButton("Pausa s/Bias")
        
        self.btn_detencion = QPushButton("Detención")
        self.btn_detencion.setStyleSheet("background-color: #c62828; color: white; font-weight: bold;") 
        
        self.btn_aplicar = QPushButton("Aplicar Cambios")
        self.btn_aplicar.setStyleSheet("background-color: #fff3e0; color: black; font-weight: bold;")

        for btn in [self.btn_medir, self.btn_aplicar, self.btn_pausa_cbias, self.btn_pausa_sbias, self.btn_detencion]:
            btn.setMinimumHeight(35)
            btn_layout.addWidget(btn)

        layout.addLayout(btn_layout, 5, 0, 1, 6)
        layout.setRowStretch(6, 1)
        
        self.setLayout(layout)
        # Cambiar Maximum por Expanding en AMBOS paneles
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)


class ParametrosRelajacionPane(QGroupBox):
    def __init__(self):
        super().__init__("Matriz de Relajación K224")
        
        layout = QGridLayout()
        layout.setVerticalSpacing(5) 
        layout.setHorizontalSpacing(8)
        layout.setContentsMargins(5, 15, 5, 5)

        # ==========================================
        # FILA 1: Matrices de Corriente y Tiempos
        # ==========================================
        layout.addWidget(QLabel("Corrientes Pulso (mA)\n[Ej: 0.01, 0.02, -0.01]"), 0, 0)
        self.corr_pulso = QLineEdit("0.010, 0.020, 0.030, -0.010, -0.020, -0.030")
        self.corr_pulso.setStyleSheet("background-color: #ffffff; color: #000000;")
        layout.addWidget(self.corr_pulso, 1, 0)

        layout.addWidget(QLabel("Tiempo de Carga (s)"), 0, 1)
        self.tiempo_pulso = QDoubleSpinBox()
        self.tiempo_pulso.setDecimals(3)
        self.tiempo_pulso.setRange(0.001, 10000.0)
        self.tiempo_pulso.setValue(5.0)
        layout.addWidget(self.tiempo_pulso, 1, 1)

        layout.addWidget(QLabel("Corrientes Bias (mA)\n[Ej: 0.001, -0.001]"), 0, 2)
        self.corr_bias = QLineEdit("0.001, -0.001, 0.002, -0.002")
        self.corr_bias.setStyleSheet("background-color: #ffffff; color: #000000;")
        layout.addWidget(self.corr_bias, 1, 2)

        layout.addWidget(QLabel("Tiempo Relajación (s)"), 0, 3)
        self.tiempo_descarga = QDoubleSpinBox()
        self.tiempo_descarga.setRange(0.1, 100000.0)
        self.tiempo_descarga.setValue(60.0)
        layout.addWidget(self.tiempo_descarga, 1, 3)

        # ==========================================
        # FILA 2: Lógica de Lectura y Seguridad
        # ==========================================
        self.btn_pulsado = QPushButton("Modo: CONTINUO")
        self.btn_pulsado.setCheckable(True)
        self.btn_pulsado.setStyleSheet("background-color: #81d4fa; color: black; font-weight: bold;")
        self.btn_pulsado.toggled.connect(self._on_pulsado_toggle)
        layout.addWidget(self.btn_pulsado, 2, 0, 2, 1)

        layout.addWidget(QLabel("Período Lectura (s)"), 2, 1)
        self.periodo = QDoubleSpinBox()
        self.periodo.setDecimals(3)
        self.periodo.setRange(0.01, 10000.0)
        self.periodo.setValue(1.0)
        self.periodo.setEnabled(False)
        layout.addWidget(self.periodo, 3, 1)

        layout.addWidget(QLabel("Ancho Lectura (s)"), 2, 2)
        self.ancho_lectura = QDoubleSpinBox()
        self.ancho_lectura.setDecimals(3)
        self.ancho_lectura.setRange(0.001, 100.0)
        self.ancho_lectura.setValue(0.5)
        self.ancho_lectura.setEnabled(False)
        layout.addWidget(self.ancho_lectura, 3, 2)
        
        # [Mantener el código anterior intacto hasta "Límite Voltaje"]
        layout.addWidget(QLabel("Límite Voltaje (V)"), 2, 3)
        self.limite_voltaje = QDoubleSpinBox()
        self.limite_voltaje.setRange(0.0, 200.0)
        self.limite_voltaje.setValue(20.0)
        layout.addWidget(self.limite_voltaje, 3, 3)

        # NUEVO: Label de advertencia de tiempos (reemplaza el setRowMinimumHeight)
        self.lbl_warning_tiempo = QLabel(" ")
        self.lbl_warning_tiempo.setStyleSheet("color: #d32f2f; font-weight: bold; font-size: 11px;")
        layout.addWidget(self.lbl_warning_tiempo, 4, 0, 1, 4)

        # ==========================================
        # FILA 3: Controles
        # ==========================================
        btn_layout = QHBoxLayout()
        self.btn_medir = QPushButton("Iniciar Matriz")
        self.btn_medir.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold;") 
        self.btn_detencion = QPushButton("Detención Global")
        self.btn_detencion.setStyleSheet("background-color: #c62828; color: white; font-weight: bold;") 
        self.btn_aplicar = QPushButton("Aplicar Cambios")
        self.btn_aplicar.setStyleSheet("background-color: #fff3e0; color: black; font-weight: bold;")

        for btn in [self.btn_medir, self.btn_aplicar, self.btn_detencion]:
            btn.setMinimumHeight(35)
            btn_layout.addWidget(btn)

        layout.addLayout(btn_layout, 5, 0, 1, 4)
        layout.setRowStretch(6, 1)
        self.setLayout(layout)
        # Cambiar Maximum por Expanding en AMBOS paneles
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def _on_pulsado_toggle(self, checked):
        if checked:
            self.btn_pulsado.setText("Modo: PULSADO")
            self.btn_pulsado.setStyleSheet("background-color: #b39ddb; color: white; font-weight: bold;")
            self.periodo.setEnabled(True)
            self.ancho_lectura.setEnabled(True)
        else:
            self.btn_pulsado.setText("Modo: CONTINUO")
            self.btn_pulsado.setStyleSheet("background-color: #81d4fa; color: black; font-weight: bold;")
            self.periodo.setEnabled(False)
            self.ancho_lectura.setEnabled(False)

# ==============================================================================
# LAS CLASES DEL SMU (B2902A) SE MANTIENEN INTACTAS DEBAJO DE ESTA LÍNEA
# ==============================================================================

class InstantPane(QGroupBox):
    def __init__(self):
        super().__init__("Instantaneous Readings")
        
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(5, 10, 5, 5)
        self.setLayout(main_layout)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        
        # ==========================================
        # SUBPANEL 1: Channel 1
        # ==========================================
        self.ch1_panel = QGroupBox("Channel 1")
        grid1 = QGridLayout()
        grid1.setVerticalSpacing(2)
        grid1.setHorizontalSpacing(8)
        self.ch1_panel.setLayout(grid1)

        self.btn_mode_toggle = QPushButton("Mode: V (mV)")
        self.btn_mode_toggle.setCheckable(True)
        self.btn_mode_toggle.toggled.connect(self._on_mode_toggle) 
        grid1.addWidget(self.btn_mode_toggle, 1, 0) 

        grid1.addWidget(QLabel("Icc 1 (mA)"), 0, 1)
        self.icc_1 = QDoubleSpinBox()
        self.icc_1.setDecimals(3)
        grid1.addWidget(self.icc_1, 1, 1)

        grid1.addWidget(QLabel("Vcc 1 (V)"), 0, 2)
        self.vcc_1 = QDoubleSpinBox()
        self.vcc_1.setDecimals(3)
        grid1.addWidget(self.vcc_1, 1, 2)

        grid1.addWidget(QLabel("Ip 1 (mA)"), 2, 0)
        self.ip_1_ro = self._create_ro_display()
        grid1.addWidget(self.ip_1_ro, 3, 0)

        grid1.addWidget(QLabel("Vp 1 (V)"), 2, 1)
        self.vp_1_ro = self._create_ro_display()
        grid1.addWidget(self.vp_1_ro, 3, 1)

        grid1.addWidget(QLabel("Rinst 1 (Ω)"), 2, 2)
        self.rinst_1_ro = self._create_ro_display()
        grid1.addWidget(self.rinst_1_ro, 3, 2)

        grid1.addWidget(QLabel("Ib 1 (mA)"), 4, 0)
        self.ib_1_ro = self._create_ro_display()
        grid1.addWidget(self.ib_1_ro, 5, 0)

        grid1.addWidget(QLabel("Vb 1 (V)"), 4, 1)
        self.vb_1_ro = self._create_ro_display()
        grid1.addWidget(self.vb_1_ro, 5, 1)

        grid1.addWidget(QLabel("Rrem 1 (Ω)"), 4, 2)
        self.rrem_1_ro = self._create_ro_display()
        grid1.addWidget(self.rrem_1_ro, 5, 2)

        grid1.setRowStretch(6, 1)

        # ==========================================
        # SUBPANEL 2: Channel 2
        # ==========================================
        self.ch2_panel = QGroupBox("Channel 2")
        grid2 = QGridLayout()
        grid2.setVerticalSpacing(2)
        grid2.setHorizontalSpacing(8)
        self.ch2_panel.setLayout(grid2)

        self.btn_ch2_toggle = QPushButton("CH 2: OFF")
        self.btn_ch2_toggle.setCheckable(True)
        self.btn_ch2_toggle.setStyleSheet("background-color: #ffcccc;") 
        self.btn_ch2_toggle.toggled.connect(self._on_ch2_toggle)
        grid2.addWidget(self.btn_ch2_toggle, 1, 0)

        grid2.addWidget(QLabel("Icc 2 (mA)"), 0, 1)
        self.icc_2 = QDoubleSpinBox()
        self.icc_2.setDecimals(3)
        grid2.addWidget(self.icc_2, 1, 1)

        grid2.addWidget(QLabel("Vcc 2 (V)"), 0, 2)
        self.vcc_2 = QDoubleSpinBox()
        self.vcc_2.setDecimals(3)
        grid2.addWidget(self.vcc_2, 1, 2)

        grid2.addWidget(QLabel("Ip 2 (mA)"), 2, 0)
        self.ip_2_ro = self._create_ro_display()
        grid2.addWidget(self.ip_2_ro, 3, 0)

        grid2.addWidget(QLabel("Vp 2 (V)"), 2, 1)
        self.vp_2_ro = self._create_ro_display()
        grid2.addWidget(self.vp_2_ro, 3, 1)

        grid2.addWidget(QLabel("Rinst 2 (Ω)"), 2, 2)
        self.rinst_2_ro = self._create_ro_display()
        grid2.addWidget(self.rinst_2_ro, 3, 2)

        grid2.addWidget(QLabel("Ib 2 (mA)"), 4, 0)
        self.ib_2_ro = self._create_ro_display()
        grid2.addWidget(self.ib_2_ro, 5, 0)

        grid2.addWidget(QLabel("Vb 2 (V)"), 4, 1)
        self.vb_2_ro = self._create_ro_display()
        grid2.addWidget(self.vb_2_ro, 5, 1)

        grid2.addWidget(QLabel("Rrem 2 (Ω)"), 4, 2)
        self.rrem_2_ro = self._create_ro_display()
        grid2.addWidget(self.rrem_2_ro, 5, 2)

        grid2.setRowStretch(6, 1)

        grid1.setColumnStretch(3, 1)
        grid2.setColumnStretch(3, 1)
        main_layout.addWidget(self.ch1_panel)
        main_layout.addWidget(self.ch2_panel)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

    def _create_ro_display(self):
        le = QLineEdit("0.00")
        le.setReadOnly(True)
        le.setStyleSheet("background-color: #f0f0f0; color: #333; font-weight: bold;")
        le.setAlignment(Qt.AlignmentFlag.AlignRight)
        return le

    def _on_mode_toggle(self, checked):
        if checked:
            self.btn_mode_toggle.setText("Mode: I (mA)")
        else:
            self.btn_mode_toggle.setText("Mode: V (mV)")

    def _on_ch2_toggle(self, checked):
        if checked:
            self.btn_ch2_toggle.setText("CH 2: ON")
            self.btn_ch2_toggle.setStyleSheet("background-color: #ccffcc;")
        else:
            self.btn_ch2_toggle.setText("CH 2: OFF")
            self.btn_ch2_toggle.setStyleSheet("background-color: #ffcccc;")


class ParametersPane(QGroupBox):
    def __init__(self):
        super().__init__("Measurement Parameters")
        
        layout = QGridLayout()
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        layout.setVerticalSpacing(2)  
        layout.setHorizontalSpacing(5) 
        layout.setContentsMargins(10, 15, 10, 10)
        
        layout.addWidget(QLabel("Ancho pulso (s)"), 0, 0)
        self.ancho_pulso = QDoubleSpinBox()
        self.ancho_pulso.setDecimals(3)
        layout.addWidget(self.ancho_pulso, 1, 0)

        layout.addWidget(QLabel("Amplitud pulso"), 0, 1)
        self.amp_pulso = QDoubleSpinBox()
        layout.addWidget(self.amp_pulso, 1, 1)

        layout.addWidget(QLabel("Amplitud inicial"), 0, 2)
        self.amp_inicial = QDoubleSpinBox()
        layout.addWidget(self.amp_inicial, 1, 2)

        layout.addWidget(QLabel("Amplitud máxima"), 0, 3)
        self.amp_max = QDoubleSpinBox()
        layout.addWidget(self.amp_max, 1, 3)

        layout.addWidget(QLabel("Amplitud pulso actual"), 0, 4)
        self.amp_actual_readout = QLineEdit("0.00")
        self.amp_actual_readout.setReadOnly(True)
        self.amp_actual_readout.setStyleSheet("background-color: #f0f0f0; color: #333;")
        self.amp_actual_readout.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.amp_actual_readout, 1, 4)

        layout.addWidget(QLabel("# mediciones bias"), 0, 5)
        self.num_mediciones = QSpinBox()
        self.num_mediciones.setRange(1, 10000)
        layout.addWidget(self.num_mediciones, 1, 5)

        layout.addWidget(QLabel("Amplitud bias"), 0, 6)
        self.amp_bias = QDoubleSpinBox()
        layout.addWidget(self.amp_bias, 1, 6)
        
        layout.addWidget(QLabel("Período pulso (s)"), 2, 0)
        self.periodo_pulso = QDoubleSpinBox()
        layout.addWidget(self.periodo_pulso, 3, 0)

        layout.addWidget(QLabel("Paso de amplitud"), 2, 1)
        self.paso_amp = QDoubleSpinBox()
        layout.addWidget(self.paso_amp, 3, 1)

        layout.addWidget(QLabel("Amplitud mínima"), 2, 2)
        self.amp_min = QDoubleSpinBox()
        layout.addWidget(self.amp_min, 3, 2)

        layout.setColumnStretch(7, 1)