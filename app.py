import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from database import init_db, db_manager
from scraper import Scraper
from utils import format_caratula, generate_report, load_juzgados_data
import time

# --- INICIALIZACIÓN Y CONFIGURACIÓN ---
init_db()
st.set_page_config(layout="wide", page_title="Gestor de Expedientes CAYT", page_icon="⚖️")

# --- LÓGICA DE LOGIN ---
def check_password():
    if st.session_state.get("authenticated", False):
        return True
    try:
        password_guardada = st.secrets["APP_PASSWORD"]
    except:
        st.error("No se ha configurado una contraseña para la aplicación en los 'Secrets' de Streamlit.")
        return False

    st.title("⚖️ Gestor de Expedientes CAYT")
    st.write("Acceso Protegido")
    with st.form("login_form"):
        password = st.text_input("Contraseña", type="password")
        submitted = st.form_submit_button("Ingresar")
        if submitted:
            if password == password_guardada:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("La contraseña es incorrecta.")
    return False

if not check_password():
    st.stop()

# --- CÓDIGO PRINCIPAL DE LA APP ---
# (El resto del código es igual a la última versión funcional, ahora protegido por el login)
@st.cache_data(ttl=300)
def load_data():
    return db_manager.get_all_data()

# (El resto del app.py va aquí...)
# --- BARRA LATERAL ---
with st.sidebar:
    st.title("⚖️ Gestor CAYT")
    opcion_menu = st.radio( "Navegación", ["📈 Dashboard", "🗂️ Mis Expedientes", "🗓️ Agenda", "📝 Notas", "🔍 Búsqueda", "📄 Reportes"], label_visibility="hidden")
    st.markdown("---")
    if st.button("🔄 Sincronizar con Portal"):
        with st.spinner("Iniciando sesión y sincronizando..."):
            scraper_instance = Scraper()
            scraper_instance.login_and_sync()
        st.success("¡Sincronización completa!")
        st.cache_data.clear()
        st.rerun()
    if 'driver' in st.session_state and st.session_state.driver:
        if st.button("❌ Cerrar Navegador"):
            Scraper().close()
            st.rerun()
    st.markdown("---")
    st.caption(f"Última sync: {st.session_state.get('last_sync', 'N/A')}")

# --- CARGA DE DATOS ---
juzgados_data = load_juzgados_data()
expedientes_df, tareas_df, notas_df, movimientos_df = load_data()

# --- PANEL DE CONTENIDO PRINCIPAL ---
if opcion_menu == "📈 Dashboard":
    st.title("📈 Panel de Control")
    if expedientes_df.empty:
        st.info("Aún no se han cargado expedientes. Use 'Sincronizar con Portal' para comenzar.")
    else:
        # (Métricas sin cambios)
        tareas_pendientes = tareas_df[~tareas_df['completada']]
        vencen_7_dias = len(tareas_pendientes[tareas_pendientes['fecha_vencimiento'] <= (date.today() + timedelta(days=7))]) if not tareas_pendientes.empty else 0
        col1, col2, col3 = st.columns(3)
        col1.metric("Expedientes Activos", len(expedientes_df))
        col2.metric("Tareas Pendientes", len(tareas_pendientes))
        col3.metric("Vencen en 7 días", vencen_7_dias)
        st.markdown("---")
        st.subheader("Últimos Movimientos y Notas")
        col_mov, col_notas = st.columns(2)
        with col_mov:
            st.write("**Novedades Recientes del Portal**")
            expedientes_df['fecha_novedad_dt'] = pd.to_datetime(expedientes_df['fecha_novedad_portal'], format='%d/%m/%Y', errors='coerce')
            ultimos_movimientos = expedientes_df.sort_values(by='fecha_novedad_dt', ascending=False).head(5)
            for _, exp in ultimos_movimientos.iterrows():
                with st.container(border=True):
                    # --- LINK CORREGIDO ---
                    link = exp.get('link_portal', '#')
                    st.markdown(f"**<a href='{link}' target='_blank' style='text-decoration: none; color: inherit;'>{format_caratula(exp['caratula'])}</a>**", unsafe_allow_html=True)
                    st.caption(f"{exp['ultima_novedad_portal']} ({exp['fecha_novedad_portal']})")
        with col_notas:
            # (Sección de notas sin cambios)
            st.write("**Últimas Notas Agregadas**")
            if not notas_df.empty:
                ultimas_notas = notas_df.sort_values(by='fecha_creacion', ascending=False).head(5)
                notas_con_caratula = pd.merge(ultimas_notas, expedientes_df[['numero', 'caratula']], left_on='expediente_numero', right_on='numero', how='left').fillna({'caratula': 'N/A'})
                for _, nota in notas_con_caratula.iterrows():
                    with st.container(border=True):
                        st.markdown(f"**Nota en:** {format_caratula(nota['caratula'])}")
                        st.caption(f"{nota['contenido'][:100]}...")

