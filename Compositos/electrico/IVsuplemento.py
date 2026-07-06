import sys
from PySide6.QtWidgets import (QApplication, QMainWindow, QHBoxLayout, QVBoxLayout, QWidget, QGridLayout, QLabel, 
                               QDoubleSpinBox, QSpinBox, QLineEdit, QGroupBox, QPushButton, QSizePolicy, QComboBox)

from PySide6.QtCore import Qt

import pyqtgraph as pg

from PySide6.QtWidgets import (QWidget, QGridLayout, QHBoxLayout, QLabel, 
                               QLineEdit, QGroupBox, QPushButton, QComboBox,
                               QSizePolicy, QSpacerItem)
from PySide6.QtCore import Qt

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
        
        # Filtro
        filtro_layout = QVBoxLayout()
        filtro_layout.addWidget(QLabel("Filtro"))
        self.combo_filtro = QComboBox()
        self.combo_filtro.addItems(["OFF", "Analógico", "Digital", "Ambos"])
        self.combo_filtro.setCurrentText("OFF") # Default actualizado
        filtro_layout.addWidget(self.combo_filtro)
        ch1_top_layout.addLayout(filtro_layout)

        # NPLC
        nplc_layout = QVBoxLayout()
        nplc_layout.addWidget(QLabel("NPLC"))
        self.combo_nplc = QComboBox()
        self.combo_nplc.addItems(["0.02", "0.2", "1", "2", "10", "20", "100", "200"]) 
        self.combo_nplc.setCurrentText("2") # Default actualizado
        nplc_layout.addWidget(self.combo_nplc)
        ch1_top_layout.addLayout(nplc_layout)

        # Rango
        rango_layout = QVBoxLayout()
        rango_layout.addWidget(QLabel("Rango"))
        self.combo_rango = QComboBox()
        self.combo_rango.addItems(["Auto", "1 mV", "10 mV", "100 mV", "1 V", "10 V", "100 V"])
        self.combo_rango.setCurrentText("10 V") # Default actualizado
        rango_layout.addWidget(self.combo_rango)
        ch1_top_layout.addLayout(rango_layout)

        self.lbl_advertencia = QLabel(" ") # Inicializado con un espacio para pre-asignar altura
        self.lbl_advertencia.setMinimumHeight(30) # Evita saltos en la UI (posible causa del freeze)
        self.lbl_advertencia.setWordWrap(True) 
        self.lbl_advertencia.setStyleSheet("color: #d32f2f; font-weight: bold; font-size: 11px;")
        ch1_top_layout.addWidget(self.lbl_advertencia)

        # Conectamos los comboboxes a una función de validación interna de la UI
        self.combo_filtro.currentTextChanged.connect(self._validar_filtros)
        self.combo_rango.currentTextChanged.connect(self._validar_filtros)

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
        # Forzamos que el botón tenga la misma altura visual que los combos + labels de Canal 1
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

        # Inicializar Canal 2 como apagado
        self._on_ch2_toggle(False)


    # ==========================================
    # MÉTODOS AUXILIARES
    # ==========================================
    def _create_ro_display(self):
        le = QLineEdit("0.00")
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
            rangos_invalidos = ["1 V", "10 V", "100 V"] # Auto puede ser riesgoso, pero lo dejamos pasar o advertimos
            if rango in rangos_invalidos:
                mensaje += f"⚠ Analógico: Rango {rango} incompatible (solo $\le$ 100mV).\n"
                
        self.lbl_advertencia.setText(mensaje)

    def _on_ch2_toggle(self, checked):
        # Cambiar colores
        if checked:
            self.btn_ch2_toggle.setText("CH 2: ENCENDIDO")
            self.btn_ch2_toggle.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold;")
        else:
            self.btn_ch2_toggle.setText("CH 2: APAGADO")
            self.btn_ch2_toggle.setStyleSheet("background-color: #ffcccc; color: black; font-weight: bold;")
            
        # Habilitar/Deshabilitar visualmente los campos del Canal 2
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
        
        # ==========================================
        # FILA 1 (Textos Fila 0, Inputs Fila 1)
        # ==========================================
        layout.addWidget(QLabel("Ancho Pulso (s)"), 0, 0)
        self.ancho_pulso = QDoubleSpinBox()
        self.ancho_pulso.setDecimals(3)
        self.ancho_pulso.setKeyboardTracking(False)
        layout.addWidget(self.ancho_pulso, 1, 0)

        layout.addWidget(QLabel("Corriente Máxima (mA)"), 0, 1)
        self.corr_maxima = QDoubleSpinBox()
        self.corr_maxima.setKeyboardTracking(False)
        layout.addWidget(self.corr_maxima, 1, 1)

        layout.addWidget(QLabel("Corriente Inicial (mA)"), 0, 2)
        self.corr_inicial = QDoubleSpinBox()
        layout.addWidget(self.corr_inicial, 1, 2)

        layout.addWidget(QLabel("Corriente Actual (mA)"), 0, 3)
        self.corr_actual_ro = QLineEdit("0.00")
        self.corr_actual_ro.setReadOnly(True)
        self.corr_actual_ro.setStyleSheet("background-color: #f0f0f0; color: #333; font-weight: bold;")
        self.corr_actual_ro.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.corr_actual_ro, 1, 3)

        layout.addWidget(QLabel("# Mediciones Bias"), 0, 4)
        self.num_mediciones = QSpinBox()
        self.num_mediciones.setRange(1, 10000)
        self.num_mediciones.setKeyboardTracking(False)
        layout.addWidget(self.num_mediciones, 1, 4)

        layout.addWidget(QLabel("Corriente Bias (mA)"), 0, 5)
        self.corr_bias = QDoubleSpinBox()
        self.corr_bias.setKeyboardTracking(False)
        
        layout.addWidget(self.corr_bias, 1, 5)

        # ==========================================
        # FILA 2 (Textos Fila 2, Inputs Fila 3)
        # ==========================================
        layout.addWidget(QLabel("Período Pulso (s)"), 2, 0)
        self.periodo_pulso = QDoubleSpinBox()
        self.periodo_pulso.setDecimals(3)
        layout.addWidget(self.periodo_pulso, 3, 0)

        layout.addWidget(QLabel("Corriente Mínima (mA)"), 2, 1)
        self.corr_minima = QDoubleSpinBox()
        layout.addWidget(self.corr_minima, 3, 1)

        layout.addWidget(QLabel("Paso Corriente (mA)"), 2, 2)
        self.paso_corr = QDoubleSpinBox()
        layout.addWidget(self.paso_corr, 3, 2)

        # NUEVO: Límite Voltaje (V)
        layout.addWidget(QLabel("Límite Voltaje (V)"), 2, 3)
        self.limite_voltaje = QDoubleSpinBox()
        self.limite_voltaje.setRange(0.0, 200.0)
        self.limite_voltaje.setValue(20.0) # Un valor por defecto seguro
        layout.addWidget(self.limite_voltaje, 3, 3)

        # NUEVO: Label de advertencia de tiempos (Ocupa la fila 4 entera)
        self.lbl_warning_tiempo = QLabel(" ")
        self.lbl_warning_tiempo.setStyleSheet("color: #d32f2f; font-weight: bold; font-size: 11px;")
        layout.addWidget(self.lbl_warning_tiempo, 4, 0, 1, 6)
        
        # Reducimos un poco el espacio mínimo ya que el label ocupa espacio
        layout.setRowMinimumHeight(4, 20)
        
        # ==========================================
        # FILA 3: BOTONES (Fila 5 en la grilla)
        # ==========================================
        btn_layout = QHBoxLayout()
        
        self.btn_medir = QPushButton("Medir")
        # Verde oscuro con texto blanco para máximo contraste
        self.btn_medir.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold;") 
        
        self.btn_pausa_cbias = QPushButton("Pausa c/Bias")
        self.btn_pausa_sbias = QPushButton("Pausa s/Bias")
        
        self.btn_detencion = QPushButton("Detención")
        # Rojo oscuro con texto blanco para máximo contraste
        self.btn_detencion.setStyleSheet("background-color: #c62828; color: white; font-weight: bold;") 
        
        self.btn_aplicar = QPushButton("Aplicar Cambios")
        self.btn_aplicar.setStyleSheet("background-color: #fff3e0; font-weight: bold;") # Naranja suave
        self.btn_aplicar.setStyleSheet("background-color: #fff3e0; color: black; font-weight: bold;")

        for btn in [self.btn_medir, self.btn_aplicar, self.btn_pausa_cbias, self.btn_pausa_sbias, self.btn_detencion]:
            btn.setMinimumHeight(35)
            btn_layout.addWidget(btn)

        layout.addLayout(btn_layout, 5, 0, 1, 6)

        # Resorte vertical final
        layout.setRowStretch(6, 1)
        
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)

