import os
import time
import csv
import math
import pyvisa
import numpy as np
import pandas as pd
from scipy.signal import savgol_filter
from PySide6.QtCore import QThread, Signal


# ==============================================================================
# DRIVERS: GENERADOR DE FUNCIONES Y OSCILOSCOPIO
# ==============================================================================
class AgilentAFG:
    def __init__(self, resource_name='GPIB0::10::INSTR', timeout=5000):
        self.direccion = resource_name
        self.inst = None
        self.timeout = timeout

    def conectar(self, rm):
        self.inst = rm.open_resource(self.direccion)
        self.inst.timeout = self.timeout
        self.inst.write('OUTP:LOAD INF')
        print(f"AFG Conectado: {self.direccion}")

    def configure_burst(self, wave_shape, num_cycles):
        self.inst.write(f'FUNC {wave_shape}')
        if wave_shape == 'RAMP':
            self.inst.write('FUNC:RAMP:SYMM 50')
        self.inst.write('BURS:MODE TRIG')
        self.inst.write(f'BURS:NCYC {num_cycles}')
        self.inst.write('BURS:STAT ON')
        self.inst.write('TRIG:SOUR BUS')

    def set_pulse_params(self, freq, amp, pulse_width, edge_time):
        self.inst.write(f'SOUR:FREQ {freq}')
        self.inst.write(f'SOUR:VOLT:HIGH {amp}')
        self.inst.write('SOUR:VOLT:LOW 0')

        period = 1.0 / freq
        target_width = max(pulse_width, 8e-9)
        max_allowed_edge = 0.625 * target_width
        actual_edge = min(edge_time, max_allowed_edge)
        actual_edge = max(actual_edge, 5e-9)
        max_safe_width = period - (1.6 * actual_edge)
        actual_width = min(target_width, max_safe_width)

        safe_buffer_width = period * 0.1
        self.inst.write(f'SOUR:PULS:WIDT {safe_buffer_width}')
        self.inst.write(f'SOUR:PULS:TRAN {actual_edge}')
        self.inst.write(f'SOUR:PULS:WIDT {actual_width}')

    def set_bipolar_params(self, freq, amp):
        self.inst.write(f'SOUR:FREQ {freq}')
        self.inst.write(f'SOUR:VOLT {amp}')
        self.inst.write('SOUR:VOLT:OFFS 0')

    def output_state(self, state):
        self.inst.write(f"OUTP {'ON' if state else 'OFF'}")

    def trigger(self):
        self.inst.write('*TRG')


class TektronixScope:
    def __init__(self, resource_name='USB0::0x0699::0x0413::C012302::0::INSTR', timeout=10000):
        self.direccion = resource_name
        self.inst = None
        self.timeout = timeout
        self.t_div = 0.001

    def conectar(self, rm):
        self.inst = rm.open_resource(self.direccion)
        self.inst.timeout = self.timeout
        # Expandir el buffer USB para soportar 10,000 puntos en ASCII (~140 KB)
        self.inst.chunk_size = 204800

        self.inst.write('HEAD OFF')
        for ch in [1, 2, 3, 4]:
            self.inst.write(f'SEL:CH{ch} ON')
            self.inst.write(f'CH{ch}:COUP DC')
            self.inst.write(f'CH{ch}:BWL 20')

        self.inst.write('ACQ:MOD HIR')
        self.inst.write('HOR:RECO 10000')
        print(f"Osciloscopio Conectado: {self.direccion}")

    def auto_scale(self, freq, amp, wave_shape, pulse_width, edge_time, num_cycles, pulse_zoom_factor, use_sync):
        if wave_shape == 'SIN':
            self.inst.write('CH1:COUP DC')
            for ch in [2, 3, 4]:
                self.inst.write(f'CH{ch}:COUP AC')
        else:
            for ch in [1, 2, 3, 4]:
                self.inst.write(f'CH{ch}:COUP DC')

        period = 1.0 / freq
        if wave_shape == 'PULS':
            target_width = max(pulse_width, 8e-9)
            max_allowed_edge = 0.625 * target_width
            actual_edge = min(edge_time, max_allowed_edge)
            actual_edge = max(actual_edge, 5e-9)
            max_safe_width = period - (1.6 * actual_edge)
            actual_width = min(target_width, max_safe_width)

            if num_cycles > 1:
                total_time_needed = (num_cycles + 3.0) * period
            else:
                active_pulse_time = (actual_edge * 2) + actual_width
                total_time_needed = active_pulse_time * pulse_zoom_factor
                total_time_needed = min(total_time_needed, period)
                total_time_needed = max(total_time_needed, 10e-9)
        else:
            total_time_needed = (num_cycles + 3.0) * period

        # Escala de tiempo en secuencia 1-2.5-5
        min_total_time = total_time_needed / 0.7
        min_t_div = min_total_time / 10.0

        if min_t_div <= 0:
            min_t_div = 1e-9
        exponent = math.floor(math.log10(min_t_div))
        mantissa = min_t_div / (10**exponent)

        if mantissa <= 1.0:
            t_div = 1.0 * (10**exponent)
        elif mantissa <= 2.5:
            t_div = 2.5 * (10**exponent)
        elif mantissa <= 5.0:
            t_div = 5.0 * (10**exponent)
        else:
            t_div = 10.0 * (10**exponent)

        self.t_div = t_div

        self.inst.write(f'HOR:SCA {t_div:.4e}')
        self.inst.write('HOR:DEL:MOD OFF')
        self.inst.write('HOR:POS 20')

        self.inst.write('TRIG:A:TYP EDGE')
        self.inst.write('TRIG:A:EDGE:SLO RISE')
        if use_sync:
            self.inst.write('TRIG:A:SOUR EXT')
            self.inst.write('TRIG:A:LEV 1.0')
        else:
            self.inst.write('TRIG:A:SOUR CH1')
            self.inst.write('TRIG:A:EDGE:COUP DC')
            self.inst.write(f'TRIG:A:LEV {amp * 0.2}')

        # Secuencia 1-2-5 para voltaje vertical
        v_div = amp / 6.0
        if v_div < 0.002:
            safe_scale = 0.002
        else:
            exp_y = math.floor(math.log10(v_div))
            man_y = v_div / (10**exp_y)
            if man_y <= 1.0:
                safe_scale = 1.0 * (10**exp_y)
            elif man_y <= 2.0:
                safe_scale = 2.0 * (10**exp_y)
            elif man_y <= 5.0:
                safe_scale = 5.0 * (10**exp_y)
            else:
                safe_scale = 10.0 * (10**exp_y)

        safe_scale = max(safe_scale, 0.002)

        for ch in [1, 2, 3, 4]:
            self.inst.write(f'CH{ch}:SCA {safe_scale:.4f}')
            self.inst.write(f'CH{ch}:POS 0')

    def prepare_acquisition(self):
        self.inst.write('ACQ:STOPA SEQ')
        self.inst.write('ACQ:STATE ON')

        t_div = getattr(self, 't_div', 0.001)
        fill_time = (t_div * 10.0) * 0.2
        time.sleep(fill_time + 0.15)

    def wait_for_trigger(self, max_wait=5.0):
        t_div = getattr(self, 't_div', 0.001)
        dinamic_wait = max(max_wait, (t_div * 10.0 * 2.0) + 5.0)

        timeout_start = time.time()
        while int(self.inst.query('BUSY?')) == 1:
            time.sleep(0.05)
            if time.time() - timeout_start > dinamic_wait:
                self.inst.write('ACQ:STATE OFF')
                return False
        return True

    def _safe_get_curve(self):
        """Descarga la curva e ignora caracteres corruptos o datos nulos."""
        raw_str = self.inst.query('CURV?').strip()
        if "CURV" in raw_str.upper() or "CURVE" in raw_str.upper():
            raw_str = raw_str.split(' ', 1)[-1]

        clean_data = []
        for val in raw_str.split(','):
            try:
                clean_data.append(float(val))
            except ValueError:
                clean_data.append(0.0)
        return np.array(clean_data)

    def auto_scale_y(self):
        for ch in [1, 2, 3, 4]:
            try:
                self.inst.write(f'DAT:SOU CH{ch}')
                time.sleep(0.1)
                self.inst.write('DAT:ENC ASCI')
                self.inst.write('DAT:WID 1')
                self.inst.write('DAT:STAR 1')
                self.inst.write('DAT:STOP 10000')

                time.sleep(0.05)
                y_mult = float(self.inst.query('WFMPre:YMULT?'))
                y_zero = float(self.inst.query('WFMPre:YZERO?'))
                y_off = float(self.inst.query('WFMPre:YOFF?'))

                raw_data = self._safe_get_curve()

                if len(raw_data) > 0:
                    volts = (raw_data - y_off) * y_mult + y_zero
                    vpp = np.max(volts) - np.min(volts)

                    if vpp > 0:
                        v_div = vpp / 6.0
                        if v_div < 0.002:
                            optimal_scale = 0.002
                        else:
                            exp_y = math.floor(math.log10(v_div))
                            man_y = v_div / (10**exp_y)
                            if man_y <= 1.0:
                                optimal_scale = 1.0 * (10**exp_y)
                            elif man_y <= 2.0:
                                optimal_scale = 2.0 * (10**exp_y)
                            elif man_y <= 5.0:
                                optimal_scale = 5.0 * (10**exp_y)
                            else:
                                optimal_scale = 10.0 * (10**exp_y)

                        optimal_scale = max(optimal_scale, 0.002)
                        self.inst.write(f'CH{ch}:SCA {optimal_scale:.4f}')
            except Exception:
                pass
        time.sleep(0.2)

    def get_waveform(self, channel):
        self.inst.write(f'DAT:SOU CH{channel}')
        time.sleep(0.1)
        self.inst.write('DAT:ENC ASCI')
        self.inst.write('DAT:WID 1')
        self.inst.write('DAT:STAR 1')
        self.inst.write('DAT:STOP 10000')

        time.sleep(0.05)
        y_mult = float(self.inst.query('WFMPre:YMULT?'))
        y_zero = float(self.inst.query('WFMPre:YZERO?'))
        y_off = float(self.inst.query('WFMPre:YOFF?'))
        x_incr = float(self.inst.query('WFMPre:XINCR?'))

        raw_data = self._safe_get_curve()
        if len(raw_data) == 0:
            raw_data = np.zeros(10000)

        volts = (raw_data - y_off) * y_mult + y_zero
        return volts, x_incr


