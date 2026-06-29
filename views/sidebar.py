# =============================================================================
# 📁 views/sidebar.py - PANEL LATERAL ULTRA COMPACTO CON JERARQUÍA ESTRICTA
# =============================================================================
import streamlit as st
import pandas as pd

def renderizar_sidebar() -> str:
    """
    Despliega la barra lateral con espaciado mínimo y orden estructural fijo.
    """
    supabase = st.session_state["supabase_client"]
    
    # Estilo CSS para reducir el margen vertical general de la sidebar y definir el divisor mini
    st.sidebar.markdown(
        """
        <style>
            [data-testid="stSidebar"] .element-container { margin-bottom: 0.3rem !important; }
            .mini-divisor { margin-top: 5px !important; margin-bottom: 8px !important; border-bottom: 1px solid #ddd; }
        </style>
        """, 
        unsafe_allow_html=True
    )

    # 1. BLOQUE DE IDENTIDAD E INFRAESTRUCTURA BASE (PERMANENTE - TOPE SUPERIOR)
    st.sidebar.markdown(f"**Usuario:** {st.session_state.get('nombre', 'Usuario')} | `{st.session_state.get('rol', 'Invitado')}`")
    
    col_cierre, col_cache = st.sidebar.columns(2)
    with col_cierre:
        if st.button("🚪 Salir", use_container_width=True):
            st.session_state.autenticado = False
            st.rerun()
    with col_cache:
        if st.button("🔄 Limpiar", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
            
    st.sidebar.markdown('<div class="mini-divisor"></div>', unsafe_allow_html=True)

    # 2. PANEL DE NAVEGACIÓN DE ATLETAS (PERMANENTE - INMEDIATAMENTE DEBAJO)
    st.sidebar.markdown("**🎯 Navegación de Atletas**")
    rol_usuario = st.session_state.get("rol")
    usuario_id = st.session_state.get("usuario_id")
    
    atleta_id = usuario_id
    nombre_atleta = st.session_state.get("nombre", "Atleta")
    genero_atleta = "F"

    if rol_usuario in ["Head Coach", "Entrenador", "Administrador"]:
        try:
            if rol_usuario == "Entrenador":
                resp_asig = supabase.table("asignaciones").select("atleta_id").eq("entrenador_id", usuario_id).execute()
                ids_asignados = [reg["atleta_id"] for reg in resp_asig.data] if resp_asig.data else []
                if ids_asignados:
                    resp_usr = supabase.table("usuarios").select("id, nombre, genero").in_("id", ids_asignados).eq("rol", "Nadador").execute()
                else:
                    resp_usr = None
            else:
                resp_usr = supabase.table("usuarios").select("id, nombre, genero").eq("rol", "Nadador").execute()

            if resp_usr and resp_usr.data:
                df_usuarios = pd.DataFrame(resp_usr.data)
                dict_atletas = dict(zip(df_usuarios['nombre'], df_usuarios['id']))
                dict_generos = dict(zip(df_usuarios['id'], df_usuarios['genero']))
                
                atleta_sel = st.sidebar.selectbox("Seleccionar Nadador de Base:", options=list(dict_atletas.keys()), label_visibility="collapsed")
                atleta_id = dict_atletas[atleta_sel]
                nombre_atleta = atleta_sel
                genero_atleta = dict_generos[atleta_id]
        except Exception as e:
            st.sidebar.error(f"Error cargando atletas: {e}")

    st.session_state["nadador_seleccionado_id"] = atleta_id
    st.session_state["nadador_seleccionado_genero"] = genero_atleta
    st.session_state["nadador_seleccionado_nombre"] = nombre_atleta

    st.sidebar.markdown('<div class="mini-divisor"></div>', unsafe_allow_html=True)

    # 4. SECCIÓN TRANSVERSAL PERMANENTE DEL MODELO (PARÁMETROS FISIOLÓGICOS)
    st.sidebar.markdown("**⏱️ Parámetros del Modelo**")
    h_val = st.sidebar.slider("Rapidez de deriva (h):", min_value=0.1, max_value=1.0, value=0.4, step=0.01)
    t_peak_val = st.sidebar.slider("Pico madurativo (t_peak):", min_value=14.0, max_value=22.0, value=18.0, step=0.5)
    T_target_val = st.sidebar.number_input("Tiempo Objetivo (T_target):", min_value=10.0, max_value=1500.0, value=52.0, step=0.1)
    
    st.session_state["control_h"] = h_val
    st.session_state["control_t_peak"] = t_peak_val
    st.session_state["control_T_target"] = T_target_val

    st.sidebar.markdown('<div class="mini-divisor"></div>', unsafe_allow_html=True)

    # 5. SELECTOR DEL MODO DE OPERACIÓN (PERMANENTE)
    st.sidebar.markdown("**🎛️ Modo de Operación**")
    modo_operacion = st.sidebar.radio(
        "Modo de Operación Interno",
        ["Individual", "Visitante (Simulación Externa)", "Equipo"],
        label_visibility="collapsed"
    )
    st.session_state["modo_operacion"] = modo_operacion

    st.sidebar.markdown('<div class="mini-divisor"></div>', unsafe_allow_html=True)

    # 6. BLOQUES DINÁMICOS CONDICIONALES (AL FONDO DE LA SIDEBAR)
    if modo_operacion == "Visitante (Simulación Externa)":
        st.sidebar.markdown("**🧪 Parámetros de Simulación**")
        c_v1, c_v2 = st.sidebar.columns(2)
        with c_v1:
            t0_sim = st.number_input("t0 (Edad Ini):", min_value=8.0, max_value=16.0, value=11.0, step=0.5)
            t_pb_sim = st.number_input("t_pb (Edad Réc):", min_value=10.0, max_value=22.0, value=14.0, step=0.5)
        with c_v2:
            T0_sim = st.number_input("T0 (Tiempo Ini):", min_value=20.0, max_value=200.0, value=120.0, step=1.0)
            T_pb_sim = st.number_input("T_pb (Tiempo Réc):", min_value=20.0, max_value=180.0, value=65.0, step=1.0)
            
        st.session_state["visitante_hitos"] = {"t0": t0_sim, "T0": T0_sim, "t_pb": t_pb_sim, "T_pb": T_pb_sim}

    elif modo_operacion == "Equipo":
        st.sidebar.markdown("**👥 Segmentación de Grupo**")
        filtro_genero = st.sidebar.selectbox("Filtro Género:", ["Todos", "Femenino (F)", "Masculino (M)"])
        tipo_filtro_equipo = st.sidebar.radio("Filtrado por:", ["Todos los Atletas", "Categoría Etaria", "Atletas Específicos"])
        
        cat_sel = None
        ids_sel = []
        
        if tipo_filtro_equipo == "Categoría Etaria":
            cat_sel = st.sidebar.selectbox("Categoría:", ["Infantil A", "Infantil B", "Juvenil A", "Juvenil B", "Máxima"])
        elif tipo_filtro_equipo == "Atletas Específicos":
            try:
                r_all = supabase.table("usuarios").select("id, nombre").eq("rol", "Nadador").execute()
                if r_all.data:
                    df_all = pd.DataFrame(r_all.data)
                    dict_all = dict(zip(df_all['nombre'], df_all['id']))
                    atletas_multi = st.sidebar.multiselect("Nadadores:", options=list(dict_all.keys()))
                    ids_sel = [dict_all[name] for name in atletas_multi]
            except Exception:
                pass
                
        st.session_state["equipo_filtros"] = {"genero": filtro_genero, "tipo_filtro": tipo_filtro_equipo, "categoria": cat_sel, "ids_especificos": ids_sel}

    return modo_operacion
