import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import fsolve
import pandas as pd
import sqlite3  # <- Adición segura para manejo de repositorio local

# 1. CONFIGURACIÓN DE LA PÁGINA
st.set_page_config(page_title="Simulador de Rendimiento de Natación", layout="wide")

# 2. INYECCIÓN DE CSS (Control de tamaño de títulos y métricas para móviles/web)
st.markdown(
    """
    <style>
    div[data-testid="stMetricValue"] {
        font-size: 22px !important;
    }
    div[data-testid="stMetricLabel"] {
        font-size: 13px !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Título con tamaño reducido controlado
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
# NUEVO: GESTIÓN DE REPOSITORIO LOCAL (SQLite) - Sustituye la sesión volátil
# -------------------------------------------------------------
DB_NAME = "natacion_repositorio.db"

def inicializar_base_datos():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS marcas_historicas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prueba TEXT NOT NULL,
            edad REAL NOT NULL,
            tiempo REAL NOT NULL,
            nota TEXT
        )
    """)
    conn.commit()
    
    # Si está vacía por ser la primera corrida, insertamos tus marcas base por defecto
    cursor.execute("SELECT COUNT(*) FROM marcas_historicas")
    if cursor.fetchone()[0] == 0:
        valores_base = [
            ("100 Libre", 9.80, 90.00, "Pstart - Registro Inicial"),
            ("100 Libre", 10.50, 81.20, "Paso de Control"),
            ("100 Libre", 11.30, 73.28, "PB Oficial Actual")
        ]
        cursor.executemany("INSERT INTO marcas_historicas (prueba, edad, tiempo, nota) VALUES (?, ?, ?, ?)", valores_base)
        conn.commit()
    conn.close()

# Ejecución inicial invisible
inicializar_base_datos()

# -------------------------------------------------------------
# BARRA LATERAL: ENTRADA DE DATOS (PRESERVADA AL 100%)
# -------------------------------------------------------------
st.sidebar.header("📊 Configuración de la Prueba")
titulo_grafico = st.sidebar.text_input("Estilo y Distancia:", value="100 Libre")

st.sidebar.subheader("⚙️ Modo del Modelo")
sincronizar_db = st.sidebar.checkbox("🚨 Adaptar Modelo a Base de Datos", value=False, 
                                     help="Si se activa, el punto inicial y el PB se calcularán automáticamente desde la tabla de abajo.")

st.sidebar.subheader("⏳ Hitos de Edad")
t0_manual = st.sidebar.number_input("Edad Start (t0):", min_value=5.0, max_value=20.0, value=9.80, step=0.01)
t_pb_manual = st.sidebar.number_input("Edad del PB Actual (t_pb):", min_value=t0_manual, max_value=30.0, value=11.30, step=0.01)
t_peak = st.sidebar.number_input("Edad Peak Proyectado (t_peak):", min_value=t_pb_manual, max_value=30.0, value=23.0, step=0.01)

st.sidebar.subheader("⏱️ Hitos de Tiempo")
T0_manual = st.sidebar.number_input("Tiempo Inicial (T0 en segundos):", min_value=1.0, value=90.0, step=0.1)
T_pb_manual = st.sidebar.number_input("Tiempo del PB Actual (T_pb en segundos):", min_value=1.0, value=73.28, step=0.01)
T_target = st.sidebar.number_input("Tiempo Objetivo Peak (T_target en segundos):", min_value=1.0, value=53.5, step=0.01)

st.sidebar.subheader("🎛️ Amortiguación de Deriva")
h = st.sidebar.slider("Factor de deriva manual (h):", min_value=0.1, max_value=1.0, value=0.4, step=0.05)