# ==============================================================================
# DRIVER DEL LCR TONGHUI TH2832
# ==============================================================================
class TonghuiTH2832:
    def __init__(self, resource_name="GPIB0::11::INSTR", timeout=5000):
        self.direccion = resource_name
        self.rm = None
        self.inst = None
        self.timeout = timeout

    def conectar(self, rm):
        self.rm = rm
        self.inst = self.rm.open_resource(self.direccion)
        self.inst.timeout = self.timeout
        self.inst.write_termination = '\n'
        self.inst.read_termination = '\n'

        self.inst.write("*CLS")
        self.inst.write("TRIG:SOUR BUS")
        self.inst.write("FUNC:IMP RX")

        try:
            self.inst.write("FUNC:SMON:VIAC ON")
        except Exception:
            pass

        print(f"TH2832 Conectado: {self.direccion}")

    def set_frecuencia(self, freq):
        self.inst.write(f"FREQ {freq}HZ")

    def set_vac(self, vac):
        self.inst.write(f"VOLT {vac}V")

    def set_alc(self, state):
        self.inst.write(f"AMPL:ALC {1 if state else 0}")

    def set_vdc(self, vdc):
        if abs(vdc) < 1e-5:
            self.inst.write("BIAS:STAT 0")
        else:
            self.inst.write("BIAS:STAT 1")
            self.inst.write(f"BIAS:VOLT {vdc}V")

    def set_speed_and_avg(self, speed_str, avg):
        self.inst.write(f"APER {speed_str}, {int(avg)}")

    def set_rsou(self, rsou_val):
        self.inst.write(f"ORES {int(rsou_val)}")

    def set_range(self, range_str):
        if range_str.upper() == "AUTO":
            self.inst.write("FUNC:IMP:RANG:AUTO ON")
        else:
            self.inst.write(f"FUNC:IMP:RANG {range_str}")

    def set_trigger_delay(self, delay_s):
        self.inst.write(f"TRIG:DEL {delay_s}S")

    def medir(self):
        self.inst.write("*TRG")
        for _ in range(40):
            time.sleep(0.05)
            try:
                respuesta = self.inst.query("FETC?")
                partes = respuesta.split(',')
                status = int(partes[2])
                if status != -1:
                    r = float(partes[0])
                    x = float(partes[1])
                    return r, x, status
            except Exception:
                pass
        return float('nan'), float('nan'), -1

    def get_monitors(self):
        try:
            vm = float(self.inst.query("FETC:SMON:VAC?"))
            im = float(self.inst.query("FETC:SMON:IAC?"))
            if abs(vm) > 1e30:
                vm = float('nan')
            if abs(im) > 1e30:
                im = float('nan')
            return vm, im
        except Exception:
            return float('nan'), float('nan')


# ==============================================================================
# DRIVER DE LA MATRIZ HP34970A
# ==============================================================================
class SwitchMatrixHP34970A:
    def __init__(self, resource_name='GPIB0::9::INSTR', timeout=2000):
        self.direccion = resource_name
        self.rm = None
        self.instrument = None
        self.timeout = timeout

    def conectar(self, rm):
        self.rm = rm
        self.instrument = self.rm.open_resource(self.direccion)
        self.instrument.timeout = self.timeout
        self.instrument.write_termination = '\n'
        self.instrument.read_termination = '\n'
        print(f"HP34970A Conectado: {self.direccion}")

    def open_channels(self, channel_list):
        if not self.instrument:
            return
        if isinstance(channel_list, (list, tuple)):
            channel_str = ','.join(str(ch) for ch in channel_list)
        else:
            channel_str = str(channel_list)
        self.instrument.write(f'ROUTe:OPEN (@{channel_str})')

    def close_channels(self, channel_list):
        if not self.instrument:
            return
        if isinstance(channel_list, (list, tuple)):
            channel_str = ','.join(str(ch) for ch in channel_list)
        else:
            channel_str = str(channel_list)
        self.instrument.write(f'ROUTe:CLOSe (@{channel_str})')


# ==============================================================================
# DRIVERS: CRIOSTATO (LAKESHORE DRC-91CA + MOTOR AGILENT E3643A)
# ==============================================================================
class LakeShoreDRC91CA:
    def __init__(self, resource_name="GPIB0::12::INSTR", timeout=2000):
        self.direccion = resource_name
        self.rm = None
        self.inst = None
        self.timeout = timeout

    def conectar(self, rm):
        self.rm = rm
        self.inst = self.rm.open_resource(self.direccion)
        self.inst.timeout = self.timeout
        print(f"LakeShore Conectado: {self.direccion}")

    def read_temperature(self):
        response = self.inst.query("WS")
        return float(response.split('\r')[0].split('K')[0])

    def set_setpoint(self, setpoint):
        self.inst.write(f"S{float(setpoint)}")

    def get_setpoint(self):
        response = self.inst.query("WP")
        return float(response.split('\r')[0].split('K')[0])

    def get_HTR(self):
        response = self.inst.query("W3")
        return float(response.split('\r')[0].split(',')[-1])

    def set_pid(self, p, i, d):
        self.inst.write(f"P{float(p)}")
        self.inst.write(f"I{float(i)}")
        self.inst.write(f"D{float(d)}")

    def get_pid(self):
        try:
            p = float(self.inst.query("P?").strip())
            i = float(self.inst.query("I?").strip())
            d = float(self.inst.query("D?").strip())
            return p, i, d
        except Exception:
            return float('nan'), float('nan'), float('nan')


class AgilentE3643A:
    def __init__(self, resource_name='GPIB0::5::INSTR', timeout=5000):
        self.direccion = resource_name
        self.rm = None
        self.inst = None
        self.timeout = timeout

    def conectar(self, rm):
        self.rm = rm
        self.inst = self.rm.open_resource(self.direccion)
        self.inst.timeout = self.timeout
        print(f"E3643A Conectado: {self.direccion}")

    def apply(self, voltage):
        if voltage > 4.9:
            voltage = 4.9
        if self.inst:
            self.inst.write(f"APPL {voltage},0")
            self.inst.write("OUTP ON")


# ==============================================================================
# DRIVERS: KEITHLEY 224 Y AGILENT 34420A
# ==============================================================================
class Keithley224:
    def __init__(self, direccion="GPIB0::02::INSTR"):
        self.direccion = direccion
        self.inst = None
        self.ultimo_limite_v = None
        self.en_operacion = False

    def conectar(self, rm):
        self.inst = rm.open_resource(self.direccion)
        self.inst.write_termination = '\r\n'
        self.inst.read_termination = '\r\n'
        self.inst.write("R0X")
        self.ultimo_limite_v = None
        self.en_operacion = False
        self.standby()
        print(f"K224 Conectado: {self.direccion}")

    def set_corriente(self, valor_ma):
        if self.inst:
            valor_amps = valor_ma * 1e-3
            self.inst.write(f"I{valor_amps:.4E}X")

    def set_limite_voltaje(self, valor_v):
        if self.inst and valor_v != self.ultimo_limite_v:
            self.inst.write(f"V{int(valor_v)}X")
            self.ultimo_limite_v = valor_v

    def operar(self):
        if self.inst and not self.en_operacion:
            self.inst.write("F1X")
            self.en_operacion = True

    def standby(self):
        try:
            if self.inst:
                self.inst.write("F0X")
                self.en_operacion = False
        except Exception:
            pass


