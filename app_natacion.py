import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import fsolve
import pandas as pd
import datetime
import io
import hashlib
from supabase import create_client, Client

# 1. CONFIGURACIÓN DE LA PÁGINA
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
# FUNCIÓN DE SEGURIDAD: HASH DE CONTRASEÑAS (Solución 2)
# -------------------------------------------------------------
def hash_password(password: str) -> str:
   """Aplica hash SHA-256 a las contraseñas antes de interactuar con la BD."""
   return hashlib.sha256(password.encode('utf-8')).hexdigest()

# -------------------------------------------------------------
# LÓGICA DE CATEGORÍAS ETARIAS (Edad cumplida al 31 de Diciembre)
# -------------------------------------------------------------
def calcular_categoria_competencia(fecha_nacimiento_date):
   if not fecha_nacimiento_date:
       return "Desconocida", 0
   if isinstance(fecha_nacimiento_date, str):
       fecha_nacimiento_date = datetime.datetime.strptime(fecha_nacimiento_date, "%Y-%m-%d").date()
   
   año_actual = datetime.datetime.now().year
   edad_competencia = año_actual - fecha_nacimiento_date.year
   
   if edad_competencia <= 9:
       cat = "Pre-Infantil"
   elif edad_competencia in [10, 11]:
       cat = "Infantil A"
   elif edad_competencia in [12, 13]:
       cat = "Infantil B"
   elif edad_competencia in [14, 15]:
       cat = "Juvenil A"
   elif edad_competencia in [16, 17, 18]:
       cat = "Juvenil B"
   else:
       cat = "Máxima"
   return cat, edad_competencia

def calcular_edad_decimal(fecha_nacimiento_date, fecha_evento_date):
   if isinstance(fecha_nacimiento_date, str):
       fecha_nacimiento_date = datetime.datetime.strptime(fecha_nacimiento_date, "%Y-%m-%d").date()
   if isinstance(fecha_evento_date, str):
       fecha_evento_date = datetime.datetime.strptime(fecha_evento_date, "%Y-%m-%d").date()
   delta_dias = (fecha_evento_date - fecha_nacimiento_date).days
   return delta_dias / 365.25

# -------------------------------------------------------------
# INICIALIZACIÓN DEL ESTADO DE SESIÓN (Solución 4)
# -------------------------------------------------------------
if "autenticado" not in st.session_state:
   st.session_state.autenticado = False
if "usuario_id" not in st.session_state:
   st.session_state.usuario_id = None
if "nombre_usuario" not in st.session_state:
   st.session_state.nombre_usuario = ""
if "rol" not in st.session_state:
   st.session_state.rol = "Nadador"
if "genero" not in st.session_state:
   st.session_state.genero = "F"
if "fecha_nacimiento" not in st.session_state:
   st.session_state.fecha_nacimiento = datetime.date(2013, 1, 1)

# Variables dinámicas de control para entrenadores/administradores
if "nadador_seleccionado_id" not in st.session_state:
   st.session_state.nadador_seleccionado_id = None
if "nadador_seleccionado_nombre" not in st.session_state:
   st.session_state.nadador_seleccionado_nombre = ""
if "nadador_seleccionado_fecha_nacimiento" not in st.session_state:
   st.session_state.nadador_seleccionado_fecha_nacimiento = datetime.date(2013, 1, 1)

