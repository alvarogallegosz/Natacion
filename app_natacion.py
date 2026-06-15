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

# -------------------------------------------------------------
# CONEXIÓN SEGURA CON SUPABASE
# -------------------------------------------------------------
try:
    url: str = st.secrets["SUPABASE_URL"]
    key: str = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(url, key)
except Exception as e:
    st.error("Faltan las credenciales de Supabase en los Secrets de la aplicación. Revisa la configuración en Streamlit Cloud.")
    st.stop()

# -------------------------------------------------------------
# CONTROL DE ACCESO (AUTHENTICATION con Registro Integrado)
# -------------------------------------------------------------
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
    st.session_state.usuario_id = None
    st.session_state.nombre_nadador = ""

def login_usuario(user, password):
    try:
        response = supabase.table("usuarios").select("id, nombre").eq("usuario", user).eq("contrasena", password).execute()
        if response.data:
            st.session_state.autenticado = True
            st.session_state.usuario_id = response.data[0]["id"]
            st.session_state.nombre_nadador = response.data[0]["nombre"]
            return True
        return False
    except Exception as e:
        st.error(f"Error en la verificación de credenciales: {e}")
        return False

# Interfaz de acceso si el usuario no está logueado (Línea 56 Modificada)
if not st.session_state.autenticado:
    st.markdown("<h2 style='text-align: center;'>🔐 Acceso al Sistema de Control y Proyección de Rendimiento del Club de Natación Centro Gallego</h2>", unsafe_allow_html=True)
    
    c_login, _ = st.columns([1.5, 1.5])
    with c_login:
        tab_login, tab_registro = st.tabs(["🔑 Iniciar Sesión", "📝 Registrarse"])
        
        with tab_login:
            with st.form("form_login"):
                usuario_input = st.text_input("Usuario (Correo o Alias):")
                contrasena_input = st.text_input("Contraseña:", type="password")
                if st.form_submit_button("Ingresar"):
                    if login_usuario(usuario_input, contrasena_input):
                        st.success(f"¡Bienvenido, {st.session_state.nombre_nadador}!")
                        st.rerun()
                    else:
                        st.error("Usuario o contraseña incorrectos.")
                        
        with tab_registro:
            with st.form("form_registro"):
                nuevo_nombre = st.text_input("Nombre completo del Nadador:", placeholder="Ej: Natalia Gallegos")
                nuevo_usuario = st.text_input("Usuario para ingresar (Correo o Alias):", placeholder="Ej: natigallegosb@gmail.com")
                nueva_contrasena = st.text_input("Contraseña nueva:", type="password")
                
                if st.form_submit_button("🚀 Crear Cuenta y Entrar"):
                    if nuevo_nombre and nuevo_usuario and nueva_contrasena:
                        try:
                            chequeo = supabase.table("usuarios").select("id").eq("usuario", nuevo_usuario).execute()
                            if chequeo.data:
                                st.error("Este usuario ya se encuentra registrado. Intenta con otro o inicia sesión.")
                            else:
                                nuevo_registro = {
                                    "nombre": nuevo_nombre,
                                    "usuario": nuevo_usuario,
                                    "contrasena": nueva_contrasena
                                }
                                insercion = supabase.table("usuarios").insert(nuevo_registro).execute()
                                
                                if insercion.data:
                                    st.success("¡Cuenta creada exitosamente!")
                                    st.session_state.autenticado = True
                                    st.session_state.usuario_id = insercion.data[0]["id"]
                                    st.session_state.nombre_nadador = insercion.data[0]["nombre"]
                                    st.rerun()
                        except Exception as reg_err:
                            st.error(f"Error al conectar con la tabla de usuarios: {reg_err}")
                    else:
                        st.error("Por favor, completa todos los campos para poder registrarte.")
                        
    st.stop()

# Botón de cerrar sesión en la barra lateral
if st.sidebar.button("🚪 Cerrar Sesión"):
    st.session_state.autenticado = False
    st.session_state.usuario_id = None
    st.session_state.nombre_nadador = ""
    st.rerun()

