# =============================================================================
# 📁 core/formulas.py - CEREBRO MATEMÁTICO Y MODELADO FISIOLÓGICO
# =============================================================================
import datetime
import numpy as np
import pandas as pd
from scipy.optimize import fsolve

# =============================================================================
# 📍 SECCIÓN 1: EL PATRÓN DEL TIEMPO (EDADES Y CATEGORÍAS FEDERATIVAS)
# =============================================================================

def calcular_edad_decimal(fecha_nacimiento, fecha_referencia=None) -> float:
    """
    Calcula la edad exacta de un atleta con precisión flotante basado en días reales.
    Elimina cualquier discrepancia de redondeo decimal en la plataforma.
    """
    if fecha_referencia is None:
        fecha_referencia = datetime.date.today()
        
    if isinstance(fecha_nacimiento, str):
        fecha_nacimiento = datetime.date.fromisoformat(fecha_nacimiento)
    if isinstance(fecha_referencia, str):
        fecha_referencia = datetime.date.fromisoformat(fecha_referencia)
        
    if isinstance(fecha_nacimiento, datetime.datetime):
        fecha_nacimiento = fecha_nacimiento.date()
    if isinstance(fecha_referencia, datetime.datetime):
        fecha_referencia = fecha_referencia.date()

    dias_totales = (fecha_referencia - fecha_nacimiento).days
    return round(dias_totales / 365.25, 4)


def calcular_edad_tecnica_al_31_dic(fecha_nacimiento, temporada_activa: int = None) -> int:
    """
    Anualiza la edad del nadador al 31 de diciembre de la temporada activa,
    según la normativa técnica internacional y nacional.
    """
    if temporada_activa is None:
        temporada_activa = datetime.date.today().year

    if isinstance(fecha_nacimiento, str):
        fecha_nacimiento = datetime.date.fromisoformat(fecha_nacimiento)
    elif isinstance(fecha_nacimiento, datetime.datetime):
        fecha_nacimiento = fecha_nacimiento.date()
        
    return temporada_activa - fecha_nacimiento.year


def calcular_categoria_competencia(fecha_nac_str) -> tuple:
    """
    Determina la categoría competitiva oficial FEVEDA basada estrictamente en la 
    edad técnica cumplida al 31 de diciembre del año en curso.
    Retorna: (Nombre de la categoría, Edad de competencia)
    """
    if not fecha_nac_str:
        return "Desconocida", 0
    try:
        fecha_nac = datetime.date.fromisoformat(str(fecha_nac_str))
    except Exception:
        return "Error Formato", 0
        
    ano_actual = datetime.date.today().year 
    edad_competencia = ano_actual - fecha_nac.year
    
    # Estructura de saltos de masificación, juveniles y máster oficiales
    if 5 <= edad_competencia <= 6:
        cat = "Preinfantil A"
    elif 7 <= edad_competencia <= 8:
        cat = "Preinfantil B"
    elif edad_competencia == 9:
        cat = "Preinfantil C"
    elif 10 <= edad_competencia < 12:
        cat = "Infantil A"
    elif 12 <= edad_competencia < 14:
        cat = "Infantil B"
    elif 14 <= edad_competencia < 16:
        cat = "Juvenil A"
    elif 16 <= edad_competencia < 18:
        cat = "Juvenil B"
    elif 18 <= edad_competencia < 25:
        cat = "Máxima"
    elif edad_competencia >= 25:
        cat = "Máster"
    else:
        cat = "Semillero / Menor"
        
    return cat, edad_competencia


def evaluar_elegibilidad_internacional(edad_tecnica: int, ente_rector: str) -> tuple:
    """
    Verifica si el nadador cumple con la edad mínima reglamentaria para eventos internacionales.
    Aplica para WORLD AQUATICS (Junior de 14 a 17) y PANAM AQUATICS.
    """
    entes_internacionales = ["PANAM AQUATICS", "WORLD AQUATICS"]
    if str(ente_rector).upper() in entes_internacionales:
        if edad_tecnica < 14:
            return False, f"Edad técnica insuficiente ({edad_tecnica} años). Mínimo reglamentario internacional: 14 años."
    return True, None


# =============================================================================
# 📍 SECCIÓN 2: MODELO DE IMPULSO-RESPUESTA FISIOLÓGICO (BANISTER / CALVERT)
# =============================================================================

def calcular_carga_fisiologica_tsb(df_diario: pd.DataFrame) -> pd.DataFrame:
    """
    Aplica el modelo de Banister/Calvert para calcular la carga acumulada del atleta.
    Procesa las constantes de tiempo internacionales:
    - tau_1 (42 días) -> CTL: Fitness a largo plazo.
    - tau_2 (7 días)  -> ATL: Fatiga a corto plazo.
    """
    if df_diario.empty:
        return pd.DataFrame(columns=['fecha', 'metros_totales', 'ctl', 'atl', 'tsb'])
        
    df_completo = df_diario.sort_values('fecha').copy()
    
    tau_1 = 42.0  
    tau_2 = 7.0   
    
    num_dias = len(df_completo)
    vector_carga = df_completo['metros_totales'].to_numpy(dtype=float)
    
    ctl = np.zeros(num_dias, dtype=float)
    atl = np.zeros(num_dias, dtype=float)
    
    for t in range(num_dias):
        if t == 0:
            ctl[t] = vector_carga[t]
            atl[t] = vector_carga[t]
        else:
            ctl[t] = ctl[t-1] * np.exp(-1.0 / tau_1) + vector_carga[t]
            atl[t] = atl[t-1] * np.exp(-1.0 / tau_2) + vector_carga[t]
            
    tsb = ctl - atl
    
    df_completo['ctl'] = np.round(ctl, 2)
    df_completo['atl'] = np.round(atl, 2)
    df_completo['tsb'] = np.round(tsb, 2)
    
    return df_completo


