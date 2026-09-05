import time
import csv
import math
import pyvisa
from PySide6.QtCore import QThread, Signal

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
        """Encapsula la lógica termodinámica del script original."""
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