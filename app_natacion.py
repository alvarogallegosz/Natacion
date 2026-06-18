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
# SERVICIO SIMULADO DE NOTIFICACIONES ELECTRÓNICAS
# -------------------------------------------------------------
def enviar_correo_sistema(destinatario: str, asunto: str, cuerpo: str):
    """Simula el envío de notificaciones de auditoría y gobernanza."""
    st.info(f"📧 **Notificación enviada a:** `{destinatario}`\n*Asunto:* {asunto}\n*Contenido:* {cuerpo}")

# -------------------------------------------------------------
# LÓGICA DE CATEGORÍAS ETARIAS (Edad cumplida al 31 de Diciembre)
# -------------------------------------------------------------
def calcular_categoria_competencia(fecha_nac_str):
    if not fecha_nac_str or str(fecha_nac_str).lower() == 'nan':
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
    if not fecha_nacimiento_str or not fecha_marca or str(fecha_nacimiento_str).lower() == 'nan':
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
# CONTROL DE ACCESO (CORREGIDO: 'rol' y 'estatus')
# -------------------------------------------------------------
if "autenticado" not in st.session_state:
    st.session_state.update({"autenticado": False, "usuario_id": None, "rol": "Nadador", "nombre_nadador": ""})

def login_usuario(user, password):
    try:
        # Asegúrate de que el select y las llaves usen los términos en español
response = supabase.table("usuarios").select("id, nombre, email, genero, rol, estatus, fecha_nacimiento").eq("usuario", user).eq("contrasena", password).execute()
if response.data:
    user_data = response.data[0]
    if user_data.get("estatus") in ["Suspendido", "Bloqueado", "Inactivo"]: # <-- CAMBIADO
        # ...
    st.session_state.rol = user_data.get("rol", "Nadador") # <-- CAMBIADO
                st.error(f"🔒 Acceso denegado: Estatus '{user_data['estatus']}'.")
                return False
                
            st.session_state.update({
                "autenticado": True,
                "usuario_id": user_data["id"],
                "nombre_nadador": user_data["nombre"],
                "rol": user_data.get("rol", "Nadador"),
                "fecha_nacimiento": user_data.get("fecha_nacimiento")
            })
            return True
        return False
    except Exception as e:
        st.error(f"Error: {e}")
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
                        st.error("Credenciales incorrectas o cuenta no autorizada.")
                        
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
                                estatus_inicial = "Activo" if es_nadador_reg else "Inactivo"
                                
                                nuevo_registro = {
                                    "nombre": nuevo_nombre, 
                                    "usuario": nuevo_usuario, 
                                    "email": nuevo_email,
                                    "contrasena": nueva_contrasena, 
                                    "rol": nuevo_rol, 
                                    "estatus": estatus_inicial,
                                    "genero": nuevo_genero if es_nadador_reg else None,
                                    "fecha_nacimiento": nueva_fecha_nac.isoformat() if (es_nadador_reg and nueva_fecha_nac) else None
                                }
                                supabase.table("usuarios").insert(nuevo_registro).execute()
                                
                                if estatus_inicial == "Inactivo":
                                    st.warning(f"⚠️ Registro Recibido: Su cuenta como **{nuevo_rol}** se ha creado con estatus 'Inactivo' por seguridad. Se ha enviado una solicitud de autorización al Administrador global.")
                                    enviar_correo_sistema(
                                        destinatario="direcciontecnica.asocgallego@gmail.com",
                                        asunto="SOLICITUD: Alta de Cuenta de Personal Técnico",
                                        cuerpo=f"El usuario {nuevo_nombre} ({nuevo_email}) ha solicitado registrarse con el rol de '{nuevo_rol}'. Por favor, revise su perfil en la Consola Global y cambie su estatus a 'Activo' para permitirle el ingreso."
                                    )
                                else:
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
                            verificacion = supabase.table("usuarios").select("id, status").eq("usuario", rec_usuario).eq("email", rec_email).execute()
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
# CONSTRUCTURA ORDENADA DE LA BARRA LATERAL (SIDEBAR)
# -------------------------------------------------------------
st.sidebar.markdown(f"**Usuario:** {st.session_state.nombre_nadador}  \n**Nivel:** `{st.session_state.rol}`")
if st.sidebar.button("🚪 Salir del Sistema"):
    st.session_state.autenticado = False
    st.rerun()

st.sidebar.markdown("---")
# CORRECCIÓN 1: Casilla invertida. Desactivada por defecto, el sistema corre nativamente conectado a la BD.
modo_manual_online = st.sidebar.checkbox("🌐 Activar modo On Line manual", value=False)

# Panel de navegación (Solo si opera con la Base de Datos)
if st.session_state.rol in ["Entrenador", "Administrador"]:
    st.sidebar.subheader("🎯 Panel de Navegación de Atletas")
    if not modo_manual_online:
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
        st.sidebar.caption("💡 Panel deshabilitado: Ejecutando verificación manual Online.")