# Mensaje de bienvenida personalizado con el nombre del nadador logueado
st.markdown(
    f"""
    <h1 style='font-size: 26px; font-weight: bold; color: #111111; margin-bottom: 0px;'>
        🏊‍♀️ Sistema Adaptativo - Expediente de {st.session_state.nombre_nadador}
    </h1>
    """, 
    unsafe_allow_html=True
)
st.markdown("---")

# -------------------------------------------------------------
# BASE DE DATOS DE RECORDS MUNDIALES (WR) OFICIALES (Piscina 50m)
# -------------------------------------------------------------
diccionario_wr = {
    "50 Libre": 20.91, "100 Libre": 46.80, "200 Libre": 102.00, "400 Libre": 212.27, "800 Libre": 443.52, "1500 Libre": 870.67,
    "50 Espalda": 23.55, "100 Espalda": 51.41, "200 Espalda": 111.92,
    "50 Mariposa": 22.27, "100 Mariposa": 49.45, "200 Mariposa": 110.34,
    "50 Pecho": 25.95, "100 Pecho": 56.88, "200 Pecho": 125.95,
    "200 Combinado": 114.00, "400 Combinado": 242.50
}

# -------------------------------------------------------------
# BARRA LATERAL: CONFIGURACIÓN DE LA PRUEBA
# -------------------------------------------------------------
st.sidebar.header("📊 Configuración de la Prueba")

lista_pruebas = list(diccionario_wr.keys())
titulo_grafico = st.sidebar.selectbox("Estilo y Distancia:", options=lista_pruebas, index=1)

wr_oficial = diccionario_wr[titulo_grafico]
tstart_predefinido_estimado = float(round(wr_oficial * 2.0, 2))

# MODO DEL MODELO
st.sidebar.subheader("⚙️ Modo del Modelo")
sincronizar_db = st.sidebar.checkbox("🚨 Adaptar Modelo a Base de Datos", value=False, 
                                     help="Si se activa, el punto inicial y el PB se extraerán automáticamente de tu historial en Supabase.")

# -------------------------------------------------------------
# CONSULTA EXCLUSIVA Y EXTRACCIÓN CRONOLÓGICA DE LA BASE DE DATOS
# -------------------------------------------------------------
try:
    response = supabase.table("marcas_historicas") \
        .select("id, edad, tiempo, nota") \
        .eq("prueba", titulo_grafico) \
        .eq("usuario_id", st.session_state.usuario_id) \
        .order("edad", desc=False).execute()  # Orden cronológico estricto (de menor a mayor edad)
        
    if response.data:
        df_procesado = pd.DataFrame(response.data)
        df_procesado = df_procesado.rename(columns={"edad": "Edad", "tiempo": "Tiempo", "nota": "Nota"})
        
        # El Punto Inicial (Start t0 y T0) siempre es el primer registro indexado (el más antiguo)
        db_t0 = float(df_procesado.iloc[0]["Edad"])
        db_T0 = float(df_procesado.iloc[0]["Tiempo"])
        
        n_registros = len(df_procesado)
        
        if n_registros == 1:
            db_t_pb = db_t0
            db_T_pb = db_T0
        elif n_registros == 2:
            # Con dos marcas, evaluamos directamente la menor de las dos para el hito PB
            if float(df_procesado.iloc[-1]["Tiempo"]) <= float(df_procesado.iloc[-2]["Tiempo"]):
                db_t_pb = float(df_procesado.iloc[-1]["Edad"])
                db_T_pb = float(df_procesado.iloc[-1]["Tiempo"])
            else:
                db_t_pb = float(df_procesado.iloc[-2]["Edad"])
                db_T_pb = float(df_procesado.iloc[-2]["Tiempo"])
        else:
            # ANÁLISIS METODOLÓGICO AVANZADO (3 o más competencias registradas)
            indice_min_tiempo = df_procesado["Tiempo"].idxmin()
            posicion_desde_el_final = (n_registros - 1) - indice_min_tiempo
            
            # Caso 1: Regresión prolongada (el menor tiempo histórico ocurrió de la antepenúltima hacia atrás)
            if posicion_desde_el_final >= 2:
                db_t_pb = float(df_procesado.iloc[-1]["Edad"])
                db_T_pb = float(df_procesado.iloc[-1]["Tiempo"])
            # Caso 2: El mejor tiempo está en el entorno reciente -> Se adopta rigurosamente la menor de las dos últimas marcas
            else:
                tiempo_ultima = float(df_procesado.iloc[-1]["Tiempo"])
                tiempo_penultima = float(df_procesado.iloc[-2]["Tiempo"])
                
                if tiempo_ultima <= tiempo_penultima:
                    db_t_pb = float(df_procesado.iloc[-1]["Edad"])
                    db_T_pb = tiempo_ultima
                else:
                    db_t_pb = float(df_procesado.iloc[-2]["Edad"])
                    db_T_pb = tiempo_penultima
                    
    else:
        df_procesado = pd.DataFrame(columns=["id", "Edad", "Tiempo", "Nota"])
        db_t0, db_T0, db_t_pb, db_T_pb = None, None, None, None
