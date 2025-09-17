import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from database import init_db, db_manager
from scraper import Scraper
from utils import format_caratula, create_expediente_link, generate_report
import time

# --- INICIALIZACIÓN Y CONFIGURACIÓN DE LA PÁGINA ---
init_db()
st.set_page_config(
    layout="wide", 
    page_title="Gestor de Expedientes CAYT",
    page_icon="⚖️"
)

# --- ESTADOS DE SESIÓN ---
if 'last_sync' not in st.session_state:
    st.session_state.last_sync = "Nunca"
if 'sync_in_progress' not in st.session_state:
    st.session_state.sync_in_progress = False

# --- FUNCIONES AUXILIARES ---
@st.cache_data(ttl=300)  # Cache por 5 minutos
def load_data():
    """Carga todos los datos de la base de datos con caché"""
    return db_manager.get_all_data()

def sync_with_portal():
    """Función para sincronizar con el portal"""
    st.session_state.sync_in_progress = True
    try:
        with st.spinner("Iniciando sesión y sincronizando..."):
            scraper_instance = Scraper()
            scraper_instance.login_and_sync()
        st.session_state.last_sync = datetime.now().strftime("%d/%m/%Y %H:%M")
        st.success("¡Sincronización completa!")
        # Limpiar caché para forzar recarga de datos
        st.cache_data.clear()
    except Exception as e:
        st.error(f"Error durante la sincronización: {str(e)}")
    finally:
        st.session_state.sync_in_progress = False

# --- BARRA LATERAL ---
with st.sidebar:
    st.title("⚖️ Gestor CAYT")
    opcion_menu = st.radio(
        "Navegación", 
        ["📈 Dashboard", "🗂️ Mis Expedientes", "🗓️ Agenda", "📝 Notas", "🔍 Búsqueda", "📄 Reportes", "⚙️ Configuración"],
        label_visibility="hidden"
    )
    
    st.markdown("---")
    
    # Botón de sincronización con estado deshabilitado durante la sincronización
    if st.button(
        "🔄 Sincronizar con Portal", 
        disabled=st.session_state.sync_in_progress,
        help="Actualiza los datos desde el portal judicial"
    ):
        sync_with_portal()
        time.sleep(1)  # Pequeña pausa para mostrar el mensaje de éxito
        st.rerun()
    
    # Estado del navegador
    if 'driver' in st.session_state and st.session_state.driver:
        if st.button("❌ Cerrar Navegador"):
            Scraper().close()
            st.rerun()
    
    st.markdown("---")
    st.caption(f"Última sincronización: {st.session_state.last_sync}")

# --- CARGA DE DATOS ---
try:
    expedientes_df, tareas_df, notas_df, movimientos_df = load_data()
except Exception as e:
    st.error(f"Error cargando datos: {str(e)}")
    st.stop()

