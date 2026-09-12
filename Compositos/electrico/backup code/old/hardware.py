import time
import csv
import math
import pyvisa
from PySide6.QtCore import QThread, Signal
import numpy as np

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
        self.inst.write("TRIG:SOUR BUS") # Bloquear trigger interno
        self.inst.write("FUNC:IMP RX")   # Siempre pedir Resistencia y Reactancia
        
        try:
            self.inst.write("FUNC:SMON:VIAC ON")
        except:
            pass # Si falla por error de sintaxis del firmware, lo ignoramos

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
        self.inst.write("*TRG") # Disparar medición
        
        # POLLING: Esperar a que el equipo termine de medir (Status != -1)
        for _ in range(40): # Espera máxima de ~2 segundos
            time.sleep(0.05)
            try:
                respuesta = self.inst.query("FETC?")
                partes = respuesta.split(',')
                status = int(partes[2])
                if status != -1:
                    r = float(partes[0])
                    x = float(partes[1])
                    return r, x, status
            except:
                pass
        return float('nan'), float('nan'), -1

    def get_monitors(self):
        # Queries extraídas de la página 86 del manual
        try:
            vm = float(self.inst.query("FETC:SMON:VAC?"))
            im = float(self.inst.query("FETC:SMON:IAC?"))
            # Filtro para ignorar el valor 9.9e37 (Error/Out of bounds)
            if abs(vm) > 1e30: vm = float('nan')
            if abs(im) > 1e30: im = float('nan')
            return vm, im
        except:
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
        if isinstance(channel_list, (list, tuple)):
            channel_str = ','.join(str(ch) for ch in channel_list)
        else:
            channel_str = str(channel_list)
        self.instrument.write(f'ROUTe:OPEN (@{channel_str})')

    def close_channels(self, channel_list):
        if isinstance(channel_list, (list, tuple)):
            channel_str = ','.join(str(ch) for ch in channel_list)
        else:
            channel_str = str(channel_list)
        self.instrument.write(f'ROUTe:CLOSe (@{channel_str})')

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
        cmd = "WS"
        response = self.inst.query(cmd)
        return float(response.split('\r')[0].split('K')[0])
            
    def set_setpoint(self, setpoint):
        cmd = f"S{float(setpoint)}"
        self.inst.write(cmd)
    
    def get_setpoint(self):
        response = self.inst.query("WP")
        return float(response.split('\r')[0].split('K')[0])
    
    def get_HTR(self):
        cmd = "W3"
        response = self.inst.query(cmd)
        return float(response.split('\r')[0].split(',')[-1])

    def set_pid(self, p, i, d):
        """Envía los parámetros Proporcional, Integral y Derivativo."""
        self.inst.write(f"P{float(p)}")
        self.inst.write(f"I{float(i)}")
        self.inst.write(f"D{float(d)}")

    def get_pid(self):
        """Recupera los parámetros PID actuales (requiere parseo según manual del 91CA)."""
        try:
            p = float(self.inst.query("P?").strip())
            i = float(self.inst.query("I?").strip())
            d = float(self.inst.query("D?").strip())
            return p, i, d
        except:
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

class Keithley224:
    def __init__(self, direccion="GPIB0::02::INSTR"):
        self.direccion = direccion
        self.inst = None
        self.ultimo_limite_v = None 

    def conectar(self, rm):
        self.inst = rm.open_resource(self.direccion)
        self.inst.write_termination = '\r\n'
        self.inst.read_termination = '\r\n'
        self.inst.write("R0X") 
        self.ultimo_limite_v = None 
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
        if self.inst:
            self.inst.write("F1X") 

    def standby(self):
        try:
            if self.inst:
                self.inst.write("F0X") 
        except:
            pass