st.sidebar.subheader("🏆 Marcas de Referencia Internacional (y = c)")
m_ano = st.sidebar.number_input("a) Marca Mínima del Año:", min_value=0.0, value=71.5, step=0.1)
m_panam_a = st.sidebar.number_input("b) PANAM Jr - Marca A:", min_value=0.0, value=59.2, step=0.1)
m_panam_b = st.sidebar.number_input("c) PANAM Jr - Marca B:", min_value=0.0, value=61.8, step=0.1)
m_wa_a = st.sidebar.number_input("d) World Aquatics - Marca A:", min_value=0.0, value=54.25, step=0.1)
m_wa_b = st.sidebar.number_input("e) World Aquatics - Marca B:", min_value=0.0, value=56.15, step=0.1)
m_wr = st.sidebar.number_input("f) World Record:", min_value=0.0, value=51.71, step=0.1)

st.sidebar.subheader("🔍 Calculadora Intermedia")
t_intermedia = st.sidebar.slider("Consultar Edad Intermedia:", min_value=float(t0_manual), max_value=float(t_peak), value=14.0, step=0.1)

# -------------------------------------------------------------
# MODIFICADO: PROCESAMIENTO DESDE EL REPOSITORIO SQLITE
# -------------------------------------------------------------
# Extrae la información filtrada por la prueba escrita en la barra lateral
conn = sqlite3.connect(DB_NAME)
df_procesado = pd.read_sql_query(
    "SELECT id, edad AS Edad, tiempo AS Tiempo, nota AS Nota FROM marcas_historicas WHERE prueba = ? ORDER BY edad ASC", 
    conn, params=(titulo_grafico,)
)
conn.close()

# Lógica adaptativa idéntica e intacta
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
# MOTOR MATEMÁTICO (PRESERVADO AL 100% SIN ALTERACIONES)
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
# MODIFICADO: INTERFAZ DE ADMINISTRACIÓN INTERACTIVA DEL REPOSITORIO LOCAL
# -------------------------------------------------------------
st.subheader(f"🗃️ Repositorio Histórico de PBs ({titulo_grafico})")
st.markdown("*Los datos ingresados aquí se guardan de forma permanente en el almacenamiento local de tu dispositivo.*")

# Crear columnas inferiores para la entrada y visualización controlada
col_registro, col_tabla = st.columns([1, 2])

with col_registro:
    st.markdown("**Añadir Nueva Marca**")
    # Formulario controlado para inserción limpia
    with st.form("registro_atletas_form", clear_on_submit=True):
        ins_edad = st.number_input("Edad de logro:", min_value=5.0, max_value=30.0, value=11.50, step=0.01)
        ins_tiempo = st.number_input("Tiempo (segundos):", min_value=1.0, value=71.20, step=0.01)
        ins_nota = st.text_input("Competencia / Nota:", placeholder="Ej: Campeonato Nacional")
        
        if st.form_submit_button("💾 Guardar Marca"):
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO marcas_historicas (prueba, edad, tiempo, nota) VALUES (?, ?, ?, ?)", 
                (titulo_grafico, ins_edad, ins_tiempo, ins_nota)
            )
            conn.commit()
            conn.close()
            st.success("¡Guardado exitosamente!")
            st.rerun()

with col_tabla:
    st.markdown("**Registros en Base de Datos**")
    if len(df_procesado) > 0:
        # Formulario o botón para eliminación segura de filas por ID técnico
        id_eliminar = st.selectbox(
            "Eliminar un registro erróneo (Selecciona por ID):", 
            df_procesado["id"].tolist(),
            format_func=lambda x: f"ID {x} | Edad: {df_procesado[df_procesado['id']==x]['Edad'].values[0]:.2f}a -> {df_procesado[df_procesado['id']==x]['Tiempo'].values[0]:.2f}s"
        )
        if st.button("🗑️ Eliminar Fila Seleccionada"):
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM marcas_historicas WHERE id = ?", (id_eliminar,))
            conn.commit()
            conn.close()
            st.warning(f"Registro ID {id_eliminar} eliminado.")
            st.rerun()
            
        # Despliegue visual limpio excluyendo la columna ID interna
        st.dataframe(df_procesado.drop(columns=["id"]), use_container_width=True)
    else:
        st.info(f"No hay registros guardados para la prueba '{titulo_grafico}' en este dispositivo.")