else:
    st.session_state.nadador_seleccionado_id = st.session_state.usuario_id
    st.session_state.nadador_seleccionado_nombre = st.session_state.nombre_nadador
    st.session_state.nadador_seleccionado_genero = st.session_state.genero
    st.session_state.nadador_seleccionado_categoria = st.session_state.categoria_atleta

# Análisis Colectivo (Solo en modo Base de Datos)
modo_equipo = False
if st.session_state.rol in ["Entrenador", "Administrador"] and not modo_manual_online:
    st.sidebar.markdown("---")
    st.sidebar.subheader("👥 Análisis Colectivo")
    modo_equipo = st.sidebar.checkbox("Activar Comparativa de Equipo", value=False)

# TÍTULO DINÁMICO CONDICIONADO DE LA CONSULTA
if modo_manual_online:
    st.markdown(f"### 🏊‍♂️ Planificación y control de resultados de competencia: Simulación Manual de Cortesía")
    st.markdown(f"**Entorno Operativo:** `Modo Online (Puntual sin registros vinculados)`")
elif modo_equipo:
    st.markdown(f"### 🏊‍♂️ Planificación y control de resultados de competencia: Comparativo")
    st.markdown(f"**Género:** Filtrado según controles lateral | **Entorno:** `Conectado a Base de Datos`")
else:
    st.markdown(f"### 🏊‍♂️ Planificación y control de resultados de competencia: {st.session_state.nadador_seleccionado_nombre}")
    st.markdown(f"**Género:** {'Masculino (M)' if st.session_state.nadador_seleccionado_genero == 'M' else 'Femenino (F)'} | **Categoría de Competencia Activa:** `{st.session_state.nadador_seleccionado_categoria}`")

# Ajuste por prueba
st.sidebar.markdown("---")
st.sidebar.subheader("📊 Ajustes por prueba")
lista_pruebas = ['50 Libre', '100 Libre', '200 Libre', '50 Espalda', '100 Espalda', '200 Espalda', '50 Mariposa', '100 Mariposa', '200 Mariposa', '50 Pecho', '100 Pecho', '200 Pecho', '200 Combinado', '400 Combinado']
titulo_grafico = st.sidebar.selectbox("Estilo y Distancia:", options=lista_pruebas, index=0)

m_ano, m_panam_b, m_panam_a, m_wa_b, m_wa_a, m_wr = 0.0, 0.0, 0.0, 0.0, 0.0, 25.0
es_preinfantil = st.session_state.nadador_seleccionado_categoria.startswith("Preinfantil") if not modo_manual_online else False

if not modo_manual_online and not es_preinfantil:
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

# Filtros de segmentación por equipos
tipo_filtro = "Todos los Atletas"
filtro_genero = "Todos"
cat_sel = None
ids_sel = []

if modo_equipo and not modo_manual_online:
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

# Carga de datos históricos base para el cálculo de límites (Solo si no está en modo_manual_online)
try:
    if not modo_manual_online:
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
    else:
        df_procesado = pd.DataFrame(columns=["id", "Edad", "Tiempo", "Evento / Fecha"])
        db_t0, db_T0, db_t_pb, db_T_pb = None, None, None, None
except Exception:
    df_procesado = pd.DataFrame(columns=["id", "Edad", "Tiempo", "Evento / Fecha"])
    db_t0, db_T0, db_t_pb, db_T_pb = None, None, None, None

val_t0 = db_t0 if (not modo_manual_online and db_t0 is not None) else 10.0
val_T0 = db_T0 if (not modo_manual_online and db_T0 is not None) else float(round(m_wr * 1.8, 2))
val_t_pb = db_t_pb if (not modo_manual_online and db_t_pb is not None) else 12.0
val_T_pb = db_T_pb if (not modo_manual_online and db_T_pb is not None) else float(round(m_wr * 1.3, 2))
val_T_target = float(round(m_wa_a * 0.99, 2)) if m_wa_a > 0 else float(round(m_wr * 1.08, 2))

# Celdas de configuración lateral
st.sidebar.markdown("---")
st.sidebar.subheader("📐 Parámetros de Límites y PB")
t0 = st.sidebar.number_input("1. Edad Start (t0):", min_value=4.0, value=val_t0, step=0.01, disabled=not modo_manual_online)
T0 = st.sidebar.number_input("2. Tiempo Inicial (T0):", min_value=1.0, value=val_T0, step=0.1, disabled=not modo_manual_online)
t_peak = st.sidebar.number_input("3. Edad Peak Proyectado (t_peak):", min_value=5.0, max_value=30.0, value=23.0)
T_target = st.sidebar.number_input("4. Tiempo Objetivo Peak (T_target):", min_value=1.0, value=val_T_target)
t_pb = st.sidebar.number_input("5. Edad del PB de Control (t_pb):", min_value=4.0, value=val_t_pb, step=0.01, disabled=not modo_manual_online)
T_pb = st.sidebar.number_input("6. Tiempo del PB de Control (T_pb):", min_value=1.0, value=val_T_pb, step=0.01, disabled=not modo_manual_online)

