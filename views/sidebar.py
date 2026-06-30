# =============================================================================
# 📁 views/sidebar.py - BARRA LATERAL CON MÁXIMO CORTAFUEGOS DE GOBERNANZA
# =============================================================================
import streamlit as st
import datetime
from core.conexion import obtener_cliente_supabase, obtener_nomina_nadadores_activos
from core.formulas import calcular_categoria_competencia

def renderizar_sidebar() -> bool:
    """
    Renderiza la barra lateral (Sidebar) aplicando estrictamente la matriz de
    gobernanza por roles y exponiendo los controles exactos de los archivos 9, 11 y 12.
    
    Retorna:
        bool: Estado de 'simulacion_externa' para que las vistas congelen escrituras en BD.
    """
    supabase = obtener_cliente_supabase()
    rol = str(st.session_state.get("rol", "Nadador")).lower().strip()
    
    # Inicialización por seguridad de variables clave de control de equipo en el estado de sesión
    if "modo_equipo" not in st.session_state:
        st.session_state.modo_equipo = False
    if "atletas_filtrados_equipo" not in st.session_state:
        st.session_state.atletas_filtrados_equipo = []

    with st.sidebar:
        st.markdown(f"### 👤 Sesión Activa")
        st.markdown(f"**Usuario:** {st.session_state.get('nombre', 'Usuario')}")
        st.markdown(f"**Rol / Nivel:** `{rol.upper()}`")
        st.markdown("---")
        
        st.markdown("### ⚙️ Panel de Control y Filtros")
        
        # 1. ESCUDO DE SIMULACIÓN EXTERNA (Archivos 10 y 12)
        # Protege la BD aislando los cálculos locales en los sliders.
        st.markdown("##### 🛡️ Entorno de Trabajo")
        simulacion_externa = st.toggle(
            "Activar Modo Simulación", 
            value=False,
            help="Habilita la alteración local de variables asintóticas (h, k) sin afectar los datos reales en Supabase."
        )
        st.session_state.simulacion_externa = simulacion_externa
        
        st.markdown("---")
        st.markdown("##### 🎯 Segmentación y Foco")

        # =====================================================================
        # CASO A: RESTRICCIÓN ABSOLUTA PARA EL ROL "NADADOR"
        # =====================================================================
        if rol == "nadador":
            # Forzado absoluto: No hay conmutador de equipo ni selectores alternos
            st.session_state.modo_equipo = False
            
            # Se fija el atleta en foco como él mismo
            st.session_state.nadador_seleccionado_id = st.session_state.get("usuario_id")
            st.session_state.nadador_seleccionado_nombre = st.session_state.get("nombre")
            st.session_state.nadador_seleccionado_genero = st.session_state.get("genero_usuario", "M")

            # Cálculo de su categoría reglamentaria local e inalterable
            fecha_nac = st.session_state.get("fecha_nacimiento_usuario")
            cat_local, _ = calcular_categoria_competencia(fecha_nac)
            st.session_state.nadador_seleccionado_categoria = cat_local
            
            st.info("📌 Acceso exclusivo a tu perfil, marcas históricas y simulador local.")
            
        # =====================================================================
        # CASO B / C: ACCESO MEDIO Y TOTAL (ENTRENADOR, HEAD COACH, ADMIN)
        # =====================================================================
        else:
            # Controles maestros exclusivos para Head Coach y Administrador
            if rol in ["head coach", "administrador"]:
                opcion_modo = st.radio(
                    "Selección de Enfoque Visual",
                    ["Modo Individual (Atleta único)", "Modo Equipo (Comparativa / Grupo)"],
                    index=0 if not st.session_state.modo_equipo else 1
                )
                st.session_state.modo_equipo = "Modo Equipo" in opcion_modo
            else:
                # El entrenador asistente está forzado al modo individual de sus atletas asignados
                st.session_state.modo_equipo = False

            # --- SUB-FLUJO: MODO INDIVIDUAL (Para Entrenador, Head Coach y Admin) ---
            if not st.session_state.modo_equipo:
                nomina_disponible = []
                
                if rol == "entrenador":
                    # Filtro cruzado estricto por la tabla intermedia 'asignaciones'
                    try:
                        resp_asig = supabase.table("asignaciones").select("atleta_id").eq("entrenador_id", st.session_state.get("usuario_id")).execute()
                        ids_asignados = [reg["atleta_id"] for reg in resp_asig.data] if resp_asig.data else []
                        
                        if ids_asignados:
                            # Cruzamos con la nómina activa global
                            nomina_completa = obtener_nomina_nadadores_activos()
                            nomina_disponible = [a for a in nomina_completa if a["id"] in ids_asignados]
                    except Exception as e:
                        st.error(f"Error al verificar asignaciones de carril: {e}")
                else:
                    # Head Coach y Administrador ven al 100% de la nómina activa
                    nomina_disponible = obtener_nomina_nadadores_activos()

                if nomina_disponible:
                    lista_nombres = [a["nombre"] for a in nomina_disponible]
                    nombre_sel = st.selectbox("Seleccionar Atleta en Foco", lista_nombres)
                    
                    # Extraer el diccionario del nadador seleccionado para mapear el st.session_state
                    atleta_sel = next(a for a in nomina_disponible if a["nombre"] == nombre_sel)
                    
                    st.session_state.nadador_seleccionado_id = atleta_sel["id"]
                    st.session_state.nadador_seleccionado_nombre = atleta_sel["nombre"]
                    st.session_state.nadador_seleccionado_genero = atleta_sel["genero"]
                    st.session_state.fecha_nacimiento = atleta_sel["fecha_nacimiento"]
                    
                    cat_calculada, _ = calcular_categoria_competencia(atleta_sel["fecha_nacimiento"])
                    st.session_state.nadador_seleccionado_categoria = cat_calculada
                    
                    # Ficha estética del Atleta en Foco
                    st.markdown("##### 📌 Ficha del Atleta en Foco")
                    st.caption(f"**Nombre:** {st.session_state.nadador_seleccionado_nombre}")
                    st.caption(f"**Género:** {'Masculino (M)' if st.session_state.nadador_seleccionado_genero == 'M' else 'Femenino (F)'}")
                    st.caption(f"**Categoría Activa:** `{st.session_state.nadador_seleccionado_categoria}`")
                else:
                    st.warning("⚠️ No posees atletas asignados bajo tu supervisión activa.")
                    st.session_state.nadador_seleccionado_id = None

            # --- SUB-FLUJO: MODO EQUIPO (Exclusivo Head Coach / Admin) ---
            else:
                st.markdown("##### 📊 Parámetros del Análisis de Equipo")
                nomina_global = obtener_nomina_nadadores_activos()
                
                # Selector de Género (Archivo 11)
                filtro_genero = st.selectbox("Filtrar por Género", ["Todos", "Femenino (F)", "Masculino (M)"])
                if filtro_genero == "Femenino (F)":
                    nomina_global = [a for a in nomina_global if a["genero"] == "F"]
                elif filtro_genero == "Masculino (M)":
                    nomina_global = [a for a in nomina_global if a["genero"] == "M"]
                    
                # Selectores en cascada por Tipo de Filtro (Archivo 11)
                tipo_filtro = st.selectbox("Segmentación de Grupo", ["Todos los Atletas", "Categoría Etaria", "Atletas Específicos"])
                
                atletas_resultado = []
                
                if tipo_filtro == "Todos los Atletas":
                    atletas_resultado = nomina_global
                    
                elif tipo_filtro == "Categoría Etaria":
                    # Lista de categorías estandarizadas de FEVEDA para el desplegable
                    categorias_pool = ["Preinfantil A", "Preinfantil B", "Preinfantil C", "Infantil A", "Infantil B", "Juvenil A", "Juvenil B", "Máxima", "Máster"]
                    cat_sel = st.selectbox("Seleccionar Categoría FEVEDA", categorias_pool)
                    
                    # Inyección en cascada de tu fórmula exacta del core para discriminar las fechas de nacimiento
                    atletas_resultado = [a for a in nomina_global if calcular_categoria_competencia(a["fecha_nacimiento"])[0] == cat_sel]
                    
                elif tipo_filtro == "Atletas Específicos":
                    mapa_nombres = {a["nombre"]: a for a in nomina_global}
                    nombres_sel = st.multiselect("Selección de Atletas (Uno a uno)", list(mapa_nombres.keys()))
                    atletas_resultado = [mapa_nombres[n] for n in nombres_sel if n in mapa_nombres]
                
                # Guardamos los registros resultantes en el estado de sesión para el renderizador del gráfico de equipo
                st.session_state.atletas_filtrados_equipo = atletas_resultado
                st.metric("Atletas en Muestra", len(atletas_resultado))

        st.markdown("---")
        
        # 2. CONTROLES GENERALES DE VENTANA Y VISTA (Archivo 9)
        st.markdown("##### 🔎 Parámetros de Visualización")
        tipo_vista = st.selectbox("Rango del Gráfico", ["Macro (Historial Completo)", "Micro (Ventana Anual)"])
        st.session_state.tipo_vista = tipo_vista
        
        # Inyección de límites dinámicos para el Slider de Zoom si aplica Micro
        if tipo_vista == "Micro (Ventana Anual)":
            # Límites por defecto de protección del lienzo
            edad_min_zoom, edad_max_zoom = st.slider(
                "🔎 Rango de la Ventana (Edad)", 
                min_value=5.0, max_value=25.0, 
                value=(10.0, 15.0), step=0.1, format="%.2f años"
            )
            st.session_state.edad_min_zoom = edad_min_zoom
            st.session_state.edad_max_zoom = edad_max_zoom
        else:
            st.session_state.edad_min_zoom = 0.0
            st.session_state.edad_max_zoom = 100.0

        # Slider dinámico de Rapidez de Deriva h (Archivos 9 y 12)
        st.markdown("**⏱️ Factor Fisiológico Ajustable**")
        factor_h = st.slider(
            "Rapidez de deriva (h):", 
            min_value=0.1, max_value=1.0, 
            value=0.4, step=0.05,
            help="Afecta directamente la caída o mantenimiento post-pico en la fórmula asintótica."
        )
        st.session_state.factor_h = factor_h

        st.markdown("---")
        if st.button("🚪 Cerrar Sesión del Sistema", use_container_width=True):
            st.session_state.autenticado = False
            st.cache_data.clear()
            st.rerun()
            
    return simulacion_externa