class Agilent34420A:
    def __init__(self, direccion="GPIB0::07::INSTR"):
        self.direccion = direccion
        self.inst = None
        self.ultimo_nplc = None
        self.ultimo_rango = None
        self.ultimo_canal = None  # <-- NUEVO CACHÉ

    def conectar(self, rm):
        self.inst = rm.open_resource(self.direccion)
        self.inst.timeout = 5000 
        self.inst.write("*CLS") 
        
        self.ultimo_nplc = None
        self.ultimo_rango = None
        self.ultimo_canal = None  # <-- NUEVO CACHÉ
        print(f"34420A Conectado: {self.direccion}")

    def seleccionar_canal(self, canal):
        # SOLO enviamos el comando si el canal realmente cambia
        if self.inst and canal != self.ultimo_canal:
            self.inst.write(f"ROUT:TERM FRON{canal}")
            self.ultimo_canal = canal

    def configurar_rapido(self, nplc, rango_str): 
        if not self.inst: return
        
        # 1. Actualizar NPLC (Global, no requiere ruteo)
        if nplc != self.ultimo_nplc:
            self.inst.write(f"VOLT:DC:NPLC {nplc}")
            self.ultimo_nplc = nplc

        # 2. Actualizar Rango (Específico por canal)
        if rango_str != self.ultimo_rango:
            diccionario_rangos = {
                "Auto": "AUTO ON", "1 mV": "0.001", "10 mV": "0.01",
                "100 mV": "0.1", "1 V": "1.0", "10 V": "10.0", "100 V": "100.0"
            }
            rango_val = diccionario_rangos.get(rango_str, "AUTO ON")

            for c in [1, 2]:
                self.inst.write(f"ROUT:TERM FRON{c}")
                if rango_val == "AUTO ON":
                    self.inst.write("VOLT:DC:RANG:AUTO ON")
                else:
                    # Protección de Hardware: CH2 no soporta el rango de 100V
                    if c == 2 and float(rango_val) > 10.0:
                        self.inst.write("VOLT:DC:RANG 10.0")
                    else:
                        self.inst.write(f"VOLT:DC:RANG {rango_val}")
                        
            self.ultimo_rango = rango_str
            
            # 3. Restaurar el canal activo para no desorientar al script principal
            canal_actual = self.ultimo_canal if self.ultimo_canal else 1
            self.inst.write(f"ROUT:TERM FRON{canal_actual}")

    def leer_voltaje(self):
        if not self.inst: return float('nan')
        try:
            val = float(self.inst.query("READ?"))
            if abs(val) > 1e9:
                return float('nan')
            return val
        except:
            return float('nan')