# --- PANEL DE CONTENIDO PRINCIPAL ---
if opcion_menu == "📈 Dashboard":
    st.title("📈 Panel de Control")
    
    if expedientes_df.empty:
        st.info("Aún no se han cargado expedientes. Use 'Sincronizar con Portal' para comenzar.")
    else:
        # Métricas
        tareas_pendientes = tareas_df[~tareas_df['completada']]
        vencen_7_dias = len(tareas_pendientes[
            (tareas_pendientes['fecha_vencimiento'] <= (date.today() + timedelta(days=7))) &
            (tareas_pendientes['fecha_vencimiento'] >= date.today())
        ]) if not tareas_pendientes.empty else 0
        
        vencidas = len(tareas_pendientes[
            tareas_pendientes['fecha_vencimiento'] < date.today()
        ]) if not tareas_pendientes.empty else 0
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Expedientes Activos", len(expedientes_df))
        col2.metric("Tareas Pendientes", len(tareas_pendientes))
        col3.metric("Vencen en 7 días", vencen_7_dias)
        col4.metric("Tareas Vencidas", vencidas, delta_color="inverse")
        
        st.markdown("---")
        
        # Últimos movimientos y notas
        st.subheader("Actividad Reciente")
        col_mov, col_notas = st.columns(2)
        
        with col_mov:
            st.write("**Novedades Recientes del Portal**")
            expedientes_df['fecha_novedad_dt'] = pd.to_datetime(
                expedientes_df['fecha_novedad_portal'], 
                format='%d/%m/%Y', 
                errors='coerce'
            )
            ultimos_movimientos = expedientes_df.sort_values(by='fecha_novedad_dt', ascending=False).head(5)
            
            for _, exp in ultimos_movimientos.iterrows():
                with st.container(border=True):
                    link = create_expediente_link(exp['numero'])
                    caratula_simple = format_caratula(exp['caratula'])
                    
                    # Determinar color según antigüedad de la novedad
                    dias_desde_novedad = (datetime.now() - exp['fecha_novedad_dt']).days
                    color = "red" if dias_desde_novedad <= 1 else "orange" if dias_desde_novedad <= 3 else "blue"
                    
                    st.markdown(f":{color}[**{caratula_simple}**]")
                    st.caption(f"{exp['ultima_novedad_portal']} ({exp['fecha_novedad_portal']})")
                    
                    if link:
                        st.markdown(f"[Abrir expediente ↗]({link})", help="Abrir en el portal oficial")
        
        with col_notas:
            st.write("**Últimas Notas Agregadas**")
            if not notas_df.empty:
                ultimas_notas = notas_df.sort_values(by='fecha_creacion', ascending=False).head(5)
                notas_con_caratula = pd.merge(
                    ultimas_notas, 
                    expedientes_df[['numero', 'caratula']], 
                    left_on='expediente_numero', 
                    right_on='numero', 
                    how='left'
                ).fillna({'caratula': 'N/A'})
                
                for _, nota in notas_con_caratula.iterrows():
                    with st.container(border=True):
                        st.markdown(f"**Nota en:** {format_caratula(nota['caratula'])}")
                        st.caption(f"{nota['contenido'][:100]}{'...' if len(nota['contenido']) > 100 else ''}")
                        st.caption(f"Añadida el {nota['fecha_creacion'].strftime('%d/%m/%Y %H:%M')}")
            else:
                st.info("No hay notas recientes")

