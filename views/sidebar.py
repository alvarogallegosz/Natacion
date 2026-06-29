# =============================================================================
# 📁 views/sidebar.py - PANEL LATERAL COMPLETO CON TRIPLE MODO DE OPERACIÓN
# =============================================================================
import streamlit as st
import pandas as pd
import datetime

def renderizar_sidebar() -> str:
    """
    Despliega la barra lateral con infraestructura de sesión, selección fija de
    atletas, parámetros transversales fijos en la parte superior, selector de
    Modo Global de operación y sub-controles dinámicos inferiores.
    
    Retorna:
        str: El modo de operación seleccionado ('Individual', 'Visitante', 'Equipo')
    """
    supabase = st.session_state["supabase_client"]
    
    # 1. 🛡️ BLOQUE DE IDENTIDAD E INFRAESTRUCTURA BASE (PERMANENTE - TOPE SUPERIOR)
    st.sidebar.markdown(f"**Usuario:** {st.session_state.get('nombre_nadador', st.session_state.get('nombre', 'Usuario'))}  \n**Nivel:** `{st.session_state.get('rol', 'Invitado')}`")
    
    col_cierre, col_cache = st.sidebar.columns(2)
    with col_cierre:
        if st.button("🚪 Salir", use_container_width=True):
            st.session_state.autenticado = False
            st.rerun()
    with col_cache:
        if st.button("🔄 Limpiar", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
            
    st.sidebar.markdown("---")

    # 2. 🎯 PANEL DE NAVEGACIÓN DE ATLETAS (PERMANENTE - UBICACIÓN CORREGIDA)
    st.sidebar.subheader("🎯 Navegación de Atletas")
    rol_usuario = st.session_state.get("rol")
    usuario_id = st.session_state.get("usuario_id")
    
    atleta_id = usuario_id
    nombre_atleta = st.session_state.get("nombre", "Atleta")
    genero_atleta = "F"
    categoria_atleta = "Infantil B"

    if rol_usuario in ["Head Coach", "Entrenador", "Administrador"]:
        try:
            if rol_usuario == "Entrenador":
                resp_asig = supabase.table("asignaciones").select("atleta_id").eq("entrenador_id", usuario_id).execute()
                ids_asignados = [reg["atleta_id"] for reg in resp_asig.data] if resp_asig.data else []
                if ids_asignados:
                    resp_usr = supabase.table("usuarios").select("id, nombre, genero, categoria_competencia").in_("id", ids_asignados).eq("rol", "Nadador").execute()
                else:
                    resp_usr = None
            else:
                resp_usr = supabase.table("usuarios").select("id, nombre, genero, categoria_competencia").eq("rol", "Nadador").execute()

            if resp_usr and resp_usr.data:
                df_usuarios = pd.DataFrame(resp_usr.data)
                dict_atletas = dict(zip(df_usuarios['nombre'], df_usuarios['id']))
                dict_generos = dict(zip(df_usuarios['id'], df_usuarios['genero']))
                dict_cats = dict(zip(df_usuarios['id'], df_usuarios['categoria_competencia']))
                
                atleta_sel = st.sidebar.selectbox("Seleccionar Nadador de Base:", options=list(dict_atletas.keys()))
                atleta_id = dict_atletas[atleta_sel]
                nombre_atleta = atleta_sel
                genero_atleta = dict_generos[atleta_id]
                categoria_atleta = dict_cats.get(atleta_id, "Juvenil A")
            else:
                st.sidebar.info("No hay nadadores asignados.")
        except Exception as e:
            st.sidebar.error(f"Error cargando atletas: {e}")
    else:
        try:
            r_g = supabase.table("usuarios").select("genero, categoria_competencia").eq("id", usuario_id).execute()
            if r_g.data:
                genero_atleta = r_g.data[0]["genero"]
                categoria_atleta = r_g.data[0]["categoria_competencia"]
        except Exception:
            pass

    # Inyección persistente en sesión del atleta activo
    st.session_state["nadador_seleccionado_id"] = atleta_id
    st.session_state["nadador_seleccionado_genero"] = genero_atleta
    st.session_state["nadador_seleccionado_nombre"] = nombre_atleta
    st.session_state["nadador_seleccionado_categoria"] = categoria_atleta

    st.sidebar.markdown("---")

    # 3. ⏱️ SECCIÓN TRANSVERSAL PERMANENTE DEL MODELO (PERMANENTE - PARÁMETROS FISIOLÓGICOS)
    st.sidebar.subheader("⏱️ Parámetros del Modelo")
    h_val = st.sidebar.slider("Rapidez de la deriva de seguridad (h):", min_value=0.1, max_value=1.0, value=0.4, step=0.01)
    t_peak_val = st.sidebar.slider("Edad pico madurativo (t_peak):", min_value=14.0, max_value=22.0, value=18.0, step=0.5)
    
    # Conservar estados globales para el lienzo gráfico
    st.session_state["control_h"] = h_val
    st.session_state["control_t_peak"] = t_peak_val

    st.sidebar.markdown("---")

    # 4. 🔀 SELECTOR DEL MODO DE OPERACIÓN (PERMANENTE)
    modo_operacion = st.sidebar.radio(
        "🎛️ Modo de Operación del Gráfico",
        ["Individual (Oficial)", "Visitante (Simulación)", "Equipo (Comparativo)"]
    )

    st.sidebar.markdown("---")

    # 5. 📦 BLOQUES DINÁMICOS CONDICIONALES (FONDO DE LA SIDEBAR)
    if modo_operacion == "Individual (Oficial)":
        st.sidebar.caption("💡 Los hitos (t0, T0, t_pb, T_pb) se calculan automáticamente desde la base de datos del nadador activo.")

    elif modo_operacion == "Visitante (Simulación)":
        st.sidebar.subheader("🧪 Inputs Manuales de Consulta")
        c_v1, c_v2 = st.sidebar.columns(2)
        with c_v1:
            t0_sim = st.number_input("Edad Inicial (t0):", min_value=8.0, max_value=16.0, value=11.0, step=0.5)
            t_pb_sim = st.number_input("Edad Récord (t_pb):", min_value=10.0, max_value=22.0, value=14.0, step=0.5)
        with c_v2:
            T0_sim = st.number_input("Tiempo Inicial (T0):", min_value=20.0, max_value=200.0, value=120.0, step=1.0)
            T_pb_sim = st.number_input("Tiempo Récord (T_pb):", min_value=20.0, max_value=180.0, value=65.0, step=1.0)
            
        st.session_state["visitante_hitos"] = {
            "t0": t0_sim, "T0": T0_sim, "t_pb": t_pb_sim, "T_pb": T_pb_sim
        }

    elif modo_operacion == "Equipo (Comparativo)":
        st.sidebar.subheader("👥 Filtros de Población")
        filtro_genero = st.sidebar.selectbox("Filtro de Género:", ["Todos", "Femenino (F)", "Masculino (M)"])
        tipo_filtro_equipo = st.sidebar.radio("Segmentación:", ["Todos los Atletas", "Categoría Etaria", "Atletas Específicos"])
        
        cat_sel = None
        ids_sel = []
        
        if tipo_filtro_equipo == "Categoría Etaria":
            cat_sel = st.sidebar.selectbox("Categoría Activa:", ["Infantil A", "Infantil B", "Juvenil A", "Juvenil B", "Máxima"])
        elif tipo_filtro_equipo == "Atletas Específicos":
            try:
                r_all = supabase.table("usuarios").select("id, nombre").eq("rol", "Nadador").execute()
                if r_all.data:
                    df_all = pd.DataFrame(r_all.data)
                    dict_all = dict(zip(df_all['nombre'], df_all['id']))
                    atletas_multi = st.sidebar.multiselect("Seleccionar Nadadores:", options=list(dict_all.keys()))
                    ids_sel = [dict_all[name] for name in atletas_multi]
            except Exception as e:
                st.sidebar.error(f"Error cargando muestra: {e}")
                
        st.session_state["equipo_filtros"] = {
            "genero": filtro_genero,
            "tipo_filtro": tipo_filtro_equipo,
            "categoria": cat_sel,
            "ids_especificos": ids_sel
        }

    # Control de infraestructura oculta (Modo de simulación de backend)
    st.sidebar.markdown("---")
    st.sidebar.caption("Configuraciones Avanzadas")
    simulacion_activa = st.sidebar.toggle("Activar Modo Simulación Local", value=False)
    st.session_state["simulacion_local_activa"] = simulacion_activa

    return modo_operacion
