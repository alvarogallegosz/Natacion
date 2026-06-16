import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import fsolve
import pandas as pd
import datetime
from supabase import create_client, Client

# 1. CONFIGURACIÓN DE LA PÁGINA
st.set_page_config(page_title="Simulador de Natación - Categorías Etarias", layout="wide")

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
    st.error("Faltan las credenciales de Supabase en los Secrets de la aplicación.")
    st.stop()

# -------------------------------------------------------------
# LÓGICA DE CATEGORÍAS ETARIAS (Edad cumplida al 31 de Diciembre)
# -------------------------------------------------------------
def calcular_categoria_competencia(fecha_nac_str):
    if not fecha_nac_str:
        return "Desconocida", 0
    try:
        fecha_nac = datetime.date.fromisoformat(str(fecha_nac_str))
    except Exception:
        return "Error Formato", 0
        
    ano_actual = datetime.date.today().year # Dinámico basado en el entorno de ejecución (2026)
    edad_competencia = ano_actual - fecha_nac.year
    
    if 5 <= edad_competencia <= 6:
        cat = "Preinfantil A"
    elif 7 <= edad_competencia <= 8:
        cat = "Preinfantil B"
    elif edad_competencia == 9:
        cat = "Preinfantil C"
    elif 10 <= edad_competencia <= 11:
        cat = "Infantil A"
    elif 12 <= edad_competencia <= 13:
        cat = "Infantil B"
    elif 14 <= edad_competencia <= 15:
        cat = "Juvenil A"
    elif 16 <= edad_competencia <= 18:
        cat = "Juvenil B"
    elif edad_competencia > 18:
        cat = "Máxima"
    else:
        cat = "Semillero / Menor"
        
    return cat, edad_competencia

# -------------------------------------------------------------
# CONTROL DE ACCESO Y SESIÓN
# -------------------------------------------------------------
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
    st.session_state.usuario_id = None
    st.session_state.nombre_nadador = ""
    st.session_state.genero = "F"
    st.session_state.rol = "Nadador"
    st.session_state.fecha_nacimiento = None
    st.session_state.categoria_atleta = ""
    st.session_state.edad_comp_atleta = 0
    # Atleta bajo análisis activo
    st.session_state.nadador_seleccionado_id = None
    st.session_state.nadador_seleccionado_nombre = ""
    st.session_state.nadador_seleccionado_genero = "F"
    st.session_state.nadador_seleccionado_categoria = ""

def login_usuario(user, password):
    try:
        response = supabase.table("usuarios").select("id, nombre, genero, rol, estatus, fecha_nacimiento").eq("usuario", user).eq("contrasena", password).execute()
        if response.data:
            user_data = response.data[0]
            if user_data.get("estatus", "Activo") in ["Suspendido", "Bloqueado"]:
                st.error(f"❌ Cuenta {user_data['estatus']}. Contacte a la dirección técnica.")
                return False
                
            st.session_state.autenticado = True
            st.session_state.usuario_id = user_data["id"]
            st.session_state.nombre_nadador = user_data["nombre"]
            st.session_state.genero = user_data.get("genero", "F")
            st.session_state.rol = user_data.get("rol", "Nadador")
            st.session_state.fecha_nacimiento = user_data.get("fecha_nacimiento")
            
            cat, ed_c = calcular_categoria_competencia(st.session_state.fecha_nacimiento)
            st.session_state.categoria_atleta = cat
            st.session_state.edad_comp_atleta = ed_c
            
            # Inicializar selección activa por defecto
            st.session_state.nadador_seleccionado_id = user_data["id"]
            st.session_state.nadador_seleccionado_nombre = user_data["nombre"]
            st.session_state.nadador_seleccionado_genero = user_data.get("genero", "F")
            st.session_state.nadador_seleccionado_categoria = cat
            return True
        return False
    except Exception as e:
        st.error(f"Error en Login: {e}")
        return False

