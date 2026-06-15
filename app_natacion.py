import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import fsolve
import pandas as pd
from supabase import create_client, Client

# 1. CONFIGURACIÓN DE LA PÁGINA
st.set_page_config(page_title="Simulador de Rendimiento de Natación", layout="wide")

# 2. INYECCIÓN DE CSS (Control de tamaño de títulos y métricas)
st.markdown(
    """
    <style>
    div[data-testid="stMetricValue"] { font-size: 22px !important; }
    div[data-testid="stMetricLabel"] { font-size: 13px !important; }
    </style>
    """,
    unsafe_allow_html=True
)

st.markdown(
    """
    <h1 style='font-size: 26px; font-weight: bold; color: #111111; margin-bottom: 0px;'>
        室内🏊‍♀️ Sistema Adaptativo y Metas de Natación
    </h1>
    """, 
    unsafe_allow_html=True
)
st.markdown("---")

# -------------------------------------------------------------
# CONEXIÓN SEGURA CON SUPABASE
# -------------------------------------------------------------
try:
    url: str = st.secrets["SUPABASE_URL"]
    key: str = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(url, key)
except Exception as e:
    st.error("Faltan las credenciales de Supabase en los Secrets de la aplicación. Revisa el archivo secrets.toml o la configuración de Streamlit Cloud.")
    st.stop()

# -------------------------------------------------------------
# BARRA LATERAL: REESTRUCTURACIÓN ESTRICTA Y CAMPOS SEGUROS
# -------------------------------------------------------------
st.sidebar.header("📊 Configuración de la Prueba")

# NUEVO: Lista desplegable estandarizada para evitar errores de transcripción
lista_pruebas = [
    "50 Libre", "100 Libre", "200 Libre", "400 Libre", "800 Libre", "1500 Libre",
    "50 Espalda", "100 Espalda", "200 Espalda",
    "50 Mariposa", "100 Mariposa", "200 Mariposa",
    "50 Pecho", "100 Pecho", "200 Pecho",
    "200 Combinado", "400 Combinado"
]

# Definimos "100 Libre" como la opción predeterminada al cargar (Index 1)
titulo_grafico = st.sidebar.selectbox("Estilo y Distancia:", opciones=lista_pruebas, index=1)

# b) Modo del modelo
st.sidebar.subheader("⚙️ Modo del Modelo")
sincronizar_db = st.sidebar.checkbox("🚨 Adaptar Modelo a Base de Datos", value=False, 
                                     help="Si se activa, el punto inicial y el PB se calcularán automáticamente desde Supabase.")

# c) Hitos básicos
st.sidebar.subheader("⏳ Hitos Básicos")

# 1. Edad Start (t0)
t0_input = st.sidebar.number_input("1. Edad Start (t0):", min_value=5.0, max_value=20.0, value=None, placeholder="Ej: 9.80", step=0.01, disabled=sincronizar_db)
t0_manual = t0_input if t0_input is not None else 9.80

# 2. Tstart (T0)
T0_input = st.sidebar.number_input("2. Tiempo Inicial (T0 en seg):", min_value=1.0, value=None, placeholder="Ej: 90.0", step=0.1, disabled=sincronizar_db)
T0_manual = T0_input if T0_input is not None else 90.0

# 3. Edad Peak (t_peak)
t_peak_input = st.sidebar.number_input("3. Edad Peak Proyectado (t_peak):", min_value=5.0, max_value=30.0, value=None, placeholder="Ej: 23.0", step=0.01)
t_peak = t_peak_input if t_peak_input is not None else 23.0

# 4. Ttarget (T_target)
T_target_input = st.sidebar.number_input("4. Tiempo Objetivo Peak (T_target en seg):", min_value=1.0, value=None, placeholder="Ej: 53.50", step=0.01)
T_target = T_target_input if T_target_input is not None else 53.50

# 5. Edad PB (t_pb)
t_pb_input = st.sidebar.number_input("5. Edad del PB Actual (t_pb):", min_value=5.0, max_value=30.0, value=None, placeholder="Ej: 11.30", step=0.01, disabled=sincronizar_db)
t_pb_manual = t_pb_input if t_pb_input is not None else 11.30

# 6. Tpb (T_pb)
T_pb_input = st.sidebar.number_input("6. Tiempo del PB Actual (T_pb en seg):", min_value=1.0, value=None, placeholder="Ej: 73.28", step=0.01, disabled=sincronizar_db)
T_pb_manual = T_pb_input if T_pb_input is not None else 73.28