# -------------------------------------------------------------
# INTERFAZ DE AUTENTICACIÓN
# -------------------------------------------------------------
if not st.session_state.autenticado:
   st.title("🏊‍♂️ Sistema de Gestión y Proyección de Rendimiento")
   menu_auth = st.tabs(["Iniciar Sesión", "Registrarse como Nadador"])
   
   with menu_auth[0]:
       st.subheader("Acceso al Sistema")
       login_email = st.text_input("Correo Electrónico", key="login_email").strip().lower()
       login_pass = st.text_input("Contraseña", type="password", key="login_pass")
       
       if st.button("Ingresar", use_container_width=True):
           if login_email and login_pass:
               # Aplicamos Hash para comparar con la BD de forma segura (Solución 2)
               hashed_pass = hash_password(login_pass)
               res = supabase.table("usuarios").select("*").eq("email", login_email).eq("contrasena", hashed_pass).execute()
               
               if len(res.data) > 0:
                   user_data = res.data[0]
                   st.session_state.autenticado = True
                   st.session_state.usuario_id = user_data["id"]
                   st.session_state.nombre_usuario = user_data["nombre"]
                   st.session_state.rol = user_data.get("rol", "Nadador")
                   st.session_state.genero = user_data.get("genero", "F")
                   
                   f_nac = user_data.get("fecha_nacimiento")
                   if f_nac:
                       st.session_state.fecha_nacimiento = datetime.datetime.strptime(f_nac, "%Y-%m-%d").date()
                   
                   st.success(f"¡Bienvenido, {st.session_state.nombre_usuario} ({st.session_state.rol})!")
                   st.rerun()
               else:
                   st.error("Credenciales incorrectas o usuario inexistente.")
           else:
               st.warning("Complete todos los campos.")
               
   with menu_auth[1]:
       st.subheader("Registro de Atleta")
       reg_nombre = st.text_input("Nombre Completo")
       reg_email = st.text_input("Correo Electrónico (Para Login)").strip().lower()
       reg_pass = st.text_input("Establecer Contraseña", type="password")
       reg_genero = str(st.selectbox("Género FINA", ["F", "M"]))
       reg_fnac = st.date_input("Fecha de Nacimiento", min_value=datetime.date(1950, 1, 1))
       
       if st.button("Registrar Cuenta", use_container_width=True):
           if reg_nombre and reg_email and reg_pass:
               check_user = supabase.table("usuarios").select("id").eq("email", reg_email).execute()
               if len(check_user.data) > 0:
                   st.error("El correo ya está registrado.")
               else:
                   # Encriptación segura de contraseña (Solución 2)
                   secure_pass = hash_password(reg_pass)
                   new_user = {
                       "nombre": reg_nombre,
                       "email": reg_email,
                       "contrasena": secure_pass,
                       "rol": "Nadador",
                       "genero": reg_genero,
                       "fecha_nacimiento": str(reg_fnac)
                   }
                   supabase.table("usuarios").insert(new_user).execute()
                   st.success("Registro exitoso. Inicie sesión en la pestaña correspondiente.")
           else:
               st.warning("Por favor rellene los campos obligatorios.")
   st.stop()

# -------------------------------------------------------------
# CONTROLADORES DE LA BARRA LATERAL (GESTIÓN DE ROLES Y MODOS)
# -------------------------------------------------------------
st.sidebar.title(f"👤 {st.session_state.nombre_usuario}")
st.sidebar.write(f"**Rol actual:** {st.session_state.rol}")

if st.sidebar.button("🔒 Cerrar Sesión"):
   for key in list(st.session_state.keys()):
       del st.session_state[key]
   st.rerun()

# INTERVENCIONES PRINCIPALES DEL SIMULADOR (Solución 7 y 8)
st.sidebar.markdown("---")
st.sidebar.markdown("### ⚙️ Configuración del Entorno")

# Inversión de casilla: Predeterminado en Falso, arranca conectado a BD (Solución 7)
modo_simulacion = st.sidebar.checkbox("Modo Simulación Externa / Libre", value=False)

# Inicialización de variables soberanas basadas en el modo (Solución 8)
if modo_simulacion:
   st.sidebar.info("🤖 Modo Simulación Activo (Datos Libres de BD)")
   genero_analisis = st.sidebar.selectbox("Género (Simulación)", ["F", "M"])
   fecha_nac_analisis = st.sidebar.date_input("Fecha de Nacimiento (Simulación)", datetime.date(2013, 1, 1))
   categoria_analisis, edad_comp_analisis = calcular_categoria_competencia(fecha_nac_analisis)
   nombre_sujeto = "Atleta en Simulación"
   id_sujeto_bd = None