elif opcion_menu == "🗂️ Mis Expedientes":
    st.title("🗂️ Mis Expedientes")
    
    # Filtros
    col1, col2 = st.columns(2)
    with col1:
        filtro_juzgado = st.selectbox(
            "Filtrar por juzgado",
            options=["Todos"] + sorted(expedientes_df['juzgado'].dropna().unique().tolist())
        )
    
    with col2:
        filtro_busqueda = st.text_input("Buscar en carátula", placeholder="Texto en carátula...")
    
    # Aplicar filtros
    expedientes_filtrados = expedientes_df.copy()
    if filtro_juzgado != "Todos":
        expedientes_filtrados = expedientes_filtrados[expedientes_filtrados['juzgado'] == filtro_juzgado]
    if filtro_busqueda:
        expedientes_filtrados = expedientes_filtrados[
            expedientes_filtrados['caratula'].str.contains(filtro_busqueda, case=False, na=False)
        ]
    
    if expedientes_filtrados.empty:
        st.info("No hay expedientes que coincidan con los filtros aplicados.")
    else:
        for _, exp in expedientes_filtrados.iterrows():
            exp_numero = exp['numero']
            tareas_pendientes_count = len(tareas_df[
                (tareas_df['expediente_numero'] == exp_numero) & 
                (~tareas_df['completada'])
            ])
            
            # Determinar color según estado de la medida cautelar
            caratula_display = exp['caratula']
            cautelar_status = str(exp.get('medida_cautelar_status', '')).lower()
            
            if 'concedida' in cautelar_status or 'otorgada' in cautelar_status:
                caratula_display = f":green[{exp['caratula']}]"
            elif 'denegada' in cautelar_status or 'rechazada' in cautelar_status:
                caratula_display = f":red[{exp['caratula']}]"
            elif 'pendiente' in cautelar_status or 'en trámite' in cautelar_status:
                caratula_display = f":orange[{exp['caratula']}]"
            
            # Badge para tareas pendientes
            badge = f" 🚨 `{tareas_pendientes_count} Tareas`" if tareas_pendientes_count > 0 else ""
            
            expander_title = f"**{exp_numero}** - {caratula_display}{badge}"
            
            with st.expander(expander_title):
                tab_ficha, tab_historial, tab_tareas, tab_notas = st.tabs(
                    ["Ficha Técnica", "Historial de Movimientos", "Tareas", "Notas"]
                )
                
                with tab_ficha:
                    with st.form(key=f"form_ficha_{exp_numero}"):
                        juzgado = st.text_input("Juzgado", value=exp.get('juzgado', ''), key=f"juzgado_{exp_numero}")
                        medida_cautelar = st.text_input(
                            "Estado Medida Cautelar", 
                            value=exp.get('medida_cautelar_status', ''), 
                            key=f"mc_{exp_numero}"
                        )
                        observaciones = st.text_area(
                            "Observaciones",
                            value=exp.get('observaciones', ''),
                            key=f"obs_{exp_numero}"
                        )
                        
                        if st.form_submit_button("Guardar Ficha"):
                            db_manager.update_ficha_expediente(exp_numero, {
                                'juzgado': juzgado,
                                'medida_cautelar_status': medida_cautelar,
                                'observaciones': observaciones
                            })
                            st.success("Ficha actualizada.")
                            st.cache_data.clear()
                            time.sleep(0.5)
                            st.rerun()
                
                with tab_historial:
                    movs = movimientos_df[movimientos_df['expediente_numero'] == exp_numero].sort_values(
                        by='fecha', 
                        ascending=False
                    )
                    
                    if movs.empty:
                        st.info("No hay movimientos registrados para este expediente.")
                    else:
                        for _, mov in movs.iterrows(): 
                            st.markdown(f"- **{mov['fecha'].strftime('%d/%m/%Y')}:** {mov['descripcion']}")
                    
                    with st.form(key=f"form_mov_{exp_numero}", clear_on_submit=True):
                        st.write("**Añadir Movimiento:**")
                        c1, c2 = st.columns([1, 3])
                        fecha_mov = c1.date_input("Fecha", key=f"fecha_mov_{exp_numero}")
                        desc_mov = c2.text_input("Descripción", key=f"desc_mov_{exp_numero}")
                        
                        if st.form_submit_button("Guardar Movimiento"):
                            db_manager.add_item('movimientos', {
                                "expediente_numero": exp_numero, 
                                "fecha": fecha_mov, 
                                "descripcion": desc_mov
                            })
                            st.cache_data.clear()
                            time.sleep(0.5)
                            st.rerun()
                
                with tab_tareas:
                    tareas_exp = tareas_df[tareas_df['expediente_numero'] == exp_numero].sort_values(
                        by='fecha_vencimiento'
                    )
                    
                    if tareas_exp.empty:
                        st.info("No hay tareas para este expediente.")
                    else:
                        for _, t in tareas_exp.iterrows():
                            col1, col2 = st.columns([0.9, 0.1])
                            with col1:
                                estado_actual = bool(t['completada'])
                                dias_restantes = (t['fecha_vencimiento'] - date.today()).days
                                
                                # Color según estado y proximidad de vencimiento
                                if estado_actual:
                                    estado_texto = f"~~{t['descripcion']}~~ ✅"
                                    color = "gray"
                                elif dias_restantes < 0:
                                    estado_texto = f"{t['descripcion']} 🚨 (Vencida)"
                                    color = "red"
                                elif dias_restantes <= 3:
                                    estado_texto = f"{t['descripcion']} ⚠️ (Vence: {t['fecha_vencimiento'].strftime('%d/%m/%Y')})"
                                    color = "orange"
                                else:
                                    estado_texto = f"{t['descripcion']} (Vence: {t['fecha_vencimiento'].strftime('%d/%m/%Y')})"
                                    color = "blue"
                                
                                st.markdown(f":{color}[{estado_texto}]")
                            
                            with col2:
                                nuevo_estado = st.checkbox(
                                    "Completada", 
                                    value=estado_actual, 
                                    key=f"chk_{t['id']}",
                                    label_visibility="collapsed"
                                )
                                if nuevo_estado != estado_actual:
                                    db_manager.update_tarea_status(t['id'], nuevo_estado)
                                    st.cache_data.clear()
                                    time.sleep(0.5)
                                    st.rerun()
                    
                    with st.form(key=f"form_tarea_{exp_numero}", clear_on_submit=True):
                        st.write("**Añadir Tarea:**")
                        nueva_desc = st.text_input("Descripción")
                        c1, c2 = st.columns(2)
                        nueva_fecha = c1.date_input("Vencimiento", min_value=date.today())
                        nueva_prioridad = c2.selectbox("Prioridad", ["Alta", "Media", "Baja"])
                        
                        if st.form_submit_button("Guardar Tarea"):
                            db_manager.add_item('tareas', {
                                "expediente_numero": exp_numero, 
                                "descripcion": nueva_desc, 
                                "fecha_vencimiento": nueva_fecha, 
                                "prioridad": nueva_prioridad.lower(),
                                "completada": False
                            })
                            st.cache_data.clear()
                            time.sleep(0.5)
                            st.rerun()
                
                with tab_notas:
                    notas_exp = notas_df[notas_df['expediente_numero'] == exp_numero].sort_values(
                        by='fecha_creacion', 
                        ascending=False
                    )
                    
                    if notas_exp.empty:
                        st.info("No hay notas para este expediente.")
                    else:
                        for _, n in notas_exp.iterrows(): 
                            with st.container(border=True):
                                st.markdown(n['contenido'])
                                st.caption(f"Añadida el {n['fecha_creacion'].strftime('%d/%m/%Y %H:%M')}")
                    
                    with st.form(key=f"form_nota_{exp_numero}", clear_on_submit=True):
                        nuevo_contenido = st.text_area("Nueva Nota:", height=100)
                        
                        if st.form_submit_button("Guardar Nota"):
                            db_manager.add_item('notas', {
                                "expediente_numero": exp_numero, 
                                "contenido": nuevo_contenido, 
                                "fecha_creacion": datetime.now()
                            })
                            st.cache_data.clear()
                            time.sleep(0.5)
                            st.rerun()