# d) Amortiguación de la deriva
st.sidebar.subheader("🎛️ Amortiguación de la Deriva")
h = st.sidebar.slider("Factor de deriva manual (h):", min_value=0.1, max_value=1.0, value=0.4, step=0.05)

# e) Marcas de referencia internacional
st.sidebar.subheader("🏆 Marcas de Referencia Internacional")

m_ano_in = st.sidebar.number_input("1. Marca Mínima del Año:", min_value=0.0, value=None, placeholder="Ej: 71.5", step=0.1)
m_ano = m_ano_in if m_ano_in is not None else 71.5

m_panam_b_in = st.sidebar.number_input("2. PANAM Jr - Marca B:", min_value=0.0, value=None, placeholder="Ej: 61.8", step=0.1)
m_panam_b = m_panam_b_in if m_panam_b_in is not None else 61.8

m_panam_a_in = st.sidebar.number_input("3. PANAM Jr - Marca A:", min_value=0.0, value=None, placeholder="Ej: 59.2", step=0.1)
m_panam_a = m_panam_a_in if m_panam_a_in is not None else 59.2

m_wa_b_in = st.sidebar.number_input("4. World Aquatics - Marca B:", min_value=0.0, value=None, placeholder="Ej: 56.15", step=0.1)
m_wa_b = m_wa_b_in if m_wa_b_in is not None else 56.15

m_wa_a_in = st.sidebar.number_input("5. World Aquatics - Marca A:", min_value=0.0, value=None, placeholder="Ej: 54.25", step=0.1)
m_wa_a = m_wa_a_in if m_wa_a_in is not None else 54.25

m_wr_in = st.sidebar.number_input("6. Record Mundial:", min_value=0.0, value=None, placeholder="Ej: 51.71", step=0.1)
m_wr = m_wr_in if m_wr_in is not None else 51.71

st.sidebar.subheader("🔍 Calculadora Intermedia")
t_intermedia = st.sidebar.slider("Consultar Edad Intermedia:", min_value=float(t0_manual), max_value=float(t_peak), value=14.0, step=0.1)

# -------------------------------------------------------------
# EXTRACCIÓN CON EL PARÁMETRO CORRECTO PARA PYTHON (desc=False)
# -------------------------------------------------------------
try:
    response = supabase.table("marcas_historicas").select("id, edad, tiempo, nota").eq("prueba", titulo_grafico).order("edad", desc=False).execute()
    if response.data:
        df_procesado = pd.DataFrame(response.data)
        df_procesado = df_procesado.rename(columns={"edad": "Edad", "tiempo": "Tiempo", "nota": "Nota"})
    else:
        df_procesado = pd.DataFrame(columns=["id", "Edad", "Tiempo", "Nota"])
except Exception as err:
    st.error(f"Error al conectar con la tabla remota de Supabase: {err}")
    df_procesado = pd.DataFrame(columns=["id", "Edad", "Tiempo", "Nota"])

if sincronizar_db and len(df_procesado) >= 2:
    t0 = float(df_procesado.iloc[0]["Edad"])
    T0 = float(df_procesado.iloc[0]["Tiempo"])
    t_pb = float(df_procesado.iloc[-1]["Edad"])
    T_pb = float(df_procesado.iloc[-1]["Tiempo"])
else:
    t0 = t0_manual
    T0 = T0_manual
    t_pb = t_pb_manual
    T_pb = T_pb_manual

# -------------------------------------------------------------
# MOTOR MATEMÁTICO (PRESERVADO AL 100%)
# -------------------------------------------------------------
tau = (t_pb - t0) / (t_peak - t0)
D = T_pb - T_target

def ecuacion_k(k_val):
    ter_exp = (np.exp(-k_val * tau) - np.exp(-k_val)) / (1 - np.exp(-k_val))
    T_predicho_f1 = T_target + (T0 - T_target) * ter_exp
    return T_predicho_f1 - T_pb

k_inicial = 1.0
k_optimizado, info, ier, mesg = fsolve(ecuacion_k, k_inicial, full_output=True)
k = k_optimizado[0]

def calcular_tiempo_proyectado(t_array):
    tiempos = []
    for t in t_array:
        if t < t_pb:
            tau_t = (t - t0) / (t_peak - t0)
            ter_exp = (np.exp(-k * tau_t) - np.exp(-k)) / (1 - np.exp(-k))
            T_t = T_target + (T0 - T_target) * ter_exp
        else:
            T_t = T_pb - D * (1 - np.exp(-h * (t - t_pb)))
        tiempos.append(T_t)
    return np.array(tiempos)

