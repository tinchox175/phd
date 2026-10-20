import sys
import os
import json
import time
import csv
import math
import numpy as np
import pyvisa
from PySide6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, 
                               QWidget, QPushButton, QLabel, QFileDialog, QComboBox)
from PySide6.QtCore import QThread, Signal, Qt
import pyqtgraph as pg

from hardware import Keithley224, Agilent34420A, SwitchMatrixHP34970A

# =============================================================================
# 1. PARÁMETROS DEL EXPERIMENTO (Ajustar según la muestra)
# =============================================================================
NODOS_SUBIDA_UA = [3, 6, 9, 12, 15, 18, 20]
NODOS_BAJADA_UA = [20, 18, 15, 12, 9, 6, 3]

I_MAX_UA = 20.0                  # Corriente pico de referencia (uA)
PASO_RAMPA_UA = 1.0              # Paso de corriente entre pulsos de la rampa (uA)
I_BIAS_UA = 0.1                  # Magnitud de corriente de lectura rápida (uA)
I_BIAS_DOBLE_UA = 0.2            # Segunda magnitud al final de la pausa para probar EMF (uA)
TIEMPO_RELAX_S = 50.0            # Duración de cada "Pausa c/Bias" en cada nodo (s)
NUM_BIAS_EN_RAMPA = 1            # Ciclos de bias por paso de rampa

# Opciones de lectura a 0 A (con K224 en Operate F1X -> Impedancia > 10 GOhm)
MEDIR_VOC_EN_TOFF = True         # Lee Voc al FINAL de la ventana t_off (0 A) de cada pulso
CUADRUPLETE_FINAL_PAUSA = True   # Al final de los 50s de pausa, mide [0, +0.1, -0.1, 0, +0.2, -0.2] uA

# Tiempos de pulso y seguridad
ANCHO_PULSO_S = 0.3              # Duración del pulso ON (s)
PERIODO_PULSO_S = 0.6            # Periodo total (0.3s ON + 0.3s OFF a 0 A) de cada pulso (s)
LIMITE_VOLTAJE_V = 10.0          # Compliance del K224 (V)
NPLC_DMM = 2                     # Integración del 34420A (40 ms a 50 Hz)
RANGO_CH1_VAL = 10               # Rango en Volts para CH1 del 34420A (0.001, 0.01, 0.1, 1, 10, 100)

# Configuración de la Matriz HP34970A
USAR_MATRIZ = True         
MATRIZ_2W = 212            
MATRIZ_3W = 222            
MEDIR_3W = True            