except Exception as err:
    st.error(f"Error al conectar con la tabla remota de Supabase: {err}")
    df_procesado = pd.DataFrame(columns=["id", "Edad", "Tiempo", "Nota"])
    db_t0, db_T0, db_t_pb, db_T_pb = None, None, None, None

# CONFIGURACIÓN DE VALORES POR DEFECTO DINÁMICOS EN LA UI
st.sidebar.subheader("⏳ Hitos Básicos")

val_t0 = db_t0 if (sincronizar_db and db_t0 is not None) else 9.80
val_T0 = db_T0 if (sincronizar_db and db_T0 is not None) else tstart_predefinido_estimado
val_t_pb = db_t_pb if (sincronizar_db and db_t_pb is not None) else 11.30
val_T_pb = db_T_pb if (sincronizar_db and db_T_pb is not None) else float(round(wr_oficial * 1.5, 2))

# 1. Edad Start (t0)
t0_input = st.sidebar.number_input("1. Edad Start (t0):", min_value=5.0, max_value=20.0, value=val_t0, step=0.01, disabled=sincronizar_db)
t0_manual = t0_input

# 2. Tstart (T0)
T0_input = st.sidebar.number_input("2. Tiempo Inicial (T0 en seg):", min_value=1.0, value=val_T0, step=0.1, disabled=sincronizar_db)
T0_manual = T0_input

# 3. Edad Peak (t_peak)
t_peak_input = st.sidebar.number_input("3. Edad Peak Proyectado (t_peak):", min_value=5.0, max_value=30.0, value=23.0, step=0.01)
t_peak = t_peak_input

# 4. Ttarget (T_target)
val_target_defecto = float(round(wr_oficial * 1.15, 2))
T_target_input = st.sidebar.number_input("4. Tiempo Objetivo Peak (T_target en seg):", min_value=1.0, value=val_target_defecto, step=0.01)
T_target = T_target_input

# 5. Edad PB (t_pb)
t_pb_input = st.sidebar.number_input("5. Edad del PB Actual (t_pb):", min_value=5.0, max_value=30.0, value=val_t_pb, step=0.01, disabled=sincronizar_db)
t_pb_manual = t_pb_input

# 6. Tpb (T_pb)
T_pb_input = st.sidebar.number_input("6. Tiempo del PB Actual (T_pb en seg):", min_value=1.0, value=val_T_pb, step=0.01, disabled=sincronizar_db)
T_pb_manual = T_pb_input

# CONDICIONAMIENTO DE VARIABLES FINALES PARA EL MOTOR
t0 = db_t0 if (sincronizar_db and db_t0 is not None) else t0_manual
T0 = db_T0 if (sincronizar_db and db_T0 is not None) else T0_manual
t_pb = db_t_pb if (sincronizar_db and db_t_pb is not None) else t_pb_manual
T_pb = db_T_pb if (sincronizar_db and db_T_pb is not None) else T_pb_manual

# AMORTIGUACIÓN DE LA DERIVA
st.sidebar.subheader("🎛️ Amortiguación de la Deriva")
h = st.sidebar.slider("Factor de deriva manual (h):", min_value=0.1, max_value=1.0, value=0.4, step=0.05)

