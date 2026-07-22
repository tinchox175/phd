import time
import csv
import math
from PySide6.QtCore import QThread, Signal

class Keithley224:
    def __init__(self, direccion="GPIB0::02::INSTR"):
        self.direccion = direccion
        self.inst = None
        self.ultimo_limite_v = None # <-- NUEVO: Cache del límite de voltaje

    def conectar(self, rm):
        self.inst = rm.open_resource(self.direccion)
        self.inst.write_termination = '\r\n'
        self.inst.read_termination = '\r\n'
        self.inst.write("R0X") 
        self.ultimo_limite_v = None # Reiniciar cache al conectar
        self.standby()
        print(f"K224 Conectado: {self.direccion}")

    def set_corriente(self, valor_ma):
        if self.inst:
            valor_amps = valor_ma * 1e-3
            self.inst.write(f"I{valor_amps:.4E}X")

    def set_limite_voltaje(self, valor_v):
        # NUEVO: Solo enviar por GPIB si el límite realmente cambió en la UI
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
        # Cache de estado para evitar spam en el bus GPIB
        self.ultimo_nplc = None
        self.ultimo_rango = None
        self.ultimo_filtro = None

    def conectar(self, rm):
        self.inst = rm.open_resource(self.direccion)
        self.inst.timeout = 5000 
        
        # Limpiar cache al conectar
        self.ultimo_nplc = None
        self.ultimo_rango = None
        self.ultimo_filtro = None
        print(f"34420A Conectado: {self.direccion}")

    def seleccionar_canal(self, canal):
        if self.inst:
            self.inst.write(f"ROUT:TERM FRON{canal}")

    def configurar_rapido(self, nplc, rango_str, filtro_str):
        if not self.inst: return
        
        # Solo enviar comandos físicos si el usuario cambió el valor en la UI
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

        if filtro_str != self.ultimo_filtro:
            if filtro_str == "OFF":
                self.inst.write("INP:FILT OFF")
                self.inst.write("VOLT:DC:FILT:STAT OFF")
            elif filtro_str == "Analógico":
                self.inst.write("INP:FILT ON")
                self.inst.write("VOLT:DC:FILT:STAT OFF")
            elif filtro_str == "Digital":
                self.inst.write("INP:FILT OFF")
                self.inst.write("VOLT:DC:FILT:TYPE MOV")
                self.inst.write("VOLT:DC:FILT:COUN 10") 
                self.inst.write("VOLT:DC:FILT:STAT ON")
            elif filtro_str == "Ambos":
                self.inst.write("INP:FILT ON")
                self.inst.write("VOLT:DC:FILT:TYPE MOV")
                self.inst.write("VOLT:DC:FILT:COUN 10")
                self.inst.write("VOLT:DC:FILT:STAT ON")
            self.ultimo_filtro = filtro_str

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

        # 1. INTENTO PROTEGIDO DE INICIALIZAR VISA
        # Mover esto aquí evita que el programa principal crashee si falta PyVISA o el backend
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

        # 2. INTENTO PROTEGIDO DE CONECTAR INSTRUMENTOS
        try:
            self.fuente.conectar(rm)
            self.voltimetro.conectar(rm)
            
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
                filtro = self.estado['filtro']
                
                self.voltimetro.configurar_rapido(nplc, self.estado['rango'], filtro)

                # --- MATEMÁTICA DE TIEMPO ---
                multiplicador = 2 if usa_ch2 else 1
                delay_relay = 0.015 if usa_ch2 else 0.0
                delay_filtro_analogico = 0.3 if filtro in ["Analógico", "Ambos"] else 0.0
                tiempo_integracion = (nplc * 0.02) * multiplicador
                overhead = 0.015 * multiplicador + delay_relay
                
                espera_pulso = max(0.05, self.estado['ancho_pulso'] - tiempo_integracion - overhead)
                espera_pulso += delay_filtro_analogico

                # ====================================================
                # FASE A: PULSO PRINCIPAL
                # ====================================================
                if not self.pausado_cbias:
                    if abs(corriente_objetivo) < 1e-5:
                        corriente_objetivo = 1e-5 if corriente_objetivo >= 0 else -1e-5

                    self.fuente.set_limite_voltaje(self.estado['limite_voltaje'])
                    self.fuente.set_corriente(corriente_objetivo)
                    
                    self.fuente.operar()
                    time.sleep(espera_pulso) 
                    
                    self.voltimetro.seleccionar_canal(1)
                    v1_inst = self.voltimetro.leer_voltaje()
                    
                    v2_inst = float('nan')
                    if usa_ch2:
                        self.voltimetro.seleccionar_canal(2)
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
                    
                    nan = float('nan')
                    # fila = [
                    #     f"{t_min:.4f}", corriente_objetivo, nan,
                    #     v1_inst, r1_inst, nan, nan,
                    #     v2_inst, r2_inst, nan, nan,
                    #     self.estado['ancho_pulso'], self.estado['periodo_pulso'], 
                    #     self.estado['limite_voltaje'], self.estado['rango'], 
                    #     nplc, usa_ch2, self.estado['num_mediciones_bias']
                    # ]
                    # self._guardar_csv(fila, archivo_csv)
                    
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

                        self.fuente.set_corriente(self.estado['corr_bias'])
                        self.fuente.operar()
                        time.sleep(espera_pulso)
                        
                        self.voltimetro.seleccionar_canal(1)
                        v1_bias = self.voltimetro.leer_voltaje()
                        
                        v2_bias = float('nan')
                        if usa_ch2:
                            self.voltimetro.seleccionar_canal(2)
                            v2_bias = self.voltimetro.leer_voltaje()
                            
                        self.fuente.standby()
                        
                        r1_bias = float('nan') if abs(self.estado['corr_bias']) < 1e-5 else (v1_bias / (self.estado['corr_bias'] * 1e-3))
                        r2_bias = float('nan') if (abs(self.estado['corr_bias']) < 1e-5 or not usa_ch2) else (v2_bias / (self.estado['corr_bias'] * 1e-3))
                        
                        t_min = (time.time() - tiempo_inicio) / 60.0
                        self.datos_actualizados.emit(t_min, v1_bias, r1_bias, v2_bias, r2_bias, self.estado['corr_bias'], True)
                        
                        fila = [
                            f"{t_min:.4f}", self.pulse_data['i_inst'], self.estado['corr_bias'],
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

        except Exception as e:
            # Captura cualquier error de hardware o comunicación y avisa a la UI sin crashear
            print(f"Error Crítico durante la medición: {e}")
            self.error_detectado.emit(str(e))
            
        finally:
            self.fuente.standby()
            self.corriendo = False
            print("Hilo finalizado. Fuente en Standby.")