# =============================================================================
# 📍 SECCIÓN 3: MODELADO ASINTÓTICO Y CURVAS DE RENDIMIENTO (INNEGOCIABLE)
# =============================================================================

def resolver_k_individual(eq_t0, eq_T0, eq_t_pb, eq_T_pb, eq_t_peak, eq_T_target) -> float:
    """
    Resuelve numéricamente la constante de curvatura biológica k basándose estrictamente
    en la fracción de tiempo tau_eq del desarrollo del nadador.
    """
    if eq_t_peak > eq_t0 and eq_t_pb > eq_t0:
        tau_eq = (eq_t_pb - eq_t0) / (eq_t_peak - eq_t0)
        
        def ecuacion_k_eq(k_val):
            # Fórmula maestra original del archivo 10
            ter_exp = (np.exp(-k_val * tau_eq) - np.exp(-k_val)) / (1 - np.exp(-k_val))
            return (eq_T_target + (eq_T0 - eq_T_target) * ter_exp) - eq_T_pb
            
        k_opt_eq, _, _, _ = fsolve(ecuacion_k_eq, 1.0, full_output=True)
        return float(k_opt_eq[0])
    return 0.4


def calcular_curva_atleta(edades_arr, eq_t0, eq_T0, eq_t_pb, eq_T_pb, eq_t_peak, eq_T_target, k_eq, h_eq) -> np.ndarray:
    """
    Genera los tiempos proyectados del atleta aplicando la proporción tau_t antes del pico,
    y penalizando asintóticamente con el factor de rapidez de deriva (h) después del pico.
    """
    tiempos = []
    edades_arr = np.array(edades_arr, dtype=float)
    
    for t in edades_arr:
        if t < eq_t_pb:
            # Fase de desarrollo temprano basada en la fracción de tiempo tau_t
            tau_t = (t - eq_t0) / (eq_t_peak - eq_t0)
            ter_exp = (np.exp(-k_eq * tau_t) - np.exp(-k_eq)) / (1 - np.exp(-k_eq))
            tiempo_estimado = eq_T_target + (eq_T0 - eq_T_target) * ter_exp
        else:
            # Fase de madurez y deriva fisiológica post-pico
            # Mantiene continuidad matemática exacta con el diseño del archivo 10
            tiempo_estimado = eq_T_pb + (eq_T_target - eq_T_pb) * (1 - np.exp(-k_eq * (t - eq_t_pb)))
            if t > eq_t_peak:
                tiempo_estimado += h_eq * (t - eq_t_peak)
                
        tiempos.append(tiempo_estimado)
        
    return np.array(tiempos, dtype=float)


# =============================================================================
# 🧮 EXTENSIONES: SEGMENTACIÓN VECTORIAL Y GENERACIÓN DE MALLAS DE EDAD
# =============================================================================

def filtrar_atletas_por_categoria(lista_atletas: list, categoria_objetivo: str) -> list:
    """
    [Segmentación Vectorial Etaria - Archivo 11]
    Toma una lista cruda de atletas activos, evalúa su categoría oficial FEVEDA 
    basándose en su fecha de nacimiento y descarta a todos los que no pertenezcan 
    a la categoría seleccionada.
    
    Parámetros:
    -----------
    lista_atletas : list
        Lista de diccionarios con la estructura [{'id', 'nombre', 'fecha_nacimiento', 'genero'}, ...]
    categoria_objetivo : str
        Nombre exacto de la categoría FEVEDA seleccionada (ej. 'Infantil B')
        
    Retorna:
    --------
    list : Subconjunto filtrado de atletas que cumplen rigurosamente el criterio etario.
    """
    if not lista_atletas or not categoria_objetivo:
        return []
        
    atletas_filtrados = []
    for atleta in lista_atletas:
        fecha_nac = atleta.get("fecha_nacimiento")
        if not fecha_nac:
            continue
            
        # Invocación a tu función reglamentaria del Core
        cat_calculada, _ = calcular_categoria_competencia(fecha_nac)
        
        if cat_calculada.lower().strip() == categoria_objetivo.lower().strip():
            atletas_filtrados.append(atleta)
            
    return atletas_filtrados


def generar_malla_edades(t0: float, t_limite: float, num_puntos: int = 300) -> np.ndarray:
    """
    [Vectorización de Curvas - Archivos 11 y 12]
    Genera el entramado o malla continua de puntos decimales de edad (eje X)
    necesario para alimentar la fórmula maestra asintótica de rendimiento.
    
    Parámetros:
    -----------
    t0 : float
        Edad inicial del modelo biológico (t0).
    t_limite : float
        Edad límite para el vector de renderizado (puede ser t_peak o edad_max_zoom).
    num_puntos : int, opcional
        Densidad de la malla para garantizar curvas suaves en Matplotlib. Por defecto 300.
        
    Retorna:
    --------
    np.ndarray : Arreglo unidimensional de NumPy con el espaciado lineal exacto.
    """
    # Evita errores de inversión si los límites vienen corruptos o invertidos por el slider
    inicio = float(t0)
    fin = float(t_limite)
    
    if inicio >= fin:
        # Failsafe: si hay cruce o coincidencia, genera una ventana mínima de protección de 1 año
        fin = inicio + 1.0
        
    return np.linspace(inicio, fin, num=num_puntos)


determinar_categoria_fina = calcular_categoria_competencia