# -------------------------------------------------------------
# LOGICA DE DESPLIEGUE VISUAL Y GRÁFICO (PRESERVADA AL 100%)
# -------------------------------------------------------------
edades_curva = np.linspace(t0, t_peak, 500)
tiempos_curva = calcular_tiempo_proyectado(edades_curva)

T_start_calc = calcular_tiempo_proyectado([t0])[0]
T_pb_calc = calcular_tiempo_proyectado([t_pb])[0]
T_peak_calc = calcular_tiempo_proyectado([t_peak])[0]
tiempo_intermedio_proyectado = calcular_tiempo_proyectado([t_intermedia])[0]

c1, c2, c3 = st.columns(3)
with c1: st.metric(label="Tasa de Mejora Calculada (k)", value=f"{k:.4f}")
with c2: st.metric(label="Deriva Total PB vs T_target (D)", value=f"{D:.2f} s")
with c3: st.metric(label=f"Predicción a los {t_intermedia:.1f} años", value=f"{tiempo_intermedio_proyectado:.2f} s")

fig, ax = plt.subplots(figsize=(11, 6.5))
ax.plot(edades_curva, tiempos_curva, color="#007A87", linewidth=2.5, label=f"Proyección Fisiológica ({titulo_grafico})")

if len(df_procesado) > 0:
    ax.plot(df_procesado["Edad"], df_procesado["Tiempo"], color="#D55E00", linestyle="--", linewidth=1.5, alpha=0.8)
    ax.scatter(df_procesado["Edad"], df_procesado["Tiempo"], color="#D55E00", edgecolor="black", s=45, label="Historial Real de PBs", zorder=3)

ax.axvline(x=t0, color="gray", linestyle="--", alpha=0.4)
ax.axvline(x=t_pb, color="red", linestyle="--", alpha=0.4)
ax.axvline(x=t_peak, color="green", linestyle="--", alpha=0.4)

ax.plot(t0, T_start_calc, 'o', color="gray", markersize=8, markeredgecolor='black', zorder=4)
ax.annotate(f"Pstart\n{t0:.2f}a\n{T_start_calc:.2f}s", xy=(t0, T_start_calc), xytext=(15, 5), textcoords="offset points", ha='left', va='bottom', fontsize=9, fontweight="bold", bbox=dict(boxstyle="round,pad=0.2", fc="white", alpha=0.7, ec="gray"))

ax.plot(t_pb, T_pb_calc, '*', color="gold", markersize=12, markeredgecolor='black', zorder=5, label="Hito PB Proyección")
ax.annotate(f"PB Actual\n{t_pb:.2f}a\n{T_pb_calc:.2f}s", xy=(t_pb, T_pb_calc), xytext=(0, 15), textcoords="offset points", ha='center', va='bottom', fontsize=9, fontweight="bold", bbox=dict(boxstyle="round,pad=0.2", fc="#FFE6CC", alpha=0.8, ec="red"))

ax.plot(t_peak, T_peak_calc, 's', color="green", markersize=8, markeredgecolor='black', zorder=4, label="Meta Peak")
ax.annotate(f"Ppeak\n{t_peak:.2f}a\n{T_peak_calc:.2f}s", xy=(t_peak, T_peak_calc), xytext=(15, 5), textcoords="offset points", ha='left', va='center', fontsize=9, fontweight="bold", bbox=dict(boxstyle="round,pad=0.2", fc="#E2F0D9", alpha=0.8, ec="green"))

ax.plot(t_intermedia, tiempo_intermedio_proyectado, 'ro', markersize=8, zorder=4, label="Punto Consultado")
ax.annotate(f"Consulta: {t_intermedia:.1f}a\n{tiempo_intermedio_proyectado:.2f}s", xy=(t_intermedia, tiempo_intermedio_proyectado), xytext=(15, 15), textcoords="offset points", bbox=dict(boxstyle="round,pad=0.3", fc="#FFCCCC", alpha=0.8, ec="red", lw=1), fontsize=9, fontweight="bold", zorder=6)

