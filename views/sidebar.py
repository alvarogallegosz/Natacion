# =============================================================================
# 📁 views/sidebar.py - PANEL LATERAL DE NAVEGACIÓN, CONTROL Y CÁLCULO DE HITOS
# =============================================================================
import streamlit as st
import pandas as pd
import datetime

def renderizar_sidebar() -> bool:
    """
    Despliega la barra lateral original, gestiona la selección de atletas, 
    calcula dinámicamente los hitos (t0, T0, t_pb, T_pb) y maneja los modos de simulación.
    """
    supabase = st.session_state["supabase_client"]
    
    # Encabezado del usuario actual
    st.sidebar.markdown(f"**Usuario:** {st.session_state.get('nombre', 'Usuario')}  \n**Nivel:** `{st.session_state.get('rol', 'Invitado')}`")
    if st.sidebar.button("🚪 Salir del Sistema"):
        st.session_state.autenticado = False
        st.rerun()

    st.sidebar.markdown("---")
    if st.sidebar.button("🔄 Refrescar Datos (Limpiar Caché)"):
        st.cache_data.clear()
        st.rerun()

    # --- ENTORNO DE SIMULACIÓN VS PRODUCCIÓN ---
    st.sidebar.markdown("### 🛠️ Configuración de Entorno")
    simulacion_activa = st.sidebar.toggle("Activar Modo Simulación", value=False)

    # --- SELECCIÓN DE ATLETA (Para Entrenadores/Admin) ---
    rol_usuario = st.session_state.get("rol")
    usuario_id = st.session_state.get("usuario_id")
    
    atleta_id = usuario_id
    nombre_atleta = st.session_state.get("nombre", "Atleta")
    genero_atleta = "F" # Valor por defecto seguro

    if rol_usuario in ["Head Coach", "Entrenador", "Administrador"]:
        st.sidebar.subheader("🎯 Panel de Navegación de Atletas")
        try:
            # Obtener lista de atletas asignados o todos si es Admin/Head Coach
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
                
                atleta_sel = st.sidebar.selectbox("Seleccionar Nadador:", options=list(dict_atletas.keys()))
                atleta_id = dict_atletas[atleta_sel]
                nombre_atleta = atleta_sel
                genero_atleta = dict_generos[atleta_id]
            else:
                st.sidebar.info("No tienes nadadores asignados en este momento.")
        except Exception as e:
            st.sidebar.error(f"Error cargando lista de atletas: {e}")
    else:
        # Si es un nadador, buscamos su propio género en la sesión o BD
        try:
            r_g = supabase.table("usuarios").select("genero").eq("id", usuario_id).execute()
            if r_g.data:
                genero_atleta = r_g.data[0]["genero"]
        except Exception:
            pass

    # Guardar variables críticas del atleta en el session_state para las vistas
    st.session_state["nadador_seleccionado_id"] = atleta_id
    st.session_state["nadador_seleccionado_genero"] = genero_atleta
    st.session_state["nadador_seleccionado_nombre"] = nombre_atleta

    # --- EXTRACCIÓN Y CÁLCULO EN TIEMPO REAL DE HITOS ---
    st.sidebar.markdown("---")
    st.sidebar.subheader("⏱️ Configuración del Modelo de Rendimiento")

    # Inicializamos valores por defecto de contingencia
    t0, T0, t_pb, T_pb, t_peak = 11.0, 120.0, 13.0, 65.0, 18.0

    # Determinar la prueba activa seleccionada en la UI
    prueba_activa = st.session_state.get("prueba_seleccionada", "100m Libre")

    try:
        # Extraer marcas del atleta seleccionado en la prueba activa
        r_hist = supabase.table("marcas_historicas")\
            .select("edad, tiempo")\
            .eq("usuario_id", atleta_id)\
            .eq("prueba", prueba_activa)\
            .order("edad", desc=False)\
            .execute()
            
        if r_hist.data:
            df_m = pd.DataFrame(r_hist.data)
            df_m['edad'] = df_m['edad'].astype(float)
            df_m['tiempo'] = df_m['tiempo'].astype(float)
            
            # Matemática original:
            t0 = float(df_m['edad'].min())
            T0 = float(df_m.loc[df_m['edad'].idxmin(), 'tiempo'])
            t_pb = float(df_m.loc[df_m['tiempo'].idxmin(), 'edad'])
            T_pb = float(df_m['tiempo'].min())
    except Exception as e:
        st.sidebar.caption(f"Hitos usando valores de referencia.")

    # Almacenar los hitos reales deducidos en el session_state
    st.session_state["hitos_modelo"] = {
        "t0": t0, "T0": T0, "t_pb": t_pb, "T_pb": T_pb
    }

    # Contenedor para los sliders en la Sidebar como en tu diseño original
    contenedor_sliders = st.sidebar.container()
    
    # Selector de tipo de visualización original
    tipo_vista = st.sidebar.radio("🔭 Escala del Gráfico", ["Macro (Historial Completo)", "Micro (Ventana Anual)"])
    st.session_state["tipo_vista"] = tipo_vista

    # Controles adaptativos de Zoom
    if tipo_vista == "Micro (Ventana Anual)":
        limite_inf_abs = float(t0)
        limite_sup_abs = 22.0  # Límite superior lógico
        rango_def_min = max(limite_inf_abs, min(float(t_pb), limite_sup_abs))
        rango_def_max = min(rango_def_min + 1.0, limite_sup_abs)
        
        edad_min_zoom, edad_max_zoom = st.sidebar.slider(
            "🔎 Rango de la Ventana (Edad)", min_value=8.0, max_value=22.0,
            value=(rango_def_min, rango_def_max), step=0.1, format="%.2f años"
        )
        st.session_state["zoom_edades"] = (edad_min_zoom, edad_max_zoom)
    else:
        st.session_state["zoom_edades"] = (8.0, 22.0)

    with contenedor_sliders:
        st.markdown("**⏱️ Rapidez de Deriva e Intervalo**")
        h_val = st.slider("Factor ajustable de rapidez de deriva (h):", min_value=0.1, max_value=1.0, value=0.4, step=0.01)
        t_peak_val = st.slider("Edad estimada del pico madurativo (t_peak):", min_value=14.0, max_value=22.0, value=18.0, step=0.5)
        
        # Guardamos los controles para que views/rendimiento.py los lea limpiamente
        st.session_state["control_h"] = h_val
        st.session_state["control_t_peak"] = t_peak_val

    return simulacion_activa