class HiloMedicionDual(QThread):
    datos_actualizados = Signal(float, float, float, float, float, float, bool)
    paso_invertido = Signal(float)
    error_detectado = Signal(str) 
    nueva_secuencia = Signal(float, float, str) # <-- NUEVO (bias, pulso, archivo)

    def __init__(self, estado_compartido):
        super().__init__()
        self.estado = estado_compartido
        self.corriendo = False
        self.pausado_cbias = False
        self.pausado_sbias = False
        
        self.fuente = Keithley224()
        self.voltimetro = Agilent34420A()

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

    def run(self):
        archivo_csv = self.estado.get('ruta_archivo', 'medicion_default.csv')

        try:
            import pyvisa
            rm = pyvisa.ResourceManager()
        except ImportError:
            self.error_detectado.emit("Librería PyVISA no instalada (hacer 'pip install pyvisa').")
            self.corriendo = False
            return
        except Exception as e:
            self.error_detectado.emit(f"Error de backend VISA: No se detecta driver (NI-VISA/Keysight). Detalle: {e}")
            self.corriendo = False
            return

        try:
            self.fuente.conectar(rm)
            self.voltimetro.conectar(rm)
            
            # Bifurcación de lógica según la pestaña seleccionada
            if self.estado.get('modo_relajacion', False):
                self._loop_relajacion(archivo_csv)
            else:
                self._loop_triangular(archivo_csv)

        except Exception as e:
            print(f"Error Crítico durante la medición: {e}")
            self.error_detectado.emit(str(e))
            
        finally:
            self.fuente.standby()
            self.corriendo = False
            print("Hilo finalizado. Fuente en Standby.")

    # ==============================================================================
    # LÓGICA 1: MATRIZ DE RELAJACIÓN (AUTOMATIZADA)
    # ==============================================================================
    def _loop_relajacion(self, archivo_csv_base):
        import os
        base_dir = os.path.dirname(archivo_csv_base)
        base_name = os.path.splitext(os.path.basename(archivo_csv_base))[0]
        
        nplc = float(self.estado['nplc'])
        usa_ch2 = self.estado['ch2_activado']
        self.voltimetro.configurar_rapido(nplc, self.estado['rango'])
        delay_cambio_canal = 0.05
        
        lista_bias = self.estado['lista_bias']
        lista_pulsos = self.estado['lista_pulsos']
        T_descarga = self.estado['tiempo_descarga']

        # Extraer parámetros de temporización de los pulsos de lectura
        ancho_lectura = self.estado.get('ancho_lectura', 0.5)
        periodo = self.estado.get('periodo_relajacion', 1.0)
        es_pulsado = self.estado.get('relajacion_pulsada', False)

        # MOTOR DE SECUENCIA (Bucle Externo: Bias, Bucle Interno: Pulso)
        for c_bias in lista_bias:
            for c_pulso in lista_pulsos:
                if not self.corriendo: return

                # Limpieza de valores nulos para el hardware
                corr_pulso = c_pulso if abs(c_pulso) >= 1e-5 else (1e-5 if c_pulso >= 0 else -1e-5)
                corr_bias = c_bias if abs(c_bias) >= 1e-5 else (1e-5 if c_bias >= 0 else -1e-5)

                # Generar nombre de archivo único para esta combinación
                b_str = str(c_bias).replace('.', 'p')
                p_str = str(c_pulso).replace('.', 'p')
                archivo_actual = os.path.join(base_dir, f"{base_name}_bias_{b_str}mA_pulso_{p_str}mA.csv")
                
                # Avisar a la interfaz para limpiar los gráficos
                self.nueva_secuencia.emit(c_bias, c_pulso, archivo_actual)

                # Inicializar el archivo CSV (Header actualizado)
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
                    
                    # Fila actualizada con Ancho y Periodo
                    fila = [
                        f"{t_min:.4f}", self.pulse_data['i_inst'], float('nan'),
                        self.pulse_data['v1_inst'], self.pulse_data['r1_inst'], float('nan'), float('nan'),
                        self.pulse_data['v2_inst'], self.pulse_data['r2_inst'], float('nan'), float('nan'),
                        self.estado['tiempo_pulso'], ancho_lectura, periodo,
                        self.estado['limite_voltaje'], self.estado['rango'], nplc, usa_ch2
                    ]
                    self._guardar_csv(fila, archivo_actual)
                    time.sleep(0.01) 
                    
                if not self.corriendo: return

                # ------------------------------------------------
                # FASE 2: DESCARGA/RELAJACIÓN (LIMITADA POR T_DESCARGA)
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
                        
                        margen_lectura = 0.1
                        if usa_ch2: margen_lectura += delay_cambio_canal
                        
                        t_espera_on = ancho_lectura - margen_lectura
                        if t_espera_on > 0:
                            while (time.time() - inicio_ciclo) < t_espera_on and self.corriendo:
                                time.sleep(0.01)
                                
                    self.voltimetro.seleccionar_canal(1)
                    if usa_ch2 and not es_pulsado: time.sleep(delay_cambio_canal) 
                    
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
                    
                    # Fila actualizada con Ancho y Periodo
                    fila = [
                        f"{t_min:.4f}", self.pulse_data['i_inst'], corr_bias,
                        self.pulse_data['v1_inst'], self.pulse_data['r1_inst'], r1_bias, v1_bias,
                        self.pulse_data['v2_inst'], self.pulse_data['r2_inst'], r2_bias, v2_bias,
                        self.estado['tiempo_pulso'], ancho_lectura, periodo, 
                        self.estado['limite_voltaje'], self.estado['rango'], nplc, usa_ch2
                    ]
                    # ... (código previo de la fila del CSV) ...
                    self._guardar_csv(fila, archivo_actual)
                    
                    if es_pulsado:
                        # TIEMPO OFF DINÁMICO
                        # Calculamos exactamente cuánto tiempo ha consumido el ciclo real (incluyendo el lag del multímetro)
                        tiempo_consumido = time.time() - inicio_ciclo
                        tiempo_off_deseado = periodo - tiempo_consumido
                        
                        # Si el hardware tardó más que el período asignado, forzamos un mínimo para proteger el bus
                        if tiempo_off_deseado <= 0: 
                            tiempo_off_deseado = 0.05 
                        
                        tiempo_inicio_off = time.time()
                        while (time.time() - tiempo_inicio_off) < tiempo_off_deseado and self.corriendo:
                            time.sleep(0.01)
                    else:
                        time.sleep(0.05)


    # ==============================================================================
    # LÓGICA 2: BARRIDO TRIANGULAR (SINCRONIZACIÓN ESTRICTA DE TIEMPO)
    # ==============================================================================
    def _loop_triangular(self, archivo_csv):
        encabezado = [
            "Tiempo (min)", "I pulso (mA)", "I bias (mA)", 
            "Vinst 1 (V)", "Rinst 1 (Ohm)", "Rrem 1 (Ohm)", "Vbias 1 (V)", 
            "Vinst 2 (V)", "Rinst 2 (Ohm)", "Rrem 2 (Ohm)", "Vbias 2 (V)", 
            "Ancho pulso (s)", "Periodo (s)", "Vcc (V)", "Vrange", "NPLC", 
            "Ch2?", "N bias"
        ]
        with open(archivo_csv, 'w', newline='') as f:
            csv.writer(f).writerow(encabezado)

        corriente_objetivo = self.estado['corr_inicial']
        tiempo_inicio = time.time()

        while self.corriendo:
            if self.pausado_sbias:
                self.fuente.standby()
                time.sleep(0.1)
                continue

            # --- CONFIGURACIÓN ---
            nplc = float(self.estado['nplc'])
            usa_ch2 = self.estado['ch2_activado']
            self.voltimetro.configurar_rapido(nplc, self.estado['rango'])

            delay_cambio_canal = 0.05 
            margen_lectura = 0.1
            if usa_ch2: margen_lectura += delay_cambio_canal

            # ====================================================
            # FASE A: PULSO PRINCIPAL
            # ====================================================
            if not self.pausado_cbias:
                inicio_ciclo_a = time.time()
                
                if abs(corriente_objetivo) < 1e-5:
                    corriente_objetivo = 1e-5 if corriente_objetivo >= 0 else -1e-5

                self.fuente.set_limite_voltaje(self.estado['limite_voltaje'])
                self.fuente.set_corriente(corriente_objetivo)
                
                self.voltimetro.seleccionar_canal(1)
                self.fuente.operar()
                
                # 1. Espera Dinámica del Pulso ON
                t_espera_on = self.estado['ancho_pulso'] - margen_lectura
                if t_espera_on > 0:
                    while (time.time() - inicio_ciclo_a) < t_espera_on and self.corriendo:
                        time.sleep(0.01)
                
                v1_inst = self.voltimetro.leer_voltaje()
                v2_inst = float('nan')
                
                if usa_ch2:
                    self.voltimetro.seleccionar_canal(2)
                    time.sleep(delay_cambio_canal)
                    v2_inst = self.voltimetro.leer_voltaje()
                
                # APAGADO INMEDIATO
                self.fuente.standby()
                
                r1_inst = float('nan') if abs(corriente_objetivo) < 1e-5 else (v1_inst / (corriente_objetivo * 1e-3))
                r2_inst = float('nan') if (abs(corriente_objetivo) < 1e-5 or not usa_ch2) else (v2_inst / (corriente_objetivo * 1e-3))
                
                t_min = (time.time() - tiempo_inicio) / 60.0
                self.datos_actualizados.emit(t_min, v1_inst, r1_inst, v2_inst, r2_inst, corriente_objetivo, False)
                
                self.pulse_data = {
                'i_inst': corriente_objetivo, 'v1_inst': v1_inst, 'r1_inst': r1_inst,
                'v2_inst': v2_inst, 'r2_inst': r2_inst
                }
                
                # 2. Espera Dinámica del Pulso OFF (Periodo)
                tiempo_consumido_a = time.time() - inicio_ciclo_a
                tiempo_off_deseado_a = self.estado['periodo_pulso'] - tiempo_consumido_a
                if tiempo_off_deseado_a <= 0: tiempo_off_deseado_a = 0.05
                
                t_inicio_off = time.time()
                while (time.time() - t_inicio_off) < tiempo_off_deseado_a and self.corriendo:
                    time.sleep(0.01)

            # ====================================================
            # FASE B: PULSOS BIAS
            # ====================================================
            num_bias = self.estado['num_mediciones_bias']
            if num_bias > 0:
                for _ in range(num_bias):
                    if not self.corriendo or self.pausado_sbias: break
                    
                    inicio_ciclo_b = time.time()
                    
                    corr_bias_actual = self.estado['corr_bias']
                    if abs(corr_bias_actual) < 1e-5:
                        corr_bias_actual = 1e-5 if corr_bias_actual >= 0 else -1e-5

                    self.fuente.set_corriente(corr_bias_actual)
                    self.voltimetro.seleccionar_canal(1)
                    self.fuente.operar()
                    
                    # 1. Espera Dinámica del Pulso ON (usamos ancho_pulso también aquí)
                    t_espera_on = self.estado['ancho_pulso'] - margen_lectura
                    if t_espera_on > 0:
                        while (time.time() - inicio_ciclo_b) < t_espera_on and self.corriendo:
                            time.sleep(0.01)
                    
                    v1_bias = self.voltimetro.leer_voltaje()
                    v2_bias = float('nan')
                    
                    if usa_ch2:
                        self.voltimetro.seleccionar_canal(2)
                        time.sleep(delay_cambio_canal)
                        v2_bias = self.voltimetro.leer_voltaje()
                        
                    # APAGADO INMEDIATO
                    self.fuente.standby()
                    
                    r1_bias = float('nan') if abs(corr_bias_actual) < 1e-5 else (v1_bias / (corr_bias_actual * 1e-3))
                    r2_bias = float('nan') if (abs(corr_bias_actual) < 1e-5 or not usa_ch2) else (v2_bias / (corr_bias_actual * 1e-3))
                    
                    t_min = (time.time() - tiempo_inicio) / 60.0
                    self.datos_actualizados.emit(t_min, v1_bias, r1_bias, v2_bias, r2_bias, corr_bias_actual, True)
                    
                    fila = [
                        f"{t_min:.4f}", self.pulse_data['i_inst'], corr_bias_actual,
                        self.pulse_data['v1_inst'], self.pulse_data['r1_inst'], r1_bias, v1_bias,
                        self.pulse_data['v2_inst'], self.pulse_data['r2_inst'], r2_bias, v2_bias,
                        self.estado['ancho_pulso'], self.estado['periodo_pulso'], 
                        self.estado['limite_voltaje'], self.estado['rango'], 
                        nplc, usa_ch2, self.estado['num_mediciones_bias']
                    ]
                    self._guardar_csv(fila, archivo_csv)
                    
                    # 2. Espera Dinámica del Pulso OFF (Periodo)
                    tiempo_consumido_b = time.time() - inicio_ciclo_b
                    tiempo_off_deseado_b = self.estado['periodo_pulso'] - tiempo_consumido_b
                    if tiempo_off_deseado_b <= 0: tiempo_off_deseado_b = 0.05
                    
                    t_inicio_off = time.time()
                    while (time.time() - t_inicio_off) < tiempo_off_deseado_b and self.corriendo:
                        time.sleep(0.01)
            
            # ====================================================
            # FASE C: LÓGICA TRIANGULAR
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

