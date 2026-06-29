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
    Resuelve numéricamente el factor de ajuste fisiológico k (desaceleración)
    usando optimización por fsolve sobre la ecuación trascendental original.
    """
    if eq_t_peak > eq_t0 and eq_t_pb > eq_t0:
        tau_eq = (eq_t_pb - eq_t0) / (eq_t_peak - eq_t0)
        
        def ecuacion_k_eq(k_val):
            if abs(1 - np.exp(-k_val)) < 1e-6:
                return 1e6
            ter_exp = (np.exp(-k_val * tau_eq) - np.exp(-k_val)) / (1 - np.exp(-k_val))
            return (eq_T_target + (eq_T0 - eq_T_target) * ter_exp) - eq_T_pb
            
        try:
            k_opt_eq, _, _, _ = fsolve(ecuacion_k_eq, 1.0, full_output=True)
            return float(k_opt_eq[0])
        except Exception:
            return 0.4
    return 0.4


def calcular_curva_atleta(edades_arr, eq_t0, eq_T0, eq_t_pb, eq_T_pb, eq_t_peak, eq_T_target, k_eq, h_eq):
    """
    Modelo matemático original dividido por tramos antes y después del hito t_pb.
    """
    tiempos = []
    D_eq = eq_T_pb - eq_T_target
    
    denominador_tau = eq_t_peak - eq_t0 if (eq_t_peak - eq_t0) != 0 else 1.0
    denominador_k = (1 - np.exp(-k_eq)) if (1 - np.exp(-k_eq)) != 0 else 1.0
    
    for t in edades_arr:
        if t < eq_t_pb:
            tau_t = (t - eq_t0) / denominador_tau
            ter_exp = (np.exp(-k_eq * tau_t) - np.exp(-k_eq)) / denominador_k
            T_t = eq_T_target + (eq_T0 - eq_T_target) * ter_exp
        else:
            T_t = eq_T_pb - D_eq * (1 - np.exp(-h_eq * (t - eq_t_pb)))
        tiempos.append(T_t)
        
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