def generar_protocolo(modo="ISO_CARGA"):
    """
    Soporta:
      - "ISO_CARGA": Compara Subida, Bajada, Triángulo y Holds de igual carga (Q = 210 uA*pulsos)
      - "CLASICO": El protocolo original de Noleti 5/6
    """
    protocolo = []

    if modo == "CLASICO":
        for nodo in NODOS_SUBIDA_UA:
            protocolo.append(("RAMPA_DESDE_CERO", float(nodo), f"Rampa_0_a_{nodo}uA"))
            protocolo.append(("PAUSA_C_BIAS", float(nodo), f"PausaBias_en_{nodo}uA"))
        for nodo in NODOS_BAJADA_UA:
            protocolo.append(("RAMPA_DESDE_CERO", float(I_MAX_UA), f"Rampa_0_a_{I_MAX_UA}uA"))
            protocolo.append(("RAMPA_CONTINUA", float(nodo), f"Rampa_{I_MAX_UA}_a_{nodo}uA"))
            protocolo.append(("PAUSA_C_BIAS", float(nodo), f"PausaBias_en_{nodo}uA"))
    else:
        # 0. Línea de base inicial (Pausa en 0 uA)
        protocolo.append(("PAUSA_C_BIAS", 0.0, "Baseline_Inicial_0uA"))

        # 1. Rampa Pura de Subida: 1 -> 20 uA (20 pulsos, Q = 210 uA*pulsos, dI/dt > 0)
        pasos_up = np.linspace(1.0, 20.0, 20)
        protocolo.append(("LISTA_PULSOS", pasos_up, "IsoQ210_Subida_1_a_20uA"))
        protocolo.append(("PAUSA_C_BIAS", 20.0, "Pausa_tras_Subida_20uA"))

        # 2. Rampa Pura de Bajada: Salto a 20 -> 1 uA (20 pulsos, Q = 210 uA*pulsos, dI/dt < 0)
        pasos_down = np.linspace(20.0, 1.0, 20)
        protocolo.append(("LISTA_PULSOS", pasos_down, "IsoQ210_BajadaPura_20_a_1uA"))
        protocolo.append(("PAUSA_C_BIAS", 1.0, "Pausa_tras_BajadaPura_1uA"))

        # 3. Triángulo Mitad de Pico: 1 -> 14 -> 1 uA (28 pulsos, Q = 210 uA*pulsos)
        pasos_tri = np.concatenate([np.linspace(1.0, 14.0, 14), np.linspace(14.0, 1.0, 14)])
        protocolo.append(("LISTA_PULSOS", pasos_tri, "IsoQ210_Triangulo_1_14_1uA"))
        protocolo.append(("PAUSA_C_BIAS", 1.0, "Pausa_tras_Triangulo_14uA"))

        # 4. Hold Constante Medio: 10 uA x 21 pulsos (Q = 210 uA*pulsos)
        pasos_hold10 = np.full(21, 10.0)
        protocolo.append(("LISTA_PULSOS", pasos_hold10, "IsoQ210_Hold_10uA_x21p"))
        protocolo.append(("PAUSA_C_BIAS", 10.0, "Pausa_tras_Hold_10uA"))

        # 5. Hold Constante Bajo: 5 uA x 42 pulsos (Q = 210 uA*pulsos)
        pasos_hold5 = np.full(42, 5.0)
        protocolo.append(("LISTA_PULSOS", pasos_hold5, "IsoQ210_Hold_5uA_x42p"))
        protocolo.append(("PAUSA_C_BIAS", 5.0, "Pausa_tras_Hold_5uA"))

        # 6. Inversión Negativa: -1 -> -20 uA (20 pulsos, Q = -210 uA*pulsos)
        pasos_neg = np.linspace(-1.0, -20.0, 20)
        protocolo.append(("LISTA_PULSOS", pasos_neg, "Reset_Negativo_-1_a_-20uA"))
        protocolo.append(("PAUSA_C_BIAS", -20.0, "Pausa_tras_Reset_Negativo"))

    return protocolo


def generar_pasos_rampa(i_inicio, i_fin, paso, incluir_inicio=False):
    if math.isclose(i_inicio, i_fin, abs_tol=1e-6):
        return np.array([i_fin]) if incluir_inicio else np.array([])
    n_pasos = max(1, int(round(abs(i_fin - i_inicio) / abs(paso))))
    puntos = np.round(np.linspace(i_inicio, i_fin, n_pasos + 1), 5)
    return puntos if incluir_inicio else puntos[1:]