class Agilent34420A:
    def __init__(self, direccion="GPIB0::07::INSTR"):
        self.direccion = direccion
        self.inst = None
        self.ultimo_nplc = None
        self.ultimo_rango = None
        self.ultimo_canal = None

    def conectar(self, rm):
        self.inst = rm.open_resource(self.direccion)
        self.inst.timeout = 5000
        self.inst.write("*CLS")

        self.ultimo_nplc = None
        self.ultimo_rango = None
        self.ultimo_canal = None
        print(f"34420A Conectado: {self.direccion}")

    def seleccionar_canal(self, canal):
        if self.inst and canal != self.ultimo_canal:
            self.inst.write(f"ROUT:TERM FRON{canal}")
            self.ultimo_canal = canal

    def configurar_rapido(self, nplc, rango_str):
        if not self.inst:
            return

        if nplc != self.ultimo_nplc:
            self.inst.write(f"VOLT:DC:NPLC {nplc}")
            self.ultimo_nplc = nplc

        if rango_str != self.ultimo_rango:
            diccionario_rangos = {
                "Auto": "AUTO ON", "1 mV": "0.001", "10 mV": "0.01",
                "100 mV": "0.1", "1 V": "1.0", "10 V": "10.0", "100 V": "100.0"
            }
            rango_val = diccionario_rangos.get(rango_str, "AUTO ON")

            # Configurar Canal 1 (soporta hasta 100V)
            self.inst.write("ROUT:TERM FRON1")
            if rango_val == "AUTO ON":
                self.inst.write("SENS1:VOLT:DC:RANG:AUTO ON")
            else:
                self.inst.write(f"SENS1:VOLT:DC:RANG {rango_val}")

            # Configurar Canal 2 (limitado a 10V máximo en el 34420A)
            self.inst.write("ROUT:TERM FRON2")
            if rango_val == "AUTO ON":
                self.inst.write("SENS2:VOLT:DC:RANG:AUTO ON")
            else:
                try:
                    val_float = float(rango_val)
                    ch2_val = "10.0" if val_float > 10.0 else rango_val
                except ValueError:
                    ch2_val = "10.0"
                self.inst.write(f"SENS2:VOLT:DC:RANG {ch2_val}")

            self.ultimo_rango = rango_str

            canal_actual = self.ultimo_canal if self.ultimo_canal else 1
            self.inst.write(f"ROUT:TERM FRON{canal_actual}")

    def leer_voltaje(self):
        if not self.inst:
            return float('nan')
        try:
            val = float(self.inst.query("READ?"))
            if abs(val) > 1e9:
                return float('nan')
            return val
        except Exception:
            return float('nan')