class HiloTemperatura(QThread):
    # Señales para actualizar la UI sin congelarla
    datos_temp = Signal(float, float, float, float, float) # t_min, T_act, T_set, Pot, V_motor
    datos_res = Signal(float, float, float, float)         # T_act, R1, R2, t_min
    estado_msg = Signal(str)                               # Mensajes como "Rampa de temperatura"
    error_detectado = Signal(str)

    def __init__(self, estado_compartido):
        super().__init__()
        self.estado = estado_compartido
        self.corriendo = False
        
        # Instanciar todos los equipos
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
        """Encapsula la lógica termodinámica con opción de Override Manual."""
        # 1. OVERRIDE MANUAL: Ignora la termodinámica
        if self.estado.get('motor_manual', False):
            return float(self.estado.get('motor_v_manual', 2.6))
            
        # 2. LÓGICA AUTOMÁTICA
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
        """Ejecuta N lecturas usando el Método Delta (+I, -I) con Auto-Rango inteligente."""
        num_mediciones = int(self.estado.get('N_stat', 3))
        i_bias = float(self.estado.get('i_bias', 0.001))
        limite_v = float(self.estado.get('vlim', 20.0))
        usa_ch2 = self.estado.get('ch2_activado', False)
        
        # Parámetros de Auto-rango
        auto_rango = self.estado.get('auto_rango_i', False)
        v_max = float(self.estado.get('v_scale_max', 0.01))
        v_min = float(self.estado.get('v_scale_min', 0.001))
        
        delay_canal = 0.05
        self.fuente_i.set_limite_voltaje(limite_v)
        
        resistencias_ch1 = []
        resistencias_ch2 = []
        
        mediciones_exitosas = 0
        
        # Usamos un while para poder repetir el ciclo si el auto-rango interviene
        while mediciones_exitosas < num_mediciones:
            if not self.corriendo: break
            
            # ==========================================
            # CICLO POSITIVO
            # ==========================================
            self.fuente_i.set_corriente(i_bias)
            self.voltimetro.seleccionar_canal(1)
            self.fuente_i.operar()
            time.sleep(0.1) 
            
            v1_pos = self.voltimetro.leer_voltaje()
            
            # --- LÓGICA DE AUTO-RANGO ---
            if auto_rango:
                if abs(v1_pos) > v_max and abs(i_bias) > 1e-9:
                    i_bias /= 10.0
                    self.estado['i_bias'] = i_bias # Actualizar estado para la UI
                    self.fuente_i.standby()
                    time.sleep(0.05)
                    continue # Abortar ciclo asimétrico y reiniciar
                    
                elif abs(v1_pos) < v_min and abs(i_bias) < 10e-3: # Techo de 10 mA
                    i_bias *= 10.0
                    self.estado['i_bias'] = i_bias
                    self.fuente_i.standby()
                    time.sleep(0.05)
                    continue # Abortar ciclo asimétrico y reiniciar

            v2_pos = float('nan')
            if usa_ch2:
                self.voltimetro.seleccionar_canal(2)
                time.sleep(delay_canal)
                v2_pos = self.voltimetro.leer_voltaje()
                
            self.fuente_i.standby()
            time.sleep(0.05)
            
            # ==========================================
            # CICLO NEGATIVO
            # ==========================================
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
            
            # ==========================================
            # CÁLCULO DELTA
            # ==========================================
            delta_i = (i_bias) - (-i_bias)
            
            r1 = (v1_pos - v1_neg) / delta_i
            resistencias_ch1.append(r1)
            
            if usa_ch2:
                r2 = (v2_pos - v2_neg) / delta_i
                resistencias_ch2.append(r2)
                
            mediciones_exitosas += 1
                
        # Retornar promedios
        r1_final = sum(resistencias_ch1) / len(resistencias_ch1) if resistencias_ch1 else float('nan')
        r2_final = sum(resistencias_ch2) / len(resistencias_ch2) if resistencias_ch2 else float('nan')
        
        return r1_final, r2_final
    
    def run(self):
        archivo_csv = self.estado.get('ruta_archivo', 'medicion_T.csv')
        
        try:
            import pyvisa
            rm = pyvisa.ResourceManager()
            self.lakeshore.conectar(rm)
            self.motor.conectar(rm)
            self.fuente_i.conectar(rm)
            self.voltimetro.conectar(rm)
        except Exception as e:
            self.error_detectado.emit(f"Error de conexión: {e}")
            self.corriendo = False
            return

        tiempo_inicio = time.time()
        tabla_pasos = self.estado.get('tabla_T', []) # Lista de diccionarios: [{'setpoint': 295, 'rate': 2, 'estable': 1}, ...]

        for paso in tabla_pasos:
            if not self.corriendo: break
            
            target_setpoint = float(paso['setpoint'])
            rate = abs(float(paso['rate']))
            requiere_estabilidad = float(paso['estable']) > 0
            tiempo_estabilidad = float(self.estado.get('tiempo_estabilidad', 60.0))
            
            # ---------------------------------------------------------
            # FASE 1: RAMPA (Dividida en sub-pasos para no bloquear)
            # ---------------------------------------------------------
            self.estado_msg.emit(f"Rampa hacia {target_setpoint} K")
            current_setpoint = self.lakeshore.read_temperature()
            
            direccion = 1 if target_setpoint > current_setpoint else -1
            paso_k = rate / 15.0 # Mismo delta temporal que el script original
            rampa = list(np.arange(current_setpoint, target_setpoint, direccion * paso_k))
            rampa.append(target_setpoint)
            
            v_motor = 2.6
            for setpoint_intermedio in rampa:
                if not self.corriendo: break
                
                self.lakeshore.set_setpoint(round(setpoint_intermedio, 2))
                self.motor.apply(v_motor)
                
                # Bucle de espera de 3 segundos (60/20) dividido en ticks de 100ms
                tK = time.time()
                while (time.time() - tK) < 3.0 and self.corriendo:
                    time.sleep(0.1)
                
                # Actualizar parámetros y enviar a UI
                T_real = self.lakeshore.read_temperature()
                v_motor = self._ajustar_motor(T_real, setpoint_intermedio, v_motor, tol=1.5, paso=0.1)
                t_min = (time.time() - tiempo_inicio) / 60.0
                
                self.datos_temp.emit(t_min, T_real, setpoint_intermedio, self.lakeshore.get_HTR(), v_motor)

            # ---------------------------------------------------------
            # FASE 2: ESTABILIZACIÓN
            # ---------------------------------------------------------
            if requiere_estabilidad and self.corriendo:
                self.estado_msg.emit(f"Esperando llegada a {target_setpoint} K")
                v_motor = 2.6
                
                # Acercamiento grueso (Tol: 0.5K)
                while True:
                    if not self.corriendo: break
                    T_real = self.lakeshore.read_temperature()
                    if abs(T_real - target_setpoint) <= 0.5: break
                    
                    v_motor = self._ajustar_motor(T_real, target_setpoint, v_motor, tol=1.0, paso=0.05)
                    self.motor.apply(v_motor)
                    
                    t_min = (time.time() - tiempo_inicio) / 60.0
                    self.datos_temp.emit(t_min, T_real, target_setpoint, self.lakeshore.get_HTR(), v_motor)
                    time.sleep(1.0)
                
                # Temporizador de estabilidad fina
                self.estado_msg.emit(f"Estabilizando {tiempo_estabilidad} s")
                t0_estabilidad = time.time()
                
                while (time.time() - t0_estabilidad) < tiempo_estabilidad and self.corriendo:
                    T_real = self.lakeshore.read_temperature()
                    v_motor = self._ajustar_motor(T_real, target_setpoint, v_motor, tol=1.0, paso=0.1)
                    self.motor.apply(v_motor)
                    
                    # Si se sale del rango de 1K, reinicia el contador
                    if abs(T_real - target_setpoint) > 1.0:
                        t0_estabilidad = time.time()
                        
                    t_min = (time.time() - tiempo_inicio) / 60.0
                    self.datos_temp.emit(t_min, T_real, target_setpoint, self.lakeshore.get_HTR(), v_motor)
                    time.sleep(1.0)

            # ---------------------------------------------------------
            # FASE 3: MEDICIÓN (N_stat_msr)
            # ---------------------------------------------------------
            if self.corriendo and requiere_estabilidad:
                self.estado_msg.emit(f"Midiendo en {target_setpoint} K")
                self.motor.apply(2.6) # Reset seguro durante la medición
                
                # AQUÍ SE LLAMARÁ A LA LÓGICA DE MEDICIÓN (I+, I-)
                r1, r2 = self._ejecutar_n_stat_msr()
                
                # Simulación temporal para evitar errores hasta que portemos N_stat_msr
                r1, r2 = 100.0, 100.0 
                t_min = (time.time() - tiempo_inicio) / 60.0
                
                self.datos_res.emit(self.lakeshore.read_temperature(), r1, r2, t_min)

        self.estado_msg.emit("Barrido de Temperatura Finalizado")
        self.motor.apply(2.6)
        self.corriendo = False

