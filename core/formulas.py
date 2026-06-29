# =============================================================================
# 📁 core/formulas.py - MATEMÁTICA EXACTA Y MODELOS DE PROYECCIÓN DEPORTIVA
# =============================================================================
import numpy as np
import pandas as pd
import datetime
from scipy.optimize import fsolve

def calcular_edad_decimal(fecha_nacimiento, fecha_evento) -> float:
    if not fecha_nacimiento or not fecha_evento:
        return 0.0
    if isinstance(fecha_nacimiento, str):
        fecha_nacimiento = datetime.date.fromisoformat(fecha_nacimiento)
    if isinstance(fecha_evento, str):
        fecha_evento = datetime.date.fromisoformat(fecha_evento)
    dias = (fecha_evento - fecha_nacimiento).days
    return round(dias / 365.25, 4)

def resolver_k_individual(eq_t0, eq_T0, eq_t_pb, eq_T_pb, eq_t_peak, eq_T_target) -> float:
    """
    Resuelve numéricamente el valor de la constante k para que la curva asintótica
    pase de manera exacta por el récord personal (PB) del nadador.
    """
    # Evitar divisiones por cero o incoherencias matemáticas elementales
    if eq_t_pb <= eq_t0 or eq_T0 <= eq_T_target:
        return 0.35

    # Tomamos h desde los parámetros o un valor sutil de envejecimiento (ej. 0.01)
    # Si 'h' se maneja globalmente en session_state, puedes usar st.session_state.get('h_slider', 0.01)
    h_val = 0.01 

    def ecuacion_objetivo(k_guess):
        # Ecuación asintótica estándar aplicada en el punto de control (PB)
        T_estimado = eq_T_target + (eq_T0 - eq_T_target) * np.exp(-k_guess * (eq_t_pb - eq_t0)) + h_val * (eq_t_pb - eq_t0)
        return T_estimado - eq_T_pb

    try:
        k_solucion = fsolve(ecuacion_objetivo, x0=0.1)[0]
        return float(np.clip(k_solucion, 0.01, 2.0))
    except:
        return 0.35

def calcular_curva_atleta(edades_arr, eq_t0, eq_T0, eq_t_pb, eq_T_pb, eq_t_peak, eq_T_target, k_eq, h_eq):
    """
    Calcula los puntos del eje Y para la curva de proyección fisiológica.
    """
    # Ecuación asintótica exponencial + factor de deriva por edad (h)
    tiempos = eq_T_target + (eq_T0 - eq_T_target) * np.exp(-k_eq * (edades_arr - eq_t0)) + h_eq * (edades_arr - eq_t0)
    return np.array(tiempos)


def computar_modelo_bannister(df_cargas, df_diario, ventana_dias=42):
    if df_cargas.empty:
        df_diario['aptitud'] = 0.0
        df_diario['fatiga'] = 0.0
        df_diario['rendimiento'] = 0.0
        return df_diario
    df_cargas['fecha'] = pd.to_datetime(df_cargas['fecha']).dt.date
    df_diario['fecha'] = pd.to_datetime(df_diario['fecha']).dt.date
    cargas_reg = df_cargas.groupby('fecha')['metros_totales'].sum().to_dict()
    
    aptitud, fatiga = 0.0, 0.0
    tau_fitness = ventana_dias
    tau_fatigue = max(3, int(ventana_dias / 6))
    
    lista_aptitud, lista_fatiga, lista_rendimiento = [], [], []
    for fila in df_diario.itertuples():
        carga_hoy = cargas_reg.get(fila.fecha, 0.0)
        aptitud = aptitud * np.exp(-1.0 / tau_fitness) + carga_hoy
        fatiga = fatiga * np.exp(-1.0 / tau_fatigue) + carga_hoy
        rendimiento = aptitud - (2.0 * fatiga)
        lista_aptitud.append(round(aptitud, 2))
        lista_fatiga.append(round(fatiga, 2))
        lista_rendimiento.append(round(rendimiento, 2))
        
    df_diario['aptitud'] = lista_aptitud
    df_diario['fatiga'] = lista_fatiga
    df_diario['rendimiento'] = lista_rendimiento
    return df_diario