else:
   # Modo Base de Datos Normal
   if st.session_state.rol in ["Entrenador", "Administrador"]:
       res_atletas = supabase.table("usuarios").select("id", "nombre", "genero", "fecha_nacimiento").eq("rol", "Nadador").order("nombre").execute()
       lista_atletas = res_atletas.data if res_atletas.data else []
       
       if lista_atletas:
           opciones_atletas = {a["nombre"]: a for a in lista_atletas}
           seleccion_nombre = st.sidebar.selectbox("Seleccionar Atleta del Equipo:", list(opciones_atletas.keys()))
           
           atleta_info = opciones_atletas[seleccion_nombre]
           st.session_state.nadador_seleccionado_id = atleta_info["id"]
           st.session_state.nadador_seleccionado_nombre = atleta_info["nombre"]
           st.session_state.genero = atleta_info["genero"]
           
           # Solución 4: Sincronización inmediata de fecha de nacimiento desde la barra lateral
           if atleta_info["fecha_nacimiento"]:
               st.session_state.nadador_seleccionado_fecha_nacimiento = datetime.datetime.strptime(atleta_info["fecha_nacimiento"], "%Y-%m-%d").date()
           else:
               st.session_state.nadador_seleccionado_fecha_nacimiento = datetime.date(2013, 1, 1)
       else:
           st.sidebar.warning("No hay nadadores en el club.")
           st.session_state.nadador_seleccionado_id = st.session_state.usuario_id
           st.session_state.nadador_seleccionado_nombre = st.session_state.nombre_usuario
           st.session_state.nadador_seleccionado_fecha_nacimiento = st.session_state.fecha_nacimiento
   else:
       # Si es rol Nadador común
       st.session_state.nadador_seleccionado_id = st.session_state.usuario_id
       st.session_state.nadador_seleccionado_nombre = st.session_state.nombre_usuario
       st.session_state.nadador_seleccionado_fecha_nacimiento = st.session_state.fecha_nacimiento

   genero_analisis = st.session_state.genero
   fecha_nac_analisis = st.session_state.nadador_seleccionado_fecha_nacimiento
   categoria_analisis, edad_comp_analisis = calcular_categoria_competencia(fecha_nac_analisis)
   nombre_sujeto = st.session_state.nadador_seleccionado_nombre
   id_sujeto_bd = st.session_state.nadador_seleccionado_id

st.sidebar.metric("Categoría Competencia", categoria_analisis)
st.sidebar.metric("Edad de Competencia", f"{edad_comp_analisis} años")

# Parámetros Globales de la Prueba
st.sidebar.markdown("---")
st.sidebar.markdown("### 🏊‍♂️ Configuración de la Prueba")
prueba_seleccionada = st.sidebar.selectbox(
   "Estilo y Distancia",
   ["50m Libre", "100m Libre", "200m Libre", "400m Libre", "800m Libre", "1500m Libre",
    "50m Espalda", "100m Espalda", "200m Espalda",
    "50m Pecho", "100m Pecho", "200m Pecho",
    "50m Mariposa", "100m Mariposa", "200m Mariposa",
    "200m Combinado", "400m Combinado"]
)

# -------------------------------------------------------------
# MOTOR MATEMÁTICO ASINTÓTICO (Restaurado a la versión original + Solución 3)
# -------------------------------------------------------------
def resolver_k_individual(eq_t0, eq_T0, eq_t_pb, eq_T_pb, eq_t_peak, eq_T_target):
    # Solución 3: Validación física para evitar fallos en fsolve y quiebres visuales
    if eq_t_peak > eq_t0 and eq_t_pb > eq_t0:
        if eq_T_pb >= eq_T0:
            return 0.4  # Retorno seguro si el tiempo empeoró
            
        tau_eq = (eq_t_pb - eq_t0) / (eq_t_peak - eq_t0)
        
        def ecuacion_k_eq(k_val):
            ter_exp = (np.exp(-k_val * tau_eq) - np.exp(-k_val)) / (1 - np.exp(-k_val))
            return (eq_T_target + (eq_T0 - eq_T_target) * ter_exp) - eq_T_pb
            
        try:
            # Solución 3: Bloque try-except para fallos de optimización
            k_opt_eq, _, ier, msg = fsolve(ecuacion_k_eq, 1.0, full_output=True)
            if ier == 1:
                return k_opt_eq[0]
            else:
                return 0.4
        except Exception:
            return 0.4
    return 0.4