referencias = [
    {"valor": m_ano, "label": "Mín. Año", "color": "#E69F00", "style": ":"},
    {"valor": m_panam_b, "label": "PANAM Jr B", "color": "#009E73", "style": ":"},
    {"valor": m_panam_a, "label": "PANAM Jr A", "color": "#56B4E9", "style": "-."},
    {"valor": m_wa_b, "label": "WA Mín. B", "color": "#D55E00", "style": ":"},
    {"valor": m_wa_a, "label": "WA Mín. A", "color": "#CC79A7", "style": "-."},
    {"valor": m_wr, "label": "World Record", "color": "#000000", "style": "--"}
]

for ref in referencias:
    val = ref["valor"]
    if val > 0.0:
        ax.axhline(y=val, color=ref["color"], linestyle=ref["style"], linewidth=1.5, alpha=0.7)
        ax.text(t_peak - (t_peak - t0) * 0.02, val, f"{ref['label']}: {val:.2f}s", color=ref["color"], fontsize=8, fontweight="bold", va="bottom", ha="right")

ax.set_xlim(t0 - 0.5, t_peak + 1.0)
y_lim_inferior = (m_wr if m_wr > 0.0 else T_target) * 0.97
y_lim_superior = T0 * 1.03
ax.set_ylim(y_lim_inferior, y_lim_superior)

ax.set_title(f"Curva de Rendimiento Asintótica vs Trayectoria Real - {titulo_grafico}", fontsize=13, fontweight="bold", pad=12)
ax.set_xlabel("Edad Fisiológica (Años)", fontsize=11)
ax.set_ylabel("Tiempo de Carrera (Segundos)", fontsize=11)
ax.grid(True, linestyle=":", alpha=0.6)
ax.legend(loc="upper right", fontsize=9)

st.pyplot(fig)

# -------------------------------------------------------------
# INTERFAZ DE ESCRITURA/ELIMINACIÓN DIRECTA EN SUPABASE
# -------------------------------------------------------------
st.subheader(f"🗃️ Repositorio Histórico de PBs ({titulo_grafico})")
st.markdown("*Los datos ingresados aquí se guardan de forma permanente y segura en la base de datos de Supabase.*")

col_registro, col_tabla = st.columns([1, 2])

with col_registro:
    st.markdown("**Añadir Nueva Marca**")
    with st.form("registro_atletas_form", clear_on_submit=True):
        ins_edad_in = st.number_input("Edad de logro:", min_value=5.0, max_value=30.0, value=None, placeholder="Ej: 11.50", step=0.01)
        ins_tiempo_in = st.number_input("Tiempo (segundos):", min_value=1.0, value=None, placeholder="Ej: 71.20", step=0.01)
        ins_nota = st.text_input("Competencia / Nota:", placeholder="Ej: Campeonato Nacional")
        
        if st.form_submit_button("💾 Guardar Marca"):
            if ins_edad_in is not None and ins_tiempo_in is not None:
                nueva_marca = {
                    "prueba": titulo_grafico,
                    "edad": float(ins_edad_in),
                    "tiempo": float(ins_tiempo_in),
                    "nota": ins_nota if ins_nota else ""
                }
                try:
                    supabase.table("marcas_historicas").insert(nueva_marca).execute()
                    st.success("¡Guardado en Supabase exitosamente!")
                    st.rerun()
                except Exception as insert_err:
                    st.error(f"Error al escribir en Supabase: {insert_err}")
            else:
                st.error("Por favor, introduce al menos la Edad y el Tiempo antes de guardar.")

with col_tabla:
    st.markdown("**Registros en Base de Datos Remota**")
    if len(df_procesado) > 0:
        id_eliminar = st.selectbox(
            "Eliminar un registro erróneo (Selecciona por ID):", 
            df_procesado["id"].tolist(),
            format_func=lambda x: f"ID {x} | Edad: {df_procesado[df_procesado['id']==x]['Edad'].values[0]:.2f}a -> {df_procesado[df_procesado['id']==x]['Tiempo'].values[0]:.2f}s"
        )
        if st.button("🗑️ Eliminar Fila Seleccionada"):
            try:
                supabase.table("marcas_historicas").delete().eq("id", int(id_eliminar)).execute()
                st.warning(f"Registro ID {id_eliminar} eliminado de Supabase.")
                st.rerun()
            except Exception as delete_err:
                st.error(f"Error al eliminar en Supabase: {delete_err}")
            
        st.dataframe(df_procesado.drop(columns=["id"]), use_container_width=True)
    else:
        st.info(f"No hay registros guardados para la prueba '{titulo_grafico}' en la base de datos.")