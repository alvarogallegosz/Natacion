# =============================================================================
# 📁 views/rendimiento.py - CONTROLADOR DE RENDIMIENTO BLINDADO (PROD & SIM)
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
    
    # Inyección de estilos CSS limpios para la estructura superior
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
    # 🔭 ZONA BLANCA SUPERIOR: SELECTORES COMPACTOS HORIZONTALES
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

    if modo_actual_render == "Equipo":
        st.markdown("**👥 Segmentación y Filtros de Equipo**")
        ce_1, ce_2 = st.columns(2)
        with ce_1:
            filtro_genero = st.selectbox("Filtro Género:", ["Todos", "Femenino (F)", "Masculino (M)"])
            tipo_filtro_equipo = st.radio("Filtrado por:", ["Todos los Atletas", "Categoría Etaria", "Atletas Específicos"])
        with ce_2:
            if tipo_filtro_equipo == "Categoría Etaria":
                cat_sel = st.selectbox("Categoría:", ["Infantil A", "Infantil B", "Juvenil A", "Juvenil B", "Máxima"])
            elif tipo_filtro_equipo == "Atletas Específicos":
                try:
                    r_all = supabase.table("usuarios").select("id, nombre").eq("rol", "Nadador").eq("estatus", "Activo").execute()
                    if r_all.data:
                        df_all = pd.DataFrame(r_all.data)
                        dict_all = dict(zip(df_all['nombre'], df_all['id']))
                        atletas_multi = st.multiselect("Nadadores específicos:", options=list(dict_all.keys()))
                        ids_sel = [dict_all[name] for name in atletas_multi]
                except Exception:
                    pass

    # -------------------------------------------------------------------------
    # 🎯 CONFIGURACIÓN DE PARÁMETROS DEL MODELO (VALORES DINÁMICOS DESDE SESSIONS)
    # -------------------------------------------------------------------------
    h = st.session_state.get("control_h", 0.40)
    t_peak = st.session_state.get("control_t_peak", 18.00)
    
    # Buscar récord mundial base para establecer metas de control por prueba
    record_mundial = 50.0
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
    df_procesado = pd.DataFrame()

    # =============================================================================
    # 📊 MOTOR GRÁFICO SECCIÓN A: MODO EQUIPO
    # =============================================================================
    if modo_actual_render == "Equipo":
        try:
            resp_todos = supabase.table("usuarios").select("id, nombre, fecha_nacimiento, genero").eq("rol", "Nadador").eq("estatus", "Activo").execute()
            atletas_lista = resp_todos.data if resp_todos.data else []
            
            # Filtrado por género directo
            if filtro_genero == "Femenino (F)":
                atletas_lista = [a for a in atletas_lista if a.get("genero") == "F"]
            elif filtro_genero == "Masculino (M)":
                atletas_lista = [a for a in atletas_lista if a.get("genero") == "M"]

            # Segmentación limpia por tipo de filtro de equipo
            atletas_filtrados = []
            if tipo_filtro_equipo == "Todos los Atletas":
                atletas_filtrados = atletas_lista
            elif tipo_filtro_equipo == "Categoría Etaria" and cat_sel:
                atletas_filtrados = [a for a in atletas_lista if determinar_categoria_fina(a.get("fecha_nacimiento"))[0] == cat_sel]
            elif tipo_filtro_equipo == "Atletas Específicos" and ids_sel:
                atletas_filtrados = [a for a in atletas_lista if a.get("id") in ids_sel]

            if not atletas_filtrados:
                st.warning("No se encontraron atletas activos con los criterios de segmentación elegidos.")
            else:
                # Sintaxis completamente lineal en una sola línea para evitar desbordes
                lista_ids = [str(atl["id"]) for atl in atletas_filtrados]
                
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

    # =============================================================================
    # 📊 MOTOR GRÁFICO SECCIÓN B: MODO INDIVIDUAL O SIMULACIÓN
    # =============================================================================
    else:
        fig = plt.figure(figsize=(8.5, 11.0))
        ax = fig.add_axes([0.14, 0.52, 0.72, 0.33])
        
        # Parámetros base del atleta para graficar curva asintótica individual
        t0, T0 = 10.0, 95.0
        t_pb, T_pb = t_pb_real, 62.0
        k = resolver_k_individual(t0, T0, t_pb, T_pb, t_peak, T_target)
        
        edades_curva = np.linspace(t0, t_peak, 300)
        tiempos_curva = calcular_curva_atleta(edades_curva, t0, T0, t_pb, T_pb, t_peak, T_target, k, h)
        
        todos_los_tiempos_ind = [T0, T_pb, T_target]
        
        if not simulacion_externa and atleta_id:
            try:
                r_ind_m = supabase.table("marcas_historicas").select("edad, tiempo, nota").eq("usuario_id", atleta_id).eq("prueba", prueba_sel).order("edad", desc=False).execute()
                if r_ind_m.data:
                    df_procesado = pd.DataFrame(r_ind_m.data)
                    df_procesado = df_procesado.rename(columns={"edad": "Edad", "tiempo": "Tiempo", "nota": "Evento / Fecha"})
                    todos_los_tiempos_ind.extend(df_procesado["Tiempo"].tolist())
            except Exception:
                pass

        if tipo_vista == "Micro (Ventana Anual)":
            edades_ventana = np.linspace(edad_min_zoom, edad_max_zoom, 300)
            tiempos_curva_ventana = calcular_curva_atleta(edades_ventana, t0, T0, t_pb, T_pb, t_peak, T_target, k, h).tolist()
            
            tiempos_reales_ventana = []
            if not df_procesado.empty:
                for _, row in df_procesado.iterrows():
                    if edad_min_zoom <= row["Edad"] <= edad_max_zoom:
                        tiempos_reales_ventana.append(row["Tiempo"])
                        
            todos_tiempos_v = tiempos_curva_ventana + tiempos_reales_ventana
            t_min_v = min(todos_tiempos_v) if todos_tiempos_v else min(tiempos_curva)
            t_max_v = max(todos_tiempos_v) if todos_tiempos_v else max(tiempos_curva)

            margen_y = max(0.5, (t_max_v - t_min_v) * 0.15)
            lim_y_inferior = t_min_v - margen_y
            lim_y_superior = t_max_v + margen_y
            lim_x_min, lim_x_max = edad_min_zoom, edad_max_zoom
        else:
            peor_tiempo_ind = max(todos_los_tiempos_ind)
            lim_y_inferior = m_wr * 0.92 if m_wr > 0 else min(todos_los_tiempos_ind) * 0.90
            lim_y_superior = peor_tiempo_ind + (peor_tiempo_ind * 0.08)
            
            if not df_procesado.empty:
                lim_x_min = min(float(t0), float(df_procesado["Edad"].min())) - 0.5
            else:
                lim_x_min = max(4.0, float(t0) - 0.5)
            lim_x_max = t_peak + 1.0

        ax.set_xlim(lim_x_min, lim_x_max)
        ax.set_ylim(lim_y_inferior, lim_y_superior)
        ax.set_autoscale_on(False)

        datos_tabla_micro = []
        
        # Pintar hitos y compromisos trimestrales
        if atleta_id and tipo_vista == "Micro (Ventana Anual)":
            try:
                r_atleta = supabase.table("usuarios").select("fecha_nacimiento").eq("id", atleta_id).execute()
                if r_atleta.data and r_atleta.data[0].get("fecha_nacimiento"):
                    fn_raw = r_atleta.data[0]["fecha_nacimiento"]
                    
                    r_hitos = supabase.table("hitos_temporada").select("fecha_evento, nombre_evento, elegible").eq("atleta_id", atleta_id).execute()
                    hitos_lista = r_hitos.data if r_hitos.data else []
                    
                    for hito in hitos_lista:
                        fecha_ev = hito.get("fecha_evento")
                        if not fecha_ev: continue
                        
                        edad_hito_calculada = calcular_edad_decimal(fn_raw, fecha_ev)
                        
                        if lim_x_min <= edad_hito_calculada <= lim_x_max:
                            es_elegible = hito.get("elegible", True)
                            color_linea = "#2ECC71" if es_elegible else "#E74C3C"
                            ax.axvline(x=edad_hito_calculada, color=color_linea, linestyle="--", linewidth=0.7, alpha=0.6)
                            
                            y_pos = lim_y_inferior + ((lim_y_superior - lim_y_inferior) * 0.03)
                            nombre_evento = hito.get("nombre_evento", "Control")
                            nombre_corto = nombre_evento[:18] + "..." if len(nombre_evento) > 18 else nombre_evento
                            
                            ax.text(edad_hito_calculada + 0.015, y_pos, f"{nombre_corto}", color=color_linea, fontsize=7.5, rotation=90, va="bottom")
                            tiempo_proyectado_val = calcular_curva_atleta([edad_hito_calculada], t0, T0, t_pb, T_pb, t_peak, T_target, k, h)[0]
                            
                            datos_tabla_micro.append({
                                "Competencia / Evento": nombre_evento,
                                "Fecha": str(fecha_ev),
                                "Edad": f"{edad_hito_calculada:.2f} a",
                                "Tiempo Prog.": f"{tiempo_proyectado_val:.2f} s"
                            })
            except Exception:
                pass

        if datos_tabla_micro:
            datos_tabla_micro.sort(key=lambda x: float(x["Edad"].replace(" a", "").strip()))

        ax.plot(edades_curva, tiempos_curva, color="#007A87", linewidth=1.8, label="Proyección Fisiológica")

        if not simulacion_externa and not df_procesado.empty:
            ax.plot(df_procesado["Edad"], df_procesado["Tiempo"], color="#D55E00", linestyle="--", linewidth=1.0, alpha=0.6, label="Evolución Real (PBs)")
            ax.scatter(df_procesado["Edad"], df_procesado["Tiempo"], color="#D55E00", edgecolor="black", s=25, zorder=3)

        # Elementos flotantes fijos en gráfico de dispersión
        estilo_bbox = dict(boxstyle="round,pad=0.25", fc="#F8F9F9", ec="#BDC3C7", alpha=0.9, linewidth=0.5)
        if lim_x_min <= t0 <= lim_x_max and lim_y_inferior <= T0 <= lim_y_superior:
            ax.scatter(t0, T0, color="#7F8C8D", edgecolor="black", s=35, zorder=4)
            ax.text(t0 + 0.1, T0, f"P. Start\n{T0:.2f}s", fontsize=8, va="bottom", bbox=estilo_bbox)

        if lim_x_min <= t_pb <= lim_x_max and lim_y_inferior <= T_pb <= lim_y_superior:
            ax.scatter(t_pb, t_pb, color="#F1C40F", marker="*", edgecolor="black", s=100, zorder=5)
            ax.text(t_pb + 0.15, T_pb, f"PB Actual\n{T_pb:.2f}s", fontsize=8, va="center", bbox=estilo_bbox)

        if lim_x_min <= t_peak <= lim_x_max and lim_y_inferior <= T_target <= lim_y_superior:
            ax.scatter(t_peak, T_target, color="#2ECC71", marker="s", edgecolor="black", s=35, zorder=4)
            ax.text(t_peak - 0.1, T_target, f"Meta Peak\n{T_target:.2f}s", fontsize=8, va="bottom", ha="right", bbox=estilo_bbox)

        # Renderizado de líneas horizontales de referencia internacional
        x_texto = lim_x_min + (lim_x_max - lim_x_min) * 0.05
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
                ax.text(x_texto, r["val"], f"{r['lbl']}: {r['val']:.2f}s", color=r["col"], fontsize=7, va=r["va"])

        ax.set_title(f"Curva de Rendimiento Asintótica - {prueba_sel}\nAtleta: {nombre_atleta}", fontsize=12, pad=10)
        ax.set_xlabel("Edad del Atleta (Años)", fontsize=9.5)
        ax.set_ylabel("Tiempo de Carrera (Segundos)", fontsize=9.5)
        ax.grid(True, linestyle=":", color="#CCD1D1", linewidth=0.5)
        
        tamano_leyenda = 6.5 if tipo_vista == "Micro (Ventana Anual)" else 8
        ax.legend(loc="upper right", fontsize=tamano_leyenda, framealpha=0.8)

        # -------------------------------------------------------------------------
        # 📋 CUADROS DE REPORTES Y DETALLES (TABLAS MATPLOTLIB)
        # -------------------------------------------------------------------------
        df_table_render = None
        es_modo_micro_tabla = (tipo_vista == "Micro (Ventana Anual)")

        if es_modo_micro_tabla:
            if datos_tabla_micro:
                df_table_render = pd.DataFrame(datos_tabla_micro)
                anchos_columnas = [0.46, 0.18, 0.16, 0.20]
            else:
                df_table_render = pd.DataFrame([{"Competencia / Evento": "Sin hitos en este rango de edad", "Fecha": "-", "Edad": "-", "Tiempo Prog.": "-"}])
                anchos_columnas = [0.52, 0.16, 0.16, 0.16]
        else:
            if not df_procesado.empty:
                df_table_render = df_procesado[["Edad", "Tiempo", "Evento / Fecha"]].copy()
                df_table_render["Edad"] = df_table_render["Edad"].map(lambda x: f"{x:.2f} a")
                df_table_render["Tiempo"] = df_table_render["Tiempo"].map(lambda x: f"{x:.2f} s")
                anchos_columnas = [0.15, 0.15, 0.70]
            else:
                df_table_render = pd.DataFrame([{"Edad": "-", "Tiempo": "-", "Evento / Fecha": "Sin marcas registradas"}])
                anchos_columnas = [0.15, 0.15, 0.70]

        if df_table_render is not None and not df_table_render.empty:
            total_filas = len(df_table_render)
            limite_filas_por_bloque = 16
            
            def estilizar_tabla_nativo(instancia_tabla):
                instancia_tabla.auto_set_font_size(False)
                instancia_tabla.set_fontsize(8.5)
                instancia_tabla.scale(1.0, 1.3)
                for (row, col), cell in instancia_tabla.get_celld().items():
                    cell.set_linewidth(0.5)            
                    cell.set_edgecolor('#E5E7EB')       
                    if row == 0:
                        cell.set_text_props(color='black', weight='light')
                        cell.set_facecolor('#C0C0C0')
                    else:
                        cell.set_facecolor('#F8F9F9' if row % 2 == 0 else 'white')

            if total_filas <= limite_filas_por_bloque:
                ax_table = fig.add_axes([0.14, 0.054, 0.72, 0.40])
                ax_table.axis('off')
                mpl_table = ax_table.table(cellText=df_table_render.values, colLabels=df_table_render.columns, cellLoc='center', loc='upper center', colWidths=anchos_columnas)
                estilizar_tabla_nativo(mpl_table)
            else:
                if total_filas > 32: df_table_render = df_table_render.iloc[:32]
                df_bloque_izq = df_table_render.iloc[:limite_filas_por_bloque]
                df_bloque_der = df_table_render.iloc[limite_filas_por_bloque:]
                anchos_doble = anchos_columnas if es_modo_micro_tabla else [0.18, 0.18, 0.64]
                
                ax_table1 = fig.add_axes([0.14, 0.054, 0.34, 0.40])
                ax_table1.axis('off')
                mpl_table1 = ax_table1.table(cellText=df_bloque_izq.values, colLabels=df_bloque_izq.columns, cellLoc='center', loc='upper center', colWidths=anchos_doble)
                estilizar_tabla_nativo(mpl_table1)
                
                ax_table2 = fig.add_axes([0.52, 0.054, 0.34, 0.40])
                ax_table2.axis('off')
                mpl_table2 = ax_table2.table(cellText=df_bloque_der.values, colLabels=df_bloque_der.columns, cellLoc='center', loc='upper center', colWidths=anchos_doble)
                estilizar_tabla_nativo(mpl_table2)

        st.pyplot(fig, use_container_width=True)