def calcular_curva_atleta(edades_arr, eq_t0, eq_T0, eq_t_pb, eq_T_pb, eq_t_peak, eq_T_target, k_eq, h_eq):
    # Restaurado a tu ecuación original de doble fase asintótica
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

# -------------------------------------------------------------
# EXTRACCIÓN Y PREPARACIÓN DE DATOS (Solución 3)
# -------------------------------------------------------------
# Extraer marcas de referencia estables resguardando nulos
res_ref = supabase.table("marcas_referencia").select("*").eq("prueba", prueba_seleccionada).eq("genero", genero_analisis).eq("categoria", categoria_analisis).execute()

# Solución 3: Control explícito de valores nulos (None) para evitar caídas en st.number_input
val_panam = 0.0
val_wa = 0.0
val_wr = 0.0

if res_ref.data and len(res_ref.data) > 0:
   ref_row = res_ref.data[0]
   try:
       val_panam = float(ref_row.get("panam")) if ref_row.get("panam") is not None else 0.0
       val_wa = float(ref_row.get("wa")) if ref_row.get("wa") is not None else 0.0
       val_wr = float(ref_row.get("wr")) if ref_row.get("wr") is not None else 0.0
   except (ValueError, TypeError):
       pass

# Cargar Historial de Tiempos del Atleta
df_procesado = pd.DataFrame()
if not modo_simulacion and id_sujeto_bd:
   res_marcas = supabase.table("marcas_historicas").select("*").eq("usuario_id", id_sujeto_bd).eq("prueba", prueba_seleccionada).order("fecha_competencia").execute()
   if res_marcas.data:
       df_raw = pd.DataFrame(res_marcas.data)
       df_raw["fecha_competencia"] = pd.to_datetime(df_raw["fecha_competencia"]).dt.date
       
       datos_procesados = []
       for index, row in df_raw.iterrows():
           t_dec = calcular_edad_decimal(fecha_nac_analisis, row["fecha_competencia"])
           datos_procesados.append({
               "id": row["id"],
               "Fecha": row["fecha_competencia"].strftime("%d-%m-%Y"),
               "Evento / Fecha": f"{row['evento']} ({row['fecha_competencia'].strftime('%d-%m-%Y')})",
               "Edad Decimal": t_dec,
               "Tiempo": float(row["tiempo_segundos"])
           })
       df_procesado = pd.DataFrame(datos_procesados)

# -------------------------------------------------------------
# CONTROL DE PESTAÑAS SEGÚN ROLES
# -------------------------------------------------------------
tabs_principales = st.tabs(["📊 Análisis y Proyección", "⏱️ Control de Marcas", "📋 Consola de Entrenamiento", "🛠️ Administración"])