# =============================================================================
# 2. HILO TRABAJADOR (Operate Continuo, OFF = 0.0 A, SCPI Validado Manual 34420A)
# =============================================================================
class HiloExperimentoHisteresis(QThread):
    # t_min, i_p, i_b, v2_i, r2_i, v2_b, r2_b, v3_i, r3_i, v3_b, r3_b, voc2, voc3, es_pausa, fase
    datos_punto = Signal(float, float, float, float, float, float, float, float, float, float, float, float, float, bool, str)
    nueva_traza = Signal()
    estado_msg = Signal(str)

    def __init__(self, archivo_destino, modo_bias="DELTA", modo_protocolo="ISO_CARGA"):
        super().__init__()
        self.archivo_csv = archivo_destino
        self.modo_bias = modo_bias        # "DELTA" (+,-), "TRIPLETE" (+,0,-), o "SIMPLE" (+)
        self.modo_protocolo = modo_protocolo
        self.corriendo = False
        self.pausa_manual_cbias = False
        self.saltar_etapa = False
        
        self.fuente = Keithley224("GPIB0::02::INSTR")
        self.voltimetro = Agilent34420A("GPIB0::07::INSTR")
        self.matriz = SwitchMatrixHP34970A("GPIB0::9::INSTR")
        self.canal_matriz_actual = None

    def _convertir_a_ma(self, corriente_ua):
        """Permite enviar exactamente 0.0 mA (I0.0000E+00X) con K224 en Operate."""
        if abs(corriente_ua) < 1e-4:
            return 0.0
        return corriente_ua * 1e-3

    def _rutar_matriz_en_cero(self, canal_destino):
        """
        Pone la corriente en 0.0 A (manteniendo Operate F1X y alta impedancia)
        antes de conmutar los canales de lectura de la matriz.
        """
        if not USAR_MATRIZ or canal_destino == self.canal_matriz_actual:
            return
        self.fuente.set_corriente(0.0)
        otro_canal = MATRIZ_3W if canal_destino == MATRIZ_2W else MATRIZ_2W
        self.matriz.open_channels(otro_canal)
        self.matriz.close_channels(canal_destino)
        self.canal_matriz_actual = canal_destino
        time.sleep(0.15)

    def _ejecutar_pulso_individual(self, corriente_ua):
        """
        Sincronización determinista de ventanas de integración (sin solapamiento):
          1. Aplica `corriente_ua` en t = 0.
          2. Espera hasta los últimos ~60 ms de ANCHO_PULSO_S para que el escalón asiente al 100%.
          3. Dispara `READ?` (integra durante 2 NPLC = 40 ms al final de la fase ON).
          4. Baja a `0.0 A` (en Operate F1X).
          5. Espera hasta los últimos ~60 ms de PERIODO_PULSO_S para que el escalón a 0 A asiente.
          6. Dispara `READ?` para `voc_off` al final de la fase OFF.
        """
        t_inicio_ciclo = time.time()
        corr_ma = self._convertir_a_ma(corriente_ua)
        margen_lectura = (NPLC_DMM * 0.02) + 0.025

        # --- FASE 1: PULSO ON ---
        self.fuente.set_corriente(corr_ma)

        t_espera_on = ANCHO_PULSO_S - margen_lectura
        if t_espera_on > 0:
            while (time.time() - t_inicio_ciclo) < t_espera_on and self.corriendo:
                time.sleep(0.005)

        voltaje_on = self.voltimetro.leer_voltaje()

        # --- FASE 2: PULSO OFF (0.0 A en Operate F1X) ---
        self.fuente.set_corriente(0.0)

        if abs(corr_ma) >= 1e-6:
            resistencia = voltaje_on / (corr_ma * 1e-3)
        else:
            resistencia = float('nan')

        voc_off = voltaje_on if abs(corr_ma) < 1e-6 else float('nan')

        if MEDIR_VOC_EN_TOFF and abs(corr_ma) >= 1e-6 and self.corriendo:
            # Esperar hasta el FINAL de la ventana t_off para que la caída a 0 A haya asentado por completo
            t_objetivo_voc = PERIODO_PULSO_S - margen_lectura
            while (time.time() - t_inicio_ciclo) < t_objetivo_voc and self.corriendo:
                time.sleep(0.005)
            voc_off = self.voltimetro.leer_voltaje()

        # Completar cualquier remanente del periodo total
        while (time.time() - t_inicio_ciclo) < PERIODO_PULSO_S and self.corriendo:
            time.sleep(0.005)

        return voltaje_on, resistencia, corr_ma * 1e3, voc_off

    def medir_2w_y_3w(self, corriente_ua):
        if not (USAR_MATRIZ and MEDIR_3W):
            self._rutar_matriz_en_cero(MATRIZ_2W)
            v2, r2, i_real_ua, voc2 = self._ejecutar_pulso_individual(corriente_ua)
            return v2, r2, float('nan'), float('nan'), i_real_ua, voc2, float('nan')

        if self.canal_matriz_actual == MATRIZ_3W:
            v3, r3, i_real_ua, voc3 = self._ejecutar_pulso_individual(corriente_ua)
            v2, r2, voc2 = float('nan'), float('nan'), float('nan')
            if self.corriendo:
                self._rutar_matriz_en_cero(MATRIZ_2W)
                v2, r2, _, voc2 = self._ejecutar_pulso_individual(corriente_ua)
        else:
            self._rutar_matriz_en_cero(MATRIZ_2W)
            v2, r2, i_real_ua, voc2 = self._ejecutar_pulso_individual(corriente_ua)
            v3, r3, voc3 = float('nan'), float('nan'), float('nan')
            if self.corriendo:
                self._rutar_matriz_en_cero(MATRIZ_3W)
                v3, r3, _, voc3 = self._ejecutar_pulso_individual(corriente_ua)

        return v2, r2, v3, r3, i_real_ua, voc2, voc3

    def _obtener_lista_biases(self):
        b_mag = abs(float(I_BIAS_UA))
        if self.modo_bias == "DELTA":
            return [b_mag, -b_mag]
        elif self.modo_bias == "TRIPLETE":
            return [b_mag, 0.0, -b_mag]
        return [b_mag]

    def _guardar_y_emitir(self, t_inicio, etiqueta, ult_pulso, i_b_real, v2_b, r2_b, v3_b, r3_b, voc2_b, voc3_b, es_pausa, emitir_ui=True):
        t_min = (time.time() - t_inicio) / 60.0
        r_diff_inst = ult_pulso['r2'] - ult_pulso['r3'] if not math.isnan(ult_pulso['r3']) else float('nan')
        r_diff_rem = r2_b - r3_b if not math.isnan(r3_b) else float('nan')

        if abs(i_b_real) < 1e-4:
            polaridad_str = "ZERO"
            r2_corr, r3_corr = float('nan'), float('nan')
        else:
            polaridad_str = "POS" if i_b_real > 0 else "NEG"
            i_b_amp = i_b_real * 1e-6
            r2_corr = (v2_b - voc2_b) / i_b_amp if not (math.isnan(v2_b) or math.isnan(voc2_b)) else float('nan')
            r3_corr = (v3_b - voc3_b) / i_b_amp if not (math.isnan(v3_b) or math.isnan(voc3_b)) else float('nan')

        fila = [
            f"{t_min:.4f}", etiqueta, polaridad_str, f"{ult_pulso['i_ua']:.4f}", f"{i_b_real:.4f}",
            ult_pulso['v2'], ult_pulso['r2'], r2_b, v2_b,
            ult_pulso['v3'], ult_pulso['r3'], r3_b, v3_b,
            r_diff_inst, r_diff_rem,
            voc2_b, voc3_b, r2_corr, r3_corr
        ]
        with open(self.archivo_csv, 'a', newline='') as f:
            csv.writer(f).writerow(fila)

        if emitir_ui:
            self.datos_punto.emit(
                t_min, ult_pulso['i_ua'], i_b_real,
                ult_pulso['v2'], ult_pulso['r2'], v2_b, r2_b,
                ult_pulso['v3'], ult_pulso['r3'], v3_b, r3_b,
                voc2_b, voc3_b, es_pausa, etiqueta
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

            # Configuración validada contra el Manual del Keysight 34420A (Cap. 4, págs. 142-179):
            self.voltimetro.inst.write("*CLS")
            self.voltimetro.inst.write('SENS:FUNC "VOLT:DC"')
            self.voltimetro.inst.write("ROUT:TERM FRON1")
            self.voltimetro.inst.write("INP:FILT:STAT OFF")           # Apaga filtro digital (boxcar) y analógico
            self.voltimetro.inst.write("SENS1:VOLT:DC:RANG:AUTO OFF") # Desactiva autorange en CH1
            self.voltimetro.inst.write(f"SENS1:VOLT:DC:RANG {RANGO_CH1_VAL}")
            self.voltimetro.inst.write(f"SENS1:VOLT:DC:NPLC {NPLC_DMM}")
            self.voltimetro.inst.write("TRIG:SOUR IMM")
            self.voltimetro.inst.write("TRIG:DEL 0")                  # Sin retardo extra antes de integrar
            time.sleep(0.15)

            self.fuente.set_limite_voltaje(LIMITE_VOLTAJE_V)

            # Cerrar canal inicial y activar Operate (F1X) a 0.0 A continuo
            if USAR_MATRIZ:
                self.matriz.close_channels(MATRIZ_2W)
                self.canal_matriz_actual = MATRIZ_2W
                time.sleep(0.15)
            self.fuente.set_corriente(0.0)
            self.fuente.operar()

            encabezado = [
                "Tiempo (min)", "Fase", "Polaridad_Bias", "I pulso (uA)", "I bias (uA)",
                "Vinst 2W (V)", "Rinst 2W (Ohm)", "Rrem 2W (Ohm)", "Vbias 2W (V)",
                "Vinst 3W (V)", "Rinst 3W (Ohm)", "Rrem 3W (Ohm)", "Vbias 3W (V)",
                "Delta_Rinst_2W_3W (Ohm)", "Delta_Rrem_2W_3W (Ohm)",
                "Voc_off 2W (V)", "Voc_off 3W (V)", "Rcorr_EMF 2W (Ohm)", "Rcorr_EMF 3W (Ohm)"
            ]
            with open(self.archivo_csv, 'w', newline='') as f:
                csv.writer(f).writerow(encabezado)

            t_inicio = time.time()
            protocolo = generar_protocolo(self.modo_protocolo)
            i_actual_ua = 0.0
            etapa_idx = 0

            ult_pulso = {
                'i_ua': 0.0,
                'v2': float('nan'), 'r2': float('nan'),
                'v3': float('nan'), 'r3': float('nan')
            }

            for accion, param, nombre_base in protocolo:
                if not self.corriendo: break
                self.saltar_etapa = False
                etapa_idx += 1
                etiqueta = f"E{etapa_idx}_{nombre_base}"

                # =================================================================
                # MODO 1: RAMPAS O LISTAS DE PULSOS (ISO-CARGA / CLÁSICO)
                # =================================================================
                if accion in ("RAMPA_DESDE_CERO", "RAMPA_CONTINUA", "LISTA_PULSOS"):
                    if accion == "RAMPA_DESDE_CERO":
                        i_actual_ua = 0.0
                        if etapa_idx > 1:
                            self.nueva_traza.emit()
                        pasos_i = generar_pasos_rampa(0.0, float(param), PASO_RAMPA_UA, incluir_inicio=True)
                    elif accion == "RAMPA_CONTINUA":
                        pasos_i = generar_pasos_rampa(i_actual_ua, float(param), PASO_RAMPA_UA, incluir_inicio=False)
                    else:
                        if etapa_idx > 1:
                            self.nueva_traza.emit()
                        pasos_i = np.array(param, dtype=float)

                    for i_step_ua in pasos_i:
                        if not self.corriendo or self.saltar_etapa: break

                        while self.pausa_manual_cbias and self.corriendo and not self.saltar_etapa:
                            for b_val in self._obtener_lista_biases():
                                if not self.pausa_manual_cbias or not self.corriendo or self.saltar_etapa: break
                                self.estado_msg.emit(f"[PAUSA MANUAL en {ult_pulso['i_ua']:.2f} uA] Bias = {b_val:+.2f} uA")
                                v2_b, r2_b, v3_b, r3_b, i_b_real, voc2_b, voc3_b = self.medir_2w_y_3w(b_val)
                                self._guardar_y_emitir(t_inicio, f"{etiqueta}_PausaManual", ult_pulso, i_b_real, v2_b, r2_b, v3_b, r3_b, voc2_b, voc3_b, True)

                        if not self.corriendo or self.saltar_etapa: break

                        self.estado_msg.emit(f"[{etiqueta}] Pulso Principal I = {i_step_ua:.2f} uA")

                        v2_inst, r2_inst, v3_inst, r3_inst, i_p_real, voc2_p, voc3_p = self.medir_2w_y_3w(i_step_ua)
                        ult_pulso = {
                            'i_ua': i_p_real,
                            'v2': v2_inst, 'r2': r2_inst,
                            'v3': v3_inst, 'r3': r3_inst
                        }
                        i_actual_ua = i_step_ua

                        if NUM_BIAS_EN_RAMPA > 0:
                            for _ in range(NUM_BIAS_EN_RAMPA):
                                if not self.corriendo or self.saltar_etapa: break
                                for b_val in self._obtener_lista_biases():
                                    if not self.corriendo or self.saltar_etapa: break
                                    self.estado_msg.emit(f"[{etiqueta}] Lectura Bias = {b_val:+.2f} uA (tras {i_step_ua:.2f} uA)")
                                    v2_b, r2_b, v3_b, r3_b, i_b_real, voc2_b, voc3_b = self.medir_2w_y_3w(b_val)
                                    self._guardar_y_emitir(t_inicio, etiqueta, ult_pulso, i_b_real, v2_b, r2_b, v3_b, r3_b, voc2_b, voc3_b, False)
                        else:
                            self._guardar_y_emitir(t_inicio, etiqueta, ult_pulso, float('nan'), float('nan'), float('nan'), float('nan'), float('nan'), voc2_p, voc3_p, False)

                # =================================================================
                # MODO 2: PAUSA CON BIAS + VERIFICACIÓN FINAL DE EMF (0 A y DOBLE BIAS)
                # =================================================================
                elif accion == "PAUSA_C_BIAS":
                    t_pausa_inicio = time.time()
                    paso_alternado = 0

                    while ((time.time() - t_pausa_inicio) < TIEMPO_RELAX_S or self.pausa_manual_cbias) and self.corriendo and not self.saltar_etapa:
                        lista_biases = self._obtener_lista_biases()
                        b_val = lista_biases[paso_alternado % len(lista_biases)]
                        paso_alternado += 1

                        restante = max(0.0, TIEMPO_RELAX_S - (time.time() - t_pausa_inicio))
                        extra_txt = " [HOLD MANUAL ACTIVO]" if self.pausa_manual_cbias else f" - Restan {restante:.1f}s"
                        self.estado_msg.emit(f"[{etiqueta}] Midiendo Bias ({b_val:+.2f} uA){extra_txt}")

                        v2_b, r2_b, v3_b, r3_b, i_b_real, voc2_b, voc3_b = self.medir_2w_y_3w(b_val)
                        self._guardar_y_emitir(t_inicio, etiqueta, ult_pulso, i_b_real, v2_b, r2_b, v3_b, r3_b, voc2_b, voc3_b, True)

                    # Secuencia final tras los 50s de relajación: [0.0, +0.1, -0.1, 0.0, +0.2, -0.2] uA
                    if CUADRUPLETE_FINAL_PAUSA and self.corriendo and not self.saltar_etapa:
                        b1 = abs(float(I_BIAS_UA))
                        b2 = abs(float(I_BIAS_DOBLE_UA))
                        secuencia_test = [0.0, b1, -b1, 0.0, b2, -b2]
                        etiqueta_test = f"{etiqueta}_CheckEMF"
                        for idx_t, b_val in enumerate(secuencia_test, 1):
                            if not self.corriendo or self.saltar_etapa: break
                            self.estado_msg.emit(f"[{etiqueta_test}] Paso {idx_t}/6: Bias = {b_val:+.2f} uA")
                            v2_b, r2_b, v3_b, r3_b, i_b_real, voc2_b, voc3_b = self.medir_2w_y_3w(b_val)
                            es_b1_o_cero = math.isclose(abs(b_val), b1, rel_tol=1e-2) or abs(b_val) < 1e-4
                            self._guardar_y_emitir(t_inicio, etiqueta_test, ult_pulso, i_b_real, v2_b, r2_b, v3_b, r3_b, voc2_b, voc3_b, True, emitir_ui=es_b1_o_cero)

            self.estado_msg.emit(f"Experimento finalizado. Guardado en {os.path.basename(self.archivo_csv)}")

        except Exception as e:
            self.estado_msg.emit(f"ERROR CRÍTICO: {e}")
        finally:
            # ÚNICO LUGAR DONDE SE PASA A STANDBY (Fin del protocolo o Parada de Emergencia)
            try:
                self.fuente.set_corriente(0.0)
                self.fuente.standby()
            except:
                pass
            if USAR_MATRIZ:
                try:
                    self.matriz.open_channels([MATRIZ_2W, MATRIZ_3W])
                except:
                    pass
            self.corriendo = False


# =============================================================================
# 3. INTERFAZ GRÁFICA EN VIVO
# =============================================================================
class VentanaHisteresis(QMainWindow):
    MODOS_BIAS = ["DELTA", "TRIPLETE", "SIMPLE"]

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mapeo Iso-Carga y EMF en Operate Continuo (0 A en OFF, Sin Standby)")
        self.resize(1440, 780)
        self.worker = None
        self.idx_modo_bias = 0  # Inicia en "DELTA" (+ / -)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        top_bar = QHBoxLayout()
        self.btn_iniciar = QPushButton("Iniciar Experimento")
        self.btn_iniciar.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold; height: 35px; padding: 0 15px;")

        self.combo_modo = QComboBox()
        self.combo_modo.addItems(["ISO_CARGA (Subida vs Bajada vs Holds)", "CLASICO (Rampas Noleti 5/6)"])
        self.combo_modo.setStyleSheet("font-weight: bold; height: 35px; padding: 0 10px;")

        self.btn_modo_bias = QPushButton()
        self.btn_modo_bias.clicked.connect(self.ciclar_modo_bias)
        self._actualizar_estilo_bias()

        self.btn_pausa_manual = QPushButton("Forzar Pausa c/Bias")
        self.btn_pausa_manual.setCheckable(True)
        self.btn_pausa_manual.setStyleSheet("background-color: #fff3e0; color: black; font-weight: bold; height: 35px; padding: 0 15px;")
        
        self.btn_saltar = QPushButton("Saltar Etapa Actual >>")
        self.btn_saltar.setStyleSheet("background-color: #e3f2fd; color: black; font-weight: bold; height: 35px; padding: 0 15px;")

        self.btn_detener = QPushButton("Detención de Emergencia")
        self.btn_detener.setStyleSheet("background-color: #c62828; color: white; font-weight: bold; height: 35px; padding: 0 15px;")
        
        self.lbl_estado = QLabel("Listo para iniciar (K224 en F1X continuo, SCPI 34420A verificado).")
        self.lbl_estado.setStyleSheet("font-weight: bold; font-size: 13px; margin-left: 10px;")

        for w in [self.btn_iniciar, self.combo_modo, self.btn_modo_bias, self.btn_pausa_manual, self.btn_saltar, self.btn_detener]:
            top_bar.addWidget(w)
        top_bar.addWidget(self.lbl_estado, stretch=1)
        layout.addLayout(top_bar)

        pg.setConfigOption('background', 'w')
        pg.setConfigOption('foreground', 'k')
        pg.setConfigOptions(antialias=True)
        plots_layout = QHBoxLayout()

        # Gráfico 1: Curva I-V
        self.iv_plot = pg.PlotWidget(title="Curva I-V (Pulsos Rampa)")
        self.iv_plot.setLabel('bottom', "Voltaje Vinst (V)")
        self.iv_plot.setLabel('left', "Corriente Pulso (uA)")
        self.iv_plot.showGrid(x=True, y=True, alpha=0.3)
        self.iv_plot.addLegend()
        self.c_iv_2w = self.iv_plot.plot(pen='#0055ff', symbol='o', symbolSize=5, symbolBrush='#0055ff', connect='finite', name="2W")
        self.c_iv_3w = self.iv_plot.plot(pen='#ff5500', symbol='s', symbolSize=5, symbolBrush='#ff5500', connect='finite', name="3W")
        self.c_iv_last = self.iv_plot.plot(pen=None, symbol='o', symbolSize=10, symbolBrush='g', symbolPen='k')
        plots_layout.addWidget(self.iv_plot)

        # Gráfico 2: Rrem vs Corriente de Pulso
        self.rrem_plot = pg.PlotWidget(title="Histéresis Remanente (Rrem vs I pulso)")
        self.rrem_plot.setLabel('bottom', "Corriente de Pulso Origen (uA)")
        self.rrem_plot.setLabel('left', "Rrem medida en Bias (Ω)")
        self.rrem_plot.showGrid(x=True, y=True, alpha=0.3)
        self.rrem_plot.addLegend()
        self.c_rrem_rampa_2w_pos = self.rrem_plot.plot(pen='#0055ff', symbol='o', symbolSize=5, symbolBrush='#0055ff', connect='finite', name="Rrem 2W (+Bias Rampa)")
        self.c_rrem_rampa_2w_neg = self.rrem_plot.plot(pen=pg.mkPen('#00aaee', style=Qt.PenStyle.DashLine), symbol='o', symbolSize=5, symbolBrush='#00aaee', connect='finite', name="Rrem 2W (-Bias Rampa)")
        self.c_rrem_pausa_2w_pos = self.rrem_plot.plot(pen=None, symbol='t', symbolSize=7, symbolBrush='#2e7d32', name="Rrem 2W (+Bias Pausa)")
        self.c_rrem_pausa_2w_neg = self.rrem_plot.plot(pen=None, symbol='t1', symbolSize=7, symbolBrush='#8e24aa', name="Rrem 2W (-Bias Pausa)")
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

    def _actualizar_estilo_bias(self):
        modo = self.MODOS_BIAS[self.idx_modo_bias]
        if modo == "DELTA":
            self.btn_modo_bias.setText("Modo Bias: ±ALTERNADO (+ / -)")
            self.btn_modo_bias.setStyleSheet("background-color: #ce93d8; color: black; font-weight: bold; height: 35px; padding: 0 15px;")
        elif modo == "TRIPLETE":
            self.btn_modo_bias.setText("Modo Bias: TRIPLETE (+ / 0 / -)")
            self.btn_modo_bias.setStyleSheet("background-color: #80cbc4; color: black; font-weight: bold; height: 35px; padding: 0 15px;")
        else:
            self.btn_modo_bias.setText("Modo Bias: SIMPLE (+)")
            self.btn_modo_bias.setStyleSheet("background-color: #e0e0e0; color: black; font-weight: bold; height: 35px; padding: 0 15px;")

    def ciclar_modo_bias(self):
        self.idx_modo_bias = (self.idx_modo_bias + 1) % len(self.MODOS_BIAS)
        self._actualizar_estilo_bias()
        if self.worker and self.worker.corriendo:
            self.worker.modo_bias = self.MODOS_BIAS[self.idx_modo_bias]

    def _obtener_ruta_guardado(self, prefijo):
        dir_defecto = ""
        if os.path.exists("config.json"):
            try:
                with open("config.json", "r") as f:
                    dir_defecto = json.load(f).get("directorio_defecto", "")
            except:
                pass
        nombre_sugerido = os.path.join(dir_defecto, f"{prefijo}_{time.strftime('%Y%m%d_%H%M%S')}.csv")
        ruta, _ = QFileDialog.getSaveFileName(self, "Guardar Experimento", nombre_sugerido, "CSV Files (*.csv)")
        if ruta and not ruta.lower().endswith(".csv"):
            ruta += ".csv"
        return ruta

    def iniciar(self):
        if self.worker and self.worker.corriendo:
            return
        modo_sel = "ISO_CARGA" if self.combo_modo.currentIndex() == 0 else "CLASICO"
        prefijo = "iso_carga_0A" if modo_sel == "ISO_CARGA" else "histeresis_0A"
        ruta_csv = self._obtener_ruta_guardado(prefijo)
        if not ruta_csv:
            return

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

        self.worker = HiloExperimentoHisteresis(
            ruta_csv,
            modo_bias=self.MODOS_BIAS[self.idx_modo_bias],
            modo_protocolo=modo_sel
        )
        self.worker.datos_punto.connect(self.actualizar_graficos)
        self.worker.nueva_traza.connect(self.insertar_corte_traza)
        self.worker.estado_msg.connect(self.lbl_estado.setText)
        self.worker.start()

    def insertar_corte_traza(self):
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
            self.lbl_estado.setText("Deteniendo... enviando 0 A y pasando K224 a Standby.")

    def closeEvent(self, event):
        if self.worker and self.worker.corriendo:
            self.worker.corriendo = False
            self.worker.wait(5000)
        event.accept()

    def actualizar_graficos(self, t_min, i_p, i_b, v2_i, r2_i, v2_b, r2_b, v3_i, r3_i, v3_b, r3_b, voc2, voc3, es_pausa, fase):
        if abs(i_b) < 1e-4:
            return

        es_pos = (i_b > 0)

        if not es_pausa:
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