# =============================================================================
# 📁 views/rendimiento.py - INTEGRACIÓN DE MOTOR GRÁFICO (INDIVIDUAL Y EQUIPO)
# =============================================================================
import streamlit as st
import pandas as pd
import numpy as np
import datetime
import matplotlib.pyplot as plt

# 1. Importaciones estrictas y validadas contra core/formulas.py
from core.formulas import (
    calcular_edad_decimal,
    resolver_k_individual, 
    calcular_curva_atleta
)

# 2. Lógica interna de asignación de categorías competitivas FINA/World Aquatics
def determinar_categoria_fina(fecha_nacimiento_str) -> tuple:
    """Calcula la categoría basada en el año de nacimiento (Criterio oficial World Aquatics)."""
    try:
        if not fecha_nacimiento_str:
            return "Única", "#7F8C8D"
        fecha_nac = pd.to_datetime(fecha_nacimiento_str)
        # Clasificación estándar por año calendario corriente
        edad_fina = datetime.date.today().year - fecha_nac.year
        
        if edad_fina <= 10:
            return "Infantil A", "#2ECC71"
        elif edad_fina <= 12:
            return "Infantil B", "#3498DB"
        elif edad_fina <= 14:
            return "Juvenil A", "#9B59B6"
        elif edad_fina <= 17:
            return "Juvenil B", "#E67E22"
        else:
            return "Máxima", "#E74C3C"
    except Exception:
        return "Única", "#7F8C8D"


def renderizar_pestana_rendimiento(simulacion_activa_global: bool):
    supabase = st.session_state.get("supabase_client")
    rol_usuario = st.session_state.get("rol", "Invitado")
    atleta_id = st.session_state.get("nadador_seleccionado_id")
    genero_atleta = st.session_state.get("nadador_seleccionado_genero", "F")
    nombre_atleta = st.session_state.get("nadador_seleccionado_nombre", "Atleta")
    simulacion_externa = st.session_state.get("modo_operacion", "Individual") == "Visitante (Simulación Externa)"
    
    # Inyección de diseño de interfaz unificada
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
    # 🔭 ZONA BLANCA SUPERIOR: SELECTORES COMPACTOS
    # -------------------------------------------------------------------------
    c_col_pruebas, c_col_escala, c_col_modo = st.columns([1.2, 1.2, 1.6])
    
    with c_col_pruebas:
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
        tipo_vista = st.radio(
            "🔭 Escala del Gráfico:", 
            ["Macro (Historial Completo)", "Micro (Ventana Anual)"],
            horizontal=False,
            key="escala_grafico_radio"
        )
        st.session_state["tipo_vista"] = tipo_vista

    with c_col_modo:
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
            st.info("👤 Análisis Individual (Nadador)")

    # -------------------------------------------------------------------------
    # 👥 SEGMENTACIÓN DE FILTROS DE EQUIPO (MÓDULO COLECTIVO)
    # -------------------------------------------------------------------------
    filtro_genero = "Todos"
    tipo_filtro_equipo = "Todos los Atletas"
    cat_sel = None
    ids_sel = []