if not st.session_state.autenticado:
    st.markdown("<h2 style='text-align: center;'>🏊‍♂️ Sistema de Proyección de Rendimiento y Gestión de Categorías Feveda</h2>", unsafe_allow_html=True)
    c_login, _ = st.columns([1.5, 1.5])
    with c_login:
        tab_login, tab_registro = st.tabs(["🔑 Iniciar Sesión", "📝 Registro de Usuarios"])
        
        with tab_login:
            with st.form("form_login"):
                usuario_input = st.text_input("Usuario / Correo:")
                contrasena_input = st.text_input("Contraseña:", type="password")
                if st.form_submit_button("Ingresar"):
                    if login_usuario(usuario_input, contrasena_input):
                        st.success("Acceso autorizado.")
                        st.rerun()
                        
        with tab_registro:
            with st.form("form_registro"):
                nuevo_nombre = st.text_input("Nombre completo:")
                nuevo_usuario = st.text_input("Nombre de Usuario (Alias):")
                nuevo_email = st.text_input("Correo Electrónico:")
                nueva_contrasena = st.text_input("Establecer Contraseña:", type="password")
                nuevo_rol = st.selectbox("Rol en el Sistema:", options=["Nadador", "Entrenador", "Administrador"])
                
                nuevo_genero = "F"
                nueva_fecha_nac = None
                
                if nuevo_rol == "Nadador":
                    st.markdown("---")
                    nuevo_genero = st.selectbox("Género:", options=["F", "M"], format_func=lambda x: "Femenino" if x == "F" else "Masculino")
                    nueva_fecha_nac = st.date_input("Fecha de Nacimiento:", min_value=datetime.date(1950, 1, 1), max_value=datetime.date.today())
                
                if st.form_submit_button("🚀 Crear Cuenta en el Sistema"):
                    if nuevo_nombre and nuevo_usuario and nueva_contrasena and nuevo_email:
                        try:
                            chequeo = supabase.table("usuarios").select("id").eq("usuario", nuevo_usuario).execute()
                            if chequeo.data:
                                st.error("El nombre de usuario ya está tomado.")
                            else:
                                nuevo_registro = {
                                    "nombre": nuevo_nombre, "usuario": nuevo_usuario, "email": nuevo_email,
                                    "contrasena": nueva_contrasena, 
                                    "genero": nuevo_genero if nuevo_rol == "Nadador" else None,
                                    "fecha_nacimiento": nueva_fecha_nac.isoformat() if (nuevo_rol == "Nadador" and nueva_fecha_nac) else None, 
                                    "rol": nuevo_rol, "estatus": "Activo"
                                }
                                supabase.table("usuarios").insert(nuevo_registro).execute()
                                st.success(f"¡Registro exitoso como **{nuevo_rol}**! Ya puede iniciar sesión.")
                        except Exception as reg_err:
                            st.error(f"Error en registro: {reg_err}")
                    else:
                        st.error("Por favor complete todos los datos del formulario.")
    st.stop()

# -------------------------------------------------------------
# CONSOLA LATERAL: SELECCIÓN GLOBAL DE ATLETAS (ENTRENADOR / ADMIN)
# -------------------------------------------------------------
st.sidebar.markdown(f"**Usuario:** {st.session_state.nombre_nadador}  \n**Nivel:** `{st.session_state.rol}`")
if st.sidebar.button("🚪 Salir del Sistema"):
    st.session_state.autenticado = False
    st.rerun()

if st.session_state.rol in ["Entrenador", "Administrador"]:
    st.sidebar.subheader("🎯 Panel de Navegación de Atletas")
    try:
        resp_atletas = supabase.table("usuarios").select("id, nombre, genero, fecha_nacimiento").eq("rol", "Nadador").eq("estatus", "Activo").execute()
        if resp_atletas.data:
            df_atl = pd.DataFrame(resp_atletas.data)
            dict_atletas = dict(zip(df_atl["id"], df_atl["nombre"]))
            
            sel_id = st.sidebar.selectbox("Monitorear Nadador:", options=list(dict_atletas.keys()), format_func=lambda x: dict_atletas[x])
            atleta_row = df_atl[df_atl["id"] == sel_id].iloc[0]
            
            st.session_state.nadador_seleccionado_id = int(atleta_row["id"])
            st.session_state.nadador_seleccionado_nombre = atleta_row["nombre"]
            st.session_state.nadador_seleccionado_genero = atleta_row["genero"]
            
            cat_calc, _ = calcular_categoria_competencia(atleta_row["fecha_nacimiento"])
            st.session_state.nadador_seleccionado_categoria = cat_calc
    except Exception as e:
        st.sidebar.error("Error cargando nómina de atletas.")