# =============================================================
# PESTAÑA 1: ANÁLISIS Y PROYECTO DE RENDIMIENTO
# =============================================================
with tabs_principales[0]:
   st.header(f"Análisis de Rendimiento: {nombre_sujeto}")
   st.subheader(f"Prueba: {prueba_seleccionada} ({genero_analisis} - {categoria_analisis})")
   
   # Parámetros de Control (Manuales o Automáticos dependientes de la casilla)
   c_p1, c_p2, c_p3, c_p4 = st.columns(4)
   
   # Lógica de asignación de variables iniciales automáticas o por defecto
   n_registros = len(df_procesado)
   def_t0, def_T0, def_t_pb, def_T_pb = 11.0, 45.0, 13.5, 31.0
   
   if n_registros >= 2:
       def_t0 = float(df_procesado["Edad Decimal"].iloc[0])
       def_T0 = float(df_procesado["Tiempo"].iloc[0])
       idx_min = df_procesado["Tiempo"].idxmin()
       def_t_pb = float(df_procesado["Edad Decimal"].loc[idx_min])
       def_T_pb = float(df_procesado["Tiempo"].loc[idx_min])
   
   with c_p1:
       t0 = st.number_input("Edad Base Fisiológica ($t_0$)", value=def_t0, step=0.1, format="%.2f")
   with c_p2:
       T0 = st.number_input("Tiempo en Edad Base ($T_0$s)", value=def_T0, step=0.1, format="%.2f")
   with c_p3:
       t_pb = st.number_input("Edad de Máximo Rendimiento ($t_{pb}$)", value=def_t_pb, step=0.1, format="%.2f")
   with c_p4:
       T_pb = st.number_input("Tiempo Récord Personal ($T_{pb}$s)", value=def_T_pb, step=0.1, format="%.2f")
       
   k_fisiologico = resolver_k_individual(t0, T0, t_pb, T_pb)
   st.sidebar.metric("Factor de Ajuste Matemático ($k$)", f"{k_fisiologico:.4f}")
   
   # Renderizado Gráfico Principal
   edades_curva = np.linspace(t0, 18.0, 200)
   tiempos_curva = [evaluar_modelo_rendimiento(ex, t0, T0, t_pb, T_pb, k_fisiologico) for ex in edades_curva]
   
   fig, ax = plt.subplots(figsize=(10, 5.5))
   ax.plot(edades_curva, tiempos_curva, label="Modelo de Proyección Continuo", color="blue", linewidth=2)
   
   if n_registros > 0:
       ax.scatter(df_procesado["Edad Decimal"], df_procesado["Tiempo"], color="red", zorder=5, label="Historial Real")
       
   if val_panam > 0: ax.axhline(val_panam, color="orange", linestyle="--", label=f"Mínima PANAM ({val_panam}s)")
   if val_wa > 0: ax.axhline(val_wa, color="purple", linestyle="--", label=f"Mínima WA ({val_wa}s)")
   if val_wr > 0: ax.axhline(val_wr, color="gold", linestyle="-.", label=f"Récord Mundial ({val_wr}s)")
   
   ax.set_title(f"Evolución y Límites Fisiológicos - {nombre_sujeto}\nPrueba: {prueba_seleccionada}")
   ax.set_xlabel("Edad del Deportista (Años)")
   ax.set_ylabel("Tiempo de Carrera (Segundos)")
   ax.grid(True, linestyle=":", alpha=0.6)
   ax.legend(loc="upper right")
   st.pyplot(fig)
   
   # ---------------------------------------------------------
   # MÓDULO COLECTIVO SIN CONSULTAS N+1 (Solución 1)
   # ---------------------------------------------------------
   st.markdown("---")
   st.markdown("### 👥 Análisis de Rendimiento Colectivo del Equipo")
   
   res_todos_atletas = supabase.table("usuarios").select("id", "nombre").eq("rol", "Nadador").execute()
   dict_todos = {at["id"]: at["nombre"] for at in res_todos_atletas.data} if res_todos_atletas.data else {}
   
   if dict_todos:
       atletas_seleccionados_ids = st.multiselect(
           "Seleccionar Atletas para Comparación:",
           options=list(dict_todos.keys()),
           format_func=lambda x: dict_todos[x]
       )
       
       if atletas_seleccionados_ids:
           # Solución 1: Una única petición a Supabase usando .in_() evitando ciclos N+1
           res_colectiva = supabase.table("marcas_historicas")\
               .select("usuario_id", "tiempo_segundos", "fecha_competencia")\
               .eq("prueba", prueba_seleccionada)\
               .in_("usuario_id", atletas_seleccionados_ids)\
               .order("fecha_competencia").execute()
               
           if res_colectiva.data:
               df_col_raw = pd.DataFrame(res_colectiva.data)
               
               # Cargar metadatos de fechas de nacimiento de atletas implicados en una sola consulta
               res_meta = supabase.table("usuarios").select("id", "fecha_nacimiento").in_("id", atletas_seleccionados_ids).execute()
               meta_nac = {m["id"]: m["fecha_nacimiento"] for m in res_meta.data} if res_meta.data else {}
               
               fig_col, ax_col = plt.subplots(figsize=(10, 5))
               
               for a_id in atletas_seleccionados_ids:
                   df_sub = df_col_raw[df_col_raw["usuario_id"] == a_id].copy()
                   f_nac_str = meta_nac.get(a_id)
                   
                   if not df_sub.empty and f_nac_str:
                       f_nac_d = datetime.datetime.strptime(f_nac_str, "%Y-%m-%d").date()
                       df_sub["fecha_competencia"] = pd.to_datetime(df_sub["fecha_competencia"]).dt.date
                       df_sub["Edad Decimal"] = df_sub["fecha_competencia"].apply(lambda x: calcular_edad_decimal(f_nac_d, x))
                       df_sub["Tiempo"] = df_sub["tiempo_segundos"].astype(float)
                       
                       ax_col.plot(df_sub["Edad Decimal"], df_sub["Tiempo"], marker="o", label=dict_todos[a_id])
               
               ax_col.set_title(f"Comparativa de Evolución Temporal de Tiempos - {prueba_seleccionada}")
               ax_col.set_xlabel("Edad Decimal")
               ax_col.set_ylabel("Segundos")
               ax_col.grid(True, linestyle=":")
               ax_col.legend()
               st.pyplot(fig_col)
           else:
               st.info("No se registran marcas cronometradas para los atletas seleccionados en esta prueba.")

