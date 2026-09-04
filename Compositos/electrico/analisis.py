# %% [1] INICIALIZACIÓN Y LIBRERÍAS
import os
import glob
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit

# Configuración visual para gráficos científicos consistentes
plt.rcParams.update({
    'font.size': 12,
    'axes.grid': True,
    'grid.alpha': 0.5,
    'lines.linewidth': 1.5,
    'lines.markersize': 6
})

# %% [2] CARGA GENERAL DE DATOS
def cargar_archivo(filepath):
    """
    Carga un CSV de medición en un DataFrame.
    Extrae los parámetros fijos (metadata) tomando la primera fila válida.
    """
    if not os.path.exists(filepath):
        print(f"Archivo no encontrado: {filepath}")
        return None, None

    df = pd.read_csv(filepath)
    
    # Extraer metadatos comunes ignorando NaNs
    metadata = {}
    columnas_fijas = ['Tiempo de Pulso (s)', 'Ancho pulso (s)', 'Periodo (s)', 
                      'Vcc (V)', 'NPLC', 'Ch2?']
    
    for col in columnas_fijas:
        if col in df.columns:
            metadata[col] = df[col].dropna().iloc[0] if not df[col].dropna().empty else np.nan

    print(f"[{os.path.basename(filepath)}] cargado. Filas: {len(df)} | Columnas: {len(df.columns)}")
    return df, metadata

def graficar_xy(df, col_x, col_y, col_color=None, titulo=""):
    """
    Graficador universal. 
    Elimina automáticamente los NaNs de las columnas seleccionadas.
    Permite usar una tercera columna para mapa de color (útil para ver evolución temporal).
    """
    # Filtrar solo las filas que tienen datos válidos en X e Y
    df_plot = df.dropna(subset=[col_x, col_y]).copy()
    
    if df_plot.empty:
        print(f"No hay datos solapados para {col_x} y {col_y}.")
        return

    plt.figure(figsize=(8, 6))
    
    if col_color and col_color in df_plot.columns:
        sc = plt.scatter(df_plot[col_x], df_plot[col_y], 
                         c=df_plot[col_color], cmap='viridis', alpha=0.8)
        plt.colorbar(sc, label=col_color)
    else:
        plt.plot(df_plot[col_x], df_plot[col_y], 'o-', alpha=0.8)

    plt.xlabel(col_x)
    plt.ylabel(col_y)
    plt.title(titulo)
    plt.tight_layout()
    plt.show()

# %% [4] ESPACIO DE TRABAJO: PRUEBA RÁPIDA (BARRIDO I-V)
# Aquí cargas un archivo específico o el último generado
archivos = sorted(glob.glob("*.csv"), key=os.path.getmtime)
archivo_actual = archivos[-1] if archivos else "medicion_ejemplo.csv"

df, meta = cargar_archivo(archivo_actual)

if df is not None:
    # Ejemplo de uso universal: Graficar I-V de la fase de pulsos
    graficar_xy(df, col_x='Vinst 1 (V)', col_y='I pulso (mA)', 
                col_color='Tiempo (min)', titulo="Curva I-V Dinámica")

# %% [5] MÓDULO ESPECÍFICO: RELAJACIÓN Y AJUSTES (SciPy Skeleton)

def decaimiento_exp(t, R_inf, A, tau):
    """Ecuación de prueba para ajuste. Modificar por Debye, KWW, etc."""
    return R_inf + A * np.exp(-t / tau)

