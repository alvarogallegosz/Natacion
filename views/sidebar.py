# =============================================================================
# 📁 views/sidebar.py - PANEL LATERAL SIMPLIFICADO Y LIGERO
# =============================================================================
import streamlit as st
import pandas as pd

def renderizar_sidebar() -> str:
    supabase = st.session_state["supabase_client"]
    
    st.sidebar.markdown(
        """
        <style>
            [data-testid="stSidebar"] .element-container { margin-bottom: 0.3rem !important; }
            .mini-divisor { margin-top: 5px !important; margin-bottom: 8px !important; border-bottom: 1px solid #ddd; }
        </style>
        """, 
        unsafe_allow_html=True
    )

    # 1. IDENTIDAD E INFRAESTRUCTURA BASE
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

    # 2. NAVEGACIÓN DE ATLETAS
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
                
                atleta_sel = st.sidebar.selectbox("Seleccionar Nadador:", options=list(dict_atletas.keys()), label_visibility="collapsed")
                atleta_id = dict_atletas[atleta_sel]
                nombre_atleta = atleta_sel
                genero_atleta = dict_generos[atleta_id]
        except Exception as e:
            st.sidebar.error(f"Error cargando atletas: {e}")

    st.session_state["nadador_seleccionado_id"] = atleta_id
    st.session_state["nadador_seleccionado_genero"] = genero_atleta
    st.session_state["nadador_seleccionado_nombre"] = nombre_atleta

    st.sidebar.markdown('<div class="mini-divisor"></div>', unsafe_allow_html=True)

    # 3. PARÁMETROS FISIOLÓGICOS DEL MODELO
    st.sidebar.markdown("**⏱️ Parámetros del Modelo**")
    h_val = st.sidebar.slider("Rapidez de deriva (h):", min_value=0.1, max_value=1.0, value=0.4, step=0.01)
    t_peak_val = st.sidebar.slider("Pico madurativo (t_peak):", min_value=14.0, max_value=26.0, value=23.0, step=0.5)
    
    t_target_def = st.session_state.get("target_calculado_rm", 52.0)
    T_target_val = st.sidebar.number_input("Tiempo Objetivo (T_target):", min_value=10.0, max_value=1500.0, value=t_target_def, step=0.1)
    
    st.session_state["control_h"] = h_val
    st.session_state["control_t_peak"] = t_peak_val
    st.session_state["control_T_target"] = T_target_val

    st.sidebar.markdown('<div class="mini-divisor"></div>', unsafe_allow_html=True)

    # 4. GESTIÓN DE SIMULACIÓN EXTERNA (OCULTA EN LA BARRA LATERAL)
    st.sidebar.markdown("**🧪 Simulación de Escenarios**")
    activar_simulacion = st.sidebar.toggle("Activar modo simulación (Visitante)", value=False)
    
    if activar_simulacion:
        st.sidebar.caption("Ingrese los datos del escenario externo:")
        c_v1, c_v2 = st.sidebar.columns(2)
        with c_v1:
            t0_sim = st.number_input("t0 (Edad Ini):", min_value=8.0, max_value=16.0, value=11.0, step=0.5)
            t_pb_sim = st.number_input("t_pb (Edad Réc):", min_value=10.0, max_value=22.0, value=11.33, step=0.01)
        with c_v2:
            T0_sim = st.number_input("T0 (Tiempo Ini):", min_value=20.0, max_value=200.0, value=120.0, step=1.0)
            T_pb_sim = st.number_input("T_pb (Tiempo Réc):", min_value=20.0, max_value=180.0, value=65.0, step=1.0)
        st.session_state["visitante_hitos"] = {"t0": t0_sim, "T0": T0_sim, "t_pb": t_pb_sim, "T_pb": T_pb_sim}
        st.session_state["modo_operacion"] = "Visitante (Simulación Externa)"
    else:
        # Por defecto individual o equipo, se decidirá en la zona blanca central
        if "modo_operacion" not in st.session_state or st.session_state["modo_operacion"] == "Visitante (Simulación Externa)":
            st.session_state["modo_operacion"] = "Individual"

    return st.session_state["modo_operacion"]
