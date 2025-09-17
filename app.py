import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from database import init_db, db_manager
from scraper import Scraper
from utils import format_caratula, create_expediente_link, generate_report

# --- INICIALIZACIÓN Y CONFIGURACIÓN DE LA PÁGINA ---
init_db()
st.set_page_config(layout="wide", page_title="Gestor de Expedientes CAYT")


# --- NUEVA FUNCIÓN DE LOGIN ---
def check_password():
    """Muestra un formulario de login y retorna True si la contraseña es correcta."""
    if st.session_state.get("authenticated", False):
        return True

    st.title("Acceso Protegido")
    st.write("Por favor, ingrese la contraseña para continuar.")

    with st.form("login_form"):
        password = st.text_input("Contraseña", type="password")
        submitted = st.form_submit_button("Ingresar")

        if submitted:
            # Compara la contraseña ingresada con la guardada en los secretos
            if password == st.secrets.get("APP_PASSWORD"):
                st.session_state["authenticated"] = True
                st.rerun()  # Recarga la app para mostrar el contenido principal
            else:
                st.error("La contraseña es incorrecta.")
    return False

# --- EJECUCIÓN DEL LOGIN AL INICIO ---
if not check_password():
    st.stop()  # Si no está autenticado, detiene la ejecución del resto de la app


# --- BARRA LATERAL ---
with st.sidebar:
    st.title("⚖️ Gestor CAYT")
    opcion_menu = st.radio("Navegación", ["📈 Dashboard", "🗂️ Mis Expedientes", "🗓️ Agenda", "📝 Notas", "🔍 Búsqueda", "📄 Reportes"], label_visibility="hidden")
    st.markdown("---")
    if st.button("🔄 Sincronizar con Portal"):
        with st.spinner("Iniciando sesión y sincronizando..."):
            scraper_instance = Scraper()
            scraper_instance.login_and_sync()
        st.success("¡Sincronización completa!")
        st.rerun()
    if 'driver' in st.session_state and st.session_state.driver:
        if st.button("❌ Cerrar Navegador"):
            Scraper().close()
            st.rerun()
    st.markdown("---")
    if 'last_sync' in st.session_state:
        st.sidebar.caption(f"Última sync: {st.session_state.get('last_sync', 'N/A')}")

# --- CARGA DE DATOS ---
expedientes_df, tareas_df, notas_df, movimientos_df = db_manager.get_all_data()

# --- PANEL DE CONTENIDO PRINCIPAL (solo se muestra si el login es exitoso) ---
if opcion_menu == "📈 Dashboard":
    st.title("📈 Panel de Control")
    if expedientes_df.empty:
        st.info("Aún no se han cargado expedientes. Use 'Sincronizar con Portal' para comenzar.")
    else:
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
                    link = create_expediente_link(exp['numero'])
                    caratula_simple = format_caratula(exp['caratula'])
                    color = "blue"
                    st.markdown(f":{color}[**<a href='{link or '#'}' target='_blank' style='text-decoration: none; color: inherit;'>{caratula_simple}</a>**]", unsafe_allow_html=True)
                    st.caption(f"{exp['ultima_novedad_portal']} ({exp['fecha_novedad_portal']})")
        with col_notas:
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
        caratula_display = exp['caratula']
        cautelar_status = str(exp.get('medida_cautelar_status', '')).lower()
        if 'concedida' in cautelar_status or 'otorgada' in cautelar_status:
            caratula_display = f":yellow[{exp['caratula']}]"
        expander_title = f"**{exp_numero}** - {caratula_display}{badge}"
        with st.expander(expander_title):
            tab_ficha, tab_historial, tab_tareas, tab_notas = st.tabs(["Ficha Técnica", "Historial de Movimientos", "Tareas", "Notas"])
            with tab_ficha:
                with st.form(key=f"form_ficha_{exp_numero}"):
                    st.text_input("Juzgado", value=exp.get('juzgado', ''), key=f"juzgado_{exp_numero}")
                    st.text_input("Estado Medida Cautelar", value=exp.get('medida_cautelar_status', ''), key=f"mc_{exp_numero}")
                    if st.form_submit_button("Guardar Ficha"):
                        db_manager.update_ficha_expediente(exp_numero, {
                            'juzgado': st.session_state[f"juzgado_{exp_numero}"],
                            'medida_cautelar_status': st.session_state[f"mc_{exp_numero}"]
                        })
                        st.success("Ficha actualizada.")
                        st.rerun()
            with tab_historial:
                movs = movimientos_df[movimientos_df['expediente_numero'] == exp_numero].sort_values(by='fecha', ascending=False)
                for _, mov in movs.iterrows(): st.markdown(f"- **{mov['fecha'].strftime('%d/%m/%Y')}:** {mov['descripcion']}")
                with st.form(key=f"form_mov_{exp_numero}", clear_on_submit=True):
                    st.write("**Añadir Movimiento:**")
                    c1, c2 = st.columns([1, 3])
                    fecha_mov = c1.date_input("Fecha", key=f"fecha_mov_{exp_numero}")
                    desc_mov = c2.text_input("Descripción", key=f"desc_mov_{exp_numero}")
                    if st.form_submit_button("Guardar Movimiento"):
                        db_manager.add_item('movimientos', {"expediente_numero
