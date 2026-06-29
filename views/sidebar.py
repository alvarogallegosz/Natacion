# =============================================================================
# 📁 views/sidebar.py - CONSOLIDADOR DE LA BARRA LATERAL Y ESCUDO DE SIMULACIÓN
# =============================================================================
import streamlit as st
import datetime

def renderizar_sidebar() -> bool:
    """
    Consolida la barra lateral (Sidebar) respetando la jerarquía de mando:
    - Head Coach / Admin: Visualizan el 100% de la nómina y pruebas de la piscina.
    - Entrenadores Asistentes: Visualizan y filtran estrictamente sus carriles/atletas asignados.
    
    Implementa también el interruptor de Simulación Externa para proteger la BD.
    Retorna el estado booleano de la simulación para el enrutador de pestañas.
    """
    supabase = st.session_state["supabase_client"]
    
    with st.sidebar:
        st.markdown(f"### 👤 Sesión Activa")
        st.markdown(f"**Usuario:** {st.session_state.nombre}")
        st.markdown(f"**Rol:** `{st.session_state.rol}`")
        st.markdown("---")
        
        st.markdown("### ⚙️ Panel de Control y Filtros")
        
        # 1. Escudo de Simulación Externa (Protección de escrituras en tablas reales)
        st.markdown("##### 🛡️ Entorno de Trabajo")
        simulacion_externa = st.toggle(
            "Activar Modo Simulación", 
            value=False,
            help="Congela las pestañas de escritura en la BD real para experimentar con parámetros analíticos."
        )
        
        st.markdown("---")
        st.markdown("### 🏊‍♂️ Filtrado de Atletas")
        
        atletas_filtrados = []
        
        # 2. Jerarquía de Mando y Filtrado de Nómina
        if st.session_state.rol in ["Head Coach", "Administrador"]:
            # El Head Coach y Admin tienen soberanía y visibilidad absoluta de la base de datos
            try:
                res_nad = supabase.table("usuarios")\
                    .select("id, nombre, genero, fecha_nacimiento")\
                    .eq("rol", "Nadador")\
                    .eq("estatus", "Activo")\
                    .order("nombre", desc=False)\
                    .execute()
                atletas_filtrados = res_nad.data if res_nad.data else []
            except Exception as e:
                st.error(f"Error cargando nómina general: {e}")
                
        elif st.session_state.rol == "Entrenador":
            # El Entrenador Asistente solo visualiza los atletas que el Head Coach le asignó en 'asignaciones'
            try:
                res_asig = supabase.table("asignaciones")\
                    .select("atleta_id, usuarios!inner(id, nombre, genero, fecha_nacimiento)")\
                    .eq("entrenador_id", st.session_state.usuario_id)\
                    .execute()
                    
                if res_asig.data:
                    # Extraemos el perfil anidado de los nadadores asignados
                    atletas_filtrados = [item["usuarios"] for item in res_asig.data]
            except Exception as e:
                st.error(f"Error cargando asignaciones de carril: {e}")
                
        # 3. Renderizado de Selectores en la Barra Lateral
        if atletas_filtrados:
            dict_atletas = {a["id"]: a["nombre"] for a in atletas_filtrados}
            
            # Selector de atleta activo en el session_state
            nadador_id_sel = st.selectbox(
                "Seleccionar Atleta:",
                options=list(dict_atletas.keys()),
                format_func=lambda x: dict_atletas[x]
            )
            
            # Guardamos en memoria global los datos del atleta seleccionado para el resto de vistas
            atleta_seleccionado = next((a for a in atletas_filtrados if a["id"] == nadador_id_sel), None)
            
            if atleta_seleccionado:
                st.session_state.nadador_seleccionado_id = atleta_seleccionado["id"]
                st.session_state.nadador_seleccionado_nombre = atleta_seleccionado["nombre"]
                st.session_state.nadador_seleccionado_genero = atleta_seleccionado["genero"]
                st.session_state.fecha_nacimiento = atleta_seleccionado["fecha_nacimiento"]
                
                # Desglose estético de la ficha del atleta en foco
                st.markdown("##### 📌 Ficha del Atleta en Foco")
                st.caption(f"**Nombre:** {st.session_state.nadador_seleccionado_nombre}")
                st.caption(f"**Género:** {st.session_state.nadador_seleccionado_genero}")
                st.caption(f"**Nacimiento:** {st.session_state.fecha_nacimiento}")
        else:
            st.warning("⚠️ No se encontraron atletas bajo tu supervisión o no hay registros activos.")
            # Limpiamos variables de sesión para evitar lecturas nulas en otros módulos
            st.session_state.nadador_seleccionado_id = None
            st.session_state.nadador_seleccionado_nombre = None
            st.session_state.nadador_seleccionado_genero = None
            st.session_state.fecha_nacimiento = None
            
        st.markdown("---")
        
        # Botón de cierre de sesión en la barra lateral para mayor comodidad
        if st.button("🚪 Cerrar Sesión", use_container_width=True):
            st.session_state.clear()
            st.rerun()
            
        return simulacion_externa