class InstantPane(QGroupBox):
    def __init__(self):
        super().__init__("Instantaneous Readings")
        
        # The main layout is horizontal to hold the two subpanels side-by-side
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

        # Row 1
        # Toggle Button (Spans row 0 and 1 for visual balance, or you can just put it in row 1)
        self.btn_mode_toggle = QPushButton("Mode: V (mV)")
        self.btn_mode_toggle.setCheckable(True)
        # Connect the click event to swap the text dynamically
        self.btn_mode_toggle.toggled.connect(self._on_mode_toggle) 
        grid1.addWidget(self.btn_mode_toggle, 1, 0) # Placed in row 1, col 0

        grid1.addWidget(QLabel("Icc 1 (mA)"), 0, 1)
        self.icc_1 = QDoubleSpinBox()
        self.icc_1.setDecimals(3)
        grid1.addWidget(self.icc_1, 1, 1)

        grid1.addWidget(QLabel("Vcc 1 (V)"), 0, 2)
        self.vcc_1 = QDoubleSpinBox()
        self.vcc_1.setDecimals(3)
        grid1.addWidget(self.vcc_1, 1, 2)

        # Row 2 (Read Only)
        grid1.addWidget(QLabel("Ip 1 (mA)"), 2, 0)
        self.ip_1_ro = self._create_ro_display()
        grid1.addWidget(self.ip_1_ro, 3, 0)

        grid1.addWidget(QLabel("Vp 1 (V)"), 2, 1)
        self.vp_1_ro = self._create_ro_display()
        grid1.addWidget(self.vp_1_ro, 3, 1)

        grid1.addWidget(QLabel("Rinst 1 (Ω)"), 2, 2)
        self.rinst_1_ro = self._create_ro_display()
        grid1.addWidget(self.rinst_1_ro, 3, 2)

        # Row 3 (Read Only)
        grid1.addWidget(QLabel("Ib 1 (mA)"), 4, 0)
        self.ib_1_ro = self._create_ro_display()
        grid1.addWidget(self.ib_1_ro, 5, 0)

        grid1.addWidget(QLabel("Vb 1 (V)"), 4, 1)
        self.vb_1_ro = self._create_ro_display()
        grid1.addWidget(self.vb_1_ro, 5, 1)

        grid1.addWidget(QLabel("Rrem 1 (Ω)"), 4, 2)
        self.rrem_1_ro = self._create_ro_display()
        grid1.addWidget(self.rrem_1_ro, 5, 2)

        # Add a spring to push Grid 1 up
        grid1.setRowStretch(6, 1)


        # ==========================================
        # SUBPANEL 2: Channel 2
        # ==========================================
        self.ch2_panel = QGroupBox("Channel 2")
        grid2 = QGridLayout()
        grid2.setVerticalSpacing(2)
        grid2.setHorizontalSpacing(8)
        self.ch2_panel.setLayout(grid2)

        # Row 1
        self.btn_ch2_toggle = QPushButton("CH 2: OFF")
        self.btn_ch2_toggle.setCheckable(True)
        self.btn_ch2_toggle.setStyleSheet("background-color: #ffcccc;") # Light red for OFF
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

        # Row 2 (Read Only)
        grid2.addWidget(QLabel("Ip 2 (mA)"), 2, 0)
        self.ip_2_ro = self._create_ro_display()
        grid2.addWidget(self.ip_2_ro, 3, 0)

        grid2.addWidget(QLabel("Vp 2 (V)"), 2, 1)
        self.vp_2_ro = self._create_ro_display()
        grid2.addWidget(self.vp_2_ro, 3, 1)

        grid2.addWidget(QLabel("Rinst 2 (Ω)"), 2, 2)
        self.rinst_2_ro = self._create_ro_display()
        grid2.addWidget(self.rinst_2_ro, 3, 2)

        # Row 3 (Read Only)
        grid2.addWidget(QLabel("Ib 2 (mA)"), 4, 0)
        self.ib_2_ro = self._create_ro_display()
        grid2.addWidget(self.ib_2_ro, 5, 0)

        grid2.addWidget(QLabel("Vb 2 (V)"), 4, 1)
        self.vb_2_ro = self._create_ro_display()
        grid2.addWidget(self.vb_2_ro, 5, 1)

        grid2.addWidget(QLabel("Rrem 2 (Ω)"), 4, 2)
        self.rrem_2_ro = self._create_ro_display()
        grid2.addWidget(self.rrem_2_ro, 5, 2)

        # Add a spring to push Grid 2 up
        grid2.setRowStretch(6, 1)

        # Add this to grid1
        grid1.setColumnStretch(3, 1)

        # Add this to grid2
        grid2.setColumnStretch(3, 1)
        # Add the two subpanels to the main horizontal layout
        main_layout.addWidget(self.ch1_panel)
        main_layout.addWidget(self.ch2_panel)

        # Compress vertically
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)


    # ==========================================
    # HELPER METHODS & SLOTS
    # ==========================================
    def _create_ro_display(self):
        """Helper to generate styled read-only line edits."""
        le = QLineEdit("0.00")
        le.setReadOnly(True)
        # Give it a grey background and dark text to look like a digital readout
        le.setStyleSheet("background-color: #f0f0f0; color: #333; font-weight: bold;")
        le.setAlignment(Qt.AlignmentFlag.AlignRight)
        return le

    def _on_mode_toggle(self, checked):
        """Swaps text when the Mode button is clicked."""
        if checked:
            self.btn_mode_toggle.setText("Mode: I (mA)")
        else:
            self.btn_mode_toggle.setText("Mode: V (mV)")

    def _on_ch2_toggle(self, checked):
        """Swaps text and color when Channel 2 is turned on/off."""
        if checked:
            self.btn_ch2_toggle.setText("CH 2: ON")
            self.btn_ch2_toggle.setStyleSheet("background-color: #ccffcc;") # Light green
        else:
            self.btn_ch2_toggle.setText("CH 2: OFF")
            self.btn_ch2_toggle.setStyleSheet("background-color: #ffcccc;") # Light red

