import sys
import os
import json
import time
import csv
import math
import numpy as np
import pyvisa
from PySide6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
                               QWidget, QPushButton, QLabel, QFileDialog)
from PySide6.QtCore import QThread, Signal, Qt
import pyqtgraph as pg

from hardware import Keithley224, Agilent34420A, SwitchMatrixHP34970A

# =============================================================================
# 1. PARÁMETROS DEL EXPERIMENTO (Ajustar según la muestra)
# =============================================================================
NODOS_SUBIDA_UA = [3, 6, 9, 12, 15, 18, 20]
NODOS_BAJADA_UA = [20, 18, 15, 12, 9, 6, 3]

I_MAX_UA = 20.0                  # Corriente pico de retorno en la fase de bajada (uA)
PASO_RAMPA_UA = 1.0              # Paso de corriente entre pulsos de la rampa (uA)
I_BIAS_UA = 0.1                  # Magnitud de corriente de lectura para Rrem (uA)
MODO_DELTA_BIAS_DEFAULT = True   # True = alterna +I_BIAS y -I_BIAS independientemente
TIEMPO_RELAX_S = 50.0            # Duración de cada "Pausa c/Bias" en cada nodo (s)
NUM_BIAS_EN_RAMPA = 1            # Pares (+ y -) o pulsos simples de bias por paso de rampa

# Tiempos de pulso y seguridad
ANCHO_PULSO_S = 0.3             # Duración del pulso ON (s)
PERIODO_PULSO_S = 0.6           # Periodo total (ON + OFF) de cada pulso (s)
LIMITE_VOLTAJE_V = 10.0         # Compliance del K224 (V)
NPLC_DMM = 2                     # Integración del 34420A
RANGO_CH1_STR = "10.0"          # Rango 10V en CH1 del 34420A

# Configuración de la Matriz HP34970A
USAR_MATRIZ = True         
MATRIZ_2W = 212            
MATRIZ_3W = 222            
MEDIR_3W = True            


def generar_protocolo():
    """
    Fase 1 (Subida desde cero):
      0 -> X uA -> Pausa 10s -> (corte a 0 uA)
    Fase 2 (Retornos pasando por I_MAX desde cero):
      0 -> I_MAX -> baja a Y uA -> Pausa 10s -> (corte a 0 uA)
    """
    protocolo = []
    
    # Fase 1: Excursiones de subida (0 -> Nodo -> Pausa)
    for nodo in NODOS_SUBIDA_UA:
        protocolo.append(("RAMPA_DESDE_CERO", float(nodo)))
        protocolo.append(("PAUSA_C_BIAS", float(nodo)))
        
    # Fase 2: Excursiones de bajada (0 -> I_MAX -> Nodo -> Pausa)
    for nodo in NODOS_BAJADA_UA:
        protocolo.append(("RAMPA_DESDE_CERO", float(I_MAX_UA)))
        protocolo.append(("RAMPA_CONTINUA", float(nodo)))
        protocolo.append(("PAUSA_C_BIAS", float(nodo)))
            
    return protocolo


def generar_pasos_rampa(i_inicio, i_fin, paso, incluir_inicio=False):
    """Evita errores de punto flotante de np.arange y garantiza llegar exacto a i_fin."""
    if math.isclose(i_inicio, i_fin, abs_tol=1e-6):
        return np.array([i_fin]) if incluir_inicio else np.array([])
    n_pasos = max(1, int(round(abs(i_fin - i_inicio) / abs(paso))))
    puntos = np.round(np.linspace(i_inicio, i_fin, n_pasos + 1), 5)
    return puntos if incluir_inicio else puntos[1:]