def analizar_relajacion(df):
    """
    Aísla la fase de relajación pura (donde el bias es numérico y el pulso principal no actúa)
    y realiza un ajuste de curva.
    """
    # Aislar datos de relajación (filtrando por la columna de bias)
    if 'I bias (mA)' not in df.columns:
        print("El archivo no tiene columna de bias.")
        return

    df_relax = df.dropna(subset=['I bias (mA)', 'Rrem 1 (Ohm)']).copy()
    
    if len(df_relax) < 3:
        print("Datos insuficientes para ajustar relajación.")
        return

    # Normalizar eje de tiempo (en segundos)
    t_raw = df_relax['Tiempo (min)'].values * 60.0
    t_fit = t_raw - t_raw[0]
    R_fit = df_relax['Rrem 1 (Ohm)'].values

    # Valores semilla: [Asintótico, Amplitud, Tau_inicial]
    p0 = [R_fit[-1], R_fit[0] - R_fit[-1], 10.0]

    try:
        popt, pcov = curve_fit(decaimiento_exp, t_fit, R_fit, p0=p0, maxfev=5000)
        R_inf, A, tau = popt
        
        # Calcular R-cuadrado para bondad de ajuste
        residuos = R_fit - decaimiento_exp(t_fit, *popt)
        ss_res = np.sum(residuos**2)
        ss_tot = np.sum((R_fit - np.mean(R_fit))**2)
        r_squared = 1 - (ss_res / ss_tot)
        
        print(f"Tau: {tau:.3f} s | R²: {r_squared:.4f}")
        
        plt.figure(figsize=(8, 5))
        plt.plot(t_fit, R_fit, 'ko', label='Datos', alpha=0.4)
        
        t_sim = np.linspace(0, max(t_fit), 300)
        plt.plot(t_sim, decaimiento_exp(t_sim, *popt), 'r-', 
                 label=f'Ajuste ($\\tau$ = {tau:.1f} s)')
        
        plt.xlabel(r'$\Delta t$ (s)')
        plt.ylabel(r'$R_{rem}$ ($\Omega$)')
        plt.legend()
        plt.show()

    except RuntimeError:
        print("No se alcanzó convergencia en el ajuste.")

if df is not None:
    analizar_relajacion(df)

# %% [6] MÓDULO ESPECÍFICO: EXTRACCIÓN MASIVA (LOOP DE DIRECTORIO)
# Ejecutar esta celda aisla parámetros de múltiples archivos en un solo resumen
resultados = []

for archivo in glob.glob("*bias*.csv"):
    df_temp, meta_temp = cargar_archivo(archivo)
    if df_temp is not None:
        # Extraer métricas básicas, ej: resistencia inicial vs final
        try:
            r_ini = df_temp['Rinst 1 (Ohm)'].dropna().iloc[0]
            r_fin = df_temp['Rrem 1 (Ohm)'].dropna().iloc[-1]
            i_pulso = df_temp['I pulso (mA)'].dropna().iloc[0]
            
            resultados.append({
                'Archivo': os.path.basename(archivo),
                'I_Pulso': i_pulso,
                'R_ini': r_ini,
                'R_fin': r_fin,
                'Delta_R': r_ini - r_fin
            })
        except IndexError:
            pass # Archivo corrupto o vacío

df_resumen = pd.DataFrame(resultados)
if not df_resumen.empty:
    print("\nResumen Extraído:")
    display(df_resumen.head()) # 'display' funciona nativo en entornos interactivos
# %% [7] SUITE DE VISUALIZACIÓN COMPLETA (7 GRÁFICOS)
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, Normalize
from PySide6.QtWidgets import QApplication, QFileDialog
%matplotlib qt
# Iniciar la aplicación Qt de forma segura
app = QApplication.instance() or QApplication([])

# Abrir diálogo para seleccionar uno o múltiples archivos
archivos, _ = QFileDialog.getOpenFileNames(
    None, 
    "Seleccionar archivos CSV para comparar", 
    "", 
    "Archivos CSV (*.csv);;Todos los archivos (*)"
)

if not archivos:
    print("No se seleccionaron archivos.")