else:
    st.session_state.nadador_seleccionado_id = st.session_state.usuario_id
    st.session_state.nadador_seleccionado_nombre = st.session_state.nombre_nadador
    st.session_state.nadador_seleccionado_genero = st.session_state.genero
    st.session_state.nadador_seleccionado_categoria = st.session_state.categoria_atleta

# Encabezado con información del atleta seleccionado
st.markdown(f"### 出租️ Plan de Trabajo: {st.session_state.nadador_seleccionado_nombre}")
st.markdown(f"**Género:** {'Masculino (M)' if st.session_state.nadador_seleccionado_genero == 'M' else 'Femenino (F)'} | **Categoría de Competencia Activa:** `{st.session_state.nadador_seleccionado_categoria}`")

# -------------------------------------------------------------
# CONFIGURACIÓN DE LA PRUEBA Y EXTRACCIÓN DE MARCAS CON FILTRO DE CATEGORÍA
# -------------------------------------------------------------
st.sidebar.header("📊 Ajustes de Carrera")
lista_pruebas = ['50 Libre', '100 Libre', '200 Libre', '50 Espalda', '100 Espalda', '200 Espalda', '50 Mariposa', '100 Mariposa', '200 Mariposa', '50 Pecho', '100 Pecho', '200 Pecho', '200 Combinado', '400 Combinado']
titulo_grafico = st.sidebar.selectbox("Estilo y Distancia:", options=lista_pruebas, index=0)

# Inicializar marcas por defecto
m_ano, m_panam_b, m_panam_a, m_wa_b, m_wa_a, m_wr = 0.0, 0.0, 0.0, 0.0, 0.0, 25.0
es_preinfantil = st.session_state.nadador_seleccionado_categoria.startswith("Preinfantil")

# Solo buscamos marcas mínimas si el nadador NO es Preinfantil
if not es_preinfantil:
    try:
        ref_resp = supabase.table("marcas_referencia").select("*")\
            .eq("prueba", titulo_grafico)\
            .eq("genero", st.session_state.nadador_seleccionado_genero)\
            .eq("categoria", st.session_state.nadador_seleccionado_categoria).execute()
        if ref_resp.data:
            ref_data = ref_resp.data[0]
            m_ano = float(ref_data["m_ano"]) if ref_data["m_ano"] else 0.0
            m_panam_b = float(ref_data["m_panam_b"]) if ref_data["m_panam_b"] else 0.0
            m_panam_a = float(ref_data["m_panam_a"]) if ref_data["m_panam_a"] else 0.0
            m_wa_b = float(ref_data["m_wa_b"]) if ref_data["m_wa_b"] else 0.0
            m_wa_a = float(ref_data["m_wa_a"]) if ref_data["m_wa_a"] else 0.0
            m_wr = float(ref_data["m_wr"]) if ref_data["m_wr"] else 25.0
    except Exception as e:
        st.error(f"Error extrayendo marcas de la categoría: {e}")

sincronizar_db = st.sidebar.checkbox("🚨 Adaptar Modelo a Base de Datos", value=True)