elif opcion_menu == "🗓️ Agenda":
    st.title("🗓️ Agenda de Vencimientos")
    
    # Filtros para la agenda
    col1, col2 = st.columns(2)
    with col1:
        filtro_prioridad = st.selectbox(
            "Filtrar por prioridad",
            options=["Todas", "Alta", "Media", "Baja"]
        )
    
    with col2:
        filtro_dias = st.slider(
            "Próximos días a mostrar",
            min_value=1,
            max_value=30,
            value=7
        )
    
    # Aplicar filtros
    tareas_pendientes = tareas_df[~tareas_df['completada']].sort_values(by='fecha_vencimiento')
    
    if filtro_prioridad != "Todas":
        tareas_pendientes = tareas_pendientes[tareas_pendientes['prioridad'] == filtro_prioridad.lower()]
    
    fecha_limite = date.today() + timedelta(days=filtro_dias)
    tareas_pendientes = tareas_pendientes[tareas_pendientes['fecha_vencimiento'] <= fecha_limite]
    
    if tareas_pendientes.empty: 
        st.success("¡No hay tareas pendientes para los criterios seleccionados! 🎉")
    else:
        # Agrupar por fecha de vencimiento
        tareas_por_fecha = tareas_pendientes.groupby('fecha_vencimiento')
        
        for fecha, grupo in tareas_por_fecha:
            dias_restantes = (fecha - date.today()).days
            
            if dias_restantes < 0:
                titulo = f"### ❌ Vencidas ({fecha.strftime('%d/%m/%Y')})"
                color_borde = "red"
            elif dias_restantes == 0:
                titulo = f"### ⚠️ Vencen hoy ({fecha.strftime('%d/%m/%Y')})"
                color_borde = "orange"
            elif dias_restantes <= 3:
                titulo = f"### 🔥 Vencen en {dias_restantes} días ({fecha.strftime('%d/%m/%Y')})"
                color_borde = "orange"
            else:
                titulo = f"### 📅 Vencen en {dias_restantes} días ({fecha.strftime('%d/%m/%Y')})"
                color_borde = "blue"
            
            st.markdown(titulo)
            
            for _, t in grupo.iterrows():
                with st.container(border=True):
                    # Obtener información del expediente asociado
                    exp_asociado_df = expedientes_df[expedientes_df['numero'] == t['expediente_numero']]
                    
                    if not exp_asociado_df.empty:
                        exp_asociado = exp_asociado_df.iloc[0]
                        caratula = format_caratula(exp_asociado['caratula'])
                        st.markdown(f"**{t['descripcion']}**")
                        st.markdown(f"**Expediente:** {caratula}")
                        
                        # Prioridad
                        prioridad_emoji = {"alta": "🔴", "media": "🟡", "baja": "🔵"}
                        st.markdown(f"**Prioridad:** {prioridad_emoji.get(t['prioridad'], '⚪')} {t['prioridad'].capitalize()}")
                    else:
                        st.markdown(f"**{t['descripcion']}**")
                        st.markdown(f"**Expediente:** {t['expediente_numero']}")
                    
                    st.markdown(f"**Vence:** {t['fecha_vencimiento'].strftime('%d/%m/%Y')}")