else:
    datos_procesados = []
    
    # 1. Extracción Dual (Pulso, Relajación y Total)
    for archivo in archivos:
        df, meta = cargar_archivo(archivo) 
        if df is None: continue
            
        try:
            i_pulso = df['I pulso (mA)'].dropna().iloc[0]
            i_bias = df['I bias (mA)'].dropna().iloc[0] if not df['I bias (mA)'].dropna().empty else 0.0
        except IndexError:
            continue
            
        d_dict = {
            'i_pulso': i_pulso,
            'i_bias': i_bias,
            'etiqueta': f"Pulso: {i_pulso} mA | Bias: {i_bias} mA"
        }
        
        # A) Procesar datos de Pulso (Carga)
        df_carga = df[df['I bias (mA)'].isna()].copy()
        if len(df_carga) > 1:
            t_raw = df_carga['Tiempo (min)'].values * 60.0
            d_dict['t_norm_pulso'] = t_raw - t_raw[0]
            d_dict['r_inst'] = df_carga['Rinst 1 (Ohm)'].values
            
        # B) Procesar datos de Relajación (Descarga)
        df_relax = df[df['I bias (mA)'].notna()].copy()
        if len(df_relax) > 1:
            t_raw = df_relax['Tiempo (min)'].values * 60.0
            d_dict['t_norm_relax'] = t_raw - t_raw[0]
            d_dict['r_rem'] = df_relax['Rrem 1 (Ohm)'].values

        # C) Procesar datos Totales (Ciclo Completo)
        if len(df) > 1:
            t_raw_total = df['Tiempo (min)'].values * 60.0
            d_dict['t_norm_total'] = t_raw_total - t_raw_total[0]
            # Combinamos Rinst y Rrem dependiendo de si la fase tiene Bias o no
            r_total = np.where(df['I bias (mA)'].isna(), df['Rinst 1 (Ohm)'], df['Rrem 1 (Ohm)'])
            d_dict['r_total'] = r_total
            
        datos_procesados.append(d_dict)

    if not datos_procesados:
        print("No hay datos válidos para graficar.")
    else:
        # 2. Definición de Colores (Actualizados) y Marcadores
        cmap_pos = LinearSegmentedColormap.from_list('reds', ['red', 'darkred'])
        cmap_neg = LinearSegmentedColormap.from_list('purples', ['blue', '#b39ddb']) 
        marcadores = ['o', 's', '^', 'v', 'D', 'p', '*', 'h', 'X', 'd', 'P', 'H']

        def crear_grafico(datos, llave_x, llave_y, variable_color, titulo, xlabel, ylabel):
            if not datos: return
            
            plt.figure(figsize=(10, 6))
            
            datos_pos = [d for d in datos if d[variable_color] > 0 and llave_x in d and llave_y in d]
            datos_neg = [d for d in datos if d[variable_color] < 0 and llave_x in d and llave_y in d]
            
            def plot_grupo(grupo, cmap, offset_marc):
                if not grupo: return
                grupo.sort(key=lambda x: x[variable_color])
                valores = [d[variable_color] for d in grupo]
                vmin, vmax = min(valores), max(valores)
                norm = Normalize(vmin=vmin, vmax=vmax) if vmin != vmax else Normalize(vmin=vmin-1, vmax=vmax+1)
                
                for idx, d in enumerate(grupo):
                    color = cmap(norm(d[variable_color]))
                    marcador = marcadores[(idx + offset_marc) % len(marcadores)]
                    espaciado = max(1, len(d[llave_x]) // 15)
                    
                    plt.plot(d[llave_x], d[llave_y], marker=marcador, markevery=1,
                             linestyle='-', color=color, label=d['etiqueta'], 
                             linewidth=1.5, alpha=0.8, markersize=7)
                             
            plot_grupo(datos_pos, cmap_pos, 0)
            plot_grupo(datos_neg, cmap_neg, len(datos_pos))

            plt.xscale('symlog')
            plt.title(titulo)
            plt.xlabel(xlabel)
            plt.ylabel(ylabel)
            plt.legend(bbox_to_anchor=(1.02, 1), loc='upper left', borderaxespad=0.)
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            plt.show()

        # 3. Generar los 7 gráficos
        
        crear_grafico([d for d in datos_procesados if d['i_pulso'] > 0], 
                      't_norm_relax', 'r_rem', 'i_bias', 
                      "1. Relajación: Pulsos Positivos", "Tiempo (s)", "R_rem (Ohm)")

        crear_grafico([d for d in datos_procesados if d['i_pulso'] < 0], 
                      't_norm_relax', 'r_rem', 'i_bias', 
                      "2. Relajación: Pulsos Negativos", "Tiempo (s)", "R_rem (Ohm)")

        crear_grafico([d for d in datos_procesados if d['i_bias'] > 0], 
                      't_norm_relax', 'r_rem', 'i_pulso', 
                      "3. Relajación: Bias Positivos", "Tiempo (s)", "R_rem (Ohm)")

        crear_grafico([d for d in datos_procesados if d['i_bias'] < 0], 
                      't_norm_relax', 'r_rem', 'i_pulso', 
                      "4. Relajación: Bias Negativos", "Tiempo (s)", "R_rem (Ohm)")

        crear_grafico(datos_procesados, 
                      't_norm_relax', 'r_rem', 'i_bias', 
                      "5. MASTER: Toda la Dinámica de Relajación", "Tiempo (s)", "R_rem (Ohm)")

        crear_grafico(datos_procesados, 
                      't_norm_pulso', 'r_inst', 'i_pulso', 
                      "6. MASTER: Toda la Dinámica de Carga (Pulso)", "Tiempo (s)", "R_inst (Ohm)")

        # NUEVO GRÁFICO 7: Ciclo Completo
        crear_grafico(datos_procesados, 
                      't_norm_total', 'r_total', 'i_pulso', 
                      "7. MASTER: Ciclo Completo (Carga + Descarga)", "Tiempo (s)", "Resistencia (Ohm)")