# -------------------------------------------------------------
# EXTRACCIÓN CRONOLÓGICA DE MARCAS DESDE LA BASE DE DATOS
# -------------------------------------------------------------
try:
    response = supabase.table("marcas_historicas") \
        .select("id, edad, tiempo, nota") \
        .eq("prueba", titulo_grafico) \
        .eq("usuario_id", st.session_state.nadador_seleccionado_id) \
        .order("edad", desc=False).execute()
        
    if response.data:
        df_procesado = pd.DataFrame(response.data)
        df_procesado = df_procesado.rename(columns={"edad": "Edad", "tiempo": "Tiempo", "nota": "Nota"})
        db_t0 = float(df_procesado.iloc[0]["Edad"])
        db_T0 = float(df_procesado.iloc[0]["Tiempo"])
        n_registros = len(df_procesado)
        
        if n_registros == 1:
            db_t_pb, db_T_pb = db_t0, db_T0
        elif n_registros == 2:
            if float(df_procesado.iloc[-1]["Tiempo"]) <= float(df_procesado.iloc[-2]["Tiempo"]):
                db_t_pb, db_T_pb = float(df_procesado.iloc[-1]["Edad"]), float(df_procesado.iloc[-1]["Tiempo"])
            else:
                db_t_pb, db_T_pb = float(df_procesado.iloc[-2]["Edad"]), float(df_procesado.iloc[-2]["Tiempo"])
        else:
            indice_min_tiempo = df_procesado["Tiempo"].idxmin()
            posicion_desde_el_final = (n_registros - 1) - indice_min_tiempo
            
            if posicion_desde_el_final >= 2: # Regresión
                db_t_pb, db_T_pb = float(df_procesado.iloc[-1]["Edad"]), float(df_procesado.iloc[-1]["Tiempo"])
            else: # Menor de las dos últimas marcas
                t_ultima, t_penultima = float(df_procesado.iloc[-1]["Tiempo"]), float(df_procesado.iloc[-2]["Tiempo"])
                if t_ultima <= t_penultima:
                    db_t_pb, db_T_pb = float(df_procesado.iloc[-1]["Edad"]), t_ultima
                else:
                    db_t_pb, db_T_pb = float(df_procesado.iloc[-2]["Edad"]), t_penultima
    else:
        df_procesado = pd.DataFrame(columns=["id", "Edad", "Tiempo", "Nota"])
        db_t0, db_T0, db_t_pb, db_T_pb = None, None, None, None
except Exception:
    df_procesado = pd.DataFrame(columns=["id", "Edad", "Tiempo", "Nota"])
    db_t0, db_T0, db_t_pb, db_T_pb = None, None, None, None

# Controles Dinámicos de la UI
val_t0 = db_t0 if (sincronizar_db and db_t0 is not None) else 10.0
val_T0 = db_T0 if (sincronizar_db and db_T0 is not None) else float(round(m_wr * 1.8, 2))
val_t_pb = db_t_pb if (sincronizar_db and db_t_pb is not None) else 12.0
val_T_pb = db_T_pb if (sincronizar_db and db_T_pb is not None) else float(round(m_wr * 1.3, 2))

t0 = st.sidebar.number_input("1. Edad Start (t0):", min_value=4.0, value=val_t0, step=0.01, disabled=sincronizar_db)
T0 = st.sidebar.number_input("2. Tiempo Inicial (T0):", min_value=1.0, value=val_T0, step=0.1, disabled=sincronizar_db)
t_peak = st.sidebar.number_input("3. Edad Peak Proyectado (t_peak):", min_value=5.0, max_value=30.0, value=22.0)
T_target = st.sidebar.number_input("4. Tiempo Objetivo Peak (T_target):", min_value=1.0, value=float(round(m_wr * 1.08, 2)))
t_pb = st.sidebar.number_input("5. Edad del PB de Control (t_pb):", min_value=4.0, value=val_t_pb, step=0.01, disabled=sincronizar_db)
T_pb = st.sidebar.number_input("6. Tiempo del PB de Control (T_pb):", min_value=1.0, value=val_T_pb, step=0.01, disabled=sincronizar_db)
h = st.sidebar.slider("Factor de deriva manual (h):", min_value=0.1, max_value=1.0, value=0.4, step=0.05)

t_intermedia = st.sidebar.slider("Consultar Edad Intermedia:", min_value=float(t0), max_value=float(t_peak), value=float(round((t0+t_peak)/2, 1)), step=0.1)

# -------------------------------------------------------------
# MOTOR MATEMÁTICO ASINTÓTICO
# -------------------------------------------------------------
if t_peak > t0 and t_pb > t0:
    tau = (t_pb - t0) / (t_peak - t0)
    D = T_pb - T_target
    def ecuacion_k(k_val):
        ter_exp = (np.exp(-k_val * tau) - np.exp(-k_val)) / (1 - np.exp(-k_val))
        return (T_target + (T0 - T_target) * ter_exp) - T_pb
    k_opt, _, _, _ = fsolve(ecuacion_k, 1.0, full_output=True)
    k = k_opt[0]
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

