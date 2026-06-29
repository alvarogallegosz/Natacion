# =============================================================================
# 📁 core/formulas.py - CEREBRO MATEMÁTICO Y MODELADO FISIOLÓGICO
# =============================================================================
import datetime
import numpy as np
import pandas as pd

# =============================================================================
# 📍 CHECKPOINT 4: EL PATRÓN DEL TIEMPO (EDAD DECIMAL ÚNICA)
# =============================================================================
def calcular_edad_decimal(fecha_nacimiento, fecha_evento=None) -> float:
    """
    Calcula la edad exacta con precisión flotante (flotante de días exactos/365.25).
    Elimina cualquier discrepancia de redondeo decimal en la plataforma.
    Garantiza consistencia absoluta entre gráficos, marcas mínimas y calendario.
    """
    if fecha_referencia is None:
        fecha_referencia = datetime.date.today()
        
    # Conversión segura a objetos datetime.date si vienen como strings de la BD
    if isinstance(fecha_nacimiento, str):
        fecha_nacimiento = datetime.date.fromisoformat(fecha_nacimiento)
    if isinstance(fecha_referencia, str):
        fecha_referencia = datetime.date.fromisoformat(fecha_referencia)
        
    if isinstance(fecha_nacimiento, datetime.datetime):
        fecha_nacimiento = fecha_nacimiento.date()
    if isinstance(fecha_referencia, datetime.datetime):
        fecha_referencia = fecha_referencia.date()

    dias_diferencia = (fecha_referencia - fecha_nacimiento).days
    edad_decimal = dias_diferencia / 365.25
    return round(edad_decimal, 4)


# =============================================================================
# MOTOR FISIOLÓGICO: MODELO IMPULSO-RESPUESTA DE BANNISTER
# =============================================================================
def computar_modelo_bannister(df_entrenamientos: pd.DataFrame, p_k: float, p_h: float, p_t_peak: float) -> pd.DataFrame:
    """
    Calcula el balance biológico de carga diaria (CTL, ATL y TSB) usando decaimientos exponenciales.
    
    Parámetros:
      - df_entrenamientos: DataFrame con columnas ['fecha', 'metros_totales', 'desglose_intensidad']
      - p_k: Factor de ponderación de la amplitud de la fatiga (ATL)
      - p_h: Factor de ponderación de la amplitud de la aptitud (CTL)
      - p_t_peak: Tiempo estimado para el pico de forma física
    """
    if df_entrenamientos.empty:
        return pd.DataFrame(columns=["fecha", "carga_diaria", "CTL", "ATL", "TSB", "TSB_relativo"])
        
    # 1. Agrupar y consolidar metros por fecha real
    df_entrenamientos['fecha'] = pd.to_datetime(df_entrenamientos['fecha']).dt.date
    df_diario = df_entrenamientos.groupby('fecha').agg({
        'metros_totales': 'sum'
    }).reset_index()
    
    # Reindexar para asegurar un vector de días continuo sin saltos temporales
    fecha_min = df_diario['fecha'].min()
    fecha_max = df_diario['fecha'].max()
    rango_fechas = pd.date_range(start=fecha_min, end=fecha_max).date
    
    df_completo = pd.DataFrame({'fecha': rango_fechas})
    df_completo = pd.merge(df_completo, df_diario, on='fecha', how='left').fillna(0)
    
    # 2. Constantes biológicas de tiempo estandarizadas a nivel internacional
    tau_1 = 42.0  # Constante de tiempo para el Fitness (Aptitud a largo plazo)
    tau_2 = 7.0   # Constante de tiempo para la Fatiga (Impacto a corto plazo)
    
    num_dias = len(df_completo)
    vector_carga = df_completo['metros_totales'].to_numpy(dtype=float)
    
    ctl = np.zeros(num_dias, dtype=float)
    atl = np.zeros(num_dias, dtype=float)
    
    # 3. Bucle de recurrencia biológica (Memoria Exponencial)
    for t in range(num_dias):
        if t == 0:
            ctl[t] = vector_carga[t]
            atl[t] = vector_carga[t]
        else:
            ctl[t] = ctl[t-1] * np.exp(-1.0 / tau_1) + vector_carga[t]
            atl[t] = atl[t-1] * np.exp(-1.0 / tau_2) + vector_carga[t]
            
    # 4. Cálculo de Balance de Estrés por Entrenamiento (TSB)
    # TSB = (CTL * Ponderación Aptitud) - (ATL * Ponderación Fatiga)
    tsb = (ctl * p_h) - (atl * p_k)
    
    df_completo['carga_diaria'] = vector_carga
    df_completo['CTL'] = np.round(ctl, 2)
    df_completo['ATL'] = np.round(atl, 2)
    df_completo['TSB'] = np.round(tsb, 2)
    
    # Cálculo del TSB Relativo en porcentaje para alertas de sobreentrenamiento
    df_completo['TSB_relativo'] = np.where(
        df_completo['CTL'] > 0,
        np.round((df_completo['TSB'] / df_completo['CTL']) * 100, 2),
        0.0
    )
    
    return df_completo