# =============================================================
# PESTAÑA 2: CONTROL DE MARCAS CRONOMETRADAS (Solución 9)
# =============================================================
with tabs_principales[1]:
   st.header("Historial Cronológico de Tiempos")
   
   if modo_simulacion:
       st.warning("⚠️ Está en Modo Simulación Libre. El registro histórico y las modificaciones de BD están deshabilitados.")
   else:
       if n_registros > 0:
           st.dataframe(df_procesado.drop(columns=["id"]), use_container_width=True)
           
           # Validación de Rol con Privilegios para Modificación y Borrado
           if st.session_state.rol in ["Entrenador", "Administrador"]:
               st.markdown("### 🗑️ Zona de Gestión de Erreores")
               
               # Solución 9: Se utiliza format_func para ocultar la ID cruda y mostrar descripción legible
               id_para_eliminar = st.selectbox(
                   "Seleccione el registro erróneo a eliminar:",
                   options=df_procesado["id"].tolist(),
                   format_func=lambda x: f"{df_procesado.loc[df_procesado['id'] == x, 'Evento / Fecha'].values[0]} -> {df_procesado.loc[df_procesado['id'] == x, 'Tiempo'].values[0]}s"
               )
               
               if st.button("Eliminar Registro Permanentemente", type="primary"):
                   supabase.table("marcas_historicas").delete().eq("id", id_para_eliminar).execute()
                   st.success("Registro eliminado satisfactoriamente de la base de datos.")
                   st.rerun()
       else:
           st.info("No hay tiempos registrados en el historial de la base de datos para esta prueba.")

       # Inserción de Nuevas Marcas
       st.markdown("---")
       st.markdown("### ⏱️ Registrar Nueva Marca Cronometrada")
       c_i1, c_i2, c_i3 = st.columns(3)
       with c_i1:
           ins_evento = st.text_input("Nombre de la Competencia / Chequeo")
       with c_i2:
           ins_fecha = st.date_input("Fecha del Evento", datetime.date.today())
       with c_i3:
           ins_tiempo = st.number_input("Tiempo Logrado (Segundos)", min_value=5.0, max_value=600.0, value=30.0, step=0.01)
           
       if st.button("Guardar Marca Histórica", use_container_width=True):
           if ins_evento and id_sujeto_bd:
               nueva_marca = {
                   "usuario_id": id_sujeto_bd,
                   "prueba": prueba_seleccionada,
                   "evento": ins_evento,
                   "fecha_competencia": str(ins_fecha),
                   "tiempo_segundos": ins_tiempo
               }
               supabase.table("marcas_historicas").insert(nueva_marca).execute()
               st.success("Nueva marca indexada con éxito.")
               st.rerun()
           else:
               st.error("Rellene el nombre del evento para efectuar la carga.")

