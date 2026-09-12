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

from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox

class ControlTemperaturaPane(QGroupBox):
    def __init__(self):
        super().__init__("Control de Temperatura (LakeShore + Motor)")
        
        layout = QGridLayout()
        layout.setVerticalSpacing(5) 
        layout.setHorizontalSpacing(8)
        layout.setContentsMargins(5, 15, 5, 5)

        # ==========================================
        # FILA 1: Configuración de la Rampa (Añadido Paso dT)
        # ==========================================
        layout.addWidget(QLabel("T Inicial (K)"), 0, 0)
        self.t_inicial = QDoubleSpinBox()
        self.t_inicial.setRange(0.0, 400.0)
        self.t_inicial.setValue(295.0)
        layout.addWidget(self.t_inicial, 1, 0)

        layout.addWidget(QLabel("T Final (K)"), 0, 1)
        self.t_final = QDoubleSpinBox()
        self.t_final.setRange(0.0, 400.0)
        self.t_final.setValue(290.0)
        layout.addWidget(self.t_final, 1, 1)

        layout.addWidget(QLabel("Paso dT (K)"), 0, 2)
        self.t_paso = QDoubleSpinBox()
        self.t_paso.setRange(0.1, 400.0)
        self.t_paso.setValue(5.0)
        layout.addWidget(self.t_paso, 1, 2)

        layout.addWidget(QLabel("Rate (K/min)"), 0, 3)
        self.rate = QDoubleSpinBox()
        self.rate.setRange(0.01, 50.0)
        self.rate.setValue(2.0)
        layout.addWidget(self.rate, 1, 3)
        
        layout.addWidget(QLabel("¿Estabilizar? (1=Sí)"), 0, 4)
        self.estabilizar = QSpinBox()
        self.estabilizar.setRange(0, 1)
        self.estabilizar.setValue(1)
        layout.addWidget(self.estabilizar, 1, 4)

        self.btn_agregar_paso = QPushButton("Agregar a Tabla")
        layout.addWidget(self.btn_agregar_paso, 1, 5)

        # ==========================================
        # FILA 2: Tabla de Pasos
        # ==========================================
        self.tabla_pasos = QTableWidget(0, 3)
        self.tabla_pasos.setHorizontalHeaderLabels(["T Setpoint (K)", "Rate (K/min)", "Estable?"])
        self.tabla_pasos.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabla_pasos.setMinimumHeight(120)
        layout.addWidget(self.tabla_pasos, 2, 0, 1, 6)
        
        btn_layout_tabla = QHBoxLayout()
        self.btn_eliminar_paso = QPushButton("Borrar Fila Seleccionada")
        self.btn_limpiar_tabla = QPushButton("Limpiar Tabla Completa")
        btn_layout_tabla.addWidget(self.btn_eliminar_paso)
        btn_layout_tabla.addWidget(self.btn_limpiar_tabla)
        layout.addLayout(btn_layout_tabla, 3, 0, 1, 6)

        # ==========================================
        # FILA 3: Límites de Motor y Control Manual 
        # ==========================================
        layout.addWidget(QLabel("Motor Máx (V)"), 4, 0)
        self.motor_max = QDoubleSpinBox()
        self.motor_max.setValue(4.8)
        layout.addWidget(self.motor_max, 5, 0)

        layout.addWidget(QLabel("Motor Mín (V)"), 4, 1)
        self.motor_min = QDoubleSpinBox()
        self.motor_min.setValue(1.2)
        layout.addWidget(self.motor_min, 5, 1)

        manual_layout = QVBoxLayout()
        self.chk_motor_manual = QCheckBox("Override Manual")
        self.chk_motor_manual.setStyleSheet("color: #d32f2f; font-weight: bold;")
        manual_layout.addWidget(self.chk_motor_manual)
        
        self.v_motor_manual = QDoubleSpinBox()
        self.v_motor_manual.setPrefix("V Motor: ")
        self.v_motor_manual.setRange(0.0, 4.9)
        self.v_motor_manual.setValue(2.6)
        manual_layout.addWidget(self.v_motor_manual)
        
        layout.addLayout(manual_layout, 4, 2, 2, 2)
        
        layout.addWidget(QLabel("P / I / D (Opcional)"), 4, 4, 1, 2)
        self.pid_input = QLineEdit("50, 20, 0")
        layout.addWidget(self.pid_input, 5, 4, 1, 2)

        # ==========================================
        # FILA 4: Parámetros de Medición (Método Delta)
        # ==========================================
        layout.addWidget(QLabel("I Bias (mA)"), 6, 0)
        self.i_bias = QDoubleSpinBox()
        self.i_bias.setDecimals(5)
        self.i_bias.setRange(-105.0, 105.0)
        self.i_bias.setValue(0.001)
        layout.addWidget(self.i_bias, 7, 0)

        layout.addWidget(QLabel("Límite Voltaje (V)"), 6, 1)
        self.vlim = QDoubleSpinBox()
        self.vlim.setValue(20.0)
        layout.addWidget(self.vlim, 7, 1)
        
        layout.addWidget(QLabel("N Mediciones (Delta)"), 6, 2)
        self.n_stat = QSpinBox()
        self.n_stat.setRange(1, 100)
        self.n_stat.setValue(3)
        layout.addWidget(self.n_stat, 7, 2)

        auto_layout = QVBoxLayout()
        self.chk_auto_rango = QCheckBox("Auto-Rango I")
        self.chk_auto_rango.setChecked(False)
        auto_layout.addWidget(self.chk_auto_rango)
        
        self.v_max = QDoubleSpinBox()
        self.v_max.setPrefix("Max V: ")
        self.v_max.setDecimals(3)
        self.v_max.setValue(0.01)
        auto_layout.addWidget(self.v_max)
        
        self.v_min = QDoubleSpinBox()
        self.v_min.setPrefix("Min V: ")
        self.v_min.setDecimals(3)
        self.v_min.setValue(0.001)
        auto_layout.addWidget(self.v_min)
        layout.addLayout(auto_layout, 6, 3, 2, 3)

        # ==========================================
        # FILA 5: Controles Principales
        # ==========================================
        btn_layout = QHBoxLayout()
        self.btn_medir = QPushButton("Iniciar Rampa")
        self.btn_medir.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold; height: 35px;") 
        
        self.btn_aplicar = QPushButton("Aplicar Cambios")
        self.btn_aplicar.setStyleSheet("background-color: #fff3e0; color: black; font-weight: bold; height: 35px;")
        
        self.btn_detencion = QPushButton("Detener Rampa")
        self.btn_detencion.setStyleSheet("background-color: #c62828; color: white; font-weight: bold; height: 35px;") 
        
        for btn in [self.btn_medir, self.btn_aplicar, self.btn_detencion]:
            btn_layout.addWidget(btn)

        layout.addLayout(btn_layout, 8, 0, 1, 6)
        
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        
        # Conexiones internas de la UI 
        self.btn_agregar_paso.clicked.connect(self._agregar_a_tabla)
        self.btn_limpiar_tabla.clicked.connect(lambda: self.tabla_pasos.setRowCount(0))
        self.btn_eliminar_paso.clicked.connect(self._eliminar_fila)

    def _agregar_a_tabla(self):
        import numpy as np
        t_ini = self.t_inicial.value()
        t_fin = self.t_final.value()
        paso = self.t_paso.value()
        rate = self.rate.value()
        estable = self.estabilizar.value()
        
        if t_ini == t_fin:
            puntos_t = [t_fin]
        else:
            direccion = 1 if t_fin > t_ini else -1
            # np.arange no incluye el último valor si es exacto, agregamos margen del 10% del paso
            puntos_t = list(np.arange(t_ini, t_fin + (direccion * paso * 0.1), direccion * paso))
            
        for p in puntos_t:
            row = self.tabla_pasos.rowCount()
            self.tabla_pasos.insertRow(row)
            self.tabla_pasos.setItem(row, 0, QTableWidgetItem(f"{p:.2f}"))
            self.tabla_pasos.setItem(row, 1, QTableWidgetItem(str(rate)))
            self.tabla_pasos.setItem(row, 2, QTableWidgetItem(str(estable)))

    def _eliminar_fila(self):
        row = self.tabla_pasos.currentRow()
        if row >= 0:
            self.tabla_pasos.removeRow(row)