T_intermedia_val = float(calcular_tiempo_proyectado([t_intermedia])[0])

c1, c2, c3 = st.columns(3)
with c1: st.metric(label="Factor de Ajuste Fisiológico (k)", value=f"{k:.4f}")
with c2: st.metric(label="Margen de Deriva de Seguridad (D)", value=f"{D:.2f} s")
with c3: st.metric(label=f"Proyección a los {t_intermedia:.1f} años", value=f"{T_intermedia_val:.2f} s")

# -------------------------------------------------------------
# RENDERIZADO GRÁFICO DINÁMICO (RESTALURADO CON MÁXIMO DETALLE)
# -------------------------------------------------------------
edades_curva = np.linspace(t0, t_peak, 500)
tiempos_curva = calcular_tiempo_proyectado(edades_curva)

fig, ax = plt.subplots(figsize=(11, 5.8))

# 1. Trazar curvas principales
ax.plot(edades_curva, tiempos_curva, color="#007A87", linewidth=2.5, label="Proyección Fisiológica")

if len(df_procesado) > 0:
    ax.plot(df_procesado["Edad"], df_procesado["Tiempo"], color="#D55E00", linestyle="--", alpha=0.4, label="Evolución Real (PBs)")
    ax.scatter(df_procesado["Edad"], df_procesado["Tiempo"], color="#D55E00", edgecolor="black", s=35, zorder=3)

# 2. Marcadores específicos de los Hitos Clave (Start, PB, Peak e Intermedio)
ax.scatter(t0, T0, color="#7F8C8D", edgecolor="black", s=50, zorder=4)
ax.scatter(t_pb, T_pb, color="#F1C40F", marker="*", edgecolor="black", s=130, zorder=5, label="PB Actual de Control")
ax.scatter(t_peak, T_target, color="#2ECC71", marker="s", edgecolor="black", s=50, zorder=4, label="Meta Peak")
ax.scatter(t_intermedia, T_intermedia_val, color="red", marker="o", s=45, zorder=5, label="Punto Consultado")

# 3. Líneas Verticales de Referencia Estructural
ax.axvline(x=t0, color="#7F8C8D", linestyle=":", linewidth=1.2, alpha=0.7)
ax.axvline(x=t_pb, color="red", linestyle="--", linewidth=1.2, alpha=0.6)
ax.axvline(x=t_peak, color="#2ECC71", linestyle=":", linewidth=1.2, alpha=0.7)
ax.axvline(x=t_intermedia, color="red", linestyle=":", linewidth=1.0, alpha=0.5)

# 4. Cuadros de Texto Informativos Dinámicos (Bboxes)
offset_y = (T0 - T_target) * 0.035
ax.text(t0 + 0.15, T0, f"P. Start\n{t0:.2f}a\n{T0:.2f}s", fontsize=8.5, va="bottom", ha="left", 
        bbox=dict(boxstyle="round,pad=0.3", fc="#FFF2CC", ec="#D6B656", alpha=0.85, lw=0.7))

ax.text(t_pb, T_pb + offset_y, f"PB Actual\n{t_pb:.2f}a\n{T_pb:.2f}s", fontsize=8.5, va="bottom", ha="center", 
        bbox=dict(boxstyle="round,pad=0.3", fc="#FCE5CD", ec="#B45F06", alpha=0.85, lw=0.7))

ax.text(t_intermedia, T_intermedia_val + offset_y, f"Consulta: {t_intermedia:.1f}a\n{T_intermedia_val:.2f}s", fontsize=8.5, va="bottom", ha="center", 
        bbox=dict(boxstyle="round,pad=0.3", fc="#F4CCCC", ec="#CC0000", alpha=0.85, lw=0.7))