# ==============================================================================
# HILO DE MEDICIÓN I-V Y RELAJACIÓN (K224 + 34420A + MATRIZ HP34970A)
# ==============================================================================
class HiloMedicionDual(QThread):
    datos_actualizados = Signal(float, float, float, float, float, float, bool)
    paso_invertido = Signal(float)
    error_detectado = Signal(str)
    nueva_secuencia = Signal(float, float, str)

    def __init__(self, estado_compartido):
        super().__init__()
        self.estado = estado_compartido
        self.corriendo = False
        self.pausado_cbias = False
        self.pausado_sbias = False

        self.fuente = Keithley224()
        self.voltimetro = Agilent34420A()
        self.matriz = SwitchMatrixHP34970A()

    def iniciar_medicion(self):
        self.corriendo = True
        self.start()

    def detener_medicion(self):
        self.corriendo = False
        self.pausado_cbias = False
        self.pausado_sbias = False

    def _guardar_csv(self, fila_datos, archivo):
        with open(archivo, 'a', newline='') as f:
            csv.writer(f).writerow(fila_datos)

    def _esperar_con_interrupcion(self, duracion_s):
        """Espera activa en ticks de 10 ms respetando la señal de detención."""
        if duracion_s <= 0:
            return
        t0 = time.time()
        while (time.time() - t0) < duracion_s and self.corriendo:
            time.sleep(0.01)

    def _medir_polaridad_simple(self, i_ma, t_espera_on, usa_ch2_fron, delay_cambio_canal):
        """Inyecta una corriente i_ma, espera t_espera_on y lee el 34420A."""
        t_inicio = time.time()
        self.fuente.set_corriente(i_ma)
        self.voltimetro.seleccionar_canal(1)
        self.fuente.operar()

        if t_espera_on > 0:
            while (time.time() - t_inicio) < t_espera_on and self.corriendo:
                time.sleep(0.01)

        v1 = self.voltimetro.leer_voltaje()
        v2 = float('nan')

        if usa_ch2_fron:
            self.voltimetro.seleccionar_canal(2)
            time.sleep(delay_cambio_canal)
            v2 = self.voltimetro.leer_voltaje()
            self.voltimetro.seleccionar_canal(1)

        return v1, v2

    def _conmutar_matriz_seguro(self, ch_abrir, ch_cerrar, delay_asentamiento=0.25):
        """
        Realiza conmutación Break-Before-Make protegiendo la muestra:
        1. Pone la K224 en Standby (F0X) para evitar picos de compliance en circuito abierto.
        2. Abre el canal previo y cierra el nuevo esperando confirmación física (*OPC?).
        3. Espera el tiempo de asentamiento mecánico/térmico del relé.
        """
        self.fuente.standby()
        time.sleep(0.03)
        self.matriz.open_channels(ch_abrir)
        self.matriz.close_channels(ch_cerrar)
        try:
            self.matriz.instrument.query("*OPC?")
        except Exception:
            pass
        time.sleep(delay_asentamiento)

    def _ejecutar_lectura_compleja(self, i_target_ma, ancho_pulso, nplc, usa_ch2_fron,
                                   no_output_off, usar_delta, usa_matriz, ch1_mat, ch2_mat):
        """
        Ejecuta una medición de punto completo protegiendo la conmutación de matriz.
        """
        delay_cambio_canal = 0.05
        delay_matriz = 0.25  # 250 ms de asentamiento post-relé para el nanovoltímetro
        margen_lectura = 0.1 + (delay_cambio_canal if (usa_ch2_fron and not usa_matriz) else 0.0)
        t_espera_on = max(0.05, ancho_pulso - margen_lectura)

        i_pos = float(i_target_ma)
        i_neg = -i_pos
        corriente_nula = abs(i_pos) < 1e-9

        def calc_r(v_val, i_ma, es_delta=False):
            if corriente_nula or math.isnan(v_val):
                return float('nan')
            factor = 2.0 if es_delta else 1.0
            return v_val / (factor * i_ma * 1e-3)

        if usa_matriz:
            self._estaba_en_matriz = True
            # ----------------------------------------------------
            # 1. CANAL 1 DE LA MATRIZ
            # ----------------------------------------------------
            self._conmutar_matriz_seguro(ch2_mat, ch1_mat, delay_matriz)

            v1_pos, _ = self._medir_polaridad_simple(i_pos, t_espera_on, False, delay_cambio_canal)
            if usar_delta and self.corriendo:
                if not no_output_off:
                    self.fuente.standby()
                    time.sleep(0.03)
                v1_neg, _ = self._medir_polaridad_simple(i_neg, t_espera_on, False, delay_cambio_canal)
                v1 = (v1_pos - v1_neg) / 2.0
                r1 = calc_r(v1_pos - v1_neg, i_pos, es_delta=True)
            else:
                v1 = v1_pos
                r1 = calc_r(v1_pos, i_pos, es_delta=False)

            # ----------------------------------------------------
            # 2. CANAL 2 DE LA MATRIZ
            # ----------------------------------------------------
            self._conmutar_matriz_seguro(ch1_mat, ch2_mat, delay_matriz)

            v2_pos, _ = self._medir_polaridad_simple(i_pos, t_espera_on, False, delay_cambio_canal)
            if usar_delta and self.corriendo:
                if not no_output_off:
                    self.fuente.standby()
                    time.sleep(0.03)
                v2_neg, _ = self._medir_polaridad_simple(i_neg, t_espera_on, False, delay_cambio_canal)
                v2 = (v2_pos - v2_neg) / 2.0
                r2 = calc_r(v2_pos - v2_neg, i_pos, es_delta=True)
            else:
                v2 = v2_pos
                r2 = calc_r(v2_pos, i_pos, es_delta=False)

            # 3. Dejar estacionada la matriz en Canal 1 para el próximo ciclo (o si se apaga la matriz)
            self._conmutar_matriz_seguro(ch2_mat, ch1_mat, 0.10)

        else:
            # Si el usuario acaba de apagar el toggle de Matriz en vivo, asegurar que quede en Ch1
            if getattr(self, '_estaba_en_matriz', False) and self.matriz.instrument:
                self._conmutar_matriz_seguro(ch2_mat, ch1_mat, 0.15)
                self._estaba_en_matriz = False

            # ----------------------------------------------------
            # MODO ESTÁNDAR (FRON1 / FRON2 en el 34420A)
            # ----------------------------------------------------
            v1_pos, v2_pos = self._medir_polaridad_simple(i_pos, t_espera_on, usa_ch2_fron, delay_cambio_canal)

            if usar_delta and self.corriendo:
                if not no_output_off:
                    self.fuente.standby()
                    time.sleep(0.03)
                v1_neg, v2_neg = self._medir_polaridad_simple(i_neg, t_espera_on, usa_ch2_fron, delay_cambio_canal)

                v1 = (v1_pos - v1_neg) / 2.0
                r1 = calc_r(v1_pos - v1_neg, i_pos, es_delta=True)

                if usa_ch2_fron:
                    v2 = (v2_pos - v2_neg) / 2.0
                    r2 = calc_r(v2_pos - v2_neg, i_pos, es_delta=True)
                else:
                    v2, r2 = float('nan'), float('nan')
            else:
                v1 = v1_pos
                r1 = calc_r(v1_pos, i_pos, es_delta=False)
                if usa_ch2_fron:
                    v2 = v2_pos
                    r2 = calc_r(v2_pos, i_pos, es_delta=False)
                else:
                    v2, r2 = float('nan'), float('nan')

        # --- FIN DEL PULSO ---
        if no_output_off:
            self.fuente.set_corriente(0.0)
            self.fuente.operar()
        else:
            self.fuente.standby()

        return v1, r1, v2, r2, i_pos

    def run(self):
        archivo_csv = self.estado.get('ruta_archivo', 'medicion_default.csv')
        usa_matriz = self.estado.get('usa_matriz', False)
        ch1_mat = self.estado.get('matriz_ch1', 212)
        ch2_mat = self.estado.get('matriz_ch2', 222)

        try:
            rm = pyvisa.ResourceManager()
        except ImportError:
            self.error_detectado.emit("Librería PyVISA no instalada (hacer 'pip install pyvisa').")
            self.corriendo = False
            return
        except Exception as e:
            self.error_detectado.emit(f"Error de backend VISA: {e}")
            self.corriendo = False
            return

        try:
            self.fuente.conectar(rm)
            self.voltimetro.conectar(rm)
            if usa_matriz and not self.estado.get('modo_relajacion', False):
                self.matriz.conectar(rm)
                self.matriz.open_channels(ch2_mat)
                self.matriz.close_channels(ch1_mat)
                time.sleep(0.2)

            if self.estado.get('modo_relajacion', False):
                self._loop_relajacion(archivo_csv)
            else:
                self._loop_triangular(archivo_csv)

        except Exception as e:
            print(f"Error Crítico durante la medición: {e}")
            self.error_detectado.emit(str(e))

        finally:
            self.fuente.standby()
            if usa_matriz and self.matriz.instrument:
                try:
                    self.matriz.open_channels([ch1_mat, ch2_mat])
                except Exception:
                    pass
            self.corriendo = False
            print("Hilo finalizado. Fuente en Standby.")

    # ==============================================================================
    # LÓGICA 1: MATRIZ DE RELAJACIÓN
    # ==============================================================================
    def _loop_relajacion(self, archivo_csv_base):
        base_dir = os.path.dirname(archivo_csv_base)
        base_name = os.path.splitext(os.path.basename(archivo_csv_base))[0]

        nplc = float(self.estado['nplc'])
        usa_ch2 = self.estado['ch2_activado']
        self.voltimetro.configurar_rapido(nplc, self.estado['rango'])
        delay_cambio_canal = 0.05

        lista_bias = self.estado['lista_bias']
        lista_pulsos = self.estado['lista_pulsos']
        T_descarga = self.estado['tiempo_descarga']

        ancho_lectura = self.estado.get('ancho_lectura', 0.5)
        periodo = self.estado.get('periodo_relajacion', 1.0)
        es_pulsado = self.estado.get('relajacion_pulsada', False)

        for c_bias in lista_bias:
            for c_pulso in lista_pulsos:
                if not self.corriendo:
                    return

                corr_pulso = c_pulso if abs(c_pulso) >= 1e-5 else (1e-5 if c_pulso >= 0 else -1e-5)
                corr_bias = c_bias if abs(c_bias) >= 1e-5 else (1e-5 if c_bias >= 0 else -1e-5)

                b_str = str(c_bias).replace('.', 'p')
                p_str = str(c_pulso).replace('.', 'p')
                archivo_actual = os.path.join(base_dir, f"{base_name}_bias_{b_str}mA_pulso_{p_str}mA.csv")

                self.nueva_secuencia.emit(c_bias, c_pulso, archivo_actual)

                encabezado = [
                    "Tiempo (min)", "I pulso (mA)", "I bias (mA)",
                    "Vinst 1 (V)", "Rinst 1 (Ohm)", "Rrem 1 (Ohm)", "Vbias 1 (V)",
                    "Vinst 2 (V)", "Rinst 2 (Ohm)", "Rrem 2 (Ohm)", "Vbias 2 (V)",
                    "Tiempo de Pulso (s)", "Ancho lectura (s)", "Periodo (s)",
                    "Vcc (V)", "Vrange", "NPLC", "Ch2?"
                ]
                with open(archivo_actual, 'w', newline='') as f:
                    csv.writer(f).writerow(encabezado)

                tiempo_inicio = time.time()

                # ------------------------------------------------
                # FASE 1: PULSO DE CARGA
                # ------------------------------------------------
                self.fuente.set_limite_voltaje(self.estado['limite_voltaje'])
                self.fuente.set_corriente(corr_pulso)
                self.voltimetro.seleccionar_canal(1)
                self.fuente.operar()

                tiempo_inicio_pulso = time.time()
                self.pulse_data = {
                    'i_inst': corr_pulso, 'v1_inst': float('nan'), 'r1_inst': float('nan'),
                    'v2_inst': float('nan'), 'r2_inst': float('nan')
                }

                while (time.time() - tiempo_inicio_pulso) < self.estado['tiempo_pulso'] and self.corriendo:
                    v1_inst = self.voltimetro.leer_voltaje()
                    v2_inst = float('nan')
                    if usa_ch2:
                        self.voltimetro.seleccionar_canal(2)
                        time.sleep(delay_cambio_canal)
                        v2_inst = self.voltimetro.leer_voltaje()
                        self.voltimetro.seleccionar_canal(1)
                        time.sleep(delay_cambio_canal)

                    r1_inst = float('nan') if abs(corr_pulso) < 1e-5 else (v1_inst / (corr_pulso * 1e-3))
                    r2_inst = float('nan') if (abs(corr_pulso) < 1e-5 or not usa_ch2) else (v2_inst / (corr_pulso * 1e-3))

                    t_min = (time.time() - tiempo_inicio) / 60.0
                    self.datos_actualizados.emit(t_min, v1_inst, r1_inst, v2_inst, r2_inst, corr_pulso, False)

                    self.pulse_data = {
                        'i_inst': corr_pulso, 'v1_inst': v1_inst, 'r1_inst': r1_inst,
                        'v2_inst': v2_inst, 'r2_inst': r2_inst
                    }

                    fila = [
                        f"{t_min:.4f}", self.pulse_data['i_inst'], float('nan'),
                        self.pulse_data['v1_inst'], self.pulse_data['r1_inst'], float('nan'), float('nan'),
                        self.pulse_data['v2_inst'], self.pulse_data['r2_inst'], float('nan'), float('nan'),
                        self.estado['tiempo_pulso'], ancho_lectura, periodo,
                        self.estado['limite_voltaje'], self.estado['rango'], nplc, usa_ch2
                    ]
                    self._guardar_csv(fila, archivo_actual)
                    time.sleep(0.01)

                if not self.corriendo:
                    return

                # ------------------------------------------------
                # FASE 2: DESCARGA / RELAJACIÓN
                # ------------------------------------------------
                if not es_pulsado:
                    self.fuente.set_corriente(corr_bias)
                    self.fuente.operar()

                tiempo_inicio_descarga = time.time()

                while (time.time() - tiempo_inicio_descarga) < T_descarga and self.corriendo:
                    inicio_ciclo = time.time()

                    if es_pulsado:
                        self.fuente.set_corriente(corr_bias)
                        self.fuente.operar()

                        margen_lectura = 0.1 + (delay_cambio_canal if usa_ch2 else 0.0)
                        t_espera_on = ancho_lectura - margen_lectura
                        if t_espera_on > 0:
                            while (time.time() - inicio_ciclo) < t_espera_on and self.corriendo:
                                time.sleep(0.01)

                    self.voltimetro.seleccionar_canal(1)
                    if usa_ch2 and not es_pulsado:
                        time.sleep(delay_cambio_canal)

                    v1_bias = self.voltimetro.leer_voltaje()
                    v2_bias = float('nan')

                    if usa_ch2:
                        self.voltimetro.seleccionar_canal(2)
                        time.sleep(delay_cambio_canal)
                        v2_bias = self.voltimetro.leer_voltaje()

                    if es_pulsado:
                        self.fuente.standby()

                    r1_bias = float('nan') if abs(corr_bias) < 1e-5 else (v1_bias / (corr_bias * 1e-3))
                    r2_bias = float('nan') if (abs(corr_bias) < 1e-5 or not usa_ch2) else (v2_bias / (corr_bias * 1e-3))

                    t_min = (time.time() - tiempo_inicio) / 60.0
                    self.datos_actualizados.emit(t_min, v1_bias, r1_bias, v2_bias, r2_bias, corr_bias, True)

                    fila = [
                        f"{t_min:.4f}", self.pulse_data['i_inst'], corr_bias,
                        self.pulse_data['v1_inst'], self.pulse_data['r1_inst'], r1_bias, v1_bias,
                        self.pulse_data['v2_inst'], self.pulse_data['r2_inst'], r2_bias, v2_bias,
                        self.estado['tiempo_pulso'], ancho_lectura, periodo,
                        self.estado['limite_voltaje'], self.estado['rango'], nplc, usa_ch2
                    ]
                    self._guardar_csv(fila, archivo_actual)

                    if es_pulsado:
                        tiempo_consumido = time.time() - inicio_ciclo
                        tiempo_off_deseado = max(0.05, periodo - tiempo_consumido)
                        self._esperar_con_interrupcion(tiempo_off_deseado)
                    else:
                        time.sleep(0.05)

    # ==============================================================================
    # LÓGICA 2: BARRIDO TRIANGULAR I-V (CON NO-OFF, DELTA Y MATRIZ)
    # ==============================================================================
    def _loop_triangular(self, archivo_csv):
        encabezado = [
            "Tiempo (min)", "I pulso (mA)", "I bias (mA)",
            "Vinst 1 (V)", "Rinst 1 (Ohm)", "Rrem 1 (Ohm)", "Vbias 1 (V)",
            "Vinst 2 (V)", "Rinst 2 (Ohm)", "Rrem 2 (Ohm)", "Vbias 2 (V)",
            "Ancho pulso (s)", "Periodo (s)", "Vcc (V)", "Vrange", "NPLC",
            "Ch2?", "N bias", "No_Off", "Delta", "Matriz"
        ]
        with open(archivo_csv, 'w', newline='') as f:
            csv.writer(f).writerow(encabezado)

        corriente_objetivo = self.estado['corr_inicial']
        tiempo_inicio = time.time()

        self.pulse_data = {
            'i_inst': float('nan'), 'v1_inst': float('nan'), 'r1_inst': float('nan'),
            'v2_inst': float('nan'), 'r2_inst': float('nan')
        }

        while self.corriendo:
            if self.pausado_sbias:
                self.fuente.standby()
                time.sleep(0.1)
                continue

            # Extraer parámetros actualizados en vivo
            nplc = float(self.estado['nplc'])
            usa_ch2_fron = self.estado.get('ch2_activado', False)
            no_output_off = self.estado.get('no_output_off', False)
            modo_delta = self.estado.get('modo_delta', False)
            usa_matriz = self.estado.get('usa_matriz', False)
            ch1_mat = self.estado.get('matriz_ch1', 212)
            ch2_mat = self.estado.get('matriz_ch2', 222)
            ch2_activo_total = usa_ch2_fron or usa_matriz

            self.voltimetro.configurar_rapido(nplc, self.estado['rango'])
            self.fuente.set_limite_voltaje(self.estado['limite_voltaje'])

            # ====================================================
            # FASE A: PULSO PRINCIPAL (Escritura -> NUNCA usa Delta)
            # ====================================================
            if not self.pausado_cbias:
                inicio_ciclo_a = time.time()

                offset_ramp = float(self.estado.get('offset_ramp', 0.0))
                i_pulso_target = corriente_objetivo + offset_ramp

                v1_inst, r1_inst, v2_inst, r2_inst, i_pulso_real = self._ejecutar_lectura_compleja(
                    i_pulso_target,
                    self.estado['ancho_pulso'],
                    nplc,
                    usa_ch2_fron,
                    no_output_off,
                    False,          # <-- FORZAR False AQUÍ: El pulso de escritura es simple
                    usa_matriz,
                    ch1_mat,
                    ch2_mat
                )

                t_min = (time.time() - tiempo_inicio) / 60.0
                self.datos_actualizados.emit(t_min, v1_inst, r1_inst, v2_inst, r2_inst, i_pulso_real, False)

                self.pulse_data = {
                    'i_inst': i_pulso_real, 'v1_inst': v1_inst, 'r1_inst': r1_inst,
                    'v2_inst': v2_inst, 'r2_inst': r2_inst
                }

                # Si NO hay mediciones de bias, guardar la fila del pulso directamente en el CSV
                if self.estado['num_mediciones_bias'] == 0:
                    fila = [
                        f"{t_min:.4f}", self.pulse_data['i_inst'], float('nan'),
                        self.pulse_data['v1_inst'], self.pulse_data['r1_inst'], float('nan'), float('nan'),
                        self.pulse_data['v2_inst'], self.pulse_data['r2_inst'], float('nan'), float('nan'),
                        self.estado['ancho_pulso'], self.estado['periodo_pulso'],
                        self.estado['limite_voltaje'], self.estado['rango'],
                        nplc, ch2_activo_total, 0, no_output_off, modo_delta, usa_matriz
                    ]
                    self._guardar_csv(fila, archivo_csv)

                # Espera del resto del período
                tiempo_consumido_a = time.time() - inicio_ciclo_a
                tiempo_off_deseado_a = max(0.05, self.estado['periodo_pulso'] - tiempo_consumido_a)
                self._esperar_con_interrupcion(tiempo_off_deseado_a)

            # ====================================================
            # FASE B: MEDICIONES BIAS
            # ====================================================
            num_bias = self.estado['num_mediciones_bias']
            if num_bias > 0:
                for _ in range(num_bias):
                    if not self.corriendo or self.pausado_sbias:
                        break

                    inicio_ciclo_b = time.time()
                    offset_ramp = float(self.estado.get('offset_ramp', 0.0))
                    i_bias_target = self.estado['corr_bias'] + offset_ramp

                    v1_bias, r1_bias, v2_bias, r2_bias, i_bias_real = self._ejecutar_lectura_compleja(
                        i_bias_target,
                        self.estado['ancho_pulso'],
                        nplc,
                        usa_ch2_fron,
                        no_output_off,
                        modo_delta,
                        usa_matriz,
                        ch1_mat,
                        ch2_mat
                    )

                    t_min = (time.time() - tiempo_inicio) / 60.0
                    self.datos_actualizados.emit(t_min, v1_bias, r1_bias, v2_bias, r2_bias, i_bias_real, True)

                    fila = [
                        f"{t_min:.4f}", self.pulse_data['i_inst'], i_bias_real,
                        self.pulse_data['v1_inst'], self.pulse_data['r1_inst'], r1_bias, v1_bias,
                        self.pulse_data['v2_inst'], self.pulse_data['r2_inst'], r2_bias, v2_bias,
                        self.estado['ancho_pulso'], self.estado['periodo_pulso'],
                        self.estado['limite_voltaje'], self.estado['rango'],
                        nplc, ch2_activo_total, num_bias, no_output_off, modo_delta, usa_matriz
                    ]
                    self._guardar_csv(fila, archivo_csv)

                    tiempo_consumido_b = time.time() - inicio_ciclo_b
                    tiempo_off_deseado_b = max(0.05, self.estado['periodo_pulso'] - tiempo_consumido_b)
                    self._esperar_con_interrupcion(tiempo_off_deseado_b)

            # ====================================================
            # FASE C: AVANCE DE LA RAMPA TRIANGULAR
            # ====================================================
            if not self.pausado_cbias:
                paso = self.estado['paso_corr']
                corriente_objetivo += paso

                if corriente_objetivo >= self.estado['corr_maxima'] and paso > 0:
                    corriente_objetivo = self.estado['corr_maxima']
                    self.estado['paso_corr'] = -paso
                    self.paso_invertido.emit(-paso)

                elif corriente_objetivo <= self.estado['corr_minima'] and paso < 0:
                    corriente_objetivo = self.estado['corr_minima']
                    self.estado['paso_corr'] = -paso
                    self.paso_invertido.emit(-paso)