class ParametersPane(QGroupBox):
    def __init__(self):
        super().__init__("Measurement Parameters")
        
        # QGridLayout allows us to place items in specific (row, column) coordinates
        layout = QGridLayout()
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Preferred)
        layout.setVerticalSpacing(2)   # Pixels between rows (default is usually ~6-10)
        layout.setHorizontalSpacing(5) # Pixels between columns
        layout.setContentsMargins(10, 15, 10, 10)

        # ==========================================
        # ROW 1: Labels (Grid Row 0) & Inputs (Grid Row 1)
        # ==========================================
        
        # 1. Ancho pulso (s)
        layout.addWidget(QLabel("Ancho pulso (s)"), 0, 0)
        self.ancho_pulso = QDoubleSpinBox()
        self.ancho_pulso.setDecimals(3) # e.g., for milliseconds
        layout.addWidget(self.ancho_pulso, 1, 0)

        # 2. Amplitud pulso
        layout.addWidget(QLabel("Amplitud pulso"), 0, 1)
        self.amp_pulso = QDoubleSpinBox()
        layout.addWidget(self.amp_pulso, 1, 1)

        # 3. Amplitud inicial
        layout.addWidget(QLabel("Amplitud inicial"), 0, 2)
        self.amp_inicial = QDoubleSpinBox()
        layout.addWidget(self.amp_inicial, 1, 2)

        # 4. Amplitud máxima
        layout.addWidget(QLabel("Amplitud máxima"), 0, 3)
        self.amp_max = QDoubleSpinBox()
        layout.addWidget(self.amp_max, 1, 3)

        # 5. Amplitud pulso actual 
        # Note: I made this a read-only QLineEdit since "actual" usually implies a live readout rather than an input.
        layout.addWidget(QLabel("Amplitud pulso actual"), 0, 4)
        self.amp_actual_readout = QLineEdit("0.00")
        self.amp_actual_readout.setReadOnly(True)
        self.amp_actual_readout.setStyleSheet("background-color: #f0f0f0; color: #333;")
        self.amp_actual_readout.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.amp_actual_readout, 1, 4)

        # 6. # mediciones bias (Integer, so we use QSpinBox)
        layout.addWidget(QLabel("# mediciones bias"), 0, 5)
        self.num_mediciones = QSpinBox()
        self.num_mediciones.setRange(1, 10000)
        layout.addWidget(self.num_mediciones, 1, 5)

        # 7. Amplitud bias
        layout.addWidget(QLabel("Amplitud bias"), 0, 6)
        self.amp_bias = QDoubleSpinBox()
        layout.addWidget(self.amp_bias, 1, 6)


        # ==========================================
        # ROW 2: Labels (Grid Row 2) & Inputs (Grid Row 3)
        # ==========================================
        
        # 1. Período pulso (s)
        layout.addWidget(QLabel("Período pulso (s)"), 2, 0)
        self.periodo_pulso = QDoubleSpinBox()
        layout.addWidget(self.periodo_pulso, 3, 0)

        # 2. Paso de amplitud
        layout.addWidget(QLabel("Paso de amplitud"), 2, 1)
        self.paso_amp = QDoubleSpinBox()
        layout.addWidget(self.paso_amp, 3, 1)

        # 3. Amplitud mínima
        layout.addWidget(QLabel("Amplitud mínima"), 2, 2)
        self.amp_min = QDoubleSpinBox()
        layout.addWidget(self.amp_min, 3, 2)

        # Optional: Add a spacer or adjust column stretch so it doesn't look squished
        layout.setColumnStretch(7, 1)