st.sidebar.markdown("---")
st.sidebar.subheader("⏱️ Rapidez de Deriva e Intervalo")
h = st.sidebar.slider("Factor ajustable de rapidez de deriva (h):", min_value=0.1, max_value=1.0, value=0.4, step=0.05)
t_intermedia = st.sidebar.slider("Consultar Edad Intermedia:", min_value=float(t0), max_value=float(t_peak), value=float(round((t0+t_peak)/2, 1)), step=0.1)


# MOTOR MATEMÁTICO ASINTÓTICO
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

k = resolver_k_individual(t0, T0, t_pb, T_pb, t_peak, T_target)

c1, c2, c3 = st.columns(3)
with c1: st.metric(label="Factor de Ajuste Fisiológico (k)", value=f"{k:.4f}")
with c2: st.metric(label="Margen de Deriva de Seguridad (D)", value=f"{(T_pb - T_target):.2f} s")
with c3: 
    T_intermedia_val = float(calcular_curva_atleta([t_intermedia], t0, T0, t_pb, T_pb, t_peak, T_target, k, h)[0])
    st.metric(label=f"Proyección a los {t_intermedia:.1f} años", value=f"{T_intermedia_val:.2f} s")

# -------------------------------------------------------------
# RENDIMIENTO GRÁFICO: MODO EQUIPO
# -------------------------------------------------------------
if modo_equipo and not modo_manual_online:
    try:
        resp_todos = supabase.table("usuarios").select("id, nombre, fecha_nacimiento, genero").eq("rol", "Nadador").eq("estatus", "Activo").execute()
        atletas_lista = resp_todos.data if resp_todos.data else []
        
        if filtro_genero == "Femenino (F)":
            atletas_lista = [a for a in atletas_lista if a["genero"] == "F"]
        elif filtro_genero == "Masculino (M)":
            atletas_lista = [a for a in atletas_lista if a["genero"] == "M"]

        atletas_filtrados = []
        if tipo_filtro == "Todos los Atletas":
            atletas_filtrados = atletas_lista
        elif tipo_filtro == "Categoría Etaria" and cat_sel:
            atletas_filtrados = [a for a in atletas_lista if calcular_categoria_competencia(a["fecha_nacimiento"])[0] == cat_sel]
        elif tipo_filtro == "Atletas Específicos" and ids_sel:
            atletas_filtrados = [a for a in atletas_lista if a["id"] in ids_sel]

        if not atletas_filtrados:
            st.warning("No se encontraron atletas activos con los criterios de segmentación elegidos.")
        else:
            fig = plt.figure(figsize=(8.5, 11.0))
            ax = fig.add_axes([0.14, 0.52, 0.72, 0.33])
            
            colores = plt.get_cmap("tab10", len(atletas_filtrados))
            hay_datos_visibles = False
            linea_fisiologica_anotada = False
            
            todas_las_edades_0 = []
            todos_los_tiempos_colectivo = []
            datos_atletas_cargados = []
            
            for idx, atl in enumerate(atletas_filtrados):
                a_id = atl["id"]
                a_nom = atl["nombre"]
                
                res_marcas = supabase.table("marcas_historicas")\
                    .select("edad, tiempo, nota")\
                    .eq("prueba", titulo_grafico)\
                    .eq("usuario_id", a_id)\
                    .order("edad", desc=False).execute()
                
                if res_marcas.data:
                    df_atl_m = pd.DataFrame(res_marcas.data)
                    df_atl_m = df_atl_m.rename(columns={"edad": "Edad", "tiempo": "Tiempo", "nota": "Evento / Fecha"})
                    hay_datos_visibles = True
                    
                    todas_las_edades_0.append(float(df_atl_m.iloc[0]["Edad"]))
                    todos_los_tiempos_colectivo.extend(df_atl_m["Tiempo"].tolist())
                    
                    datos_atletas_cargados.append({
                        "nom": a_nom,
                        "df": df_atl_m,
                        "color": colores(idx)
                    })

            if hay_datos_visibles:
                edad_0_min_colectivo = min(todas_las_edades_0)
                lim_x_min = max(4.0, edad_0_min_colectivo - 0.5)
                lim_x_max = t_peak + 1.0
                ax.set_xlim(lim_x_min, lim_x_max)
                
                peor_tiempo_colectivo = max(todos_los_tiempos_colectivo)
                lim_y_inferior = m_wr * 0.95
                lim_y_superior = peor_tiempo_colectivo + (peor_tiempo_colectivo * 0.05)
                ax.set_ylim(lim_y_inferior, lim_y_superior)
                
                for item in datos_atletas_cargados:
                    df_atl_m = item["df"]
                    color_curr = item["color"]
                    a_nom = item["nom"]
                    
                    t0_i = float(df_atl_m.iloc[0]["Edad"])
                    T0_i = float(df_atl_m.iloc[0]["Tiempo"])
                    idx_pb_i = df_atl_m["Tiempo"].idxmin()
                    t_pb_i = float(df_atl_m.loc[idx_pb_i, "Edad"])
                    T_pb_i = float(df_atl_m.loc[idx_pb_i, "Tiempo"])
                    
                    k_i = resolver_k_individual(t0_i, T0_i, t_pb_i, T_pb_i, t_peak, T_target)
                    edades_curva_i = np.linspace(t0_i, t_peak, 300)
                    tiempos_curva_i = calcular_curva_atleta(edades_curva_i, t0_i, T0_i, t_pb_i, T_pb_i, t_peak, T_target, k_i, h)
                    
                    if not linea_fisiologica_anotada:
                        ax.plot(edades_curva_i, tiempos_curva_i, color="#7F8C8D", linestyle=":", linewidth=1.2, label="Proyección fisiológica estimada")
                        linea_fisiologica_anotada = True
                    else:
                        ax.plot(edades_curva_i, tiempos_curva_i, color="#7F8C8D", linestyle=":", linewidth=1.2)
                    
                    ax.plot(df_atl_m["Edad"], df_atl_m["Tiempo"], color=color_curr, linestyle="-", linewidth=1.5, label=f"Evolución real - {a_nom}")
                    ax.scatter(df_atl_m["Edad"], df_atl_m["Tiempo"], color=color_curr, edgecolor="black", s=25, linewidths=0.5, zorder=3)
                    ax.scatter(t_pb_i, T_pb_i, color=color_curr, marker="*", edgecolor="black", s=80, linewidths=0.5, zorder=5)

                # Renderizado de marcas mínimas
                x_texto = lim_x_min + 0.1
                referencias = [
                    {"val": m_ano, "lbl": "Mín. Año", "col": "#A06000", "va": "bottom"}, 
                    {"val": m_panam_b, "lbl": "PANAM Jr B", "col": "#006644", "va": "bottom"},      
                    {"val": m_panam_a, "lbl": "PANAM Jr A", "col": "#2A658A", "va": "top"},   
                    {"val": m_wa_b, "lbl": "WA B", "col": "#943100", "va": "bottom"},               
                    {"val": m_wa_a, "lbl": "WA A", "col": "#883963", "va": "top"},            
                    {"val": m_wr, "lbl": "World Record", "col": "#2C3E50", "va": "top"}   
                ]
                for r in referencias:
                    if r["val"] > 0 and lim_y_inferior <= r["val"] <= lim_y_superior:
                        ax.axhline(y=r["val"], color=r["col"], linestyle=":", linewidth=0.6, alpha=0.7)
                        desplazamiento_y = (lim_y_superior - lim_y_inferior) * 0.006 if r["va"] == "bottom" else -((lim_y_superior - lim_y_inferior) * 0.006)
                        ax.text(x_texto, r["val"] + desplazamiento_y, f"{r['lbl']}: {r['val']:.2f}s", color=r["col"], fontsize=7, va=r["va"], ha="left")
                
                ax.set_title(f"Análisis Comparativo de Equipo - {titulo_grafico}", fontsize=12, pad=10)
                ax.set_xlabel("Edad del Atleta (Años)", fontsize=9.5)
                ax.set_ylabel("Tiempo de Carrera (Segundos)", fontsize=9.5)
                ax.grid(True, which="both", axis="both", linestyle=":", color="#CCD1D1", linewidth=0.5)
                ax.set_axisbelow(True)
                ax.legend(loc="upper right", fontsize=8, framealpha=0.8)
                
                st.pyplot(fig)
            else:
                st.info("No se hallaron marcas en la base de datos para los nadadores seleccionados en esta prueba.")
    except Exception as e:
        st.error(f"Error procesando los segmentos de equipo: {e}")

