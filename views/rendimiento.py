# =============================================================================
# 📁 views/rendimiento.py - ZONA BLANCA CENTRAL REESTRUCTURADA Y FUNCIONAL
# =============================================================================
import streamlit as st
import pandas as pd
import numpy as np
import datetime
import matplotlib.pyplot as plt

# Funciones de apoyo simuladas o importadas de tu módulo 'formulas.py'
# Asegúrate de importar las tuyas reales.
from formulas import (
    calcular_categoria_competencia, resolver_k_individual, 
    calcular_curva_atleta, obtener_datos_hitos_atleta
)

def renderizar_pestana_rendimiento(simulacion_activa_global: bool):
    supabase = st.session_state.get("supabase_client")
    rol_usuario = st.session_state.get("rol", "Invitado")
    atleta_id = st.session_state.get("nadador_seleccionado_id")
    genero_atleta = st.session_state.get("nadador_seleccionado_genero", "F")
    nombre_atleta = st.session_state.get("nadador_seleccionado_nombre", "Atleta")
    
    # Inyección de estilos para mantener divisores compactos y botones sin desbordes
    st.markdown(
        """
        <style>
            .divisor-blanco { margin-top: 4px !important; margin-bottom: 12px !important; border-bottom: 1px solid #eaeaea; }
            [data-testid="stHorizontalBlock"] { gap: 1rem !important; }
        </style>
        """, 
        unsafe_allow_html=True
    )
    
    # -------------------------------------------------------------------------
    # 🔭 ZONA BLANCA SUPERIOR: DISTRIBUCIÓN HORIZONTAL (IZQUIERDA, CENTRO, DERECHA)
    # -------------------------------------------------------------------------
    c_col_pruebas, c_col_escala, c_col_modo = st.columns([1.2, 1.2, 1.6])
    
    with c_col_pruebas:
        # 1. Catálogo de pruebas a la izquierda con tamaño fijo y etiqueta "Pruebas"
        CATALOGO_OFICIAL_WA = (
            "50m Libre", "100m Libre", "200m Libre", "400m Libre", "800m Libre", "1500m Libre",
            "50m Espalda", "100m Espalda", "200m Espalda",
            "50m Mariposa", "100m Mariposa", "200m Mariposa",
            "50m Pecho", "100m Pecho", "200m Pecho",
            "200m CI", "400m CI"
        )
        prueba_sel = st.selectbox(
            "🏊 Pruebas:",
            options=CATALOGO_OFICIAL_WA,
            index=1,
            key="selector_wa_zona_blanca"
        )
        st.session_state["prueba_seleccionada"] = prueba_sel

    with c_col_escala:
        # 4. Escala del gráfico en el centro
        tipo_vista = st.radio(
            "🔭 Escala del Gráfico:", 
            ["Macro (Historial Completo)", "Micro (Ventana Anual)"],
            horizontal=False,
            key="escala_grafico_radio"
        )
        st.session_state["tipo_vista"] = tipo_vista

    with c_col_modo:
        # 2. Controles de Individual y Equipo limitados a entrenadores/admins
        modo_actual_render = "Individual"
        if rol_usuario in ["Head Coach", "Entrenador", "Administrador"]:
            eleccion_analisis = st.radio(
                "📋 Tipo de Análisis:", 
                ["Individual", "Equipo"],
                horizontal=False,
                key="eleccion_analisis_radio"
            )
            st.session_state["modo_operacion"] = eleccion_analisis
            modo_actual_render = eleccion_analisis
        else:
            st.session_state["modo_operacion"] = "Individual"
            st.markdown("**Tipo de Análisis:**")
            st.info("👤 Vista Individual (Nadador)")

    # -------------------------------------------------------------------------
    # 3. GESTIÓN Y DESPLIEGUE CONDICIONAL DEL MODO EQUIPO
    # -------------------------------------------------------------------------
    filtro_genero = "Todos"
    tipo_filtro_equipo = "Todos los Atletas"
    cat_sel = None
    ids_sel = []

    if modo_actual_render == "Equipo" and rol_usuario in ["Head Coach", "Entrenador", "Administrador"]:
        st.markdown("**👥 Configuración de Análisis de Equipo**")
        ce_1, ce_2 = st.columns(2)
        with ce_1:
            filtro_genero = st.selectbox("Filtro Género:", ["Todos", "Femenino (F)", "Masculino (M)"])
            tipo_filtro_equipo = st.radio("Filtrado por:", ["Todos los Atletas", "Categoría Etaria", "Atletas Específicos"])
        with ce_2:
            if tipo_filtro_equipo == "Categoría Etaria":
                cat_sel = st.selectbox("Categoría:", ["Infantil A", "Infantil B", "Juvenil A", "Juvenil B", "Máxima"])
            elif tipo_filtro_equipo == "Atletas Específicos":
                try:
                    r_all = supabase.table("usuarios").select("id, nombre").eq("rol", "Nadador").execute()
                    if r_all.data:
                        df_all = pd.DataFrame(r_all.data)
                        dict_all = dict(zip(df_all['nombre'], df_all['id']))
                        atletas_multi = st.multiselect("Nadadores específicos:", options=list(dict_all.keys()))
                        ids_sel = [dict_all[name] for name in atletas_multi]
                except Exception:
                    pass

    # Guardar en sesión
    st.session_state["equipo_filtros"] = {
        "genero": filtro_genero, "tipo_filtro": tipo_filtro_equipo, 
        "categoria": cat_sel, "ids_especificos": ids_sel
    }

    # -------------------------------------------------------------------------
    # 🎯 EXTRACCIÓN DE PARÁMETROS BÁSICOS (Récord Mundial y Ventana Zoom)
    # -------------------------------------------------------------------------
    record_mundial = 50.0
    try:
        r_rm = supabase.table("marcas_referencia").select("record_mundial").eq("prueba", prueba_sel).eq("genero", genero_atleta).execute()
        if r_rm.data and r_rm.data[0].get("record_mundial"):
            record_mundial = float(r_rm.data[0]["record_mundial"])
    except Exception:
        pass
    
    target_5_porciento = round(record_mundial * 1.05, 2)
    st.session_state["target_calculado_rm"] = target_5_porciento

    t_pb_real = 11.33
    if atleta_id:
        try:
            r_pb = supabase.table("marcas_historicas").select("edad").eq("usuario_id", atleta_id).eq("prueba", prueba_sel).order("tiempo", ascending=True).limit(1).execute()
            if r_pb.data:
                t_pb_real = float(r_pb.data[0]["edad"])
        except Exception:
            pass

    edad_min_zoom, edad_max_zoom = 8.0, 22.0
    if "Micro" in tipo_vista:
        val_inicial = float(round(t_pb_real, 2))
        val_final = float(round(t_pb_real + 1.0, 2))
        st.markdown("")
        edad_min_zoom, edad_max_zoom = st.slider(
            "🔎 Ventana Enfocada (Predeterminada: +1 Año desde Marca Personal):",
            min_value=8.0, max_value=26.0, value=(val_inicial, val_final), step=0.01, format="%.2f años"
        )
    
    st.session_state["zoom_edades"] = (edad_min_zoom, edad_max_zoom)
    st.markdown('<div class="divisor-blanco"></div>', unsafe_allow_html=True)

    # -------------------------------------------------------------------------
    # 5. RENDERIZADO DE GRÁFICOS (RESTAURACIÓN DE MOTORES DE PLOTEO)
    # -------------------------------------------------------------------------
    t_peak = st.session_state.get("control_t_peak", 18.0)
    T_target = st.session_state.get("control_T_target", target_5_porciento)
    h = st.session_state.get("control_h", 0.4)
    t0 = 11.0
    T0 = 120.0
    t_pb = t_pb_real
    T_pb = 65.0
    k = 0.5
    t_intermedia = 13.5
    T_intermedia_val = 55.0
    m_ano, m_panam_b, m_panam_a, m_wa_b, m_wa_a, m_wr = 60.0, 58.0, 56.0, 54.0, 52.0, 47.0
    es_preinfantil = False

    # Carga de marcas simuladas/procesadas de individuo o visitante
    df_procesado = pd.DataFrame() # Simulado, adapta a tu instancia de BD real

    if modo_actual_render == "Equipo" and rol_usuario in ["Head Coach", "Entrenador", "Administrador"]:
        # --- Motor Gráfico Modo Equipo ---
        try:
            resp_todos = supabase.table("usuarios").select("id, nombre, fecha_nacimiento, genero").eq("rol", "Nadador").eq("estatus", "Activo").execute()
            atletas_lista = resp_todos.data if resp_todos.data else []
            
            if filtro_genero == "Femenino (F)":
                atletas_lista = [a for a in atletas_lista if a["genero"] == "F"]
            elif filtro_genero == "Masculino (M)":
                atletas_lista = [a for a in atletas_lista if a["genero"] == "M"]

            atletas_filtrados = []
            if tipo_filtro_equipo == "Todos los Atletas":
                atletas_filtrados = atletas_lista
            elif tipo_filtro_equipo == "Categoría Etaria" and cat_sel:
                atletas_filtrados = [a for a in atletas_lista if calcular_categoria_competencia(a["fecha_nacimiento"])[0] == cat_sel]
            elif tipo_filtro_equipo == "Atletas Específicos" and ids_sel:
                atletas_filtrados = [a for a in atletas_lista if a["id"] in ids_sel]

            if not atletas_filtrados:
                st.warning("No se encontraron atletas activos con los criterios elegidos.")
            else:
                lista_ids = [atl["id"] for atl in atletas_filtrados]
                res_marcas = supabase.table("marcas_historicas").select("usuario_id, edad, tiempo, nota").eq("prueba", prueba_sel).in_("usuario_id", lista_ids).order("edad", desc=False).execute()
                df_global = pd.DataFrame(res_marcas.data) if res_marcas.data else pd.DataFrame()

                fig = plt.figure(figsize=(8.5, 11.0))
                ax = fig.add_axes([0.14, 0.52, 0.72, 0.33])
                colores = plt.get_cmap("tab10", len(atletas_filtrados))
                hay_datos = False
                
                for idx, atl in enumerate(atletas_filtrados):
                    a_id = atl["id"]
                    a_nom = atl["nombre"]
                    if not df_global.empty and a_id in df_global["usuario_id"].values:
                        df_atl = df_global[df_global["usuario_id"] == a_id].copy()
                        hay_datos = True
                        ax.plot(df_atl["edad"], df_atl["tiempo"], color=colores(idx), label=f"Evolución - {a_nom}")
                        ax.scatter(df_atl["edad"], df_atl["tiempo"], color=colores(idx), edgecolor="black", s=25)

                if hay_datos:
                    ax.set_title(f"Análisis Comparativo de Equipo - {prueba_sel}", fontsize=12)
                    ax.set_xlabel("Edad del Atleta (Años)")
                    ax.set_ylabel("Tiempo (Segundos)")
                    ax.legend(loc="upper right", fontsize=8)
                    st.pyplot(fig, use_container_width=True)
                else:
                    st.info("No se hallaron marcas para los nadadores seleccionados en esta prueba.")
        except Exception as e:
            st.error(f"Error procesando visualización en equipo: {e}")

    else:
        # --- Motor Gráfico Modo Individual o Simulación ---
        fig = plt.figure(figsize=(8.5, 11.0))
        ax = fig.add_axes([0.14, 0.52, 0.72, 0.33])
        
        edades_curva = np.linspace(t0, t_peak, 300)
        tiempos_curva = calcular_curva_atleta(edades_curva, t0, T0, t_pb, T_pb, t_peak, T_target, k, h)
        
        ax.plot(edades_curva, tiempos_curva, color="#007A87", linewidth=1.8, label="Proyección Fisiológica")
        
        if len(df_procesado) > 0:
            ax.plot(df_procesado["Edad"], df_procesado["Tiempo"], color="#D55E00", linestyle="--", linewidth=1.0, alpha=0.6, label="Evolución Real (PBs)")
            ax.scatter(df_procesado["Edad"], df_procesado["Tiempo"], color="#D55E00", edgecolor="black", s=25, linewidths=0.6, zorder=3)

        ax.set_title(f"Curva de Rendimiento Asintótica - {prueba_sel}\nAtleta: {nombre_atleta}", fontsize=12, pad=10)
        ax.set_xlabel("Edad del Atleta (Años)", fontsize=9.5)
        ax.set_ylabel("Tiempo de Carrera (Segundos)", fontsize=9.5)
        ax.grid(True, which="both", axis="both", linestyle=":", color="#CCD1D1", linewidth=0.5)
        ax.legend(loc="upper right", fontsize=8, framealpha=0.8)
        
        st.pyplot(fig, use_container_width=True)