# ==============================================================================
# HILO DE TEMPERATURA (LAKESHORE + MOTOR + K224 + 34420A)
# ==============================================================================
class HiloTemperatura(QThread):
    datos_temp = Signal(float, float, float, float, float)  # t_min, T_act, T_set, Pot, V_motor
    datos_res = Signal(float, float, float, float)          # T_act, R1, R2, t_min
    estado_msg = Signal(str)
    error_detectado = Signal(str)

    def __init__(self, estado_compartido):
        super().__init__()
        self.estado = estado_compartido
        self.corriendo = False

        self.lakeshore = LakeShoreDRC91CA()
        self.motor = AgilentE3643A()
        self.fuente_i = Keithley224()
        self.voltimetro = Agilent34420A()

    def iniciar_medicion(self):
        self.corriendo = True
        self.start()

    def detener_medicion(self):
        self.corriendo = False

    def _ajustar_motor(self, T_real, setpoint, v_actual, tol=1.5, paso=0.1):
        if self.estado.get('motor_manual', False):
            return float(self.estado.get('motor_v_manual', 2.6))

        mlo = self.estado.get('mlo', 1.2)
        mhi = self.estado.get('mhi', 4.8)
        htr = self.lakeshore.get_HTR()

        if T_real > setpoint + tol and v_actual > mlo and htr < 10.0:
            return v_actual - paso
        elif T_real < setpoint - tol and v_actual < mhi and htr > 70.0:
            return v_actual + paso
        elif setpoint - tol <= T_real <= setpoint + tol:
            return 2.6
        return v_actual

    def _ejecutar_n_stat_msr(self):
        """Ejecuta N lecturas usando el Método Delta (+I, -I) con Auto-Rango en Amperes."""
        num_mediciones = int(self.estado.get('N_stat', 3))
        i_bias = float(self.estado.get('i_bias', 0.001))
        limite_v = float(self.estado.get('vlim', 20.0))
        usa_ch2 = self.estado.get('ch2_activado', False)

        auto_rango = self.estado.get('auto_rango_i', False)
        v_max = float(self.estado.get('v_scale_max', 0.01))
        v_min = float(self.estado.get('v_scale_min', 0.001))

        delay_canal = 0.05
        self.fuente_i.set_limite_voltaje(limite_v)
        self.voltimetro.configurar_rapido(float(self.estado.get('nplc', 2)), self.estado.get('rango', '10 V'))

        resistencias_ch1 = []
        resistencias_ch2 = []
        mediciones_exitosas = 0

        while mediciones_exitosas < num_mediciones:
            if not self.corriendo:
                break

            # CICLO POSITIVO (+I)
            self.fuente_i.set_corriente(i_bias)
            self.voltimetro.seleccionar_canal(1)
            self.fuente_i.operar()
            time.sleep(0.1)

            v1_pos = self.voltimetro.leer_voltaje()

            if auto_rango:
                if abs(v1_pos) > v_max and abs(i_bias) > 1e-6:
                    i_bias /= 10.0
                    self.estado['i_bias'] = i_bias
                    self.fuente_i.standby()
                    time.sleep(0.05)
                    continue
                elif abs(v1_pos) < v_min and abs(i_bias) < 10.0:  # Techo de 10 mA
                    i_bias *= 10.0
                    self.estado['i_bias'] = i_bias
                    self.fuente_i.standby()
                    time.sleep(0.05)
                    continue

            v2_pos = float('nan')
            if usa_ch2:
                self.voltimetro.seleccionar_canal(2)
                time.sleep(delay_canal)
                v2_pos = self.voltimetro.leer_voltaje()

            self.fuente_i.standby()
            time.sleep(0.05)

            # CICLO NEGATIVO (-I)
            self.fuente_i.set_corriente(-i_bias)
            self.voltimetro.seleccionar_canal(1)
            self.fuente_i.operar()
            time.sleep(0.1)

            v1_neg = self.voltimetro.leer_voltaje()
            v2_neg = float('nan')
            if usa_ch2:
                self.voltimetro.seleccionar_canal(2)
                time.sleep(delay_canal)
                v2_neg = self.voltimetro.leer_voltaje()

            self.fuente_i.standby()
            time.sleep(0.05)

            # CÁLCULO DELTA EN OHMS (convirtiendo mA a A)
            delta_i_amps = (i_bias - (-i_bias)) * 1e-3
            if abs(delta_i_amps) > 0:
                r1 = (v1_pos - v1_neg) / delta_i_amps
                resistencias_ch1.append(r1)
                if usa_ch2:
                    r2 = (v2_pos - v2_neg) / delta_i_amps
                    resistencias_ch2.append(r2)

            mediciones_exitosas += 1

        r1_final = sum(resistencias_ch1) / len(resistencias_ch1) if resistencias_ch1 else float('nan')
        r2_final = sum(resistencias_ch2) / len(resistencias_ch2) if resistencias_ch2 else float('nan')

        return r1_final, r2_final

    def run(self):
        archivo_csv = self.estado.get('ruta_archivo', 'medicion_T.csv')

        try:
            rm = pyvisa.ResourceManager()
            self.lakeshore.conectar(rm)
            self.motor.conectar(rm)
            self.fuente_i.conectar(rm)
            self.voltimetro.conectar(rm)
        except Exception as e:
            self.error_detectado.emit(f"Error de conexión en Temperatura: {e}")
            self.corriendo = False
            return

        encabezado = [
            "Tiempo (min)", "T_real (K)", "T_setpoint (K)", "HTR (%)",
            "V_motor (V)", "I_bias (mA)", "R1_delta (Ohm)", "R2_delta (Ohm)"
        ]
        with open(archivo_csv, 'w', newline='') as f:
            csv.writer(f).writerow(encabezado)

        tiempo_inicio = time.time()
        tabla_pasos = self.estado.get('tabla_T', [])

        try:
            for paso in tabla_pasos:
                if not self.corriendo:
                    break

                target_setpoint = float(paso['setpoint'])
                rate = abs(float(paso['rate']))
                requiere_estabilidad = float(paso['estable']) > 0
                tiempo_estabilidad = float(self.estado.get('tiempo_estabilidad', 60.0))

                # ---------------------------------------------------------
                # FASE 1: RAMPA DE TEMPERATURA
                # ---------------------------------------------------------
                self.estado_msg.emit(f"Rampa hacia {target_setpoint} K")
                current_setpoint = self.lakeshore.read_temperature()

                direccion = 1 if target_setpoint > current_setpoint else -1
                paso_k = max(0.01, rate / 15.0)
                rampa = list(np.arange(current_setpoint, target_setpoint, direccion * paso_k))
                rampa.append(target_setpoint)

                v_motor = 2.6
                for setpoint_intermedio in rampa:
                    if not self.corriendo:
                        break

                    self.lakeshore.set_setpoint(round(setpoint_intermedio, 2))
                    self.motor.apply(v_motor)

                    tK = time.time()
                    while (time.time() - tK) < 3.0 and self.corriendo:
                        time.sleep(0.1)

                    T_real = self.lakeshore.read_temperature()
                    htr = self.lakeshore.get_HTR()
                    v_motor = self._ajustar_motor(T_real, setpoint_intermedio, v_motor, tol=1.5, paso=0.1)
                    t_min = (time.time() - tiempo_inicio) / 60.0

                    self.datos_temp.emit(t_min, T_real, setpoint_intermedio, htr, v_motor)

                # ---------------------------------------------------------
                # FASE 2: ESTABILIZACIÓN
                # ---------------------------------------------------------
                if requiere_estabilidad and self.corriendo:
                    self.estado_msg.emit(f"Esperando llegada a {target_setpoint} K")
                    v_motor = 2.6

                    while self.corriendo:
                        T_real = self.lakeshore.read_temperature()
                        if abs(T_real - target_setpoint) <= 0.5:
                            break

                        htr = self.lakeshore.get_HTR()
                        v_motor = self._ajustar_motor(T_real, target_setpoint, v_motor, tol=1.0, paso=0.05)
                        self.motor.apply(v_motor)

                        t_min = (time.time() - tiempo_inicio) / 60.0
                        self.datos_temp.emit(t_min, T_real, target_setpoint, htr, v_motor)
                        time.sleep(1.0)

                    self.estado_msg.emit(f"Estabilizando {tiempo_estabilidad} s en {target_setpoint} K")
                    t0_estabilidad = time.time()

                    while (time.time() - t0_estabilidad) < tiempo_estabilidad and self.corriendo:
                        T_real = self.lakeshore.read_temperature()
                        htr = self.lakeshore.get_HTR()
                        v_motor = self._ajustar_motor(T_real, target_setpoint, v_motor, tol=1.0, paso=0.1)
                        self.motor.apply(v_motor)

                        if abs(T_real - target_setpoint) > 1.0:
                            t0_estabilidad = time.time()

                        t_min = (time.time() - tiempo_inicio) / 60.0
                        self.datos_temp.emit(t_min, T_real, target_setpoint, htr, v_motor)
                        time.sleep(1.0)

                # ---------------------------------------------------------
                # FASE 3: MEDICIÓN DELTA (N_stat_msr)
                # ---------------------------------------------------------
                if self.corriendo and requiere_estabilidad:
                    self.estado_msg.emit(f"Midiendo resistencia Delta en {target_setpoint} K")
                    self.motor.apply(2.6)

                    r1, r2 = self._ejecutar_n_stat_msr()
                    T_med = self.lakeshore.read_temperature()
                    htr = self.lakeshore.get_HTR()
                    t_min = (time.time() - tiempo_inicio) / 60.0

                    self.datos_res.emit(T_med, r1, r2, t_min)

                    with open(archivo_csv, 'a', newline='') as f:
                        csv.writer(f).writerow([
                            f"{t_min:.4f}", f"{T_med:.3f}", f"{target_setpoint:.2f}",
                            f"{htr:.1f}", "2.6", self.estado.get('i_bias', 0.001), r1, r2
                        ])

            self.estado_msg.emit("Barrido de Temperatura Finalizado")

        except Exception as e:
            self.error_detectado.emit(f"Error durante rampa de temperatura: {e}")

        finally:
            self.fuente_i.standby()
            try:
                self.motor.apply(2.6)
            except Exception:
                pass
            self.corriendo = False