# =============================================================================
# 2. HILO TRABAJADOR (Ejecución de Hardware)
# =============================================================================
class HiloExperimentoHisteresis(QThread):
    # t_min, i_p, i_b, v2_i, r2_i, v2_b, r2_b, v3_i, r3_i, v3_b, r3_b, es_pausa, fase
    datos_punto = Signal(float, float, float, float, float, float, float, float, float, float, float, bool, str)
    nueva_traza = Signal()
    estado_msg = Signal(str)

    def __init__(self, archivo_destino, usar_delta_bias=True):
        super().__init__()
        self.archivo_csv = archivo_destino
        self.usar_delta_bias = usar_delta_bias
        self.corriendo = False
        self.pausa_manual_cbias = False
        self.saltar_etapa = False
        
        self.fuente = Keithley224("GPIB0::02::INSTR")
        self.voltimetro = Agilent34420A("GPIB0::07::INSTR")
        self.matriz = SwitchMatrixHP34970A("GPIB0::9::INSTR")
        self.canal_matriz_actual = None

    def _clamp_ma(self, corriente_ua):
        corr_ma = corriente_ua * 1e-3
        if abs(corr_ma) < 1e-5:
            return 1e-5 if corr_ma >= 0 else -1e-5
        return corr_ma

    def _rutar_matriz_en_frio(self, canal_destino):
        """Conmuta la matriz en Standby (F0X) solo si el canal objetivo cambia."""
        if not USAR_MATRIZ or canal_destino == self.canal_matriz_actual:
            return
        self.fuente.standby()
        otro_canal = MATRIZ_3W if canal_destino == MATRIZ_2W else MATRIZ_2W
        self.matriz.open_channels(otro_canal)
        self.matriz.close_channels(canal_destino)
        self.canal_matriz_actual = canal_destino
        time.sleep(0.15)

    def _ejecutar_pulso_individual(self, corriente_ua):
        t_inicio_ciclo = time.time()
        corr_ma = self._clamp_ma(corriente_ua)
        margen_lectura = (NPLC_DMM * 0.02) + 0.04

        self.fuente.set_corriente(corr_ma)
        self.fuente.operar()

        t_espera_on = ANCHO_PULSO_S - margen_lectura
        if t_espera_on > 0:
            while (time.time() - t_inicio_ciclo) < t_espera_on and self.corriendo:
                time.sleep(0.01)

        voltaje = self.voltimetro.leer_voltaje()
        self.fuente.standby()

        resistencia = voltaje / (corr_ma * 1e-3) if abs(corr_ma) >= 1e-5 else float('nan')

        t_consumido = time.time() - t_inicio_ciclo
        t_off = max(0.05, PERIODO_PULSO_S - t_consumido)
        t_off_start = time.time()
        while (time.time() - t_off_start) < t_off and self.corriendo:
            time.sleep(0.01)

        return voltaje, resistencia, corr_ma * 1e3

    def medir_2w_y_3w(self, corriente_ua):
        if not (USAR_MATRIZ and MEDIR_3W):
            self._rutar_matriz_en_frio(MATRIZ_2W)
            v2, r2, i_real_ua = self._ejecutar_pulso_individual(corriente_ua)
            return v2, r2, float('nan'), float('nan'), i_real_ua

        if self.canal_matriz_actual == MATRIZ_3W:
            v3, r3, i_real_ua = self._ejecutar_pulso_individual(corriente_ua)
            v2, r2 = float('nan'), float('nan')
            if self.corriendo:
                self._rutar_matriz_en_frio(MATRIZ_2W)
                v2, r2, _ = self._ejecutar_pulso_individual(corriente_ua)
        else:
            self._rutar_matriz_en_frio(MATRIZ_2W)
            v2, r2, i_real_ua = self._ejecutar_pulso_individual(corriente_ua)
            v3, r3 = float('nan'), float('nan')
            if self.corriendo:
                self._rutar_matriz_en_frio(MATRIZ_3W)
                v3, r3, _ = self._ejecutar_pulso_individual(corriente_ua)

        return v2, r2, v3, r3, i_real_ua

    def _obtener_lista_biases(self):
        """Retorna [+I_bias, -I_bias] si el modo alternado está activo, o solo [+I_bias]."""
        b_mag = abs(float(I_BIAS_UA))
        if self.usar_delta_bias:
            return [b_mag, -b_mag]
        return [float(I_BIAS_UA)]

    def _guardar_y_emitir(self, t_inicio, etiqueta, ult_pulso, i_b_real, v2_b, r2_b, v3_b, r3_b, es_pausa):
        t_min = (time.time() - t_inicio) / 60.0
        r_diff_inst = ult_pulso['r2'] - ult_pulso['r3'] if not math.isnan(ult_pulso['r3']) else float('nan')
        r_diff_rem = r2_b - r3_b if not math.isnan(r3_b) else float('nan')
        polaridad_str = "POS" if i_b_real >= 0 else "NEG"

        fila = [
            f"{t_min:.4f}", etiqueta, polaridad_str, f"{ult_pulso['i_ua']:.4f}", f"{i_b_real:.4f}",
            ult_pulso['v2'], ult_pulso['r2'], r2_b, v2_b,
            ult_pulso['v3'], ult_pulso['r3'], r3_b, v3_b,
            r_diff_inst, r_diff_rem
        ]
        with open(self.archivo_csv, 'a', newline='') as f:
            csv.writer(f).writerow(fila)

        self.datos_punto.emit(
            t_min, ult_pulso['i_ua'], i_b_real,
            ult_pulso['v2'], ult_pulso['r2'], v2_b, r2_b,
            ult_pulso['v3'], ult_pulso['r3'], v3_b, r3_b,
            es_pausa, etiqueta
        )

    def run(self):
        self.corriendo = True
        try:
            rm = pyvisa.ResourceManager()
            self.fuente.conectar(rm)
            self.voltimetro.conectar(rm)
            if USAR_MATRIZ:
                self.matriz.conectar(rm)
                self.matriz.open_channels([MATRIZ_2W, MATRIZ_3W])
                self.canal_matriz_actual = None

            self.voltimetro.inst.write("ROUT:TERM FRON1")
            self.voltimetro.inst.write(f"VOLT:DC:NPLC {NPLC_DMM}")
            self.voltimetro.inst.write(f"SENS1:VOLT:DC:RANG {RANGO_CH1_STR}")
            self.fuente.set_limite_voltaje(LIMITE_VOLTAJE_V)

            encabezado = [
                "Tiempo (min)", "Fase", "Polaridad_Bias", "I pulso (uA)", "I bias (uA)",
                "Vinst 2W (V)", "Rinst 2W (Ohm)", "Rrem 2W (Ohm)", "Vbias 2W (V)",
                "Vinst 3W (V)", "Rinst 3W (Ohm)", "Rrem 3W (Ohm)", "Vbias 3W (V)",
                "Delta_Rinst_2W_3W (Ohm)", "Delta_Rrem_2W_3W (Ohm)"
            ]
            with open(self.archivo_csv, 'w', newline='') as f:
                csv.writer(f).writerow(encabezado)

            t_inicio = time.time()
            protocolo = generar_protocolo()
            i_actual_ua = 0.0
            etapa_idx = 0

            ult_pulso = {
                'i_ua': 0.0,
                'v2': float('nan'), 'r2': float('nan'),
                'v3': float('nan'), 'r3': float('nan')
            }

            for accion, target_ua in protocolo:
                if not self.corriendo: break
                self.saltar_etapa = False
                etapa_idx += 1

                # =================================================================
                # MODO 1: RAMPAS (Desde 0 uA o Continuas)
                # =================================================================
                if accion in ("RAMPA_DESDE_CERO", "RAMPA_CONTINUA"):
                    if accion == "RAMPA_DESDE_CERO":
                        i_actual_ua = 0.0
                        if etapa_idx > 1:
                            self.nueva_traza.emit()
                        pasos_i = generar_pasos_rampa(0.0, target_ua, PASO_RAMPA_UA, incluir_inicio=True)
                        etiqueta = f"E{etapa_idx}_Rampa_0_a_{target_ua}uA"
                    else:
                        pasos_i = generar_pasos_rampa(i_actual_ua, target_ua, PASO_RAMPA_UA, incluir_inicio=False)
                        etiqueta = f"E{etapa_idx}_Rampa_{i_actual_ua}_a_{target_ua}uA"

                    for i_step_ua in pasos_i:
                        if not self.corriendo or self.saltar_etapa: break

                        # Si el usuario activó Pausa c/Bias manual en plena rampa
                        while self.pausa_manual_cbias and self.corriendo and not self.saltar_etapa:
                            for b_val in self._obtener_lista_biases():
                                if not self.pausa_manual_cbias or not self.corriendo or self.saltar_etapa: break
                                self.estado_msg.emit(f"[PAUSA MANUAL en {ult_pulso['i_ua']:.2f} uA] Bias = {b_val:+.2f} uA")
                                v2_b, r2_b, v3_b, r3_b, i_b_real = self.medir_2w_y_3w(b_val)
                                self._guardar_y_emitir(t_inicio, f"{etiqueta}_PausaManual", ult_pulso, i_b_real, v2_b, r2_b, v3_b, r3_b, True)

                        if not self.corriendo or self.saltar_etapa: break

                        self.estado_msg.emit(f"[{etiqueta}] Pulso Principal I = {i_step_ua:.2f} uA")

                        # FASE A: Pulso Principal
                        v2_inst, r2_inst, v3_inst, r3_inst, i_p_real = self.medir_2w_y_3w(i_step_ua)
                        ult_pulso = {
                            'i_ua': i_p_real,
                            'v2': v2_inst, 'r2': r2_inst,
                            'v3': v3_inst, 'r3': r3_inst
                        }
                        i_actual_ua = i_step_ua

                        # FASE B: Pulsos Bias intercalados (+I_bias y -I_bias independientes)
                        if NUM_BIAS_EN_RAMPA > 0:
                            for _ in range(NUM_BIAS_EN_RAMPA):
                                if not self.corriendo or self.saltar_etapa: break
                                for b_val in self._obtener_lista_biases():
                                    if not self.corriendo or self.saltar_etapa: break
                                    self.estado_msg.emit(f"[{etiqueta}] Lectura Bias = {b_val:+.2f} uA (tras {i_step_ua:.2f} uA)")
                                    v2_b, r2_b, v3_b, r3_b, i_b_real = self.medir_2w_y_3w(b_val)
                                    self._guardar_y_emitir(t_inicio, etiqueta, ult_pulso, i_b_real, v2_b, r2_b, v3_b, r3_b, False)
                        else:
                            self._guardar_y_emitir(t_inicio, etiqueta, ult_pulso, float('nan'), float('nan'), float('nan'), float('nan'), float('nan'), False)

                # =================================================================
                # MODO 2: PAUSA CON BIAS PROGRAMADA (Alterna +Bias / -Bias si está activo)
                # =================================================================
                elif accion == "PAUSA_C_BIAS":
                    etiqueta = f"E{etapa_idx}_PausaBias_en_{target_ua}uA"
                    t_pausa_inicio = time.time()
                    paso_alternado = 0

                    while ((time.time() - t_pausa_inicio) < TIEMPO_RELAX_S or self.pausa_manual_cbias) and self.corriendo and not self.saltar_etapa:
                        lista_biases = self._obtener_lista_biases()
                        b_val = lista_biases[paso_alternado % len(lista_biases)]
                        paso_alternado += 1

                        restante = max(0.0, TIEMPO_RELAX_S - (time.time() - t_pausa_inicio))
                        extra_txt = " [HOLD MANUAL ACTIVO]" if self.pausa_manual_cbias else f" - Restan {restante:.1f}s"
                        self.estado_msg.emit(f"[{etiqueta}] Midiendo Bias ({b_val:+.2f} uA){extra_txt}")

                        v2_b, r2_b, v3_b, r3_b, i_b_real = self.medir_2w_y_3w(b_val)
                        self._guardar_y_emitir(t_inicio, etiqueta, ult_pulso, i_b_real, v2_b, r2_b, v3_b, r3_b, True)

            self.estado_msg.emit(f"Experimento finalizado. Guardado en {os.path.basename(self.archivo_csv)}")

        except Exception as e:
            self.estado_msg.emit(f"ERROR CRÍTICO: {e}")
        finally:
            self.fuente.standby()
            if USAR_MATRIZ:
                try:
                    self.matriz.open_channels([MATRIZ_2W, MATRIZ_3W])
                except:
                    pass
            self.corriendo = False