# =============================================================================
    # 📊 MOTOR GRÁFICO SECCIÓN A: MODO EQUIPO
    # =============================================================================
    if modo_actual_render == "Equipo":
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
                atletas_filtrados = [a for a in atletas_lista if determinar_categoria_fina(a["fecha_nacimiento"])[0] == cat_sel]
            elif tipo_filtro_equipo == "Atletas Específicos" and ids_sel:
                atletas_filtrados = [a for a in atletas_lista if a["id"] in ids_sel]

            if not atletas_filtrados:
                st.warning("No se encontraron atletas activos con los criterios de segmentación elegidos.")
            else:
                lista_ids = [atl["id"] for atl in atletas_filtrados]
                
                res_marcas_colectivo = supabase.table("marcas_historicas").select("usuario_id, edad, tiempo, nota").eq("prueba", prueba_sel).in_("usuario_id", lista_ids).order("edad", desc=False).execute()
                df_global_marcas = pd.DataFrame(res_marcas_colectivo.data) if res_marcas_colectivo.data else pd.DataFrame()

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
                    
                    if not df_global_marcas.empty and a_id in df_global_marcas["usuario_id"].values:
                        df_atl_m = df_global_marcas[df_global_marcas["usuario_id"] == a_id].copy()
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
                    
                    ax.set_title(f"Análisis Comparativo de Equipo - {prueba_sel}", fontsize=12, pad=10)
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

    # -------------------------------------------------------------------------
    # 🎯 CONFIGURACIÓN DE PARÁMETROS DEL MODELO (VALORES DINÁMICOS DESDE SESSIONS)
    # -------------------------------------------------------------------------
    h = st.session_state.get("control_h", 0.33)
    t_peak = st.session_state.get("control_t_peak", 23.00)
    
    # Buscar récord mundial base para establecer metas de control por prueba
    record_mundial = 48.0
    try:
        r_rm = supabase.table("marcas_referencia").select("record_mundial").eq("prueba", prueba_sel).eq("genero", genero_atleta).execute()
        if r_rm.data and r_rm.data[0].get("record_mundial"):
            record_mundial = float(r_rm.data[0]["record_mundial"])
    except Exception:
        pass
    
    T_target = st.session_state.get("control_T_target", round(record_mundial * 1.05, 2))

    # Determinar la edad de inicio y PB de control del atleta activo
    t_pb_real = 13.50
    if atleta_id:
        try:
            r_pb = supabase.table("marcas_historicas").select("edad").eq("usuario_id", atleta_id).eq("prueba", prueba_sel).order("tiempo", ascending=True).limit(1).execute()
            if r_pb.data:
                t_pb_real = float(r_pb.data[0]["edad"])
        except Exception:
            pass

    edad_min_zoom, edad_max_zoom = 8.0, 22.0
    if "Micro" in tipo_vista:
        val_inicial_slider = float(round(t_pb_real, 2))
        val_final_slider = float(round(t_pb_real + 1.0, 2))
        st.markdown("")
        edad_min_zoom, edad_max_zoom = st.slider(
            "🔎 Ventana Enfocada (Predeterminada: +1 Año desde Marca Personal):",
            min_value=8.0, max_value=26.0, value=(val_inicial_slider, val_final_slider), step=0.01, format="%.2f años"
        )
    
    st.session_state["zoom_edades"] = (edad_min_zoom, edad_max_zoom)
    st.markdown('<div class="divisor-blanco"></div>', unsafe_allow_html=True)

    # Variables de límites internacionales
    m_ano, m_panam_b, m_panam_a, m_wa_b, m_wa_a, m_wr = 60.0, 58.0, 56.0, 54.0, 52.0, float(record_mundial)
    es_preinfantil = False
    df_procesado = pd.DataFrame()

    # =============================================================================
    # 📊 MOTOR GRÁFICO SECCIÓN A: MODO EQUIPO
    # =============================================================================
    if modo_actual_render == "Equipo":
        try:
            resp_todos = supabase.table("usuarios").select("id, nombre, fecha_nacimiento, genero").eq("rol", "Nadador").eq("estatus", "Activo").execute() [cite: 75]
            atletas_lista = resp_todos.data if resp_todos.data else [] [cite: 75]
            
            if filtro_genero == "Femenino (F)": [cite: 75]
                atletas_lista = [a for a in atletas_lista if a["genero"] == "F"] [cite: 75]
            elif filtro_genero == "Masculino (M)": [cite: 75]
                atletas_lista = [a for a in atletas_lista if a["genero"] == "M"] [cite: 76]

            atletas_filtrados = [] [cite: 76]
            if tipo_filtro_equipo == "Todos los Atletas": [cite: 76]
                atletas_filtrados = atletas_lista [cite: 76]
            elif tipo_filtro_equipo == "Categoría Etaria" and cat_sel: [cite: 76]
                # Corregido usando la función local mapeada de categorías
                atletas_filtrados = [a for a in atletas_lista if determinar_categoria_fina(a["fecha_nacimiento"])[0] == cat_sel] [cite: 76]
            elif tipo_filtro_equipo == "Atletas Específicos" and ids_sel: [cite: 76, 77]
                # Corregido mapeo de identificadores específicos
                atletas_filtrados = [a for a in atletas_lista if a["id"] in ids_sel] [cite: 77]

            if not atletas_filtrados: [cite: 77]
                st.warning("No se encontraron atletas activos con los criterios de segmentación elegidos.") [cite: 77]
            else:
                lista_ids = [atl["id"] for atl in atletas_filtrados] [cite: 77, 78]
                
                res_marcas_colectivo = supabase.table("marcas_historicas")\ [cite: 78]
                    .select("usuario_id, edad, tiempo, nota")\ [cite: 78]
                    .eq("prueba", prueba_sel)\ [cite: 78]
                    .in_("usuario_id", lista_ids)\ [cite: 79]
                    .order("edad", desc=False).execute() [cite: 79]
                    
                df_global_marcas = pd.DataFrame(res_marcas_colectivo.data) if res_marcas_colectivo.data else pd.DataFrame() [cite: 79]

                fig = plt.figure(figsize=(8.5, 11.0)) [cite: 79]
                ax = fig.add_axes([0.14, 0.52, 0.72, 0.33]) [cite: 80]
                
                colores = plt.get_cmap("tab10", len(atletas_filtrados)) [cite: 80]
                hay_datos_visibles = False [cite: 80]
                linea_fisiologica_anotada = False [cite: 80]
                
                todas_las_edades_0 = [] [cite: 80]
                todos_los_tiempos_colectivo = [] [cite: 81]
                datos_atletas_cargados = [] [cite: 81]
                
                for idx, atl in enumerate(atletas_filtrados): [cite: 81]
                    a_id = atl["id"] [cite: 81]
                    a_nom = atl["nombre"] [cite: 82]
                    
                    if not df_global_marcas.empty and a_id in df_global_marcas["usuario_id"].values: [cite: 82]
                        df_atl_m = df_global_marcas[df_global_marcas["usuario_id"] == a_id].copy() [cite: 82, 83]
                        df_atl_m = df_atl_m.rename(columns={"edad": "Edad", "tiempo": "Tiempo", "nota": "Evento / Fecha"}) [cite: 83]
                        hay_datos_visibles = True [cite: 83]
                        
                        todas_las_edades_0.append(float(df_atl_m.iloc[0]["Edad"])) [cite: 83]
                        todos_los_tiempos_colectivo.extend(df_atl_m["Tiempo"].tolist()) [cite: 84]
                        
                        datos_atletas_cargados.append({ [cite: 84]
                            "nom": a_nom, [cite: 84]
                            "df": df_atl_m, [cite: 85]
                            "color": colores(idx) [cite: 85]
                        })

                if hay_datos_visibles: [cite: 85]
                    edad_0_min_colectivo = min(todas_las_edades_0) [cite: 85]
                    lim_x_min = max(4.0, edad_0_min_colectivo - 0.5) [cite: 85, 86]
                    lim_x_max = t_peak + 1.0 [cite: 86]
                    ax.set_xlim(lim_x_min, lim_x_max) [cite: 86]
                    
                    peor_tiempo_colectivo = max(todos_los_tiempos_colectivo) [cite: 86]
                    lim_y_inferior = m_wr * 0.95 [cite: 86]
                    lim_y_superior = peor_tiempo_colectivo + (peor_tiempo_colectivo * 0.05) [cite: 87]
                    ax.set_ylim(lim_y_inferior, lim_y_superior) [cite: 87]
                    
                    for item in datos_atletas_cargados: [cite: 87]
                        df_atl_m = item["df"] [cite: 87]
                        color_curr = item["color"] [cite: 88]
                        a_nom = item["nom"] [cite: 88]
                        
                        t0_i = float(df_atl_m.iloc[0]["Edad"]) [cite: 88]
                        T0_i = float(df_atl_m.iloc[0]["Tiempo"]) [cite: 88]
                        idx_pb_i = df_atl_m["Tiempo"].idxmin() [cite: 89]
                        t_pb_i = float(df_atl_m.loc[idx_pb_i, "Edad"]) [cite: 89]
                        T_pb_i = float(df_atl_m.loc[idx_pb_i, "Tiempo"]) [cite: 89]
                        
                        k_i = resolver_k_individual(t0_i, T0_i, t_pb_i, T_pb_i, t_peak, T_target) [cite: 90]
                        edades_curva_i = np.linspace(t0_i, t_peak, 300) [cite: 90]
                        
                        # Firma corregida agregando el parámetro 'h' esperado por core/formulas.py
                        tiempos_curva_i = calcular_curva_atleta(edades_curva_i, t0_i, T0_i, t_pb_i, T_pb_i, t_peak, T_target, k_i, h) [cite: 90]
                        
                        if not linea_fisiologica_anotada: [cite: 91]
                            ax.plot(edades_curva_i, tiempos_curva_i, color="#7F8C8D", linestyle=":", linewidth=1.2, label="Proyección fisiológica estimada") [cite: 91]
                            linea_fisiologica_anotada = True [cite: 91]
                        else:
                            ax.plot(edades_curva_i, tiempos_curva_i, color="#7F8C8D", linestyle=":", linewidth=1.2) [cite: 92]
                        
                        ax.plot(df_atl_m["Edad"], df_atl_m["Tiempo"], color=color_curr, linestyle="-", linewidth=1.5, label=f"Evolución real - {a_nom}") [cite: 92]
                        ax.scatter(df_atl_m["Edad"], df_atl_m["Tiempo"], color=color_curr, edgecolor="black", s=25, linewidths=0.5, zorder=3) [cite: 92]
                        ax.scatter(t_pb_i, T_pb_i, color=color_curr, marker="*", edgecolor="black", s=80, linewidths=0.5, zorder=5) [cite: 93]

                    x_texto = lim_x_min + 0.1 [cite: 93]
                    referencias = [ [cite: 93]
                        {"val": m_ano, "lbl": "Mín. Año", "col": "#A06000", "va": "bottom"}, [cite: 93, 94]
                        {"val": m_panam_b, "lbl": "PANAM Jr B", "col": "#006644", "va": "bottom"}, [cite: 94]
                        {"val": m_panam_a, "lbl": "PANAM Jr A", "col": "#2A658A", "va": "top"}, [cite: 94]
                        {"val": m_wa_b, "lbl": "WA B", "col": "#943100", "va": "bottom"}, [cite: 95]
                        {"val": m_wa_a, "lbl": "WA A", "col": "#883963", "va": "top"}, [cite: 95]
                        {"val": m_wr, "lbl": "World Record", "col": "#2C3E50", "va": "top"} [cite: 95]
                    ]
                    for r in referencias: [cite: 96]
                        if r["val"] > 0 and lim_y_inferior <= r["val"] <= lim_y_superior: [cite: 96]
                            ax.axhline(y=r["val"], color=r["col"], linestyle=":", linewidth=0.6, alpha=0.7) [cite: 97]
                            desplazamiento_y = (lim_y_superior - lim_y_inferior) * 0.006 if r["va"] == "bottom" else -((lim_y_superior - lim_y_inferior) * 0.006) [cite: 97]
                            ax.text(x_texto, r["val"] + desplazamiento_y, f"{r['lbl']}: {r['val']:.2f}s", color=r["col"], fontsize=7, va=r["va"], ha="left") [cite: 97]
                    
                    ax.set_title(f"Análisis Comparativo de Equipo - {prueba_sel}", fontsize=12, pad=10) [cite: 99]
                    ax.set_xlabel("Edad del Atleta (Años)", fontsize=9.5) [cite: 99]
                    ax.set_ylabel("Tiempo de Carrera (Segundos)", fontsize=9.5) [cite: 99]
                    ax.grid(True, which="both", axis="both", linestyle=":", color="#CCD1D1", linewidth=0.5) [cite: 100]
                    ax.set_axisbelow(True) [cite: 100]
                    ax.legend(loc="upper right", fontsize=8, framealpha=0.8) [cite: 100]
                    
                    st.pyplot(fig) [cite: 100]
                else:
                    st.info("No se hallaron marcas en la base de datos para los nadadores seleccionados en esta prueba.") [cite: 101]
        except Exception as e:
            st.error(f"Error procesando los segmentos de equipo: {e}") [cite: 101]

    # =============================================================================
    # 📊 MOTOR GRÁFICO SECCIÓN B: MODO INDIVIDUAL O SIMULACIÓN
    # =============================================================================
    else:
        fig = plt.figure(figsize=(8.5, 11.0)) [cite: 102]
        ax = fig.add_axes([0.14, 0.52, 0.72, 0.33]) [cite: 102]
        
        # Parámetros base del atleta para graficar curva asintótica individual
        t0, T0 = 10.0, 95.0
        t_pb, T_pb = t_pb_real, 62.0
        k = resolver_k_individual(t0, T0, t_pb, T_pb, t_peak, T_target)
        
        edades_curva = np.linspace(t0, t_peak, 300) [cite: 102]
        tiempos_curva = calcular_curva_atleta(edades_curva, t0, T0, t_pb, T_pb, t_peak, T_target, k, h) [cite: 102]
        
        todos_los_tiempos_ind = [T0, T_pb, T_target] [cite: 102]
        
        if not simulacion_externa and atleta_id:
            try:
                r_ind_m = supabase.table("marcas_historicas").select("edad, tiempo, nota").eq("usuario_id", atleta_id).eq("prueba", prueba_sel).order("edad", desc=False).execute()
                if r_ind_m.data:
                    df_procesado = pd.DataFrame(r_ind_m.data)
                    df_procesado = df_procesado.rename(columns={"edad": "Edad", "tiempo": "Tiempo", "nota": "Evento / Fecha"})
                    todos_los_tiempos_ind.extend(df_procesado["Tiempo"].tolist()) [cite: 102]
            except Exception:
                pass

        if tipo_vista == "Micro (Ventana Anual)": [cite: 102]
            edades_ventana = np.linspace(edad_min_zoom, edad_max_zoom, 300) [cite: 102, 103]
            tiempos_curva_ventana = calcular_curva_atleta(edades_ventana, t0, T0, t_pb, T_pb, t_peak, T_target, k, h).tolist() [cite: 103]
            
            tiempos_reales_ventana = [] [cite: 103]
            if not df_procesado.empty:
                for _, row in df_procesado.iterrows(): [cite: 103]
                    if edad_min_zoom <= row["Edad"] <= edad_max_zoom: [cite: 103]
                        tiempos_reales_ventana.append(row["Tiempo"]) [cite: 104]
                        
            todos_tiempos_v = tiempos_curva_ventana + tiempos_reales_ventana [cite: 104]
            t_min_v = min(todos_tiempos_v) if todos_tiempos_v else min(tiempos_curva) [cite: 104, 105]
            t_max_v = max(todos_tiempos_v) if todos_tiempos_v else max(tiempos_curva) [cite: 104, 105]

            margen_y = max(0.5, (t_max_v - t_min_v) * 0.15) [cite: 105]
            lim_y_inferior = t_min_v - margen_y [cite: 105]
            lim_y_superior = t_max_v + margen_y [cite: 105]
            lim_x_min, lim_x_max = edad_min_zoom, edad_max_zoom [cite: 105]
        else:
            peor_tiempo_ind = max(todos_los_tiempos_ind) [cite: 106]
            lim_y_inferior = m_wr * 0.92 if m_wr > 0 else min(todos_los_tiempos_ind) * 0.90 [cite: 106]
            lim_y_superior = peor_tiempo_ind + (peor_tiempo_ind * 0.08) [cite: 106]
            
            if not df_procesado.empty: [cite: 106]
                lim_x_min = min(float(t0), float(df_procesado["Edad"].min())) - 0.5 [cite: 106]
            else:
                lim_x_min = max(4.0, float(t0) - 0.5) [cite: 107]
            lim_x_max = t_peak + 1.0 [cite: 107]

        ax.set_xlim(lim_x_min, lim_x_max) [cite: 107]
        ax.set_ylim(lim_y_inferior, lim_y_superior) [cite: 107]
        ax.set_autoscale_on(False) [cite: 107]

        datos_tabla_micro = [] [cite: 107]
        
        # Pintar hitos y compromisos utilizando la función core nativa de edad decimal
        if atleta_id and tipo_vista == "Micro (Ventana Anual)": [cite: 107]
            try:
                # Mock o llamada segura para hitos de control de planeación trimestral
                r_atleta = supabase.table("usuarios").select("fecha_nacimiento").eq("id", atleta_id).execute()
                if r_atleta.data and r_atleta.data[0].get("fecha_nacimiento"):
                    fn_raw = r_atleta.data[0]["fecha_nacimiento"]
                    
                    r_hitos = supabase.table("hitos_temporada").select("fecha_evento, nombre_evento, elegible").eq("atleta_id", atleta_id).execute()
                    hitos_lista = r_hitos.data if r_hitos.data else []
                    
                    for hito in hitos_lista:
                        fecha_ev = hito.get("fecha_evento")
                        if not fecha_ev: continue
                        
                        # Acudimos a tu función central calculada
                        edad_hito_calculada = calcular_edad_decimal(fn_raw, fecha_ev)
                        
                        if lim_x_min <= edad_hito_calculada <= lim_x_max: [cite: 114]
                            es_elegible = hito.get("elegible", True) [cite: 114]
                            color_linea = "#2ECC71" if es_elegible else "#E74C3C" [cite: 114]
                            ax.axvline(x=edad_hito_calculada, color=color_linea, linestyle="--", linewidth=0.7, alpha=0.6) [cite: 115, 116]
                            
                            y_pos = lim_y_inferior + ((lim_y_superior - lim_y_inferior) * 0.03) [cite: 118]
                            nombre_evento = hito.get("nombre_evento", "Control") [cite: 119]
                            nombre_corto = nombre_evento[:18] + "..." if len(nombre_evento) > 18 else nombre_evento [cite: 119]
                            
                            ax.text(edad_hito_calculada + 0.015, y_pos, f"{nombre_corto}", color=color_linea, fontsize=7.5, rotation=90, va="bottom") [cite: 120, 121]
                            tiempo_proyectado_val = calcular_curva_atleta([edad_hito_calculada], t0, T0, t_pb, T_pb, t_peak, T_target, k, h)[0] [cite: 124, 125]
                            
                            datos_tabla_micro.append({ [cite: 125]
                                "Competencia / Evento": nombre_evento, [cite: 126]
                                "Fecha": str(fecha_ev), [cite: 126]
                                "Edad": f"{edad_hito_calculada:.2f} a", [cite: 126]
                                "Tiempo Prog.": f"{tiempo_proyectado_val:.2f} s" [cite: 127]
                            })
            except Exception:
                pass

        if datos_tabla_micro: [cite: 127]
            datos_tabla_micro.sort(key=lambda x: float(x["Edad"].replace(" a", "").strip())) [cite: 128]

        ax.plot(edades_curva, tiempos_curva, color="#007A87", linewidth=1.8, label="Proyección Fisiológica") [cite: 128]

        if not simulacion_externa and not df_procesado.empty: [cite: 128]
            ax.plot(df_procesado["Edad"], df_procesado["Tiempo"], color="#D55E00", linestyle="--", linewidth=1.0, alpha=0.6, label="Evolución Real (PBs)") [cite: 128]
            ax.scatter(df_procesado["Edad"], df_procesado["Tiempo"], color="#D55E00", edgecolor="black", s=25, zorder=3) [cite: 128]

        # Elementos flotantes fijos en gráfico de dispersión
        estilo_bbox = dict(boxstyle="round,pad=0.25", fc="#F8F9F9", ec="#BDC3C7", alpha=0.9, linewidth=0.5) [cite: 128]
        if lim_x_min <= t0 <= lim_x_max and lim_y_inferior <= T0 <= lim_y_superior: [cite: 128]
            ax.scatter(t0, T0, color="#7F8C8D", edgecolor="black", s=35, zorder=4) [cite: 128, 129]
            ax.text(t0 + 0.1, T0, f"P. Start\n{T0:.2f}s", fontsize=8, va="bottom", bbox=estilo_bbox) [cite: 130]

        if lim_x_min <= t_pb <= lim_x_max and lim_y_inferior <= T_pb <= lim_y_superior: [cite: 130]
            ax.scatter(t_pb, T_pb, color="#F1C40F", marker="*", edgecolor="black", s=100, zorder=5) [cite: 130]
            ax.text(t_pb + 0.15, T_pb, f"PB Actual\n{T_pb:.2f}s", fontsize=8, va="center", bbox=estilo_bbox) [cite: 130]

        if lim_x_min <= t_peak <= lim_x_max and lim_y_inferior <= T_target <= lim_y_superior: [cite: 131]
            ax.scatter(t_peak, T_target, color="#2ECC71", marker="s", edgecolor="black", s=35, zorder=4) [cite: 131]
            ax.text(t_peak - 0.1, T_target, f"Meta Peak\n{T_target:.2f}s", fontsize=8, va="bottom", ha="right", bbox=estilo_bbox) [cite: 131]

        # Renderizado de líneas horizontales de referencia internacional
        x_texto = lim_x_min + (lim_x_max - lim_x_min) * 0.05 [cite: 132]
        referencias = [ [cite: 132]
            {"val": m_ano, "lbl": "Mín. Año", "col": "#A06000", "va": "bottom"}, [cite: 132, 133]
            {"val": m_panam_b, "lbl": "PANAM Jr B", "col": "#006644", "va": "bottom"}, [cite: 133]
            {"val": m_panam_a, "lbl": "PANAM Jr A", "col": "#2A658A", "va": "top"}, [cite: 133]
            {"val": m_wa_b, "lbl": "WA B", "col": "#943100", "va": "bottom"}, [cite: 133]
            {"val": m_wa_a, "lbl": "WA A", "col": "#883963", "va": "top"}, [cite: 134]
            {"val": m_wr, "lbl": "World Record", "col": "#2C3E50", "va": "top"} [cite: 134]
        ]
        for r in referencias: [cite: 134]
            if r["val"] > 0 and lim_y_inferior <= r["val"] <= lim_y_superior: [cite: 134]
                ax.axhline(y=r["val"], color=r["col"], linestyle=":", linewidth=0.6, alpha=0.7) [cite: 135]
                ax.text(x_texto, r["val"], f"{r['lbl']}: {r['val']:.2f}s", color=r["col"], fontsize=7, va=r["va"]) [cite: 135]

        ax.set_title(f"Curva de Rendimiento Asintótica - {prueba_sel}\nAtleta: {nombre_atleta}", fontsize=12, pad=10) [cite: 137]
        ax.set_xlabel("Edad del Atleta (Años)", fontsize=9.5) [cite: 137]
        ax.set_ylabel("Tiempo de Carrera (Segundos)", fontsize=9.5) [cite: 137]
        ax.grid(True, linestyle=":", color="#CCD1D1", linewidth=0.5) [cite: 137]
        
        tamano_leyenda = 6.5 if tipo_vista == "Micro (Ventana Anual)" else 8 [cite: 137, 138]
        ax.legend(loc="upper right", fontsize=tamano_leyenda, framealpha=0.8) [cite: 138]

        # -------------------------------------------------------------------------
        # 📋 CUADROS DE REPORTES Y DETALLES (TABLAS MATPLOTLIB)
        # -------------------------------------------------------------------------
        df_table_render = None [cite: 138]
        es_modo_micro_tabla = (tipo_vista == "Micro (Ventana Anual)") [cite: 138]

        if es_modo_micro_tabla: [cite: 138]
            if datos_tabla_micro: [cite: 138]
                df_table_render = pd.DataFrame(datos_tabla_micro) [cite: 138]
                anchos_columnas = [0.46, 0.18, 0.16, 0.20] [cite: 138]
            else:
                df_table_render = pd.DataFrame([{"Competencia / Evento": "Sin hitos en este rango de edad", "Fecha": "-", "Edad": "-", "Tiempo Prog.": "-"}]) [cite: 138, 139]
                anchos_columnas = [0.52, 0.16, 0.16, 0.16] [cite: 140]
        else:
            if not df_procesado.empty: [cite: 140]
                df_table_render = df_procesado[["Edad", "Tiempo", "Evento / Fecha"]].copy() [cite: 140]
                df_table_render["Edad"] = df_table_render["Edad"].map(lambda x: f"{x:.2f} a") [cite: 140]
                df_table_render["Tiempo"] = df_table_render["Tiempo"].map(lambda x: f"{x:.2f} s") [cite: 140]
                anchos_columnas = [0.15, 0.15, 0.70] [cite: 140]
            else:
                df_table_render = pd.DataFrame([{"Edad": "-", "Tiempo": "-", "Evento / Fecha": "Sin marcas registradas"}]) [cite: 141]
                anchos_columnas = [0.15, 0.15, 0.70] [cite: 141, 142]

        if df_table_render is not None and not df_table_render.empty: [cite: 142]
            total_filas = len(df_table_render) [cite: 142]
            limite_filas_por_bloque = 16 [cite: 142]
            
            def estilizar_tabla_nativo(instancia_tabla): [cite: 142]
                instancia_tabla.auto_set_font_size(False) [cite: 142]
                instancia_tabla.set_fontsize(8.5) [cite: 142]
                instancia_tabla.scale(1.0, 1.3) [cite: 142]
                for (row, col), cell in instancia_tabla.get_celld().items(): [cite: 142, 143]
                    cell.set_linewidth(0.5) [cite: 143]            
                    cell.set_edgecolor('#E5E7EB') [cite: 143]       
                    if row == 0: [cite: 143]
                        cell.set_text_props(color='black', weight='light') [cite: 144]
                        cell.set_facecolor('#C0C0C0') [cite: 144]
                    else:
                        cell.set_facecolor('#F8F9F9' if row % 2 == 0 else 'white') [cite: 144]

            if total_filas <= limite_filas_por_bloque: [cite: 144]
                ax_table = fig.add_axes([0.14, 0.054, 0.72, 0.40]) [cite: 144]
                ax_table.axis('off') [cite: 145]
                mpl_table = ax_table.table(cellText=df_table_render.values, colLabels=df_table_render.columns, cellLoc='center', loc='upper center', colWidths=anchos_columnas) [cite: 145, 146]
                estilizar_tabla_nativo(mpl_table) [cite: 146]
            else:
                if total_filas > 32: df_table_render = df_table_render.iloc[:32] [cite: 146]
                df_bloque_izq = df_table_render.iloc[:limite_filas_por_bloque] [cite: 146]
                df_bloque_der = df_table_render.iloc[limite_filas_por_bloque:] [cite: 146, 147]
                anchos_doble = anchos_columnas if es_modo_micro_tabla else [0.18, 0.18, 0.64] [cite: 147]
                
                ax_table1 = fig.add_axes([0.14, 0.054, 0.34, 0.40]) [cite: 147]
                ax_table1.axis('off') [cite: 147]
                mpl_table1 = ax_table1.table(cellText=df_bloque_izq.values, colLabels=df_bloque_izq.columns, cellLoc='center', loc='upper center', colWidths=anchos_doble) [cite: 147]
                estilizar_tabla_nativo(mpl_table1) [cite: 148]
                
                ax_table2 = fig.add_axes([0.52, 0.054, 0.34, 0.40]) [cite: 148]
                ax_table2.axis('off') [cite: 148]
                mpl_table2 = ax_table2.table(cellText=df_bloque_der.values, colLabels=df_bloque_der.columns, cellLoc='center', loc='upper center', colWidths=anchos_doble) [cite: 148]
                estilizar_tabla_nativo(mpl_table2) [cite: 148]

        st.pyplot(fig, use_container_width=True) [cite: 148]