# 5. Dibujar marcas horizontales únicamente si NO es categoría Preinfantil
if not es_preinfantil:
    referencias = [
        {"val": m_ano, "lbl": "Mín. Año", "col": "#E69F00"},
        {"val": m_panam_b, "lbl": "PANAM Jr B", "col": "#009E73"},
        {"val": m_panam_a, "lbl": "PANAM Jr A", "col": "#56B4E9"},
        {"val": m_wa_b, "lbl": "WA B", "col": "#D55E00"},
        {"val": m_wa_a, "lbl": "WA A", "col": "#CC79A7"},
        {"val": m_wr, "lbl": "World Record", "col": "#000000"}
    ]
    for r in referencias:
        if r["val"] > 0:
            ax.axhline(y=r["val"], color=r["col"], linestyle=":", linewidth=1.2)
            ax.text(t_peak, r["val"], f" {r['lbl']}: {r['val']:.2f}s", color=r["col"], fontsize=8, fontweight="bold", va="bottom")
else:
    ax.axhline(y=m_wr, color="#000000", linestyle="--", linewidth=1.2)
    ax.text(t_peak, m_wr, f" WR Base: {m_wr:.2f}s", color="#000000", fontsize=8, fontweight="bold", va="bottom")
    st.info("ℹ️ Las categorías Preinfantiles se consideran de desarrollo formativo y no poseen marcas mínimas exigidas.")

# 6. Rotulado, Leyendas Estéticas y Ejes
ax.set_title(f"Curva de Rendimiento Asintótica - {titulo_grafico} | Categoría: {st.session_state.nadador_seleccionado_categoria}", fontsize=12, fontweight="bold", pad=12)
ax.set_xlabel("Edad del Atleta (Anos)", fontsize=10, fontweight="bold")
ax.set_ylabel("Tiempo de Carrera (Segundos)", fontsize=10, fontweight="bold")
ax.grid(True, linestyle=":", alpha=0.5)
ax.legend(loc="upper right", fontsize=9, framealpha=0.9)

st.pyplot(fig)

# -------------------------------------------------------------
# MÓDULOS DE GESTIÓN SEGÚN ROL
# -------------------------------------------------------------
st.markdown("---")
tab_marcas, tab_entrenador, tab_admin = st.tabs(["📋 Control de Marcas", "⏱️ Configurar Tiempos por Categoría (Entrenador)", "🛡️ Consola Global (Admin)"])

with tab_marcas:
    col_ins, col_vistas = st.columns([1, 2])
    with col_ins:
        st.markdown("**Ingresar Nueva Marca**")
        with st.form("form_insertar_marca", clear_on_submit=True):
            ins_edad = st.number_input("Edad de logro:", min_value=4.0, max_value=30.0, step=0.01)
            ins_tiempo = st.number_input("Tiempo Oficial (seg):", min_value=1.0, step=0.01)
            ins_nota = st.text_input("Sede / Evento:")
            
            if st.form_submit_button("💾 Guardar Registro"):
                if st.session_state.rol in ["Entrenador", "Administrador"] or st.session_state.usuario_id == st.session_state.nadador_seleccionado_id:
                    nueva_m = {
                        "prueba": titulo_grafico, "edad": float(ins_edad), "tiempo": float(ins_tiempo),
                        "nota": ins_nota, "usuario_id": st.session_state.nadador_seleccionado_id
                    }
                    supabase.table("marcas_historicas").insert(nueva_m).execute()
                    st.success("Marca guardada.")
                    st.rerun()
                    
    with col_vistas:
        st.markdown("**Historial Cronológico de Tiempos**")
        if len(df_procesado) > 0:
            if st.session_state.rol in ["Entrenador", "Administrador"]:
                id_del = st.selectbox("Eliminar registro (ID):", options=df_procesado["id"].tolist())
                if st.button("🗑️ Eliminar Fila"):
                    supabase.table("marcas_historicas").delete().eq("id", int(id_del)).execute()
                    st.warning("Registro removido.")
                    st.rerun()
            st.dataframe(df_procesado.drop(columns=["id"]), use_container_width=True)