else:
    # -------------------------------------------------------------
    # LIENZO INDIVIDUAL (CONDICIONADO POR MODO ONLINE/DB)
    # -------------------------------------------------------------
    edades_curva = np.linspace(t0, t_peak, 500)
    tiempos_curva = calcular_curva_atleta(edades_curva, t0, T0, t_pb, T_pb, t_peak, T_target, k, h)

    fig = plt.figure(figsize=(8.5, 11.0))
    ax = fig.add_axes([0.14, 0.52, 0.72, 0.33])

    ax.plot(edades_curva, tiempos_curva, color="#007A87", linewidth=1.8, label="Proyección Fisiológica")

    todos_los_tiempos_ind = [T0, T_pb, T_target]
    
    # Solo dibuja los datos históricos si se está en Modo Base de Datos (modo_manual_online=False)
    if not modo_manual_online and len(df_procesado) > 0:
        ax.plot(df_procesado["Edad"], df_procesado["Tiempo"], color="#D55E00", linestyle="--", linewidth=1.0, alpha=0.6, label="Evolución Real (PBs)")
        ax.scatter(df_procesado["Edad"], df_procesado["Tiempo"], color="#D55E00", edgecolor="black", s=25, linewidths=0.6, zorder=3)
        todos_los_tiempos_ind.extend(df_procesado["Tiempo"].tolist())

    ax.scatter(t0, T0, color="#7F8C8D", edgecolor="black", s=35, linewidths=0.6, zorder=4)
    ax.scatter(t_pb, T_pb, color="#F1C40F", marker="*", edgecolor="black", s=100, linewidths=0.6, zorder=5, label="PB Actual de Control")
    ax.scatter(t_peak, T_target, color="#2ECC71", marker="s", edgecolor="black", s=35, linewidths=0.6, zorder=4, label="Meta Peak")
    ax.scatter(t_intermedia, T_intermedia_val, color="red", marker="o", s=30, zorder=5, label="Punto Consultado")

    ax.axvline(x=t0, color="#7F8C8D", linestyle=":", linewidth=0.7, alpha=0.5)
    ax.axvline(x=t_pb, color="red", linestyle="--", linewidth=0.7, alpha=0.4)
    ax.axvline(x=t_peak, color="#2ECC71", linestyle=":", linewidth=0.7, alpha=0.5)
    ax.axvline(x=t_intermedia, color="red", linestyle=":", linewidth=0.7, alpha=0.4)

    lim_x_min = max(4.0, t0 - 0.5)
    lim_x_max = t_peak + 1.0
    ax.set_xlim(lim_x_min, lim_x_max)

    peor_tiempo_ind = max(todos_los_tiempos_ind)
    lim_y_inferior = m_wr * 0.95
    lim_y_superior = peor_tiempo_ind + (peor_tiempo_ind * 0.05)
    ax.set_ylim(lim_y_inferior, lim_y_superior)

    offset_y = (lim_y_superior - lim_y_inferior) * 0.025
    estilo_bbox = dict(boxstyle="round,pad=0.25", fc="#F8F9F9", ec="#BDC3C7", alpha=0.9, linewidth=0.5)

    ax.text(t0 + 0.1, T0, f"P. Start\n{t0:.2f}a\n{T0:.2f}s", fontsize=8, va="bottom", ha="left", bbox=estilo_bbox)
    ax.text(t_pb + 0.15, T_pb, f"PB Actual\n{t_pb:.2f}a\n{T_pb:.2f}s", fontsize=8, va="center", ha="left", bbox=estilo_bbox)
    ax.text(t_intermedia, T_intermedia_val + offset_y, f"Consulta: {t_intermedia:.1f}a\n{T_intermedia_val:.2f}s", fontsize=8, va="bottom", ha="center", bbox=estilo_bbox)
    ax.text(t_peak - 0.1, T_target, f"Meta Peak\n{t_peak:.2f}a\n{T_target:.2f}s", fontsize=8, va="bottom", ha="right", bbox=estilo_bbox)

    # Renderizado de marcas mínimas
    x_texto = lim_x_min + 0.1
    if not modo_manual_online and not es_preinfantil:
        referencias = [
            {"val": m_ano, "lbl": "Mín. Año", "col": "#A06000", "va": "bottom"}, 
            {"val": m_panam_b, "lbl": "PANAM Jr B", "col": "#006644", "va": "bottom"},      
            {"val": m_panam_a, "lbl": "PANAM Jr A", "col": "#2A658A", "va": "top"},   
            {"val": m_wa_b, "lbl": "WA B", "col": "#943100", "va": "bottom"},               
            {"val": m_wa_a, "lbl": "WA A", "col": "#883963", "va": "top"},            
            {"val": m_wr, "lbl": "World Record", "col": "#2C3E50", "va": "top"}   
        ]
        for r in referencias:
            if r["val"] > 0 and lim_y_inferior <= r["val"] <= lim_y_superior:
                ax.axhline(y=r["val"], color=r["col"], linestyle=":", linewidth=0.6, alpha=0.7)
                desplazamiento_y = (lim_y_superior - lim_y_inferior) * 0.006 if r["va"] == "bottom" else -((lim_y_superior - lim_y_inferior) * 0.006)
                ax.text(x_texto, r["val"] + desplazamiento_y, f"{r['lbl']}: {r['val']:.2f}s", color=r["col"], fontsize=7, va=r["va"], ha="left")
    else:
        ax.axhline(y=m_wr, color="#2C3E50", linestyle="--", linewidth=0.6, alpha=0.7)
        ax.text(x_texto, m_wr - ((lim_y_superior - lim_y_inferior) * 0.006), f"WR Base: {m_wr:.2f}s", color="#2C3E50", fontsize=7, va="top", ha="left")

    # Título condicionado que oculta al atleta si está en modo manual
    if not modo_manual_online:
        ax.set_title(f"Curva de Rendimiento Asintótica - {titulo_grafico}\nAtleta: {st.session_state.nadador_seleccionado_nombre} | Categoría: {st.session_state.nadador_seleccionado_categoria}", fontsize=12, pad=10)
    else:
        ax.set_title(f"Curva de Rendimiento Asintótica - {titulo_grafico}\nVerificación Técnica Externa (Simulación Online)", fontsize=12, pad=10)
        
    ax.set_xlabel("Edad del Atleta (Años)", fontsize=9.5)
    ax.set_ylabel("Tiempo de Carrera (Segundos)", fontsize=9.5)
    ax.grid(True, which="both", axis="both", linestyle=":", color="#CCD1D1", linewidth=0.5)
    ax.set_axisbelow(True) 
    ax.legend(loc="upper right", fontsize=8, framealpha=0.8)

    # Ocultar la tabla de resultados históricos de manera definitiva si está en modo manual
    if not modo_manual_online and len(df_procesado) > 0:
        df_table_render = df_procesado[["Edad", "Tiempo", "Evento / Fecha"]].copy()
        df_table_render["Edad"] = df_table_render["Edad"].map(lambda x: f"{x:.2f} a")
        df_table_render["Tiempo"] = df_table_render["Tiempo"].map(lambda x: f"{x:.2f} s")
        
        limite_filas_por_bloque = 16
        total_filas = len(df_table_render)
        
        def dar_formato_tabla_nativo(instancia_tabla):
            instancia_tabla.auto_set_font_size(False)
            instancia_tabla.set_fontsize(8.5)
            instancia_tabla.scale(1.0, 1.3)
            for (row, col), cell in instancia_tabla.get_celld().items():
                if row == 0:
                    cell.set_text_props(color='white')
                    cell.set_facecolor('#007A87')
                else:
                    cell.set_facecolor('#F8F9F9' if row % 2 == 0 else 'white')

        if total_filas <= limite_filas_por_bloque:
            ax_table = fig.add_axes([0.14, 0.054, 0.72, 0.40])
            ax_table.axis('off')
            mpl_table = ax_table.table(cellText=df_table_render.values, colLabels=df_table_render.columns, cellLoc='center', loc='upper center', colWidths=[0.15, 0.15, 0.70])
            dar_formato_tabla_nativo(mpl_table)
        else:
            if total_filas > 32: df_table_render = df_table_render.iloc[:32]
            df_bloque_izq = df_table_render.iloc[:limite_filas_por_bloque]
            df_bloque_der = df_table_render.iloc[limite_filas_por_bloque:]
            
            ax_table1 = fig.add_axes([0.14, 0.054, 0.34, 0.40])
            ax_table1.axis('off')
            mpl_table1 = ax_table1.table(cellText=df_bloque_izq.values, colLabels=df_bloque_izq.columns, cellLoc='center', loc='upper center', colWidths=[0.18, 0.18, 0.64])
            dar_formato_tabla_nativo(mpl_table1)
            
            ax_table2 = fig.add_axes([0.52, 0.054, 0.34, 0.40])
            ax_table2.axis('off')
            mpl_table2 = ax_table2.table(cellText=df_bloque_der.values, colLabels=df_bloque_der.columns, cellLoc='center', loc='upper center', colWidths=[0.18, 0.18, 0.64])
            dar_formato_tabla_nativo(mpl_table2)

    st.pyplot(fig)