# MARCAS DE REFERENCIA INTERNACIONAL AUTOMÁTICAS O AJUSTABLES
st.sidebar.subheader("🏆 Marcas de Referencia Internacional")
m_ano = st.sidebar.number_input("1. Marca Mínima del Año:", min_value=0.0, value=float(round(wr_oficial*1.4, 2)), step=0.1)
m_panam_b = st.sidebar.number_input("2. PANAM Jr - Marca B:", min_value=0.0, value=float(round(wr_oficial*1.25, 2)), step=0.1)
m_panam_a = st.sidebar.number_input("3. PANAM Jr - Marca A:", min_value=0.0, value=float(round(wr_oficial*1.18, 2)), step=0.1)
m_wa_b = st.sidebar.number_input("4. World Aquatics - Marca B:", min_value=0.0, value=float(round(wr_oficial*1.10, 2)), step=0.1)
m_wa_a = st.sidebar.number_input("5. World Aquatics - Marca A:", min_value=0.0, value=float(round(wr_oficial*1.05, 2)), step=0.1)
m_wr = st.sidebar.number_input("6. Record Mundial:", min_value=0.0, value=wr_oficial, step=0.01, disabled=True)

st.sidebar.subheader("🔍 Calculadora Intermedia")
t_intermedia = st.sidebar.slider("Consultar Edad Intermedia:", min_value=float(t0), max_value=float(t_peak), value=float(round((t0+t_peak)/2, 1)), step=0.1)

# -------------------------------------------------------------
# MOTOR MATEMÁTICO (PROTEGIDO CONTRA DIVISIONES POR CERO)
# -------------------------------------------------------------
if t_peak > t0 and t_pb > t0:
    tau = (t_pb - t0) / (t_peak - t0)
    D = T_pb - T_target

    def ecuacion_k(k_val):
        ter_exp = (np.exp(-k_val * tau) - np.exp(-k_val)) / (1 - np.exp(-k_val))
        T_predicho_f1 = T_target + (T0 - T_target) * ter_exp
        return T_predicho_f1 - T_pb

    k_inicial = 1.0
    k_optimizado, info, ier, mesg = fsolve(ecuacion_k, k_inicial, full_output=True)
    k = k_optimizado[0]
else:
    k, D = 0.0, 0.0

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
# DESPLIEGUE VISUAL Y GRÁFICO DINÁMICO
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

# AJUSTE ENCUADRE DE ESCALA Y ENTORNO VISUAL DINÁMICO
y_lim_inferior = m_wr * 0.95
y_lim_superior = max(T0, tstart_predefinido_estimado) * 1.05
ax.set_ylim(y_lim_inferior, y_lim_superior)

ax.set_title(f"Curva de Rendimiento Asintótica vs Trayectoria Real - {titulo_grafico}", fontsize=13, fontweight="bold", pad=12)
ax.set_xlabel("Edad Fisiológica (Años)", fontsize=11)
ax.set_ylabel("Tiempo de Carrera (Segundos)", fontsize=11)
ax.grid(True, linestyle=":", alpha=0.6)
ax.legend(loc="upper right", fontsize=9)

st.pyplot(fig)

# -------------------------------------------------------------
# INTERFAZ DE ESCRITURA CON INYECCIÓN DE USUARIO_ID
# -------------------------------------------------------------
st.subheader(f"🗃️ Repositorio Histórico de PBs ({titulo_grafico})")
st.markdown("*Los datos ingresados aquí se guardan de forma permanente y segura bajo tu perfil personal.*")

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
                    "nota": ins_nota if ins_nota else "",
                    "usuario_id": st.session_state.usuario_id
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
                supabase.table("marcas_historicas").delete() \
                    .eq("id", int(id_eliminar)) \
                    .eq("usuario_id", st.session_state.usuario_id).execute()
                st.warning(f"Registro ID {id_eliminar} eliminado de Supabase.")
                st.rerun()
            except Exception as delete_err:
                st.error(f"Error al eliminar en Supabase: {delete_err}")
            
        st.dataframe(df_procesado.drop(columns=["id"]), use_container_width=True)
    else:
        st.info(f"No tienes marcas registradas para '{titulo_grafico}' en tu cuenta.")