with tab_entrenador:
    if st.session_state.rol in ["Entrenador", "Administrador"]:
        st.markdown(f"### ⚙️ Umbrales de Competencia para la Categoría: `{st.session_state.nadador_seleccionado_categoria}`")
        if es_preinfantil:
            st.warning("⚠️ No se definen marcas mínimas reguladas para los niveles Preinfantiles.")
        
        with st.form("form_update_referencias"):
            u_cat = st.selectbox("Categoría a Modificar u Organizar:", options=["Infantil A", "Infantil B", "Juvenil A", "Juvenil B", "Máxima"])
            u_ano = st.number_input("Marca Mínima Año (seg):", value=m_ano if u_cat == st.session_state.nadador_seleccionado_categoria else 0.0)
            u_panamb = st.number_input("PANAM Jr - Marca B (seg):", value=m_panam_b if u_cat == st.session_state.nadador_seleccionado_categoria else 0.0)
            u_panama = st.number_input("PANAM Jr - Marca A (seg):", value=m_panam_a if u_cat == st.session_state.nadador_seleccionado_categoria else 0.0)
            u_wab = st.number_input("World Aquatics - Marca B (seg):", value=m_wa_b if u_cat == st.session_state.nadador_seleccionado_categoria else 0.0)
            u_waa = st.number_input("World Aquatics - Marca A (seg):", value=m_wa_a if u_cat == st.session_state.nadador_seleccionado_categoria else 0.0)
            u_wr = st.number_input("Record Mundial de Estilo Absoluto:", value=m_wr)
            
            if st.form_submit_button("⚡ Guardar Configuración de Tiempos"):
                up_data = {
                    "m_ano": u_ano, "m_panam_b": u_panamb, "m_panam_a": u_panama,
                    "m_wa_b": u_wab, "m_wa_a": u_waa, "m_wr": u_wr
                }
                supabase.table("marcas_referencia").upsert({
                    "prueba": titulo_grafico, "genero": st.session_state.nadador_seleccionado_genero,
                    "categoria": u_cat, **up_data
                }, on_conflict="prueba,genero,categoria").execute()
                st.success(f"Tiempos de referencia actualizados para {u_cat} ({st.session_state.nadador_seleccionado_genero}).")
                st.rerun()
    else:
        st.warning("🔒 Requiere credenciales de Dirección Técnica o Entrenador.")

with tab_admin:
    if st.session_state.rol == "Administrador":
        st.markdown("### 🛡️ Consola de Control de Usuarios e Integridad de Datos")
        try:
            resp_usuarios = supabase.table("usuarios").select("id, nombre, usuario, email, rol, genero, estatus, fecha_nacimiento").execute()
            if resp_usuarios.data:
                df_usr = pd.DataFrame(resp_usuarios.data)
                st.dataframe(df_usr, use_container_width=True)
                
                st.markdown("**Editar Perfil de Usuario**")
                c_sel, c_rol, c_est, c_gen = st.columns(4)
                with c_sel:
                    id_mod = st.selectbox("ID Usuario:", options=df_usr["id"].tolist())
                    user_actual = df_usr[df_usr["id"] == id_mod].iloc[0]
                with c_rol:
                    nuevo_rol_user = st.selectbox("Rol:", options=["Nadador", "Entrenador", "Administrador"], index=["Nadador", "Entrenador", "Administrador"].index(user_actual["rol"]))
                with c_est:
                    nuevo_est_user = st.selectbox("Estatus:", options=["Activo", "Suspendido", "Bloqueado"], index=["Activo", "Suspendido", "Bloqueado"].index(user_actual["estatus"]))
                with c_gen:
                    nuevo_gen_user = st.selectbox("Género:", options=["F", "M"], index=["F", "M"].index(user_actual["genero"]))
                
                nueva_f_nac_admin = st.date_input("Corregir Fecha Nacimiento:", value=datetime.date.fromisoformat(user_actual["fecha_nacimiento"]) if user_actual["fecha_nacimiento"] else datetime.date.today())
                
                if st.button("⚠️ Forzar Cambios de Perfil"):
                    supabase.table("usuarios").update({
                        "rol": nuevo_rol_user, "estatus": nuevo_est_user, 
                        "genero": nuevo_gen_user, "fecha_nacimiento": nueva_f_nac_admin.isoformat()
                    }).eq("id", int(id_mod)).execute()
                    st.success("Cambios aplicados con éxito.")
                    st.rerun()
        except Exception as e:
            st.error(f"Error en panel de control: {e}")
    else:
        st.warning("🔒 Acceso restringido al Administrador del sistema.")