# ==============================================================================
# HILO DE ESPECTROSCOPÍA DE IMPEDANCIA (ACTUALIZADO PARA MATRIZ Y ALC)
# ==============================================================================
class HiloEspectroscopia(QThread):
    # Emite: Vdc, Freq, R1, X1, Z1, Theta1, R2, X2, Z2, Theta2, t_min, Status
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
            import pyvisa
            rm = pyvisa.ResourceManager()
            self.lcr.conectar(rm)
            if usa_matriz:
                self.matriz.conectar(rm)
                
                # SEGURIDAD INICIAL: Desactivar ALC antes de cualquier ruteo
                self.lcr.set_alc(False)
                self.matriz.open_channels(ch2_matriz)
                self.matriz.close_channels(ch1_matriz)
                time.sleep(0.5) 
        except Exception as e:
            self.error_detectado.emit(f"Error conectando equipos IS: {e}")
            self.corriendo = False
            return

        # Aplicar settings base (dejando el ALC apagado temporalmente si se usa matriz)
        self.lcr.set_alc(False if usa_matriz else alc_habilitado)
        self.lcr.set_vac(self.estado.get('vac', 0.1))
        self.lcr.set_speed_and_avg(self.estado.get('speed', "MED"), self.estado.get('avg', 1))
        self.lcr.set_rsou(self.estado.get('rsou', 100))
        self.lcr.set_range(self.estado.get('rango', "AUTO"))
        self.lcr.set_trigger_delay(self.estado.get('trig_delay', 0.0))
        
        lista_vdc = self.estado.get('lista_vdc', [0.0])
        frecuencias = self.estado.get('frecuencias', [])
        
        encabezado = [
            "Tiempo (min)", "Vdc (V)", "Freq (Hz)", 
            "R_ch1 (Ohm)", "X_ch1 (Ohm)", "|Z|_ch1 (Ohm)", "Theta_ch1 (Deg)", "Vm_ch1 (V)", "Im_ch1 (A)",
            "R_ch2 (Ohm)", "X_ch2 (Ohm)", "|Z|_ch2 (Ohm)", "Theta_ch2 (Deg)", "Vm_ch2 (V)", "Im_ch2 (A)",
            "Status"
        ]
        with open(archivo_csv, 'w', newline='') as f:
            csv.writer(f).writerow(encabezado)

        tiempo_inicio = time.time()

        for vdc in lista_vdc:
            if not self.corriendo: break
            
            self.estado_msg.emit(f"Estabilizando Vdc = {vdc} V")
            self.lcr.set_vdc(vdc)
            time.sleep(1.0) 
            
            for freq in frecuencias:
                if not self.corriendo: break
                
                # ====================================================
                # MEDICIÓN CANAL 1 (Protección ALC)
                # ====================================================
                if usa_matriz:
                    # 1. Desactivar ALC para evitar el pico de corriente al abrir Hpot
                    if alc_habilitado: 
                        self.lcr.set_alc(False)
                        time.sleep(0.1)
                        
                    # 2. Break-before-make seguro
                    self.matriz.open_channels(ch2_matriz)
                    self.matriz.close_channels(ch1_matriz)
                    time.sleep(0.2) 
                    
                    # 3. Restaurar ALC con el circuito ya cerrado y feedback funcional
                    if alc_habilitado:
                        self.lcr.set_alc(True)
                        time.sleep(0.4) # Dar tiempo al lazo ALC para que llegue al setpoint suavemente
                    
                self.lcr.set_frecuencia(freq)
                delay_freq = 0.5 if freq < 100 else 0.15
                time.sleep(delay_freq) 
                
                r1, x1, status1 = self.lcr.medir()
                vm1, im1 = self.lcr.get_monitors()
                z1 = math.sqrt(r1**2 + x1**2) if not math.isnan(r1) else float('nan')
                theta1 = math.degrees(math.atan2(x1, r1)) if not math.isnan(r1) else float('nan')
                
                # ====================================================
                # MEDICIÓN CANAL 2 (Protección ALC)
                # ====================================================
                r2, x2, status2 = float('nan'), float('nan'), status1
                vm2, im2 = float('nan'), float('nan')
                z2, theta2 = float('nan'), float('nan')
                
                if usa_matriz and self.corriendo:
                    # 1. Desactivar ALC de nuevo
                    if alc_habilitado:
                        self.lcr.set_alc(False)
                        time.sleep(0.1)
                        
                    # 2. Break-before-make seguro
                    self.matriz.open_channels(ch1_matriz)
                    self.matriz.close_channels(ch2_matriz)
                    time.sleep(0.2)
                    
                    # 3. Restaurar ALC
                    if alc_habilitado:
                        self.lcr.set_alc(True)
                        time.sleep(0.4)
                    
                    # Espera extra por el salto de impedancia a misma frecuencia
                    time.sleep(0.15)
                    
                    r2, x2, status2 = self.lcr.medir()
                    vm2, im2 = self.lcr.get_monitors()
                    z2 = math.sqrt(r2**2 + x2**2) if not math.isnan(r2) else float('nan')
                    theta2 = math.degrees(math.atan2(x2, r2)) if not math.isnan(r2) else float('nan')

                t_min = (time.time() - tiempo_inicio) / 60.0
                status_general = status1 if status1 != 0 else status2
                
                self.datos_is.emit(vdc, freq, r1, x1, z1, theta1, r2, x2, z2, theta2, t_min, status_general)
                
                with open(archivo_csv, 'a', newline='') as f:
                    csv.writer(f).writerow([f"{t_min:.4f}", vdc, freq, r1, x1, z1, theta1, vm1, im1, r2, x2, z2, theta2, vm2, im2, status_general])

        self.estado_msg.emit("Espectroscopía Finalizada")
        self.lcr.set_vdc(0.0)
        self.lcr.set_alc(False) # Dejar el equipo seguro al terminar
        
        if usa_matriz:
            self.matriz.open_channels([ch1_matriz, ch2_matriz])
            
        self.corriendo = False