elif opcion_menu == "🗂️ Mis Expedientes":
    st.title("🗂️ Mis Expedientes")
    for _, exp in expedientes_df.iterrows():
        exp_numero = exp['numero']
        badge_count = len(tareas_df[(tareas_df['expediente_numero'] == exp_numero) & (~tareas_df['completada'])])
        badge = f" `{badge_count} Tareas`" if badge_count > 0 else ""
        
        # --- LÓGICA DE COLORES MEJORADA ---
        caratula_display = exp['caratula']
        cautelar_status = str(exp.get('medida_cautelar_status', '')).upper()
        if cautelar_status == 'CONCEDIDA':
            caratula_display = f":green[{exp['caratula']}]"
        elif cautelar_status == 'PENDIENTE':
            caratula_display = f":red[{exp['caratula']}]"
        elif cautelar_status == 'PARCIALMENTE CONCEDIDA':
            caratula_display = f":orange[{exp['caratula']}]"
        
        with st.expander(f"**{exp_numero}** - {caratula_display}{badge}"):
            tab_ficha, tab_historial, tab_tareas, tab_notas = st.tabs(["Ficha Técnica", "Historial", "Tareas", "Notas"])
            with tab_ficha:
                with st.form(key=f"form_ficha_{exp_numero}"):
                    # --- SELECTBOX PARA CAUTELAR ---
                    opciones_cautelar = ["", "PENDIENTE", "CONCEDIDA", "PARCIALMENTE CONCEDIDA", "DENEGADA"]
                    indice_cautelar = opciones_cautelar.index(exp.get('medida_cautelar_status', '').upper()) if exp.get('medida_cautelar_status', '').upper() in opciones_cautelar else 0
                    
                    st.selectbox("Juzgado", options=[""] + [j['nombre'] for j in juzgados_data], key=f"juzgado_{exp_numero}", index=0)
                    st.selectbox("Secretaría", options=[""], key=f"secretaria_{exp_numero}", index=0) # Simplificado por ahora
                    st.selectbox("Estado Medida Cautelar", options=opciones_cautelar, key=f"mc_{exp_numero}", index=indice_cautelar)
                    st.text_area("Observaciones", value=exp.get('observaciones', ''), key=f"obs_{exp_numero}")

                    if st.form_submit_button("Guardar Ficha"):
                        db_manager.update_ficha_expediente(exp_numero, {
                            'juzgado_nombre': st.session_state[f"juzgado_{exp_numero}"],
                            'secretaria_nombre': st.session_state[f"secretaria_{exp_numero}"],
                            'medida_cautelar_status': st.session_state[f"mc_{exp_numero}"],
                            'observaciones': st.session_state[f"obs_{exp_numero}"]
                        })
                        st.success("Ficha actualizada.")
                        st.cache_data.clear()
                        st.rerun()
            # (Resto de las tabs sin cambios)
            with tab_historial:
                 # ...
                pass
            with tab_tareas:
                # ...
                pass
            with tab_notas:
                # ...
                pass

# (Resto de las secciones sin cambios)
elif opcion_menu == "🗓️ Agenda":
    # ...
    pass
elif opcion_menu == "📝 Notas":
    # ...
    pass
elif opcion_menu == "🔍 Búsqueda":
    # ...
    pass
elif opcion_menu == "📄 Reportes":
    # ...
    pass