class TemperaturaTab(QWidget):
    """Wrapper para la pestaña de prueba de Temperatura (LakeShore + Motor + K224 + A34420A)."""
    def __init__(self):
        super().__init__()
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)

        panes_layout = QHBoxLayout()
        self.params_pane = ControlTemperaturaPane()
        self.instant_pane = Lecturas34420APane() # Reutilizamos el panel del voltímetro de IVsuplemento
        
        panes_layout.addWidget(self.params_pane, alignment=Qt.AlignmentFlag.AlignTop)
        panes_layout.addWidget(self.instant_pane, alignment=Qt.AlignmentFlag.AlignTop)
        panes_layout.addStretch()
        
        main_layout.addLayout(panes_layout)
        self.setLayout(main_layout)

class ControlEspectroscopiaPane(QGroupBox):
    def __init__(self):
        super().__init__("Parámetros de Espectroscopía (TH2832)")
        main_layout = QHBoxLayout(self) # Split principal: Izquierda / Derecha

        # ==========================================
        # MITAD IZQUIERDA: Paneles Verticales (Grid de 3 Columnas)
        # ==========================================
        left_pane = QWidget()
        left_layout = QVBoxLayout(left_pane)
        left_layout.setContentsMargins(0, 0, 10, 0)
        
        # --- 1. Generador de Frecuencias ---
        grp_freq = QGroupBox("Generador de Frecuencias")
        l_freq = QGridLayout(grp_freq)
        
        l_freq.addWidget(QLabel("Inicial (Hz):"), 0, 0)
        self.f_ini = QDoubleSpinBox()
        self.f_ini.setRange(20, 200000)
        self.f_ini.setValue(20)
        l_freq.addWidget(self.f_ini, 0, 1)

        l_freq.addWidget(QLabel("Final (Hz):"), 0, 2)
        self.f_fin = QDoubleSpinBox()
        self.f_fin.setRange(20, 200000)
        self.f_fin.setValue(200000)
        l_freq.addWidget(self.f_fin, 0, 3)

        l_freq.addWidget(QLabel("Puntos:"), 0, 4)
        self.f_pts = QSpinBox()
        self.f_pts.setRange(2, 2000)
        self.f_pts.setValue(50)
        l_freq.addWidget(self.f_pts, 0, 5)

        l_freq.addWidget(QLabel("Escala:"), 1, 0)
        self.f_escala = QComboBox()
        self.f_escala.addItems(["Log", "Lin"])
        l_freq.addWidget(self.f_escala, 1, 1)

        self.btn_add_freq = QPushButton("Añadir a Lista Freq ->")
        l_freq.addWidget(self.btn_add_freq, 1, 2, 1, 4)
        left_layout.addWidget(grp_freq)

        # --- 2. Generador de Vdc Bias ---
        grp_vdc = QGroupBox("Configuración Vdc Bias")
        l_vdc = QGridLayout(grp_vdc)
        
        self.chk_vdc_sweep = QCheckBox("Habilitar Barrido Vdc")
        self.chk_vdc_sweep.setChecked(False)
        l_vdc.addWidget(self.chk_vdc_sweep, 0, 0, 1, 3)
        
        l_vdc.addWidget(QLabel("Vdc Fijo (V):"), 0, 3)
        self.vdc_fijo = QDoubleSpinBox()
        self.vdc_fijo.setRange(-5.0, 5.0)
        self.vdc_fijo.setValue(0.0)
        l_vdc.addWidget(self.vdc_fijo, 0, 4, 1, 2)

        l_vdc.addWidget(QLabel("V Inicial:"), 1, 0)
        self.v_ini = QDoubleSpinBox()
        self.v_ini.setRange(-5.0, 5.0)
        l_vdc.addWidget(self.v_ini, 1, 1)

        l_vdc.addWidget(QLabel("V Final:"), 1, 2)
        self.v_fin = QDoubleSpinBox()
        self.v_fin.setRange(-5.0, 5.0)
        l_vdc.addWidget(self.v_fin, 1, 3)

        l_vdc.addWidget(QLabel("Paso:"), 1, 4)
        self.v_paso = QDoubleSpinBox()
        self.v_paso.setRange(0.001, 5.0)
        self.v_paso.setValue(0.1)
        l_vdc.addWidget(self.v_paso, 1, 5)

        self.btn_add_vdc = QPushButton("Añadir a Lista Vdc ->")
        l_vdc.addWidget(self.btn_add_vdc, 2, 0, 1, 6)
        left_layout.addWidget(grp_vdc)

        # --- 3. Ajustes del LCR ---
        grp_lcr = QGroupBox("Ajustes TH2832")
        l_lcr = QGridLayout(grp_lcr)
        
        l_lcr.addWidget(QLabel("Vac (Vrms):"), 0, 0)
        self.vac = QDoubleSpinBox()
        self.vac.setRange(0.01, 2.0)
        self.vac.setValue(0.1)
        l_lcr.addWidget(self.vac, 0, 1)
        
        self.chk_alc = QCheckBox("ALC ON")
        self.chk_alc.setChecked(True)
        l_lcr.addWidget(self.chk_alc, 0, 2, 1, 2)

        l_lcr.addWidget(QLabel("Velocidad:"), 0, 4)
        self.combo_speed = QComboBox()
        self.combo_speed.addItems(["SLOW", "MED", "FAST"])
        self.combo_speed.setCurrentText("MED")
        l_lcr.addWidget(self.combo_speed, 0, 5)

        l_lcr.addWidget(QLabel("Avg Pts:"), 1, 0)
        self.avg_pts = QSpinBox()
        self.avg_pts.setRange(1, 255)
        self.avg_pts.setValue(1)
        l_lcr.addWidget(self.avg_pts, 1, 1)

        l_lcr.addWidget(QLabel("Rsou (Ω):"), 1, 2)
        self.combo_rsou = QComboBox()
        self.combo_rsou.addItems(["100", "30"])
        l_lcr.addWidget(self.combo_rsou, 1, 3)

        l_lcr.addWidget(QLabel("Rango:"), 1, 4)
        self.combo_rango = QComboBox()
        self.combo_rango.addItems(["AUTO", "3", "10", "30", "100", "300", "1000", "3000", "10000", "30000", "100000"])
        l_lcr.addWidget(self.combo_rango, 1, 5)

        l_lcr.addWidget(QLabel("Trig Delay(s):"), 2, 0)
        self.trig_delay = QDoubleSpinBox()
        self.trig_delay.setRange(0.0, 60.0)
        l_lcr.addWidget(self.trig_delay, 2, 1)
        left_layout.addWidget(grp_lcr)

        # --- 4. Control Matriz ---
        grp_matriz = QGroupBox("Control Matriz HP34970A")
        l_matriz = QGridLayout(grp_matriz)
        
        self.chk_matriz = QCheckBox("Usar Matriz (Ch1/Ch2)")
        self.chk_matriz.setChecked(False)
        l_matriz.addWidget(self.chk_matriz, 0, 0, 1, 2)
        
        l_matriz.addWidget(QLabel("Canal 1:"), 0, 2)
        self.matriz_ch1 = QSpinBox()
        self.matriz_ch1.setRange(100, 999)
        self.matriz_ch1.setValue(212)
        l_matriz.addWidget(self.matriz_ch1, 0, 3)
        
        l_matriz.addWidget(QLabel("Canal 2:"), 0, 4)
        self.matriz_ch2 = QSpinBox()
        self.matriz_ch2.setRange(100, 999)
        self.matriz_ch2.setValue(222)
        l_matriz.addWidget(self.matriz_ch2, 0, 5)
        left_layout.addWidget(grp_matriz)

        # --- Botones Principales y Warning ---
        self.lbl_warning_is = QLabel(" ")
        self.lbl_warning_is.setStyleSheet("color: #d32f2f; font-weight: bold; font-size: 11px;")
        left_layout.addWidget(self.lbl_warning_is)

        btn_layout = QHBoxLayout()
        self.btn_medir = QPushButton("Iniciar Espectroscopía")
        self.btn_medir.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold; height: 35px;") 
        self.btn_detencion = QPushButton("Detener")
        self.btn_detencion.setStyleSheet("background-color: #c62828; color: white; font-weight: bold; height: 35px;") 
        
        btn_layout.addWidget(self.btn_medir)
        btn_layout.addWidget(self.btn_detencion)
        left_layout.addLayout(btn_layout)
        
        left_layout.addStretch() # Empuja todo hacia arriba suavemente
        main_layout.addWidget(left_pane, stretch=3)

        # ==========================================
        # MITAD DERECHA: Listas Verticales Altas
        # ==========================================
        right_pane = QWidget()
        right_layout = QHBoxLayout(right_pane)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # Columna Lista Frecuencias
        freq_col = QVBoxLayout()
        self.tabla_freq = QTableWidget(0, 1)
        self.tabla_freq.setHorizontalHeaderLabels(["Freqs (Hz)"])
        self.tabla_freq.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        # CRÍTICO: NO PONER setMaximumHeight AQUÍ
        freq_col.addWidget(self.tabla_freq)
        
        btn_f_lay = QHBoxLayout()
        self.btn_eliminar_freq = QPushButton("Borrar Sel.")
        self.btn_limpiar_freq = QPushButton("Limpiar Todo")
        btn_f_lay.addWidget(self.btn_eliminar_freq)
        btn_f_lay.addWidget(self.btn_limpiar_freq)
        freq_col.addLayout(btn_f_lay)

        # --- NUEVOS BOTONES DE CORRECCIÓN ---
        corr_grp = QGroupBox("Corrección de Hardware (Spot)")
        corr_lay = QVBoxLayout(corr_grp)
        self.btn_corr_open = QPushButton("Ejecutar OPEN")
        self.btn_corr_open.setStyleSheet("background-color: #bbdefb; font-weight: bold;")
        self.btn_corr_short = QPushButton("Ejecutar SHORT")
        self.btn_corr_short.setStyleSheet("background-color: #ffcdd2; font-weight: bold;")
        corr_lay.addWidget(self.btn_corr_open)
        corr_lay.addWidget(self.btn_corr_short)
        freq_col.addWidget(corr_grp)
        
        right_layout.addLayout(freq_col)

        right_layout.addLayout(freq_col)

        # Columna Lista Vdc
        vdc_col = QVBoxLayout()
        self.tabla_vdc = QTableWidget(0, 1)
        self.tabla_vdc.setHorizontalHeaderLabels(["Vdc (V)"])
        self.tabla_vdc.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        # CRÍTICO: NO PONER setMaximumHeight AQUÍ
        vdc_col.addWidget(self.tabla_vdc)
        
        btn_v_lay = QHBoxLayout()
        self.btn_eliminar_vdc = QPushButton("Borrar Sel.")
        self.btn_limpiar_vdc = QPushButton("Limpiar Todo")
        btn_v_lay.addWidget(self.btn_eliminar_vdc)
        btn_v_lay.addWidget(self.btn_limpiar_vdc)
        vdc_col.addLayout(btn_v_lay)
        right_layout.addLayout(vdc_col)

        main_layout.addWidget(right_pane, stretch=2)

        # ==========================================
        # POBLAR FRECUENCIAS POR DEFECTO
        # ==========================================
        frecuencias_default = [
            20, 25, 30, 40, 50, 60, 75, 100, 120, 150, 200, 250, 300, 400, 500, 
            600, 750, 1000, 1200, 1500, 2000, 2500, 3000, 4000, 5000, 6000, 7500, 
            10000, 12000, 15000, 20000, 25000, 30000, 40000, 50000, 60000, 75000, 
            100000, 120000, 150000, 200000
        ]
        for f in frecuencias_default:
            row = self.tabla_freq.rowCount()
            self.tabla_freq.insertRow(row)
            self.tabla_freq.setItem(row, 0, QTableWidgetItem(str(f)))
        
        # Permitir que el tab superior entero respire sin expandirse infinitamente
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        
        # Conexiones
        self.btn_add_freq.clicked.connect(self._add_freq)
        self.btn_add_vdc.clicked.connect(self._add_vdc)
        self.btn_limpiar_freq.clicked.connect(lambda: self.tabla_freq.setRowCount(0))
        self.btn_limpiar_vdc.clicked.connect(lambda: self.tabla_vdc.setRowCount(0))
        self.btn_eliminar_freq.clicked.connect(lambda: self._eliminar_fila(self.tabla_freq))
        self.btn_eliminar_vdc.clicked.connect(lambda: self._eliminar_fila(self.tabla_vdc))
        
        self.combo_rsou.currentTextChanged.connect(self._validar_limites_bias)
        self.chk_vdc_sweep.toggled.connect(self._toggle_vdc_mode)
        
        self._toggle_vdc_mode(False) # Estado por defecto: Vdc Fijo

    def _toggle_vdc_mode(self, checked):
        self.vdc_fijo.setEnabled(not checked)
        self.v_ini.setEnabled(checked)
        self.v_fin.setEnabled(checked)
        self.v_paso.setEnabled(checked)
        self.btn_add_vdc.setEnabled(checked)
        self.tabla_vdc.setEnabled(checked)
        self.btn_eliminar_vdc.setEnabled(checked)
        self.btn_limpiar_vdc.setEnabled(checked)

    def _validar_limites_bias(self, rsou_str):
        if rsou_str == "30":
            max_v = 1.5
            self.lbl_warning_is.setText("⚠ Rsou 30Ω: Límite de Vdc restringido a ±1.5V")
        else:
            max_v = 5.0
            self.lbl_warning_is.setText(" ")
            
        for caja in [self.v_ini, self.v_fin, self.vdc_fijo]:
            caja.blockSignals(True)
            caja.setRange(-max_v, max_v)
            caja.blockSignals(False)

    def _add_freq(self):
        import numpy as np
        start = self.f_ini.value()
        stop = self.f_fin.value()
        pts = self.f_pts.value()
        escala = self.f_escala.currentText()
        
        if escala == "Log": frecuencias = list(np.logspace(np.log10(start), np.log10(stop), pts))
        else: frecuencias = list(np.linspace(start, stop, pts))
            
        for f in frecuencias:
            f_int = int(round(f)) # Redondeo al entero más cercano
            row = self.tabla_freq.rowCount()
            self.tabla_freq.insertRow(row)
            self.tabla_freq.setItem(row, 0, QTableWidgetItem(f"{f_int}"))

    def _add_vdc(self):
        import numpy as np
        v_ini = self.v_ini.value()
        v_fin = self.v_fin.value()
        v_paso = self.v_paso.value()
        
        if v_ini == v_fin: voltajes = [v_fin]
        else:
            direccion = 1 if v_fin > v_ini else -1
            voltajes = list(np.arange(v_ini, v_fin + (direccion * v_paso * 0.1), direccion * v_paso))
            
        for v in voltajes:
            row = self.tabla_vdc.rowCount()
            self.tabla_vdc.insertRow(row)
            self.tabla_vdc.setItem(row, 0, QTableWidgetItem(f"{v:.3f}"))

    def _eliminar_fila(self, tabla):
        row = tabla.currentRow()
        if row >= 0:
            tabla.removeRow(row)

class EspectroscopiaTab(QWidget):
    def __init__(self):
        super().__init__()
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        self.params_pane = ControlEspectroscopiaPane()
        main_layout.addWidget(self.params_pane, alignment=Qt.AlignmentFlag.AlignTop)
        main_layout.addStretch()