# =============================================================
# PESTAÑA 3: CONSOLA DE ENTRENAMIENTO (Solución 6)
# =============================================================
with tabs_principales[2]:
   st.header("Parámetros de Referencia Deportiva (Carga de Mínimas)")
   
   if st.session_state.rol not in ["Entrenador", "Administrador"]:
       st.error("Área restringida. Solo personal técnico autorizado con rol de Entrenador o Administrador.")
   else:
       st.subheader(f"Configurar Tiempos para: {prueba_seleccionada}")
       st.write(f"Parámetros actuales para la categoría **{categoria_analisis}** ({genero_analisis})")
       
       c_r1, c_r2, c_r3 = st.columns(3)
       with c_r1:
           in_panam = st.number_input("Mínima Panamericana (PANAM)", value=val_panam, step=0.01)
       with c_r2:
           in_wa = st.number_input("Marca de Calificación WA", value=val_wa, step=0.01)
       with c_r3:
           in_wr = st.number_input("Récord Mundial Vigente (WR)", value=val_wr, step=0.01)
           
       if st.button("Actualizar Tiempos de Referencia", use_container_width=True):
           # Solución 6: Eliminamos el .upsert() ciego y estructuramos verificación explícita con select-insert/update
           check_existencia = supabase.table("marcas_referencia")\
               .select("id")\
               .eq("prueba", prueba_seleccionada)\
               .eq("genero", genero_analisis)\
               .eq("categoria", categoria_analisis).execute()
               
           datos_ref = {
               "prueba": prueba_seleccionada,
               "genero": genero_analisis,
               "categoria": categoria_analisis,
               "panam": in_panam,
               "wa": in_wa,
               "wr": in_wr
           }
           
           if check_existencia.data and len(check_existencia.data) > 0:
               # Si ya existe, ejecutamos un Update dirigido por ID único
               row_id = check_existencia.data[0]["id"]
               supabase.table("marcas_referencia").update(datos_ref).eq("id", row_id).execute()
               st.success("Tiempos de referencia actualizados mediante UPDATE con éxito.")
           else:
               # Si no existe, creamos la fila limpia
               supabase.table("marcas_referencia").insert(datos_ref).execute()
               st.success("Nuevos tiempos de referencia insertados mediante INSERT con éxito.")
           st.rerun()

# =============================================================
# PESTAÑA 4: ADMINISTRACIÓN GENERAL DEL SISTEMA
# =============================================================
with tabs_principales[3]:
   st.header("Consola de Control de Cuentas")
   if st.session_state.rol != "Administrador":
       st.error("Acceso Denegado. Se requieren credenciales de Administrador del sistema.")
   else:
       res_usuarios_total = supabase.table("usuarios").select("id", "nombre", "email", "rol", "genero").order("nombre").execute()
       if res_usuarios_total.data:
           df_usuarios = pd.DataFrame(res_usuarios_total.data)
           st.dataframe(df_usuarios, use_container_width=True)
           
           st.markdown("### Promoción de Privilegios Técnicos")
           user_cambio_id = st.selectbox("Seleccione el Usuario:", options=df_usuarios["id"].tolist(), format_func=lambda x: df_usuarios.loc[df_usuarios["id"] == x, "nombre"].values[0])
           nuevo_rol = st.selectbox("Asignar Nuevo Rol Técnico:", ["Nadador", "Entrenador", "Administrador"])
           
           if st.button("Confirmar Cambio de Rol Estructural"):
               supabase.table("usuarios").update({"rol": nuevo_rol}).eq("id", user_cambio_id).execute()
               st.success("Jerarquía de usuario actualizada.")
               st.rerun()