# ==============================================================================
# HILO DE ESPECTROSCOPÍA DE IMPEDANCIA (TH2832 + MATRIZ HP34970A)
# ==============================================================================
class HiloEspectroscopia(QThread):
    datos_is = Signal(float, float, float, float, float, float, float, float, float, float, float, int)
    estado_msg = Signal(str)
    error_detectado = Signal(str)

    def __init__(self, estado_compartido):
        super().__init__()
        self.estado = estado_compartido
        self.corriendo = False
        self.lcr = TonghuiTH2832(resource_name=self.estado.get('gpib_lcr', "GPIB0::11::INSTR"))
        self.matriz = SwitchMatrixHP34970A(resource_name=self.estado.get('gpib_matriz', "GPIB0::9::INSTR"))

    def iniciar_medicion(self):
        self.corriendo = True
        self.start()

    def detener_medicion(self):
        self.corriendo = False

    def run(self):
        archivo_csv = self.estado.get('ruta_archivo_is', 'espectroscopia.csv')
        usa_matriz = self.estado.get('usa_matriz', False)
        ch1_matriz = self.estado.get('matriz_ch1', 212)
        ch2_matriz = self.estado.get('matriz_ch2', 222)
        alc_habilitado = self.estado.get('alc_on', False)

        try:
            rm = pyvisa.ResourceManager()
            self.lcr.conectar(rm)
            if usa_matriz:
                self.matriz.conectar(rm)
                self.lcr.set_alc(False)
                self.matriz.open_channels(ch2_matriz)
                self.matriz.close_channels(ch1_matriz)
                time.sleep(0.5)
        except Exception as e:
            self.error_detectado.emit(f"Error conectando equipos IS: {e}")
            self.corriendo = False
            return

        self.lcr.set_alc(False if usa_matriz else alc_habilitado)
        self.lcr.set_vac(self.estado.get('vac', 0.1))
        self.lcr.set_speed_and_avg(self.estado.get('speed', "MED"), self.estado.get('avg', 1))
        self.lcr.set_rsou(self.estado.get('rsou', 100))
        self.lcr.set_range(self.estado.get('rango', "AUTO"))
        self.lcr.set_trigger_delay(self.estado.get('trig_delay', 0.0))

        lista_vdc = self.estado.get('lista_vdc', [0.0])
        frecuencias = self.estado.get('frecuencias', [])

        vac = self.estado.get('vac', 0.1)
        speed = self.estado.get('speed', "MED")
        avg = self.estado.get('avg', 1)
        rsou = self.estado.get('rsou', 100)
        rango = self.estado.get('rango', "AUTO")
        trig_delay = self.estado.get('trig_delay', 0.0)

        encabezado = [
            "Tiempo (min)", "Vdc (V)", "Freq (Hz)",
            "R_ch1 (Ohm)", "X_ch1 (Ohm)", "|Z|_ch1 (Ohm)", "Theta_ch1 (Deg)", "Vm_ch1 (V)", "Im_ch1 (A)",
            "R_ch2 (Ohm)", "X_ch2 (Ohm)", "|Z|_ch2 (Ohm)", "Theta_ch2 (Deg)", "Vm_ch2 (V)", "Im_ch2 (A)",
            "Status", "Vac (Vrms)", "ALC", "Speed", "Avg Pts", "Rsou (Ohm)", "Range", "Trig Delay (s)", "Matriz"
        ]
        with open(archivo_csv, 'w', newline='') as f:
            csv.writer(f).writerow(encabezado)

        tiempo_inicio = time.time()

        try:
            for vdc in lista_vdc:
                if not self.corriendo:
                    break

                self.estado_msg.emit(f"Estabilizando Vdc = {vdc} V")
                self.lcr.set_vdc(vdc)
                time.sleep(1.0)

                for freq in frecuencias:
                    if not self.corriendo:
                        break

                    # MEDICIÓN CANAL 1
                    if usa_matriz:
                        if alc_habilitado:
                            self.lcr.set_alc(False)
                            time.sleep(0.1)
                        self.matriz.open_channels(ch2_matriz)
                        self.matriz.close_channels(ch1_matriz)
                        time.sleep(0.2)
                        if alc_habilitado:
                            self.lcr.set_alc(True)
                            time.sleep(0.4)

                    self.lcr.set_frecuencia(freq)
                    delay_freq = 0.5 if freq < 100 else 0.15
                    time.sleep(delay_freq)

                    r1, x1, status1 = self.lcr.medir()
                    vm1, im1 = self.lcr.get_monitors()
                    z1 = math.sqrt(r1**2 + x1**2) if not math.isnan(r1) else float('nan')
                    theta1 = math.degrees(math.atan2(x1, r1)) if not math.isnan(r1) else float('nan')

                    # MEDICIÓN CANAL 2
                    r2, x2, status2 = float('nan'), float('nan'), status1
                    vm2, im2 = float('nan'), float('nan')
                    z2, theta2 = float('nan'), float('nan')

                    if usa_matriz and self.corriendo:
                        if alc_habilitado:
                            self.lcr.set_alc(False)
                            time.sleep(0.1)
                        self.matriz.open_channels(ch1_matriz)
                        self.matriz.close_channels(ch2_matriz)
                        time.sleep(0.2)
                        if alc_habilitado:
                            self.lcr.set_alc(True)
                            time.sleep(0.4)
                        time.sleep(0.15)

                        r2, x2, status2 = self.lcr.medir()
                        vm2, im2 = self.lcr.get_monitors()
                        z2 = math.sqrt(r2**2 + x2**2) if not math.isnan(r2) else float('nan')
                        theta2 = math.degrees(math.atan2(x2, r2)) if not math.isnan(r2) else float('nan')

                    t_min = (time.time() - tiempo_inicio) / 60.0
                    status_general = status1 if status1 != 0 else status2

                    self.datos_is.emit(vdc, freq, r1, x1, z1, theta1, r2, x2, z2, theta2, t_min, status_general)

                    with open(archivo_csv, 'a', newline='') as f:
                        csv.writer(f).writerow([
                            f"{t_min:.4f}", vdc, freq,
                            r1, x1, z1, theta1, vm1, im1,
                            r2, x2, z2, theta2, vm2, im2,
                            status_general, vac, alc_habilitado, speed, avg, rsou, rango, trig_delay, usa_matriz
                        ])

            self.estado_msg.emit("Espectroscopía Finalizada")

        finally:
            try:
                self.lcr.set_vdc(0.0)
                self.lcr.set_alc(False)
            except Exception:
                pass
            if usa_matriz and self.matriz.instrument:
                try:
                    self.matriz.open_channels([ch1_matriz, ch2_matriz])
                except Exception:
                    pass
            self.corriendo = False