class HiloCorreccionSpot(QThread):
    progreso = Signal(int, int, float) 
    estado_msg = Signal(str)
    finalizado = Signal(str)
    error_detectado = Signal(str)

    def __init__(self, estado_compartido, tipo):
        super().__init__()
        self.estado = estado_compartido
        self.tipo = tipo # Viene como "OPEN" o "SHOR" desde la UI
        self.lcr = TonghuiTH2832(resource_name=self.estado.get('gpib_lcr', "GPIB0::11::INSTR"))

    def run(self):
        frecuencias = self.estado.get('frecuencias_corr', [])
        if not frecuencias:
            self.error_detectado.emit("No hay frecuencias cargadas para corregir.")
            return

        try:
            import pyvisa
            rm = pyvisa.ResourceManager()
            self.lcr.conectar(rm)
            
            self.estado_msg.emit(f"Preparando equipo para corrección {self.tipo}...")
            
            comando_tipo = "OPEN" if self.tipo == "OPEN" else "SHORT"
            
            # 1. Preparación Crítica del Equipo
            self.lcr.inst.write("DISP:PAGE CSET") 
            time.sleep(0.5)
            
            # Aumentamos el timeout de VISA dramáticamente para que *OPC? no aborte 
            # esperando las mediciones de 20Hz
            self.lcr.inst.timeout = 60000 
            
            self.lcr.inst.write("TRIG:SOUR INT")
            self.lcr.inst.write("FUNC:IMP:RANG:AUTO ON")
            self.lcr.inst.write("APER SLOW, 1") 
            self.lcr.inst.write("VOLT 1V")      
            self.lcr.inst.write("BIAS:STAT 0")  
            self.lcr.inst.write("AMPL:ALC 0")   
            time.sleep(1.0)

            for i, freq in enumerate(frecuencias):
                if not self.isRunning(): break 
                
                spot_id = i + 1
                if spot_id > 201: 
                    break
                
                self.progreso.emit(spot_id, len(frecuencias), freq)
                
                self.lcr.inst.write(f"FREQ {freq}HZ")
                time.sleep(0.1)
                
                # 2. Configurar el Spot (ESPACIO MANTENIDO)
                self.lcr.inst.write(f"CORR:SPOT {spot_id}:FREQ {freq}HZ")
                self.lcr.inst.write(f"CORR:SPOT {spot_id}:STAT ON")
                
                # 3. Disparar calibración
                self.lcr.inst.write(f"CORR:SPOT {spot_id}:{comando_tipo}")
                
                # 4. Polling nativo: Python esperará aquí exactamente el tiempo
                # que el LCR necesite para integrar el punto, sin adivinar.
                self.lcr.inst.query("*OPC?")

            # 5. Activar la bandera global para que el equipo use estos spots
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
                except:
                    pass