# -------------------------------------------------------------
# MÓDULOS DE GESTIÓN SEGÚN ROL
# -------------------------------------------------------------
st.markdown("---")
tab_marcas, tab_entrenador, tab_admin = st.tabs(["📋 Control de Marcas", "⏱️ Configurar Tiempos por Categoría (Entrenador)", "🛡️ Consola Global (Admin)"])

with tab_marcas:
    if modo_manual_online:
        st.info("💡 Módulo Manual Online de Cortesía Activo: Las tablas de historial y el panel para archivar datos están deshabilitados.")
    else:
        col_ins, col_vistas = st.columns([1, 2])
        with col_ins:
            st.markdown("**Ingresar Nueva Marca**")
            with st.form("form_insertar_marca", clear_on_submit=True):
                ins_fecha_evento = st.date_input("Fecha de la Competencia:", value=datetime.date.today())
                ins_tiempo = st.number_input("Tiempo Oficial (seg):", min_value=1.0, step=0.01)
                ins_nota = st.text_input("Evento / Fecha:")
                
                if st.form_submit_button("💾 Guardar Registro"):
                    if st.session_state.rol in ["Entrenador", "Administrador"] or st.session_state.usuario_id == st.session_state.nadador_seleccionado_id:
                        try:
                            id_atleta = st.session_state.nadador_seleccionado_id
                            fecha_nacimiento_atleta = st.session_state.fecha_nacimiento
                            
                            if st.session_state.rol in ["Entrenador", "Administrador"]:
                                atleta_query = supabase.table("usuarios").select("fecha_nacimiento").eq("id", id_atleta).execute()
                                if atleta_query.data:
                                    fecha_nacimiento_atleta = atleta_query.data[0]["fecha_nacimiento"]
                            
                            if not fecha_nacimiento_atleta:
                                st.error("❌ El atleta no posee fecha de nacimiento en su perfil.")
                            else:
                                edad_calculada = calcular_edad_decimal(fecha_nacimiento_atleta, ins_fecha_evento)
                                if edad_calculada is None:
                                    st.error("❌ Error al procesar la fecha de nacimiento.")
                                else:
                                    nueva_m = {
                                        "prueba": titulo_grafico, 
                                        "edad": float(edad_calculada), 
                                        "tiempo": float(ins_tiempo),
                                        "nota": ins_nota, 
                                        "usuario_id": id_atleta
                                    }
                                    supabase.table("marcas_historicas").insert(nueva_m).execute()
                                    st.success(f"Marca guardada. Edad calculada automáticamente: {edad_calculada} años.")
                                    st.rerun()
                        except Exception as e:
                            st.error(f"Error al guardar el registro: {e}")
                        
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
        st.markdown(f"### ⚙️ Umbrales de Competencia para la Categoría")
        u_cat = st.selectbox("Categoría a Modificar u Organizar:", options=["Infantil A", "Infantil B", "Juvenil A", "Juvenil B", "Máxima"])
        
        db_m_ano, db_m_panam_b, db_m_panam_a, db_m_wa_b, db_m_wa_a, db_m_wr = None, None, None, None, None, None
        try:
            ref_dinamica = supabase.table("marcas_referencia").select("*")\
                .eq("prueba", titulo_grafico)\
                .eq("genero", st.session_state.nadador_seleccionado_genero)\
                .eq("categoria", u_cat).execute()
            if ref_dinamica.data:
                r_det = ref_dinamica.data[0]
                db_m_ano = float(r_det["m_ano"]) if r_det["m_ano"] is not None else None
                db_m_panam_b = float(r_det["m_panam_b"]) if r_det["m_panam_b"] is not None else None
                db_m_panam_a = float(r_det["m_panam_a"]) if r_det["m_panam_a"] is not None else None
                db_m_wa_b = float(r_det["m_wa_b"]) if r_det["m_wa_b"] is not None else None
                db_m_wa_a = float(r_det["m_wa_a"]) if r_det["m_wa_a"] is not None else None
                db_m_wr = float(r_det["m_wr"]) if r_det["m_wr"] is not None else None
        except Exception:
            pass

        with st.form("form_update_referencias"):
            u_ano = st.number_input("Marca Mínima Año (seg):", value=db_m_ano if db_m_ano is not None else 0.0, disabled=(db_m_ano is None))
            u_panamb = st.number_input("PANAM Jr - Marca B (seg):", value=db_m_panam_b if db_m_panam_b is not None else 0.0, disabled=(db_m_panam_b is None))
            u_panama = st.number_input("PANAM Jr - Marca A (seg):", value=db_m_panam_a if db_m_panam_a is not None else 0.0, disabled=(db_m_panam_a is None))
            u_wab = st.number_input("World Aquatics - Marca B (seg):", value=db_m_wa_b if db_m_wa_b is not None else 0.0, disabled=(db_m_wa_b is None))
            u_waa = st.number_input("World Aquatics - Marca A (seg):", value=db_m_wa_a if db_m_wa_a is not None else 0.0, disabled=(db_m_wa_a is None))
            u_wr = st.number_input("Récord Mundial de Estilo Absoluto:", value=db_m_wr if db_m_wr is not None else 25.0, disabled=(db_m_wr is None))
            
            if st.form_submit_button("⚡ Guardar Configuración de Tiempos"):
                up_data = {}
                if db_m_ano is not None: up_data["m_ano"] = u_ano
                if db_m_panam_b is not None: up_data["m_panam_b"] = u_panamb
                if db_m_panam_a is not None: up_data["m_panam_a"] = u_panama
                if db_m_wa_b is not None: up_data["m_wa_b"] = u_wab
                if db_m_wa_a is not None: up_data["m_wa_a"] = u_waa
                if db_m_wr is not None: up_data["m_wr"] = u_wr
                
                if up_data:
                    supabase.table("marcas_referencia").upsert({
                        "prueba": titulo_grafico, "genero": st.session_state.nadador_seleccionado_genero,
                        "categoria": u_cat, **up_data
                    }, on_conflict="prueba,genero,categoria").execute()
                    st.success(f"Tiempos de referencia actualizados para {u_cat}.")
                    st.rerun()
    else:
        st.warning("🔒 Requiere credenciales de Dirección Técnico o Entrenador.")