class HiloCorreccionSpot(QThread):
    progreso = Signal(int, int, float)
    estado_msg = Signal(str)
    finalizado = Signal(str)
    error_detectado = Signal(str)

    def __init__(self, estado_compartido, tipo):
        super().__init__()
        self.estado = estado_compartido
        self.tipo = tipo
        self.lcr = TonghuiTH2832(resource_name=self.estado.get('gpib_lcr', "GPIB0::11::INSTR"))

    def run(self):
        frecuencias = self.estado.get('frecuencias_corr', [])
        if not frecuencias:
            self.error_detectado.emit("No hay frecuencias cargadas para corregir.")
            return

        try:
            rm = pyvisa.ResourceManager()
            self.lcr.conectar(rm)

            self.estado_msg.emit(f"Preparando equipo para corrección {self.tipo}...")
            comando_tipo = "OPEN" if self.tipo == "OPEN" else "SHORT"

            self.lcr.inst.write("DISP:PAGE CSET")
            time.sleep(0.5)
            self.lcr.inst.timeout = 60000

            self.lcr.inst.write("TRIG:SOUR INT")
            self.lcr.inst.write("FUNC:IMP:RANG:AUTO ON")
            self.lcr.inst.write("APER SLOW, 1")
            self.lcr.inst.write("VOLT 1V")
            self.lcr.inst.write("BIAS:STAT 0")
            self.lcr.inst.write("AMPL:ALC 0")
            time.sleep(1.0)

            for i, freq in enumerate(frecuencias):
                if not self.isRunning():
                    break

                spot_id = i + 1
                if spot_id > 201:
                    break

                self.progreso.emit(spot_id, len(frecuencias), freq)

                self.lcr.inst.write(f"FREQ {freq}HZ")
                time.sleep(0.1)
                self.lcr.inst.write(f"CORR:SPOT {spot_id}:FREQ {freq}HZ")
                self.lcr.inst.write(f"CORR:SPOT {spot_id}:STAT ON")
                self.lcr.inst.write(f"CORR:SPOT {spot_id}:{comando_tipo}")
                self.lcr.inst.query("*OPC?")

            if comando_tipo == "OPEN":
                self.lcr.inst.write("CORR:OPEN:STAT ON")
            else:
                self.lcr.inst.write("CORR:SHOR:STAT ON")

            self.finalizado.emit(f"Corrección {self.tipo} de {len(frecuencias)} puntos completada con éxito.")

        except Exception as e:
            self.error_detectado.emit(f"Error durante corrección {self.tipo}: {e}")
        finally:
            if self.lcr.inst:
                try:
                    self.lcr.inst.timeout = 5000
                    self.lcr.inst.write("DISP:PAGE MEAS")
                    self.lcr.inst.write("TRIG:SOUR BUS")
                except Exception:
                    pass


