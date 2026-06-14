import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import fsolve

# Configuración de la página
st.set_page_config(page_title="Simulador de Rendimiento Proyectado de Natación", layout="wide")
st.markdown(
    """
    <style>
    /* Reduce el tamaño del número */
    div[data-testid="stMetricValue"] {
        font-size: 22px !important; /* El tamaño por defecto suele ser ~40px */
    }
    /* Reduce el tamaño de la etiqueta superior (opcional) */
    div[data-testid="stMetricLabel"] {
        font-size: 13px !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)
st.subheader("🏊‍♀️ Sistema de Proyección y Metas de Rendimiento para Natación")
st.markdown("---")

# -------------------------------------------------------------
# BARRA LATERAL: ENTRADA DE DATOS
# -------------------------------------------------------------
st.sidebar.header("📊 Configuración de la Prueba")
titulo_grafico = st.sidebar.text_input("Estilo y Distancia:", value="100 Libre")

st.sidebar.subheader("⏳ Hitos de Edad")
t0 = st.sidebar.number_input("Edad Start (t0):", min_value=5.0, max_value=20.0, value=9.0, step=0.01)
t_pb = st.sidebar.number_input("Edad del PB Actual (t_pb):", min_value=t0, max_value=30.0, value=9.0, step=0.01)
t_peak = st.sidebar.number_input("Edad Peak Proyectado (t_peak):", min_value=t_pb, max_value=30.0, value=23.0, step=0.01)

st.sidebar.subheader("⏱️ Hitos de Tiempo")
T0 = st.sidebar.number_input("Tiempo Inicial (T0 en segundos):", min_value=1.0, value=1.0, step=0.1)
T_pb = st.sidebar.number_input("Tiempo del PB Actual (T_pb en segundos):", min_value=1.0, value=1.0, step=0.01)
T_target = st.sidebar.number_input("Tiempo Objetivo Peak (T_target en segundos):", min_value=1.0, value=1.0, step=0.01)

st.sidebar.subheader("🎛️ Amortiguación de Deriva")
h = st.sidebar.slider("Factor de deriva manual (h):", min_value=0.1, max_value=1.0, value=0.3, step=0.05)

# NUEVA SECCIÓN: MARCAS CONSTANTES DE REFERENCIA
st.sidebar.subheader("🏆 Marcas de Referencia Internacional (y = c)")
st.sidebar.markdown("*Dejar en 0.0 para ocultar en el gráfico*")
m_ano = st.sidebar.number_input("a) Marca Mínima del Año:", min_value=0.0, value=0.0, step=0.1)
m_panam_a = st.sidebar.number_input("b) PANAM Jr - Marca A:", min_value=0.0, value=0.0, step=0.1)
m_panam_b = st.sidebar.number_input("c) PANAM Jr - Marca B:", min_value=0.0, value=0.0, step=0.1)
m_wa_a = st.sidebar.number_input("d) World Aquatics - Marca A:", min_value=0.0, value=0.0, step=0.1)
m_wa_b = st.sidebar.number_input("e) World Aquatics - Marca B:", min_value=0.0, value=0.0, step=0.1)
m_wr = st.sidebar.number_input("f) World Record:", min_value=0.0, value=0.0, step=0.1)

# CONSULTA INTERMEDIA
st.sidebar.subheader("🔍 Calculadora Intermedia")
t_intermedia = st.sidebar.slider("Consultar Edad Intermedia:", min_value=float(t0), max_value=float(t_peak), value=15.0, step=0.1)

# -------------------------------------------------------------
# MOTOR MATEMÁTICO (Ecuación Exponencial Inversa)
# -------------------------------------------------------------
# 1. Cálculo de Tau (Proporción biológica)
tau = (t_pb - t0) / (t_peak - t0)

# 2. Cálculo automático del GAP de deriva (D)
D = T_pb - T_target

# 3. Solver dinámico para la tasa de mejora (k) en la Fase 1
def ecuacion_k(k_val):
    # Condición obligatoria: T_predicho en t_pb debe ser igual a T_pb
    # Evaluamos la primera parte de tu fórmula de Excel
    ter_exp = (np.exp(-k_val * tau) - np.exp(-k_val)) / (1 - np.exp(-k_val))
    T_predicho_f1 = T_target + (T0 - T_target) * ter_exp
    return T_predicho_f1 - T_pb

# Iteramos de forma segura para hallar k
k_inicial = 1.0
k_optimizado, info, ier, mesg = fsolve(ecuacion_k, k_inicial, full_output=True)
k = k_optimizado[0]

# 4. Función de predicción continua para todo el rango de edades
def calcular_tiempo_proyectado(t_array):
    tiempos = []
    for t in t_array:
        if t < t_pb:
            # Fase 1: Trayectoria inicial orientada al PB
            tau_t = (t - t0) / (t_peak - t0)
            ter_exp = (np.exp(-k * tau_t) - np.exp(-k)) / (1 - np.exp(-k))
            T_t = T_target + (T0 - T_target) * ter_exp
        else:
            # Fase 2: Amortiguación post-PB controlada por 'h' buscando la asíntota
            T_t = T_pb - D * (1 - np.exp(-h * (t - t_pb)))
        tiempos.append(T_t)
    return np.array(tiempos)

# -------------------------------------------------------------
# LOGICA DE DESPLIEGUE VISUAL (CON LÍMITES DE EJES DINÁMICOS)
# -------------------------------------------------------------
# Generación de la curva
edades_curva = np.linspace(t0, t_peak, 500)
tiempos_curva = calcular_tiempo_proyectado(edades_curva)

# Cálculo exacto de los tiempos en los hitos clave para las etiquetas
T_start_calc = calcular_tiempo_proyectado([t0])[0]
T_pb_calc = calcular_tiempo_proyectado([t_pb])[0]
T_peak_calc = calcular_tiempo_proyectado([t_peak])[0]

# Cálculo del punto parcial solicitado
tiempo_intermedio_proyectado = calcular_tiempo_proyectado([t_intermedia])[0]

# Métricas rápidas en la interfaz
c1, c2, c3 = st.columns(3)
with c1:
    st.metric(label="Tasa de Mejora Calculada (k)", value=f"{k:.4f}")
with c2:
    st.metric(label="Deriva Total PB vs T_target (D)", value=f"{D:.2f} s")
with c3:
    st.metric(label=f"Predicción a los {t_intermedia:.1f} años", value=f"{tiempo_intermedio_proyectado:.2f} s")

# Diseño del gráfico con Matplotlib
fig, ax = plt.subplots(figsize=(11, 7))

# 1. Curva principal
ax.plot(edades_curva, tiempos_curva, color="#007A87", linewidth=2.5, label=f"Proyección Fisiológica ({titulo_grafico})")

# 2. Líneas base de los hitos (Verticales discretas)
ax.axvline(x=t0, color="gray", linestyle="--", alpha=0.4)
ax.axvline(x=t_pb, color="red", linestyle="--", alpha=0.4)
ax.axvline(x=t_peak, color="green", linestyle="--", alpha=0.4)

# 3. RENDERIZADO DE HITOS CLAVE (Puntos + Etiquetas con markeredgecolor)
# -------------------------------------------------------------
# Hito: Pstart
ax.plot(t0, T_start_calc, 'o', color="gray", markersize=8, markeredgecolor='black', zorder=4)
ax.annotate(
    f"Pstart\n{t0:.2f}a\n{T_start_calc:.2f}s",
    xy=(t0, T_start_calc),
    xytext=(15, 5), 
    textcoords="offset points",
    ha='left', va='bottom',
    fontsize=9, fontweight="bold",
    bbox=dict(boxstyle="round,pad=0.2", fc="white", alpha=0.7, ec="gray")
)

# Hito: PB (Punto de quiebre)
ax.plot(t_pb, T_pb_calc, '*', color="gold", markersize=12, markeredgecolor='black', zorder=5, label="PB Actual")
ax.annotate(
    f"PB Actual\n{t_pb:.2f}a\n{T_pb_calc:.2f}s",
    xy=(t_pb, T_pb_calc),
    xytext=(0, 15), 
    textcoords="offset points",
    ha='center', va='bottom',
    fontsize=9, fontweight="bold",
    bbox=dict(boxstyle="round,pad=0.2", fc="#FFE6CC", alpha=0.8, ec="red")
)

# Hito: Ppeak (Meta de la asíntota)
ax.plot(t_peak, T_peak_calc, 's', color="green", markersize=8, markeredgecolor='black', zorder=4, label="Meta Peak")
ax.annotate(
    f"Ppeak\n{t_peak:.2f}a\n{T_peak_calc:.2f}s",
    xy=(t_peak, T_peak_calc),
    xytext=(15, 5), 
    textcoords="offset points",
    ha='left', va='center',
    fontsize=9, fontweight="bold",
    bbox=dict(boxstyle="round,pad=0.2", fc="#E2F0D9", alpha=0.8, ec="green")
)

# 4. Marcador y etiqueta dinámica para el Punto Proyectado Parcial
ax.plot(t_intermedia, tiempo_intermedio_proyectado, 'ro', markersize=8, zorder=4, label="Punto Consultado")
ax.annotate(
    f"Consulta: {t_intermedia:.1f}a\n{tiempo_intermedio_proyectado:.2f}s",
    xy=(t_intermedia, tiempo_intermedio_proyectado),
    xytext=(15, 15),
    textcoords="offset points",
    bbox=dict(boxstyle="round,pad=0.3", fc="#FFCCCC", alpha=0.8, ec="red", lw=1),
    fontsize=9, fontweight="bold", zorder=6
)

# 5. Funciones Constantes de Referencia (y = c)
referencias = [
    {"valor": m_ano, "label": "Mín. Año", "color": "#E69F00", "style": ":"},
    {"valor": m_panam_a, "label": "PANAM Jr A", "color": "#56B4E9", "style": "-."},
    {"valor": m_panam_b, "label": "PANAM Jr B", "color": "#009E73", "style": ":"},
    {"valor": m_wa_a, "label": "WA Mín. A", "color": "#CC79A7", "style": "-."},
    {"valor": m_wa_b, "label": "WA Mín. B", "color": "#D55E00", "style": ":"},
    {"valor": m_wr, "label": "World Record", "color": "#000000", "style": "--"}
]

for ref in referencias:
    val = ref["valor"]
    if val > 0.0:
        ax.axhline(y=val, color=ref["color"], linestyle=ref["style"], linewidth=1.5, alpha=0.7)
        ax.text(
            t_peak - (t_peak - t0) * 0.02, val, f"{ref['label']}: {val:.2f}s",
            color=ref["color"], fontsize=8, fontweight="bold",
            va="bottom", ha="right"
        )

# 6. Formateo estético del gráfico y ENCUEBRE DE EJES SOLICITADO
# -------------------------------------------------------------
ax.set_title(f"Curva de Rendimiento Asintótica - {titulo_grafico}", fontsize=12, fontweight="bold", pad=15)
ax.set_xlabel("Edad Fisiológica (Años)", fontsize=11)
ax.set_ylabel("Tiempo de Carrera (Segundos)", fontsize=11)

# Límites estrictos para el eje X (Edad): 6 meses antes de t0 hasta 1 año después de t_peak
ax.set_xlim(t0 - 0.5, t_peak + 1.0)

# Límites estrictos para el eje Y (Tiempo): 3% menos del WR (abajo) hasta 3% más de Tstart (arriba)
y_lim_inferior = (m_wr if m_wr > 0.0 else T_target) * 0.97
y_lim_superior = T0 * 1.03
ax.set_ylim(y_lim_inferior, y_lim_superior)

ax.grid(True, linestyle=":", alpha=0.6)
ax.legend(loc="upper right", fontsize=9)

# Despliegue en Streamlit
st.pyplot(fig)