with tab_admin:
    if st.session_state.rol == "Administrador":
        st.markdown("### 🛡️ Consola de Control de Usuarios e Integridad de Datos")
        try:
            resp_usuarios = supabase.table("usuarios").select("id, nombre, usuario, email, rol, genero, estatus, fecha_nacimiento").execute()
            if resp_usuarios.data:
                df_usr = pd.DataFrame(resp_usuarios.data)
                st.dataframe(df_usr, use_container_width=True)
                
                st.markdown("**Editar Perfil de Usuario**")
                
                lista_usuarios_nombres = df_usr["nombre"].tolist()
                select_user_edit = st.selectbox("Seleccione el Usuario a Modificar:", options=lista_usuarios_nombres)
                fila_edit = df_usr[df_usr["nombre"] == select_user_edit].iloc[0]
                
                c_rol, c_est, c_gen = st.columns(3)
                with c_rol:
                    new_role = st.selectbox("Rol Institucional:", options=["Nadador", "Entrenador", "Administrador"], index=["Nadador", "Entrenador", "Administrador"].index(fila_edit["rol"]))
                with c_est:
                    new_status = st.selectbox("Estado Operativo:", options=["Activo", "Inactivo", "Suspendido", "Bloqueado"], index=["Activo", "Inactivo", "Suspendido", "Bloqueado"].index(fila_edit["estatus"]))
                
                es_tecnico = new_role in ["Entrenador", "Administrador"]
                
                with c_gen:
                    gen_inicial = fila_edit["genero"] if fila_edit["genero"] in ["F", "M"] else "F"
                    new_genero = st.selectbox("Género Biométrico:", options=["F", "M"], index=["F", "M"].index(gen_inicial), disabled=es_tecnico)
                
                # CORRECCIÓN 2: Filtro de seguridad (Type Guard) para interceptar valores nulos, vacíos o 'nan' de la BD
                raw_fecha = fila_edit["fecha_nacimiento"]
                if not raw_fecha or str(raw_fecha).lower() == 'nan':
                    f_nac_inicial = datetime.date.today()
                else:
                    try:
                        f_nac_inicial = datetime.date.fromisoformat(str(raw_fecha))
                    except ValueError:
                        f_nac_inicial = datetime.date.today()
                        
                new_f_nac = st.date_input("Corregir Fecha Nacimiento:", value=f_nac_inicial, disabled=es_tecnico)
                
                if st.button("⚠️ Forzar Cambios de Perfil"):
                    status_previo_db = fila_edit["estatus"]
                    correo_usuario_afectado = fila_edit["email"]
                    
                    payload_enmienda_admin = {
    "rol": new_role,       # <-- CAMBIADO
    "estatus": new_status, # <-- CAMBIADO
    "fecha_nacimiento": None if es_tecnico else new_f_nac.strftime("%Y-%m-%d"),
    "genero": None if es_tecnico else new_genero
}
                    
                    supabase.table("usuarios").update(payload_enmienda_admin).eq("id", fila_edit["id"]).execute()
                    st.success(f"Enmienda consolidada en Supabase para {select_user_edit}.")
                    
                    if status_previo_db != new_status:
                        enviar_correo_sistema(
                            destinatario=correo_usuario_afectado,
                            asunto="Notificación Oficial: Modificación de Estado de Cuenta",
                            cuerpo=f"Estimado {select_user_edit}, le informamos que la Dirección Técnica ha cambiado el estado de su cuenta de acceso a la plataforma de natación a: '{new_status}'."
                        )
                        enviar_correo_sistema(
                            destinatario=st.session_state.usuario_email,
                            asunto="LOG DE AUDITORÍA: Cambio de Estado Procesado",
                            cuerpo=f"Seguridad: Se alteró el estado de ingreso de '{correo_usuario_afectado}'. Transición: {status_previo_db} -> {new_status}."
                        )
                    st.rerun()
        except Exception as e:
            st.error(f"Error en panel de control: {e}")
    else:
        st.warning("🔒 Acceso restringido al Administrador.")