elif opcion_menu == "📝 Notas":
    st.title("📝 Resumen de Notas")
    
    # Filtros para notas
    filtro_expediente = st.selectbox(
        "Filtrar por expediente",
        options=["Todos"] + sorted(expedientes_df['numero'].unique().tolist()),
        format_func=lambda x: format_caratula(
            expedientes_df[expedientes_df['numero'] == x].iloc[0]['caratula']
        ) if x != "Todos" else "Todos"
    )
    
    if notas_df.empty: 
        st.info("Aún no has añadido ninguna nota.")
    else:
        # Aplicar filtro
        notas_filtradas = notas_df.copy()
        if filtro_expediente != "Todos":
            notas_filtradas = notas_filtradas[notas_filtradas['expediente_numero'] == filtro_expediente]
        
        notas_filtradas = notas_filtradas.sort_values(by='fecha_creacion', ascending=False)
        
        if notas_filtradas.empty:
            st.info("No hay notas para el expediente seleccionado.")
        else:
            notas_con_caratula = pd.merge(
                notas_filtradas, 
                expedientes_df[['numero', 'caratula']], 
                left_on='expediente_numero', 
                right_on='numero', 
                how='left'
            )
            
            for _, n in notas_con_caratula.iterrows():
                with st.container(border=True):
                    st.markdown(f"**Nota en:** {format_caratula(n.get('caratula', n['expediente_numero']))}")
                    st.write(n['contenido'])
                    st.caption(f"Añadido el {n['fecha_creacion'].strftime('%d/%m/%Y %H:%M')}")

