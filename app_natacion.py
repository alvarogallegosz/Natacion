import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import fsolve
import pandas as pd
import datetime
import io
from supabase import create_client, Client

# 1. CONFIGURACIÓN DE LA PÁGINA
st.set_page_config(page_title="Simulador de proyección de rendimiento para natación", layout="wide")

st.markdown(
    """
    <style>
    div[data-testid="stMetricValue"] { font-size: 22px !important; }\r
    div[data-testid="stMetricLabel"] { font-size: 13px !important; }\r
    @media print {
        .no-print { display: none !important; }
        .print-only { display: block !important; }
    }
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
        
    ano_actual = datetime.date.today().year 
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
# FUNCIÓN AUXILIAR: CALCULAR EDAD DECIMAL EXACTA
# -------------------------------------------------------------
def calcular_edad_decimal(fecha_nacimiento_str, fecha_marca):
    if not fecha_nacimiento_str or not fecha_marca:
        return None
    try:
        if isinstance(fecha_nacimiento_str, str):
            fecha_nac_obj = datetime.date.fromisoformat(fecha_nacimiento_str)
        else:
            fecha_nac_obj = fecha_nacimiento_str
            
        diferencia_dias = (fecha_marca - fecha_nac_obj).days
        edad_decimal = diferencia_dias / 365.25
        return round(edad_decimal, 2)
    except Exception:
        return None

# -------------------------------------------------------------
# CONTROL DE ACCESO, REGISTRO Y RECUPERACIÓN DE SESIÓN UNIFICADO
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
    st.markdown("<h2 style='text-align: center;'>🏊‍♂️ Sistema de Proyección de Rendimiento y Gestión de Resultados en Competencia - Club de Natación Centro Gallego</h2>", unsafe_allow_html=True)
    c_login, _ = st.columns([1.5, 1.5])
    with c_login:
        tab_login, tab_registro, tab_recuperar = st.tabs(["🔑 Iniciar Sesión", "📝 Registro de Usuarios", "🔄 Recuperar Contraseña"])
        
        with tab_login:
            with st.form("form_login"):
                usuario_input = st.text_input("Usuario o Correo:")
                contrasena_input = st.text_input("Contraseña:", type="password")
                if st.form_submit_button("Ingresar"):
                    if login_usuario(usuario_input, contrasena_input):
                        st.success("Acceso autorizado.")
                        st.rerun()
                    else:
                        st.error("Credenciales incorrectas. Verifique sus datos o use la pestaña de recuperación.")
                        
        with tab_registro:
            st.markdown("### 📝 Registro de Nuevas Cuentas")
            nuevo_rol = st.selectbox("Seleccione el Rol para la nueva cuenta:", options=["Nadador", "Entrenador", "Administrador"], key="reg_rol_selector")
            es_nadador_reg = (nuevo_rol == "Nadador")
            
            with st.form("form_registro_dinamico"):
                nuevo_nombre = st.text_input("Nombre completo:")
                nuevo_usuario = st.text_input("Nombre de Usuario (Alias):")
                nuevo_email = st.text_input("Correo Electrónico:")
                nueva_contrasena = st.text_input("Establecer Contraseña:", type="password")
                
                nuevo_genero = None
                nueva_fecha_nac = None
                
                if es_nadador_reg:
                    st.markdown("---")
                    st.markdown("##### 🧬 Datos Biométricos Requeridos (Categorías Feveda)")
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
                                    "nombre": nuevo_nombre, 
                                    "usuario": nuevo_usuario, 
                                    "email": nuevo_email,
                                    "contrasena": nueva_contrasena, 
                                    "rol": nuevo_rol, 
                                    "estatus": "Activo",
                                    "genero": nuevo_genero if es_nadador_reg else None,
                                    "fecha_nacimiento": nueva_fecha_nac.isoformat() if (es_nadador_reg and nueva_fecha_nac) else None
                                }
                                supabase.table("usuarios").insert(nuevo_registro).execute()
                                st.success(f"¡Registro exitoso como **{nuevo_rol}**! Ya puede iniciar sesión.")
                        except Exception as reg_err:
                            st.error(f"Error en registro: {reg_err}")
                    else:
                        st.error("Por favor complete todos los datos obligatorios del formulario.")

        with tab_recuperar:
            st.markdown("### Restablecer Contraseña")
            with st.form("form_recuperacion"):
                rec_usuario = st.text_input("Nombre de Usuario (Alias):")
                rec_email = st.text_input("Correo Electrónico Asociado:")
                nueva_clave = st.text_input("Nueva Contraseña Deseada:", type="password")
                confirmar_clave = st.text_input("Confirmar Nueva Contraseña:", type="password")
                
                if st.form_submit_button("🔄 Actualizar Contraseña"):
                    if not (rec_usuario and rec_email and nueva_clave and confirmar_clave):
                        st.error("Todos los campos del formulario de recuperación son obligatorios.")
                    elif nueva_clave != confirmar_clave:
                        st.error("La confirmación no coincide con la nueva contraseña introducida.")
                    else:
                        try:
                            verificacion = supabase.table("usuarios").select("id, estatus").eq("usuario", rec_usuario).eq("email", rec_email).execute()
                            if verificacion.data:
                                user_info = verificacion.data[0]
                                if user_info.get("estatus") in ["Suspendido", "Bloqueado"]:
                                    st.error("Esta cuenta se encuentra suspendida o bloqueada por la administración.")
                                else:
                                    supabase.table("usuarios").update({"contrasena": nueva_clave}).eq("id", user_info["id"]).execute()
                                    st.success("✅ Contraseña actualizada correctamente.")
                            else:
                                st.error("❌ Los datos proporcionados no coinciden.")
                        except Exception as rec_err:
                            st.error(f"Error durante el proceso de restablecimiento: {rec_err}")
                            
    st.stop()

# -------------------------------------------------------------
# CONSTRUCCIÓN ORDENADA DE LA BARRA LATERAL (SIDEBAR)
# -------------------------------------------------------------
st.sidebar.markdown(f"**Usuario:** {st.session_state.nombre_nadador}  \n**Nivel:** `{st.session_state.rol}`")
if st.sidebar.button("🚪 Salir del Sistema"):
    st.session_state.autenticado = False
    st.rerun()

# Elemento 1: Panel de navegación
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

st.markdown(f"### 🏊‍♂️ Planificación y control de resultados de competencia: {st.session_state.nadador_seleccionado_nombre}")
st.markdown(f"**Género:** {'Masculino (M)' if st.session_state.nadador_seleccionado_genero == 'M' else 'Femenino (F)'} | **Categoría de Competencia Activa:** `{st.session_state.nadador_seleccionado_categoria}`")

# Elemento 2: Ajuste por prueba
st.sidebar.markdown("---")
st.sidebar.subheader("📊 Ajustes por prueba")
lista_pruebas = ['50 Libre', '100 Libre', '200 Libre', '50 Espalda', '100 Espalda', '200 Espalda', '50 Mariposa', '100 Mariposa', '200 Mariposa', '50 Pecho', '100 Pecho', '200 Pecho', '200 Combinado', '400 Combinado']
titulo_grafico = st.sidebar.selectbox("Estilo y Distancia:", options=lista_pruebas, index=0)

m_ano, m_panam_b, m_panam_a, m_wa_b, m_wa_a, m_wr = 0.0, 0.0, 0.0, 0.0, 0.0, 25.0
es_preinfantil = st.session_state.nadador_seleccionado_categoria.startswith("Preinfantil")

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

# Elemento 3: Adaptar modelo a Base de datos
sincronizar_db = st.sidebar.checkbox("🚨 Adaptar Modelo a Base de Datos", value=True)

# Elemento 4: Análisis Colectivo
modo_equipo = False
if st.session_state.rol in ["Entrenador", "Administrador"]:
    st.sidebar.markdown("---")
    st.sidebar.subheader("👥 Análisis Colectivo")
    modo_equipo = st.sidebar.checkbox("Activar Comparativa de Equipo", value=False)

# Elemento 5: Filtros de segmentación por equipos
tipo_filtro = "Todos los Atletas"
filtro_genero = "Todos"
cat_sel = None
ids_sel = []

if modo_equipo:
    st.sidebar.subheader("🔍 Filtros de Segmentación de Equipo")
    filtro_genero = st.sidebar.radio("Segmentar obligatoriamente por Género:", options=["Todos", "Femenino (F)", "Masculino (M)"])
    tipo_filtro = st.sidebar.radio("Segmentar adicionalmente por:", options=["Todos los Atletas", "Categoría Etaria", "Atletas Específicos"])
    
    try:
        resp_preload = supabase.table("usuarios").select("id, nombre, fecha_nacimiento, genero").eq("rol", "Nadador").eq("estatus", "Activo").execute()
        atletas_preload = resp_preload.data if resp_preload.data else []
        
        if filtro_genero == "Femenino (F)":
            atletas_preload = [a for a in atletas_preload if a["genero"] == "F"]
        elif filtro_genero == "Masculino (M)":
            atletas_preload = [a for a in atletas_preload if a["genero"] == "M"]

        if tipo_filtro == "Categoría Etaria" and atletas_preload:
            categorias_disponibles = sorted(list(set([calcular_categoria_competencia(a["fecha_nacimiento"])[0] for a in atletas_preload])))
            if categorias_disponibles:
                cat_sel = st.sidebar.selectbox("Seleccione la categoría:", options=categorias_disponibles)
                
        elif tipo_filtro == "Atletas Específicos" and atletas_preload:
            dict_nom = {a["id"]: a["nombre"] for a in atletas_preload}
            if dict_nom:
                ids_sel = st.sidebar.multiselect("Seleccione nadadores:", options=list(dict_nom.keys()), format_func=lambda x: dict_nom[x])
    except Exception as e:
        st.sidebar.error("Error cargando los filtros secundarios.")

# Carga de datos históricos base para el cálculo de límites
try:
    response = supabase.table("marcas_historicas") \
        .select("id, edad, tiempo, nota") \
        .eq("prueba", titulo_grafico) \
        .eq("usuario_id", st.session_state.nadador_seleccionado_id) \
        .order("edad", desc=False).execute()
        
    if response.data:
        df_procesado = pd.DataFrame(response.data)
        df_procesado = df_procesado.rename(columns={"edad": "Edad", "tiempo": "Tiempo", "nota": "Evento / Fecha"})
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
            
            if posicion_desde_el_final >= 2:
                db_t_pb, db_T_pb = float(df_procesado.iloc[-1]["Edad"]), float(df_procesado.iloc[-1]["Tiempo"])
            else:
                t_ultima, t_penultima = float(df_procesado.iloc[-1]["Tiempo"]), float(df_procesado.iloc[-2]["Tiempo"])
                if t_ultima <= t_penultima:
                    db_t_pb, db_T_pb = float(df_procesado.iloc[-1]["Edad"]), t_ultima
                else:
                    db_t_pb, db_T_pb = float(df_procesado.iloc[-2]["Edad"]), t_penultima
    else:
        df_procesado = pd.DataFrame(columns=["id", "Edad", "Tiempo", "Evento / Fecha"])
        db_t0, db_T0, db_t_pb, db_T_pb = None, None, None, None
except Exception:
    df_procesado = pd.DataFrame(columns=["id", "Edad", "Tiempo", "Evento / Fecha"])
    db_t0, db_T0, db_t_pb, db_T_pb = None, None, None, None

val_t0 = db_t0 if (sincronizar_db and db_t0 is not None) else 10.0
val_T0 = db_T0 if (sincronizar_db and db_T0 is not None) else float(round(m_wr * 1.8, 2))
val_t_pb = db_t_pb if (sincronizar_db and db_t_pb is not None) else 12.0
val_T_pb = db_T_pb if (sincronizar_db and db_T_pb is not None) else float(round(m_wr * 1.3, 2))
val_T_target = float(round(m_wa_a * 0.99, 2)) if m_wa_a > 0 else float(round(m_wr * 1.08, 2))

# Elemento 6: Celdas de edad y tiempos para limites y PB
st.sidebar.markdown("---")
st.sidebar.subheader("📐 Parámetros de Límites y PB")
t0 = st.sidebar.number_input("1. Edad Start (t0):", min_value=4.0, value=val_t0, step=0.01, disabled=sincronizar_db)
T0 = st.sidebar.number_input("2. Tiempo Inicial (T0):", min_value=1.0, value=val_T0, step=0.1, disabled=sincronizar_db)
t_peak = st.sidebar.number_input("3. Edad Peak Proyectado (t_peak):", min_value=5.0, max_value=30.0, value=23.0)
T_target = st.sidebar.number_input("4. Tiempo Objetivo Peak (T_target):", min_value=1.0, value=val_T_target)
t_pb = st.sidebar.number_input("5. Edad del PB de Control (t_pb):", min_value=4.0, value=val_t_pb, step=0.01, disabled=sincronizar_db)
T_pb = st.sidebar.number_input("6. Tiempo del PB de Control (T_pb):", min_value=1.0, value=val_T_pb, step=0.01, disabled=sincronizar_db)

# Elemento 7: Factores ajustables de rapidez de deriva y edad intermedia
st.sidebar.markdown("---")
st.sidebar.subheader("⏱️ Rapidez de Deriva e Intervalo")
h = st.sidebar.slider("Factor ajustable de rapidez de deriva (h):", min_value=0.1, max_value=1.0, value=0.4, step=0.05)
t_intermedia = st.sidebar.slider("Consultar Edad Intermedia:", min_value=float(t0), max_value=float(t_peak), value=float(round((t0+t_peak)/2, 1)), step=0.1)


# MOTOR MATEMÁTICO ASINTÓTICO GENERAL
def resolver_k_individual(eq_t0, eq_T0, eq_t_pb, eq_T_pb, eq_t_peak, eq_T_target):
    if eq_t_peak > eq_t0 and eq_t_pb > eq_t0:
        tau_eq = (eq_t_pb - eq_t0) / (eq_t_peak - eq_t0)
        def ecuacion_k_eq(k_val):
            ter_exp = (np.exp(-k_val * tau_eq) - np.exp(-k_val)) / (1 - np.exp(-k_val))
            return (eq_T_target + (eq_T0 - eq_T_target) * ter_exp) - eq_T_pb
        k_opt_eq, _, _, _ = fsolve(ecuacion_k_eq, 1.0, full_output=True)
        return k_opt_eq[0]
    return 0.4

def calcular_curva_atleta(edades_arr, eq_t0, eq_T0, eq_t_pb, eq_T_pb, eq_t_peak, eq_T_target, k_eq, h_eq):
    tiempos = []
    D_eq = eq_T_pb - eq_T_target
    for t in edades_arr:
        if t < eq_t_pb:
            tau_t = (t - eq_t0) / (eq_t_peak - eq_t0)
            ter_exp = (np.exp(-k_eq * tau_t) - np.exp(-k_eq)) / (1 - np.exp(-k_eq))
            T_t = eq_T_target + (eq_T0 - eq_T_target) * ter_exp
        else:
            T_t = eq_T_pb - D_eq * (1 - np.exp(-h_eq * (t - eq_t_pb)))
        tiempos.append(T_t)
    return np.array(tiempos)

# Valores de control del perfil principal
k = resolver_k_individual(t0, T0, t_pb, T_pb, t_peak, T_target)

c1, c2, c3 = st.columns(3)
with c1: st.metric(label="Factor de Ajuste Fisiológico (k)", value=f"{k:.4f}")
with c2: st.metric(label="Margen de Deriva de Seguridad (D)", value=f"{(T_pb - T_target):.2f} s")
with c3: 
    T_intermedia_val = float(calcular_curva_atleta([t_intermedia], t0, T0, t_pb, T_pb, t_peak, T_target, k, h)[0])
    st.metric(label=f"Proyección a los {t_intermedia:.1f} años", value=f"{T_intermedia_val:.2f} s")

# -------------------------------------------------------------
# RENDIMIENTO GRÁFICO (MODO EQUIPO - LÓGICA DE LÍMITES CORREGIDA)
# -------------------------------------------------------------
if modo_equipo:
    try:
        resp_todos = supabase.table("usuarios").select("id, nombre, fecha_nacimiento, genero").eq("rol", "Nadador").eq("