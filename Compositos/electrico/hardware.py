import time
import csv
import math
from PySide6.QtCore import QThread, Signal

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

    def conectar(self, rm):
        self.inst = rm.open_resource(self.direccion)
        self.inst.timeout = 5000 
        self.inst.write("*CLS") # LIMPIA MEMORIA DE ERRORES AL CONECTAR
        
        self.ultimo_nplc = None
        self.ultimo_rango = None
        print(f"34420A Conectado: {self.direccion}")

    def seleccionar_canal(self, canal):
        if self.inst:
            self.inst.write(f"ROUT:TERM FRON{canal}")

    def configurar_rapido(self, nplc, rango_str): # Quitamos el argumento filtro_str
        if not self.inst: return
        
        if nplc != self.ultimo_nplc:
            self.inst.write(f"VOLT:DC:NPLC {nplc}")
            self.ultimo_nplc = nplc

        if rango_str != self.ultimo_rango:
            diccionario_rangos = {
                "Auto": "AUTO ON", "1 mV": "0.001", "10 mV": "0.01",
                "100 mV": "0.1", "1 V": "1.0", "10 V": "10.0", "100 V": "100.0"
            }
            rango_val = diccionario_rangos.get(rango_str, "AUTO ON")
            if rango_val == "AUTO ON":
                self.inst.write("VOLT:DC:RANG:AUTO ON")
            else:
                self.inst.write(f"VOLT:DC:RANG {rango_val}")
            self.ultimo_rango = rango_str

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
        delay_cambio_canal = 1.5 
        
        lista_bias = self.estado['lista_bias']
        lista_pulsos = self.estado['lista_pulsos']
        T_descarga = self.estado['tiempo_descarga']

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

                # Inicializar el archivo CSV
                encabezado = [
                    "Tiempo (min)", "I pulso (mA)", "I bias (mA)", 
                    "Vinst 1 (V)", "Rinst 1 (Ohm)", "Rrem 1 (Ohm)", "Vbias 1 (V)", 
                    "Vinst 2 (V)", "Rinst 2 (Ohm)", "Rrem 2 (Ohm)", "Vbias 2 (V)", 
                    "Tiempo de Pulso (s)", "Vcc (V)", "Vrange", "NPLC", "Ch2?"
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
                        self.estado['tiempo_pulso'], self.estado['limite_voltaje'], 
                        self.estado['rango'], nplc, usa_ch2
                    ]
                    self._guardar_csv(fila, archivo_actual)
                    time.sleep(0.01) 
                    
                if not self.corriendo: return

                # ------------------------------------------------
                # FASE 2: DESCARGA/RELAJACIÓN (LIMITADA POR T_DESCARGA)
                # ------------------------------------------------
                es_pulsado = self.estado.get('relajacion_pulsada', False)
                periodo = self.estado.get('periodo_relajacion', 1.0)
                ancho = self.estado.get('ancho_lectura', 0.5)
                
                if not es_pulsado:
                    self.fuente.set_corriente(corr_bias)
                    self.fuente.operar()
                
                tiempo_inicio_descarga = time.time()

                while (time.time() - tiempo_inicio_descarga) < T_descarga and self.corriendo:
                    inicio_ciclo = time.time()
                    
                    if es_pulsado:
                        self.fuente.set_corriente(corr_bias)
                        self.fuente.operar()
                        
                        # Dejamos que el pulso fluya casi todo el 'Ancho' antes de pedir la lectura.
                        # Asumimos que la lectura y el cable GPIB consumen ~100ms
                        margen_lectura = 0.1
                        if usa_ch2: margen_lectura += delay_cambio_canal
                        
                        t_espera_on = ancho - margen_lectura
                        if t_espera_on > 0:
                            # Espera pasiva comprobando el reloj (no congela la interfaz)
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
                        # APAGADO INMEDIATO: Cortamos la fuente apenas devuelve el valor el voltímetro
                        self.fuente.standby()
                        
                    r1_bias = float('nan') if abs(corr_bias) < 1e-5 else (v1_bias / (corr_bias * 1e-3))
                    r2_bias = float('nan') if (abs(corr_bias) < 1e-5 or not usa_ch2) else (v2_bias / (corr_bias * 1e-3))
                    
                    t_min = (time.time() - tiempo_inicio) / 60.0
                    
                    self.datos_actualizados.emit(t_min, v1_bias, r1_bias, v2_bias, r2_bias, corr_bias, True)
                    
                    fila = [
                        f"{t_min:.4f}", self.pulse_data['i_inst'], corr_bias,
                        self.pulse_data['v1_inst'], self.pulse_data['r1_inst'], r1_bias, v1_bias,
                        self.pulse_data['v2_inst'], self.pulse_data['r2_inst'], r2_bias, v2_bias,
                        self.estado['tiempo_pulso'], self.estado['limite_voltaje'], 
                        self.estado['rango'], nplc, usa_ch2
                    ]
                    self._guardar_csv(fila, archivo_actual)
                    
                    if es_pulsado:
                        # TIEMPO OFF GARANTIZADO
                        # Forzamos el descanso exacto (Período - Ancho) sin importar
                        # cuánto se trabó el voltímetro durante el ciclo ON.
                        tiempo_off_deseado = periodo - ancho
                        if tiempo_off_deseado <= 0: 
                            tiempo_off_deseado = 0.1 # Seguro anti-colapso si el usuario configura mal la UI
                        
                        tiempo_inicio_off = time.time()
                        while (time.time() - tiempo_inicio_off) < tiempo_off_deseado and self.corriendo:
                            time.sleep(0.01)
                    else:
                        time.sleep(0.05)


    # ==============================================================================
    # LÓGICA 2: BARRIDO TRIANGULAR (El código original)
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

            # --- MATEMÁTICA DE TIEMPO ---
            multiplicador = 2 if usa_ch2 else 1
            delay_relay = 0.015 if usa_ch2 else 0.0
            tiempo_integracion = (nplc * 0.02) * multiplicador
            overhead = 0.015 * multiplicador + delay_relay
            
            espera_pulso = max(0.05, self.estado['ancho_pulso'] - tiempo_integracion - overhead)
            delay_cambio_canal = 1.5 

            # ====================================================
            # FASE A: PULSO PRINCIPAL
            # ====================================================
            if not self.pausado_cbias:
                if abs(corriente_objetivo) < 1e-5:
                    corriente_objetivo = 1e-5 if corriente_objetivo >= 0 else -1e-5

                self.fuente.set_limite_voltaje(self.estado['limite_voltaje'])
                self.fuente.set_corriente(corriente_objetivo)
                
                self.voltimetro.seleccionar_canal(1)
                self.fuente.operar()
                time.sleep(espera_pulso) 
                
                v1_inst = self.voltimetro.leer_voltaje()
                
                v2_inst = float('nan')
                if usa_ch2:
                    self.voltimetro.seleccionar_canal(2)
                    time.sleep(delay_cambio_canal)
                    v2_inst = self.voltimetro.leer_voltaje()
                
                self.fuente.standby()
                
                r1_inst = float('nan') if abs(corriente_objetivo) < 1e-5 else (v1_inst / (corriente_objetivo * 1e-3))
                r2_inst = float('nan') if (abs(corriente_objetivo) < 1e-5 or not usa_ch2) else (v2_inst / (corriente_objetivo * 1e-3))
                
                t_min = (time.time() - tiempo_inicio) / 60.0
                self.datos_actualizados.emit(t_min, v1_inst, r1_inst, v2_inst, r2_inst, corriente_objetivo, False)
                
                self.pulse_data = {
                'i_inst': corriente_objetivo, 'v1_inst': v1_inst, 'r1_inst': r1_inst,
                'v2_inst': v2_inst, 'r2_inst': r2_inst
                }
                
                time.sleep(self.estado['periodo_pulso'])

            # ====================================================
            # FASE B: PULSOS BIAS
            # ====================================================
            num_bias = self.estado['num_mediciones_bias']
            if num_bias > 0:
                for _ in range(num_bias):
                    if not self.corriendo or self.pausado_sbias: break
                    
                    corr_bias_actual = self.estado['corr_bias']
                    if abs(corr_bias_actual) < 1e-5:
                        corr_bias_actual = 1e-5 if corr_bias_actual >= 0 else -1e-5

                    self.fuente.set_corriente(corr_bias_actual)
                    self.voltimetro.seleccionar_canal(1)
                    self.fuente.operar()
                    time.sleep(espera_pulso)
                    
                    v1_bias = self.voltimetro.leer_voltaje()
                    
                    v2_bias = float('nan')
                    if usa_ch2:
                        self.voltimetro.seleccionar_canal(2)
                        time.sleep(delay_cambio_canal)
                        v2_bias = self.voltimetro.leer_voltaje()
                        
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
                    
                    time.sleep(self.estado['periodo_pulso'])
            
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