elif opcion_menu == "🔍 Búsqueda":
    st.title("🔍 Búsqueda General en Portal CAYT")
    
    if 'driver' not in st.session_state or st.session_state.driver is None:
        st.warning("⚠️ Para buscar, primero debe 'Iniciar Sesión y Sincronizar' desde la barra lateral.")
    else:
        query = st.text_input("Ingrese su búsqueda", key="search_query", placeholder="Número de expediente, carátula, etc.")
        
        col1, col2 = st.columns([1, 3])
        with col1:
            tipo_busqueda = st.selectbox(
                "Tipo de búsqueda",
                options=["General", "Por número", "Por carátula"]
            )
        
        if st.button("Buscar en Portal", type="primary"):
            with st.spinner(f"Buscando '{query}'..."):
                try:
                    if tipo_busqueda == "Por número":
                        search_results = Scraper().search_by_number(query)
                    elif tipo_busqueda == "Por carátula":
                        search_results = Scraper().search_by_caratula(query)
                    else:
                        search_results = Scraper().search_on_portal(query)
                    
                    if not search_results.empty:
                        st.dataframe(
                            search_results, 
                            column_config={
                                "Enlace": st.column_config.LinkColumn("Abrir", display_text="↗️")
                            }, 
                            hide_index=True,
                            use_container_width=True
                        )
                    else:
                        st.info("No se encontraron resultados.")
                except Exception as e:
                    st.error(f"Error en la búsqueda: {str(e)}")

elif opcion_menu == "📄 Reportes":
    st.title("📄 Generador de Informes")
    
    if expedientes_df.empty:
        st.info("No hay expedientes para generar reportes.")
    else:
        # Selección de expedientes
        selected_expedientes = st.multiselect(
            "Seleccione los expedientes para incluir en el reporte:",
            options=expedientes_df['numero'],
            format_func=lambda x: format_caratula(
                expedientes_df[expedientes_df['numero'] == x].iloc[0]['caratula']
            )
        )
        
        # Opciones de formato
        formato_reporte = st.selectbox(
            "Formato del reporte",
            options=["Markdown", "HTML", "Texto plano"]
        )
        
        if st.button("Generar Reporte", type="primary"):
            if not selected_expedientes:
                st.warning("Debe seleccionar al menos un expediente.")
            else:
                with st.spinner("Generando reporte..."):
                    reporte = generate_report(
                        expedientes_df, 
                        tareas_df, 
                        notas_df, 
                        movimientos_df, 
                        selected_expedientes,
                        formato=formato_reporte
                    )
                
                # Mostrar previsualización
                with st.expander("Vista previa del reporte"):
                    if formato_reporte == "Markdown":
                        st.markdown(reporte)
                    elif formato_reporte == "HTML":
                        st.components.v1.html(reporte, height=400, scrolling=True)
                    else:
                        st.text(reporte)
                
                # Descargar reporte
                extension = {
                    "Markdown": "md",
                    "HTML": "html",
                    "Texto plano": "txt"
                }[formato_reporte]
                
                st.download_button(
                    f"Descargar Reporte (.{extension})",
                    reporte,
                    file_name=f"Reporte_Expedientes_{datetime.now().strftime('%Y%m%d_%H%M')}.{extension}",
                    mime={
                        "Markdown": "text/markdown",
                        "HTML": "text/html",
                        "Texto plano": "text/plain"
                    }[formato_reporte]
                )

elif opcion_menu == "⚙️ Configuración":
    st.title("⚙️ Configuración")
    
    st.subheader("Preferencias de visualización")
    col1, col2 = st.columns(2)
    
    with col1:
        modo_oscuro = st.toggle("Modo oscuro", value=False)
    
    with col2:
        elementos_por_pagina = st.slider("Elementos por página", 5, 50, 10)
    
    st.subheader("Configuración de sincronización")
    sincronizacion_automatica = st.toggle("Sincronización automática al iniciar", value=False)
    intervalo_sincronizacion = st.selectbox(
        "Intervalo de sincronización automática",
        options=["Desactivada", "Cada hora", "Cada 6 horas", "Diariamente"]
    )
    
    if st.button("Guardar configuración"):
        # Aquí iría la lógica para guardar la configuración
        st.success("Configuración guardada correctamente")