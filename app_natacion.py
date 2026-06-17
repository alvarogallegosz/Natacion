import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import fsolve
import pandas as pd
import datetime
import io
from supabase import create_client, Client

# ==============================================================================
# 1. CONFIGURACIÓN DE LA PÁGINA E INYECCIÓN DE ESTILOS CSS
# ==============================================================================
st.set_page_config(page_title="Simulador de proyección de rendimiento para natación", layout="wide")

st.markdown(
    """
    <style>
    div[data-testid="stMetricValue"] { font-size: 22px !important; }
    div[data-testid="stMetricLabel"] { font-size: 13px !important; }
    @media print {
        .no-print { display: none !important; }
        .print-only { display: block !important; }
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Conexión segura con Supabase utilizando Secrets de Streamlit
try:
    url: str = st.secrets["SUPABASE_URL"]
    key: str = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(url, key)
except Exception as e:
    st.error("Faltan las credenciales de Supabase en los Secrets de la aplicación.")
    st.stop()

# ------------------------------------------------------------------------------
# SERVICIO SIMULADO DE NOTIFICACIONES ELECTRÓNICAS
# ------------------------------------------------------------------------------
def enviar_correo_sistema(destinatario: str, asunto: str, cuerpo: str):
    """Simula el envío de notificaciones de auditoría y gobernanza."""
    st.info(f"📧 **Notificación enviada a:** `{destinatario}`\n*Asunto:* {asunto}\n*Contenido:* {cuerpo}")

# ------------------------------------------------------------------------------
# LÓGICA DE CATEGORÍAS ETARIAS (Edad cumplida al 31 de Diciembre del año en curso)
# ------------------------------------------------------------------------------
def calcular_categoria_fevera(fecha_nacimiento):
    if not fecha_nacimiento:
        return "Desconocida"
    if isinstance(fecha_nacimiento, str):
        fecha_nacimiento = datetime.datetime.strptime(fecha_nacimiento, "%Y-%m-%d").date()
    anio_actual = datetime.date.today().year
    edad_fevera = anio_actual - fecha_nacimiento.year
    
    if edad_fevera <= 9: return "Pre-Infantil"
    elif edad_fevera in [10, 11]: return "Infantil A"
    elif edad_fevera in [12, 13]: return "Infantil B"
    elif edad_fevera in [14, 15]: return "Juvenil A"
    elif edad_fevera in [16, 17, 18]: return "Juvenil B"
    else: return "Máxima / Mayor"

# ==============================================================================
# 2. MOTOR MATEMÁTICO DE SIMULACIÓN ASINTÓTICA (SOLVER EXPONENCIAL)
# ==============================================================================
def resolver_k_individual(t0, edad0, tpb, edad_pb, tpeak):
    if (t0 - tpeak) <= 0 or (tpb - tpeak) <= 0 or (edad_pb - edad0) <= 0:
        return 0.25
    def ecuacion(k):
        return tpeak + (t0 - tpeak) * np.exp(-k * (edad_pb - edad0)) - tpb
    k_inicial = 0.25
    k_solucion, info, ier, msg = fsolve(ecuacion, k_inicial, full_output=True)
    if ier == 1:
        return float(k_solucion[0])
    else:
        return 0.25

def calcular_curva_atleta(t0, edad0, tpeak, k, edades_proyeccion):
    tiempos_proyectados = []
    for edad in edades_proyeccion:
        if edad < edad0:
            t = t0 + (edad0 - edad) * 1.5
        else:
            t = tpeak + (t0 - tpeak) * np.exp(-k * (edad - edad0))
        tiempos_proyectados.append(t)
    return np.array(tiempos_proyectados)

# ==============================================================================
# 3. INTERFAZ DE CONTROL: AUTENTICACIÓN Y REGISTRO REESTRUCTURADO
# ==============================================================================
if "autenticado" not in st.session_state:
    st.session_state.autenticado = False
if "usuario_rol" not in st.session_state:
    st.session_state.usuario_rol = None
if "usuario_email" not in st.session_state:
    st.session_state.usuario_email = ""

if not st.session_state.autenticado:
    st.title("🏊 Sistema de Planificación y Gestión de Resultados - Centro Gallego")
    pest_login, pest_registro = st.tabs(["🔑 Iniciar Sesión", "📝 Registrarse en el Sistema"])
    
    with pest_login:
        with st.form("login_form"):
            email_log = st.text_input("Correo electrónico:")
            pass_log = st.text_input("Contraseña:", type="password") 
            btn_login = st.form_submit_button("Ingresar")
            
            if btn_login:
                try:
                    # Sincronizado con tus columnas reales en español (email, contrasena)
                    res = supabase.table("usuarios").select("*").eq("email", email_log).eq("contrasena", pass_log).execute()
                    if res.data:
                        user = res.data[0]
                        # Validando usando la columna en español 'estatus'
                        if user.get("estatus") == "Inactivo":
                            st.error("🔒 Acceso Bloqueado: Su cuenta está inactiva. Los roles de Entrenador o Administrador requieren autorización expresa del Administrador del club.")
                        else:
                            st.session_state.autenticado = True
                            st.session_state.usuario_rol = user["rol"] # Tu columna 'rol'
                            st.session_state.usuario_email = user["email"]
                            st.session_state.nadador_seleccionado_id = user["id"] if user["rol"] == "Nadador" else None
                            st.session_state.nadador_seleccionado_nombre = user["nombre"] if user["rol"] == "Nadador" else ""
                            st.success("Acceso concedido.")
                            st.rerun()
                    else:
                        st.error("Credenciales inválidas o cuenta inexistente.")
                except Exception as ex:
                    st.error(f"Error de comunicación con Supabase. Verifique los campos de su tabla: {ex}")
                    
    with pest_registro:
        with st.form("registro_form"):
            reg_nombre = st.text_input("Nombre Completo:")
            reg_email = st.text_input("Correo Electrónico:")
            reg_pass = st.text_input("Contraseña de Acceso:")
            reg_rol = st.selectbox("Rol Solicitado:", ["Nadador", "Entrenador", "Administrador"])
            reg_genero = st.selectbox("Género (F/M):", ["F", "M"])
            reg_fecha_nac = st.date_input("Fecha de Nacimiento:", value=datetime.date(2012, 1, 1))
            btn_reg = st.form_submit_button("Registrar Nueva Cuenta")
            
            if btn_reg:
                if not reg_nombre or not reg_email or not reg_pass:
                    st.error("Por favor, rellene todos los campos del formulario.")
                else:
                    status_inicial = "Activo" if reg_rol == "Nadador" else "Inactivo"
                    
                    # Estructura del payload 100% en español
                    payload_nuevo_user = {
                        "nombre": reg_nombre,
                        "email": reg_email,
                        "contrasena": reg_pass,
                        "rol": reg_rol,
                        "genero": reg_genero,
                        "fecha_nacimiento": reg_fecha_nac.strftime("%Y-%m-%d"),
                        "estatus": status_inicial
                    }
                    try:
                        res_ins = supabase.table("usuarios").insert(payload_nuevo_user).execute()
                        if res_ins.data:
                            if status_inicial == "Inactivo":
                                st.warning("⚠️ Registro Recibido: Su cuenta técnica se ha creado como 'Inactiva' por seguridad. Se notificó al Administrador para su validación.")
                                enviar_correo_sistema(
                                    destinatario=st.secrets.get("ADMIN_EMAIL", "admin_gallego@natacion.com"),
                                    asunto="SOLICITUD: Alta de Personal Técnico",
                                    cuerpo=f"El usuario {reg_nombre} ({reg_email}) solicita ingresar con el rol '{reg_rol}'. Autorice su acceso desde la Consola Global cambiando su estatus a Activo."
                                )
                            else:
                                st.success("¡Registro completado! Ya puede iniciar sesión.")
                    except Exception as e:
                        st.error(f"Error al procesar el alta: La dirección de correo electrónico ya está registrada. ({e})")

else:
    # ==============================================================================
    # 4. BARRA LATERAL (ENTORNO OPERATIVO CONFIGURABLE)
    # ==============================================================================
    st.sidebar.title("Configuración Técnico")
    st.sidebar.markdown(f"**Usuario:** `{st.session_state.usuario_email}`")
    st.sidebar.markdown(f"**Rol Operativo:** `{st.session_state.usuario_rol}`")
    
    if st.sidebar.button("🚪 Cerrar Sesión"):
        st.session_state.autenticado = False
        st.session_state.usuario_rol = None
        st.session_state.usuario_email = ""
        st.rerun()
        
    st.sidebar.markdown("---")
    
    lista_estilos = [
        "50m Libre", "100m Libre", "200m Libre", "400m Libre", "800m Libre", "1500m Libre",
        "50m Mariposa", "100m Mariposa", "200m Mariposa",
        "50m Espalda", "100m Espalda", "200m Espalda",
        "50m Pecho", "100m Pecho", "200m Pecho",
        "200m Combinado", "400m Combinado"
    ]
    estilo_seleccionado = st.sidebar.selectbox("Seleccione la Prueba de Análisis:", lista_estilos)
    
    modo_online = st.sidebar.checkbox("Activar modo On Line manual", value=False)
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📊 Parámetros de Ajuste de Curvatura")
    k_manual = st.sidebar.slider("Rapidez de deriva manual (k):", min_value=0.05, max_value=0.80, value=0.22, step=0.01)
    edad_consulta = st.sidebar.slider("Edad de Proyección Dinámica:", min_value=8.0, max_value=25.0, value=15.0, step=0.1)
    
    modo_equipo = False
    if st.session_state.usuario_rol in ["Entrenador", "Administrador"]:
        st.sidebar.markdown("---")
        st.sidebar.markdown("### 👥 Panel de Dirección de Atletas")
        
        # Consulta modificada para buscar con 'rol' y 'estatus' en español
        res_atletas = supabase.table("usuarios").select("id, nombre").eq("rol", "Nadador").eq("estatus", "Activo").execute()
        if res_atletas.data:
            df_atl = pd.DataFrame(res_atletas.data)
            dict_atletas = dict(zip(df_atl["nombre"], df_atl["id"]))
            
            if modo_online:
                st.sidebar.caption("👉 Selección de atletas deshabilitada en Modo Online.")
                nadador_id = None
                nadador_nombre = "Invitado Anónimo"
            else:
                nadador_nombre = st.sidebar.selectbox("Seleccione el Atleta a evaluar:", df_atl["nombre"].tolist())
                nadador_id = dict_atletas[nadador_nombre]
                st.session_state.nadador_seleccionado_id = nadador_id
                st.session_state.nadador_seleccionado_nombre = nadador_nombre
                
                if st.session_state.usuario_rol == "Entrenador":
                    modo_equipo = st.sidebar.checkbox("Activar Comparativa de Equipo", value=False)
        else:
            st.sidebar.warning("No existen nadadores registrados activos.")
            nadador_id = None
            nadador_nombre = "Invitado"
    else:
        nadador_id = st.session_state.nadador_seleccionado_id
        nadador_nombre = st.session_state.nadador_seleccionado_nombre

    # ==============================================================================
    # 5. ESTRUCTURA CENTRAL DE PESTAÑAS SEGÚN ROL
    # ==============================================================================
    pestañas_validas = ["📈 Visualización de Proyecciones"]
    if st.session_state.usuario_rol == "Administrador":
        pestañas_validas.append("🛡️ Consola Global de Administración")
        
    tabs_sistema = st.tabs(pestañas_validas)
    
    # ------------------------------------------------------------------------------
    # 5.1 PESTAÑA PRINCIPAL: CANVAS GRÁFICO
    # ------------------------------------------------------------------------------
    with tabs_sistema[0]:
        
        if modo_online:
            st.title("📊 Planificación y control de resultados de competencia")
            st.subheader(f"Prueba: {estilo_seleccionado} (Modo Online Manual de Cortesía)")
            st.info("💡 Módulo de Verificación Online Activo: Gráficos y tablas vinculados a la Base de Datos están ocultos.")
            
            c_on1, c_on2, c_on3 = st.columns(3)
            with c_on1:
                t0_on = st.number_input("Tiempo Inicial T0 (seg):", min_value=10.0, max_value=200.0, value=38.50, step=0.01)
                edad0_on = st.number_input("Edad del Tiempo T0:", min_value=5.0, max_value=25.0, value=10.0, step=0.1)
            with c_on2:
                tpb_on = st.number_input("Mejor Marca Personal Tpb (seg):", min_value=10.0, max_value=200.0, value=30.12, step=0.01)
                edad_pb_on = st.number_input("Edad del Tiempo Tpb:", min_value=5.0, max_value=25.0, value=13.4, step=0.1)
            with c_on3:
                tpeak_on = st.number_input("Límite Fisiológico Tpeak (seg):", min_value=10.0, max_value=200.0, value=24.20, step=0.01)
                edad_peak_on = st.number_input("Edad Objetivo de Madurez:", min_value=14.0, max_value=30.0, value=18.0, step=0.1)
                
            k_calculado_on = resolver_k_individual(t0_on, edad0_on, tpb_on, edad_pb_on, tpeak_on)
            edades_x = np.linspace(8.0, 24.0, 300)
            curva_y = calcular_curva_atleta(t0_on, edad0_on, tpeak_on, k_calculado_on, edades_x)
            tiempo_interp_on = float(np.interp(edad_consulta, edades_x, curva_y))
            
            fig, ax = plt.subplots(figsize=(10, 5.5))
            ax.plot(edades_x, curva_y, label=f"Proyección Teórica (k: {k_calculado_on:.4f})", color="blue", linewidth=2.5)
            ax.scatter([edad0_on], [t0_on], color="gray", s=100, zorder=5, label=f"T0 Debut: {t0_on:.2f}s")
            ax.scatter([edad_pb_on], [tpb_on], color="gold", marker="*", s=150, zorder=5, label=f"Tpb Récord: {tpb_on:.2f}s")
            ax.scatter([edad_peak_on], [tpeak_on], color="green", marker="s", s=100, zorder=5, label=f"Tpeak Target: {tpeak_on:.2f}s")
            ax.scatter([edad_consulta], [tiempo_interp_on], color="red", s=120, zorder=6, label=f"Consulta {edad_consulta}a: {tiempo_interp_on:.2f}s")
            
            ax.set_title(f"Simulación de Proyección de Rendimiento - {estilo_seleccionado}\n(Modo Online Manual de Cortesía)", fontsize=11, fontweight="bold")
            ax.set_xlabel("Edad Decimal (Años)", fontsize=10)
            ax.set_ylabel("Tiempo de Carrera (Segundos)", fontsize=10)
            ax.grid(True, linestyle=":", alpha=0.6)
            ax.legend(loc="upper right", fontsize=9)
            st.pyplot(fig)
            
            cm1, cm2 = st.columns(2)
            cm1.metric(label=f"Tiempo Estimado para la Edad de {edad_consulta} años:", value=f"{tiempo_interp_on:.2f} segundos")
            cm2.metric(label="Factor de Curvatura Biológica (k Calculado):", value=f"{k_calculado_on:.4f}")
            df_procesado = pd.DataFrame()

        # RAMAL CONECTADO COMPLETO CON BASE DE DATOS (MODO PREDETERMINADO)
        else:
            res_bio = supabase.table("usuarios").select("fecha_nacimiento, genero").eq("id", st.session_state.nadador_seleccionado_id).execute()
            if res_bio.data:
                bio = res_bio.data[0]
                genero_atleta = bio["genero"]
                cat_atleta = calcular_categoria_fevera(bio["fecha_nacimiento"])
                nacimiento_date = datetime.datetime.strptime(bio["fecha_nacimiento"], "%Y-%m-%d").date()
                edad_actual = (datetime.date.today() - nacimiento_date).days / 365.25
            else:
                genero_atleta = "F"; cat_atleta = "Juvenil A"; edad_actual = 14.5

            st.title("📊 Planificación y control de resultados de competencia")
            st.subheader(f"Atleta: {st.session_state.nadador_seleccionado_nombre} | Categoría: {cat_atleta} ({edad_actual:.2f} años)")

            # CORRECCIÓN DE LA LÍNEA 311: Cambiado 'usuario_id' por 'id_usuario' según tu esquema real
            res_marcas = supabase.table("marcas").select("*").eq("id_usuario", st.session_state.nadador_seleccionado_id).eq("estilo", estilo_seleccionado).order("edad_decimal").execute()
            df_procesado = pd.DataFrame(res_marcas.data) if res_marcas.data else pd.DataFrame()

            fig, ax = plt.subplots(figsize=(10, 5.5))
            edades_x = np.linspace(8.0, 24.0, 300)

            if not df_procesado.empty:
                t0_db = float(df_procesado.iloc[0]["tiempo_segundos"])
                edad0_db = float(df_procesado.iloc[0]["edad_decimal"])
                idx_pb = df_procesado["tiempo_segundos"].idxmin()
                tpb_db = float(df_procesado.loc[idx_pb, "tiempo_segundos"])
                edad_pb_db = float(df_procesado.loc[idx_pb, "edad_decimal"])
                
                tpeak_db = tpb_db * 0.85; edad_peak_db = 19.0
                k_solucion_db = resolver_k_individual(t0_db, edad0_db, tpb_db, edad_pb_db, tpeak_db)
                cur