# =============================================================================
# 3. INTERFAZ GRÁFICA EN VIVO (CORREGIDA PARA 3W EN RELAJACIÓN)
# =============================================================================
class VentanaHisteresis(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mapeo de Histéresis y Relajación (K224 + 34420A CH1 100V + Matriz)")
        self.resize(1400, 780)
        self.worker = None

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Barra de control interactiva
        top_bar = QHBoxLayout()
        self.btn_iniciar = QPushButton("Iniciar Experimento")
        self.btn_iniciar.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold; height: 35px; padding: 0 15px;")
        
        self.btn_delta_bias = QPushButton()
        self.btn_delta_bias.setCheckable(True)
        self.btn_delta_bias.setChecked(MODO_DELTA_BIAS_DEFAULT)
        self.btn_delta_bias.toggled.connect(self.toggle_delta_bias)
        self._actualizar_estilo_delta(MODO_DELTA_BIAS_DEFAULT)

        self.btn_pausa_manual = QPushButton("Forzar Pausa c/Bias")
        self.btn_pausa_manual.setCheckable(True)
        self.btn_pausa_manual.setStyleSheet("background-color: #fff3e0; color: black; font-weight: bold; height: 35px; padding: 0 15px;")
        
        self.btn_saltar = QPushButton("Saltar Etapa Actual >>")
        self.btn_saltar.setStyleSheet("background-color: #e3f2fd; color: black; font-weight: bold; height: 35px; padding: 0 15px;")

        self.btn_detener = QPushButton("Detención de Emergencia")
        self.btn_detener.setStyleSheet("background-color: #c62828; color: white; font-weight: bold; height: 35px; padding: 0 15px;")
        
        self.lbl_estado = QLabel("Listo para iniciar.")
        self.lbl_estado.setStyleSheet("font-weight: bold; font-size: 13px; margin-left: 10px;")

        for b in [self.btn_iniciar, self.btn_delta_bias, self.btn_pausa_manual, self.btn_saltar, self.btn_detener]:
            top_bar.addWidget(b)
        top_bar.addWidget(self.lbl_estado, stretch=1)
        layout.addLayout(top_bar)

        # Gráficos
        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')
        pg.setConfigOptions(antialias=True)
        plots_layout = QHBoxLayout()

        # Gráfico 1: Curva I-V (Pulsos principales)
        self.iv_plot = pg.PlotWidget(title="Curva I-V (Pulsos Rampa)")
        self.iv_plot.setLabel('bottom', "Voltaje Vinst (V)")
        self.iv_plot.setLabel('left', "Corriente Pulso (uA)")
        self.iv_plot.showGrid(x=True, y=True, alpha=0.3)
        self.iv_plot.addLegend()
        self.c_iv_2w = self.iv_plot.plot(pen='#0055ff', symbol='o', symbolSize=5, symbolBrush='#0055ff', connect='finite', name="2W")
        self.c_iv_3w = self.iv_plot.plot(pen='#ff5500', symbol='s', symbolSize=5, symbolBrush='#ff5500', connect='finite', name="3W")
        self.c_iv_last = self.iv_plot.plot(pen=None, symbol='o', symbolSize=10, symbolBrush='g', symbolPen='k')
        plots_layout.addWidget(self.iv_plot)

        # Gráfico 2: Rrem vs Corriente de Pulso (2W y 3W, Rampa y Pausa, +Bias y -Bias)
        self.rrem_plot = pg.PlotWidget(title="Histéresis Remanente (Rrem vs I pulso)")
        self.rrem_plot.setLabel('bottom', "Corriente de Pulso Origen (uA)")
        self.rrem_plot.setLabel('left', "Rrem medida en Bias (Ω)")
        self.rrem_plot.showGrid(x=True, y=True, alpha=0.3)
        self.rrem_plot.addLegend()
        # 2W Rampa y Pausa
        self.c_rrem_rampa_2w_pos = self.rrem_plot.plot(pen='#0055ff', symbol='o', symbolSize=5, symbolBrush='#0055ff', connect='finite', name="Rrem 2W (+Bias Rampa)")
        self.c_rrem_rampa_2w_neg = self.rrem_plot.plot(pen=pg.mkPen('#00aaee', style=Qt.PenStyle.DashLine), symbol='o', symbolSize=5, symbolBrush='#00aaee', connect='finite', name="Rrem 2W (-Bias Rampa)")
        self.c_rrem_pausa_2w_pos = self.rrem_plot.plot(pen=None, symbol='t', symbolSize=7, symbolBrush='#2e7d32', name="Rrem 2W (+Bias Pausa)")
        self.c_rrem_pausa_2w_neg = self.rrem_plot.plot(pen=None, symbol='t1', symbolSize=7, symbolBrush='#8e24aa', name="Rrem 2W (-Bias Pausa)")
        # 3W Rampa y Pausa (AÑADIDOS LOS PUNTOS DE PAUSA 3W)
        self.c_rrem_rampa_3w_pos = self.rrem_plot.plot(pen='#ff5500', symbol='s', symbolSize=5, symbolBrush='#ff5500', connect='finite', name="Rrem 3W (+Bias Rampa)")
        self.c_rrem_rampa_3w_neg = self.rrem_plot.plot(pen=pg.mkPen('#ff9800', style=Qt.PenStyle.DashLine), symbol='s', symbolSize=5, symbolBrush='#ff9800', connect='finite', name="Rrem 3W (-Bias Rampa)")
        self.c_rrem_pausa_3w_pos = self.rrem_plot.plot(pen=None, symbol='d', symbolSize=7, symbolBrush='#d32f2f', name="Rrem 3W (+Bias Pausa)")
        self.c_rrem_pausa_3w_neg = self.rrem_plot.plot(pen=None, symbol='star', symbolSize=8, symbolBrush='#c2185b', name="Rrem 3W (-Bias Pausa)")
        plots_layout.addWidget(self.rrem_plot)

        # Gráfico 3: Evolución Temporal
        self.rt_plot = pg.PlotWidget(title="Evolución Temporal (R vs Tiempo)")
        self.rt_plot.setLabel('bottom', "Tiempo (min)")
        self.rt_plot.setLabel('left', "Resistencia (Ω)")
        self.rt_plot.showGrid(x=True, y=True, alpha=0.3)
        self.rt_plot.addLegend()
        self.c_rt_inst_2w = self.rt_plot.plot(pen=None, symbol='o', symbolSize=4, symbolBrush='#0055ff', name="Rinst 2W")
        self.c_rt_inst_3w = self.rt_plot.plot(pen=None, symbol='s', symbolSize=4, symbolBrush='#ff5500', name="Rinst 3W")
        self.c_rt_rem_2w_pos = self.rt_plot.plot(pen='#2e7d32', symbol='t', symbolSize=5, symbolBrush='#2e7d32', name="Rrem 2W (+Bias)")
        self.c_rt_rem_2w_neg = self.rt_plot.plot(pen='#8e24aa', symbol='t1', symbolSize=5, symbolBrush='#8e24aa', name="Rrem 2W (-Bias)")
        self.c_rt_rem_3w_pos = self.rt_plot.plot(pen='#d32f2f', symbol='d', symbolSize=5, symbolBrush='#d32f2f', name="Rrem 3W (+Bias)")
        self.c_rt_rem_3w_neg = self.rt_plot.plot(pen='#ff9800', symbol='star', symbolSize=6, symbolBrush='#ff9800', name="Rrem 3W (-Bias)")
        plots_layout.addWidget(self.rt_plot)

        layout.addLayout(plots_layout)

        self.btn_iniciar.clicked.connect(self.iniciar)
        self.btn_pausa_manual.toggled.connect(self.toggle_pausa_manual)
        self.btn_saltar.clicked.connect(self.saltar_etapa)
        self.btn_detener.clicked.connect(self.detener)

    def _actualizar_estilo_delta(self, activo):
        if activo:
            self.btn_delta_bias.setText("Modo Bias: ±ALTERNADO (+ / -)")
            self.btn_delta_bias.setStyleSheet("background-color: #ce93d8; color: black; font-weight: bold; height: 35px; padding: 0 15px;")
        else:
            self.btn_delta_bias.setText("Modo Bias: SIMPLE (+)")
            self.btn_delta_bias.setStyleSheet("background-color: #e0e0e0; color: black; font-weight: bold; height: 35px; padding: 0 15px;")

    def toggle_delta_bias(self, checked):
        self._actualizar_estilo_delta(checked)
        if self.worker and self.worker.corriendo:
            self.worker.usar_delta_bias = checked

    def _obtener_ruta_guardado(self):
        dir_defecto = ""
        if os.path.exists("config.json"):
            try:
                with open("config.json", "r") as f:
                    dir_defecto = json.load(f).get("directorio_defecto", "")
            except:
                pass
        nombre_sugerido = os.path.join(dir_defecto, f"histeresis_relax_{time.strftime('%Y%m%d_%H%M%S')}.csv")
        ruta, _ = QFileDialog.getSaveFileName(self, "Guardar Experimento de Histéresis", nombre_sugerido, "CSV Files (*.csv)")
        if ruta and not ruta.lower().endswith(".csv"):
            ruta += ".csv"
        return ruta

    def iniciar(self):
        if self.worker and self.worker.corriendo:
            return
        ruta_csv = self._obtener_ruta_guardado()
        if not ruta_csv:
            return

        # Listas independientes (X, Y) para que 2W y 3W jamás se desincronicen
        self.v2_iv, self.i2_iv = [], []
        self.v3_iv, self.i3_iv = [], []

        self.i2_rampa_pos, self.r2_rampa_pos = [], []
        self.i2_rampa_neg, self.r2_rampa_neg = [], []
        self.i3_rampa_pos, self.r3_rampa_pos = [], []
        self.i3_rampa_neg, self.r3_rampa_neg = [], []

        self.i2_pausa_pos, self.r2_pausa_pos = [], []
        self.i2_pausa_neg, self.r2_pausa_neg = [], []
        self.i3_pausa_pos, self.r3_pausa_pos = [], []
        self.i3_pausa_neg, self.r3_pausa_neg = [], []

        self.t2_inst, self.r2_inst_t = [], []
        self.t3_inst, self.r3_inst_t = [], []

        self.t2_rem_pos, self.r2_rem_t_pos = [], []
        self.t2_rem_neg, self.r2_rem_t_neg = [], []
        self.t3_rem_pos, self.r3_rem_t_pos = [], []
        self.t3_rem_neg, self.r3_rem_t_neg = [], []

        for c in [self.c_iv_2w, self.c_iv_3w, self.c_iv_last,
                  self.c_rrem_rampa_2w_pos, self.c_rrem_rampa_2w_neg,
                  self.c_rrem_pausa_2w_pos, self.c_rrem_pausa_2w_neg,
                  self.c_rrem_rampa_3w_pos, self.c_rrem_rampa_3w_neg,
                  self.c_rrem_pausa_3w_pos, self.c_rrem_pausa_3w_neg,
                  self.c_rt_inst_2w, self.c_rt_inst_3w,
                  self.c_rt_rem_2w_pos, self.c_rt_rem_2w_neg,
                  self.c_rt_rem_3w_pos, self.c_rt_rem_3w_neg]:
            c.setData([], [])

        self.worker = HiloExperimentoHisteresis(ruta_csv, usar_delta_bias=self.btn_delta_bias.isChecked())
        self.worker.datos_punto.connect(self.actualizar_graficos)
        self.worker.nueva_traza.connect(self.insertar_corte_traza)
        self.worker.estado_msg.connect(self.lbl_estado.setText)
        self.worker.start()

    def insertar_corte_traza(self):
        """Inserta NaNs para que pyqtgraph no dibuje una línea diagonal al volver a 0 uA."""
        nan = float('nan')
        for lst in [self.v2_iv, self.i2_iv, self.v3_iv, self.i3_iv,
                    self.i2_rampa_pos, self.r2_rampa_pos, self.i2_rampa_neg, self.r2_rampa_neg,
                    self.i3_rampa_pos, self.r3_rampa_pos, self.i3_rampa_neg, self.r3_rampa_neg]:
            if len(lst) > 0:
                lst.append(nan)

    def toggle_pausa_manual(self, checked):
        if self.worker and self.worker.corriendo:
            self.worker.pausa_manual_cbias = checked
        if checked:
            self.btn_pausa_manual.setText("Reanudar Rampa (Hold Activo)")
            self.btn_pausa_manual.setStyleSheet("background-color: #ffb74d; color: black; font-weight: bold; height: 35px; padding: 0 15px;")
        else:
            self.btn_pausa_manual.setText("Forzar Pausa c/Bias")
            self.btn_pausa_manual.setStyleSheet("background-color: #fff3e0; color: black; font-weight: bold; height: 35px; padding: 0 15px;")

    def saltar_etapa(self):
        if self.worker and self.worker.corriendo:
            self.worker.saltar_etapa = True

    def detener(self):
        if self.worker and self.worker.corriendo:
            self.worker.corriendo = False
            self.lbl_estado.setText("Deteniendo... pasando K224 a Standby.")

    def closeEvent(self, event):
        if self.worker and self.worker.corriendo:
            self.worker.corriendo = False
            self.worker.wait(5000)
        event.accept()

    def actualizar_graficos(self, t_min, i_p, i_b, v2_i, r2_i, v2_b, r2_b, v3_i, r3_i, v3_b, r3_b, es_pausa, fase):
        es_pos = (i_b >= 0)

        if not es_pausa:
            # 1. Graficar pulso principal (solo una vez por paso de corriente)
            if es_pos or math.isnan(i_b):
                if not math.isnan(v2_i):
                    self.v2_iv.append(v2_i)
                    self.i2_iv.append(i_p)
                    self.c_iv_2w.setData(self.v2_iv, self.i2_iv)
                    self.c_iv_last.setData([v2_i], [i_p])
                if not math.isnan(v3_i):
                    self.v3_iv.append(v3_i)
                    self.i3_iv.append(i_p)
                    self.c_iv_3w.setData(self.v3_iv, self.i3_iv)

                if not math.isnan(r2_i):
                    self.t2_inst.append(t_min)
                    self.r2_inst_t.append(r2_i)
                    self.c_rt_inst_2w.setData(self.t2_inst, self.r2_inst_t)
                if not math.isnan(r3_i):
                    self.t3_inst.append(t_min)
                    self.r3_inst_t.append(r3_i)
                    self.c_rt_inst_3w.setData(self.t3_inst, self.r3_inst_t)

            # 2. Graficar Rrem durante la Rampa (2W y 3W)
            if es_pos:
                if not math.isnan(r2_b):
                    self.i2_rampa_pos.append(i_p)
                    self.r2_rampa_pos.append(r2_b)
                    self.c_rrem_rampa_2w_pos.setData(self.i2_rampa_pos, self.r2_rampa_pos)
                if not math.isnan(r3_b):
                    self.i3_rampa_pos.append(i_p)
                    self.r3_rampa_pos.append(r3_b)
                    self.c_rrem_rampa_3w_pos.setData(self.i3_rampa_pos, self.r3_rampa_pos)
            else:
                if not math.isnan(r2_b):
                    self.i2_rampa_neg.append(i_p)
                    self.r2_rampa_neg.append(r2_b)
                    self.c_rrem_rampa_2w_neg.setData(self.i2_rampa_neg, self.r2_rampa_neg)
                if not math.isnan(r3_b):
                    self.i3_rampa_neg.append(i_p)
                    self.r3_rampa_neg.append(r3_b)
                    self.c_rrem_rampa_3w_neg.setData(self.i3_rampa_neg, self.r3_rampa_neg)
        else:
            # 3. Graficar Rrem durante la Pausa de Relajación (2W y 3W)
            if es_pos:
                if not math.isnan(r2_b):
                    self.i2_pausa_pos.append(i_p)
                    self.r2_pausa_pos.append(r2_b)
                    self.c_rrem_pausa_2w_pos.setData(self.i2_pausa_pos, self.r2_pausa_pos)
                if not math.isnan(r3_b):
                    self.i3_pausa_pos.append(i_p)
                    self.r3_pausa_pos.append(r3_b)
                    self.c_rrem_pausa_3w_pos.setData(self.i3_pausa_pos, self.r3_pausa_pos)
            else:
                if not math.isnan(r2_b):
                    self.i2_pausa_neg.append(i_p)
                    self.r2_pausa_neg.append(r2_b)
                    self.c_rrem_pausa_2w_neg.setData(self.i2_pausa_neg, self.r2_pausa_neg)
                if not math.isnan(r3_b):
                    self.i3_pausa_neg.append(i_p)
                    self.r3_pausa_neg.append(r3_b)
                    self.c_rrem_pausa_3w_neg.setData(self.i3_pausa_neg, self.r3_pausa_neg)

        # 4. Gráfico Temporal (Rrem separada en +Bias y -Bias para 2W y 3W)
        if es_pos:
            if not math.isnan(r2_b):
                self.t2_rem_pos.append(t_min)
                self.r2_rem_t_pos.append(r2_b)
                self.c_rt_rem_2w_pos.setData(self.t2_rem_pos, self.r2_rem_t_pos)
            if not math.isnan(r3_b):
                self.t3_rem_pos.append(t_min)
                self.r3_rem_t_pos.append(r3_b)
                self.c_rt_rem_3w_pos.setData(self.t3_rem_pos, self.r3_rem_t_pos)
        else:
            if not math.isnan(r2_b):
                self.t2_rem_neg.append(t_min)
                self.r2_rem_t_neg.append(r2_b)
                self.c_rt_rem_2w_neg.setData(self.t2_rem_neg, self.r2_rem_t_neg)
            if not math.isnan(r3_b):
                self.t3_rem_neg.append(t_min)
                self.r3_rem_t_neg.append(r3_b)
                self.c_rt_rem_3w_neg.setData(self.t3_rem_neg, self.r3_rem_t_neg)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = VentanaHisteresis()
    win.show()
    sys.exit(app.exec())