# ==============================================================================
# HILO DE PULSOS TRANSIENTES (AFG + OSCILOSCOPIO)
# ==============================================================================
class HiloPulsos(QThread):
    datos_pulso = Signal(float, float, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray)
    estado_msg = Signal(str)
    error_detectado = Signal(str)

    def __init__(self, estado_compartido):
        super().__init__()
        self.estado = estado_compartido
        self.corriendo = False
        self.afg = AgilentAFG(resource_name=self.estado.get('afg_addr', 'GPIB0::10::INSTR'))
        self.scope = TektronixScope(resource_name=self.estado.get('scope_addr', 'USB0::0x0699::0x0413::C012302::0::INSTR'))

    def iniciar_medicion(self):
        self.corriendo = True
        self.start()

    def detener_medicion(self):
        self.corriendo = False

    def run(self):
        try:
            rm = pyvisa.ResourceManager()
            self.afg.conectar(rm)
            self.scope.conectar(rm)
        except Exception as e:
            self.error_detectado.emit(f"Error conectando AFG/Scope: {e}")
            self.corriendo = False
            return

        frecuencias = self.estado.get('frecuencias_pulsos', [1000])
        amplitudes = self.estado.get('amplitudes_pulsos', [0.15])
        r_limit = self.estado.get('r_limit', 1000.0)
        max_voltage = self.estado.get('max_voltage_pulse', 0.4)
        num_cycles = self.estado.get('num_cycles', 1)
        wave_shape = self.estado.get('wave_shape', 'SQU')
        pulse_width = self.estado.get('pulse_width', 2000e-9)
        edge_time = self.estado.get('edge_time', 50e-9)
        pulse_zoom = self.estado.get('pulse_zoom_factor', 10.0)
        use_sync = self.estado.get('use_sync_cable', False)
        high_res = self.estado.get('high_res', True)
        base_dir = self.estado.get('ruta_archivo_pulsos', '')

        if self.scope.inst:
            self.scope.inst.write('ACQ:MOD HIR' if high_res else 'ACQ:MOD SAMP')

        self.afg.configure_burst(wave_shape, num_cycles)

        try:
            for freq in frecuencias:
                for raw_amp in amplitudes:
                    if not self.corriendo:
                        break

                    amp = max_voltage if raw_amp > max_voltage else raw_amp
                    self.estado_msg.emit(f"Sweeping: Freq = {freq} Hz, Amp = {amp} V")

                    self.afg.configure_burst(wave_shape, num_cycles)

                    if wave_shape in ['SQU', 'PULS']:
                        self.afg.set_pulse_params(freq, amp, pulse_width, edge_time)
                    else:
                        self.afg.set_bipolar_params(freq, amp)

                    self.afg.configure_burst(wave_shape, num_cycles)
                    self.afg.output_state(True)
                    self.scope.auto_scale(freq, amp, wave_shape, pulse_width, edge_time, num_cycles, pulse_zoom, use_sync)

                    # Primer disparo para calibrar escala vertical Y
                    self.scope.prepare_acquisition()
                    self.afg.trigger()
                    if self.scope.wait_for_trigger(max_wait=2.0):
                        self.scope.auto_scale_y()

                    # Adquisición definitiva
                    self.scope.prepare_acquisition()
                    self.afg.trigger()
                    success = self.scope.wait_for_trigger(max_wait=5.0)
                    self.afg.output_state(False)

                    if not success:
                        self.estado_msg.emit(f"⚠ Trigger Timeout en {freq}Hz, {amp}V.")
                        continue

                    v1, dt = self.scope.get_waveform(1)
                    v2, _ = self.scope.get_waveform(2)
                    v3, _ = self.scope.get_waveform(3)
                    v4, _ = self.scope.get_waveform(4)

                    min_len = min(len(v1), len(v2), len(v3), len(v4))
                    v1, v2, v3, v4 = v1[:min_len], v2[:min_len], v3[:min_len], v4[:min_len]

                    time_axis = np.arange(len(v1)) * dt

                    r_scope = 1e6
                    i_total = (v1 - v2) / r_limit
                    i_leak2 = v2 / r_scope
                    i_leak3 = v3 / r_scope
                    current = i_total - i_leak2 - i_leak3

                    v_dut = v3 - v4

                    window_len = min(101, len(time_axis))
                    if window_len % 2 == 0:
                        window_len -= 1
                    v_dut_filt = savgol_filter(v_dut, window_len, 3)
                    current_filt = savgol_filter(current, window_len, 3)

                    self.datos_pulso.emit(freq, amp, time_axis, v1, v2, v3, v4, v_dut_filt, current_filt)

                    if base_dir:
                        filename = os.path.join(base_dir, f"{freq}Hz_{amp}V.csv")
                        metadata = (
                            f"# --- BURST CONFIG LOG ---\n"
                            f"# Shape: {wave_shape}\n"
                            f"# Freq: {freq}\n"
                            f"# Amp: {amp}\n"
                            f"# R_lim: {r_limit}\n"
                            f"# Filter: Savitzky-Golay\n"
                            f"# -------------------\n"
                        )
                        df = pd.DataFrame({
                            'Time_s': time_axis, 'CH1_V_Supply': v1, 'CH2_V_Resistor': v2,
                            'CH3_V_SenseP': v3, 'CH4_V_SenseN': v4, 'I_Sample_Raw': current,
                            'V_Sample_Raw': v_dut, 'I_Sample_Filt': current_filt, 'V_Sample_Filt': v_dut_filt
                        })
                        with open(filename, 'w') as f:
                            f.write(metadata)
                        df.to_csv(filename, mode='a', index=False)

            self.estado_msg.emit("Barrido de Transientes Finalizado")

        finally:
            if self.afg.inst:
                try:
                    self.afg.output_state(False)
                    self.afg.inst.close()
                except Exception:
                    pass

            if self.scope.inst:
                try:
                    self.scope.inst.close()
                except Exception:
                    pass

            self.corriendo = False