# -------------------------------------------------------------
# CENTRO DE EXPORTACIÓN
# -------------------------------------------------------------
st.markdown("---")
st.markdown("### 🖨️ Centro de Exportación de Reportes y Gráficos")

if (not modo_manual_online and len(df_procesado) > 0) or modo_manual_online or modo_equipo:
    export_df = df_procesado.drop(columns=["id", "usuario_id"], errors="ignore")
    csv_data = export_df.to_csv(index=False).encode('utf-8')
    txt_string = export_df.to_string(index=False)
    
    img_buffer = io.BytesIO()
    fig.savefig(img_buffer, format="png", bbox_inches=None, dpi=300)
    img_buffer.seek(0)
    
    c_exp1, c_exp2, c_exp3 = st.columns(3)
    with c_exp1:
        if not modo_manual_online:
            st.download_button(label="📥 Descargar Historial (CSV)", data=csv_data, file_name=f"marcas_{titulo_grafico}_{st.session_state.nadador_seleccionado_nombre}.csv", mime="text/csv")
        else:
            st.download_button(label="📥 Descargar Plantilla Manual (CSV)", data=csv_data, file_name=f"simulacion_manual_{titulo_grafico}.csv", mime="text/csv", disabled=True)
    with c_exp2:
        if not modo_manual_online:
            st.download_button(label="📄 Descargar Datos (TXT)", data=txt_string, file_name=f"reporte_{titulo_grafico}_{st.session_state.nadador_seleccionado_nombre}.txt", mime="text/plain")
        else:
            st.download_button(label="📄 Descargar Datos (TXT)", data=txt_string, file_name=f"reporte_manual_{titulo_grafico}.txt", mime="text/plain", disabled=True)
    with c_exp3:
        nombre_reporte_img = f"reporte_carta_{titulo_grafico}_{st.session_state.nadador_seleccionado_nombre}.png" if not modo_manual_online else f"reporte_cortesia_{titulo_grafico}.png"
        st.download_button(label="🖼️ Guardar Gráfico Completo (Imagen PNG - Tamaño Carta)", data=img_buffer, file_name=nombre_reporte_img, mime="image/png")
        
    st.caption("💡 *Nota de Impresión:* La imagen generada respeta estrictamente los márgenes de 1.5 cm laterales, 2.5 cm superior y 1.5 cm inferior al imprimirse en formato Carta vertical.")
else:
    st.info("No hay datos históricos disponibles para exportar en esta prueba todavía.")