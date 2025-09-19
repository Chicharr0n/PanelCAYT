import streamlit as st
import sqlalchemy as db
import pandas as pd
from datetime import datetime

# Estructura de la base de datos
metadata = db.MetaData()

expedientes_table = db.Table('expedientes', metadata,
    db.Column('numero', db.String, primary_key=True), db.Column('caratula', db.String),
    db.Column('estado', db.String), db.Column('juzgado_nombre', db.String), 
    db.Column('secretaria_nombre', db.String), db.Column('medida_cautelar_status', db.String),
    db.Column('observaciones', db.Text), db.Column('ultima_novedad_portal', db.String), 
    db.Column('fecha_novedad_portal', db.String), db.Column('link_portal', db.String)
)

movimientos_table = db.Table('movimientos', metadata,
    db.Column('id', db.Integer, primary_key=True, autoincrement=True),
    db.Column('expediente_numero', db.String, db.ForeignKey('expedientes.numero')),
    db.Column('fecha', db.Date, nullable=False), db.Column('descripcion', db.String, nullable=False)
)

tareas_table = db.Table('tareas', metadata,
    db.Column('id', db.Integer, primary_key=True, autoincrement=True),
    db.Column('expediente_numero', db.String, db.ForeignKey('expedientes.numero')),
    db.Column('descripcion', db.String, nullable=False), db.Column('fecha_vencimiento', db.Date),
    db.Column('prioridad', db.String), db.Column('completada', db.Boolean, default=False)
)

notas_table = db.Table('notas', metadata,
    db.Column('id', db.Integer, primary_key=True, autoincrement=True),
    db.Column('expediente_numero', db.String, db.ForeignKey('expedientes.numero')),
    db.Column('contenido', db.Text, nullable=False), db.Column('fecha_creacion', db.DateTime, default=datetime.now)
)

def get_engine():
    """Devuelve el motor de conexión a la base de datos (Turso Cloud o local)."""
    try:
        url = st.secrets["TURSO_DATABASE_URL"]
        token = st.secrets["TURSO_AUTH_TOKEN"]
        conn_url = f"sqlite+{url}/?authToken={token}&secure=true"
        engine = db.create_engine(conn_url, connect_args={'check_same_thread': False}, echo=False)
        st.session_state['db_connection_type'] = "☁️ Turso Cloud"
        return engine
    except Exception:
        DB_FILE = "gestor_definitivo.db"
        engine = db.create_engine(f'sqlite:///{DB_FILE}')
        st.session_state['db_connection_type'] = "💾 Local"
        return engine

def init_db(engine):
    """Crea las tablas en la base de datos si no existen."""
    inspector = db.inspect(engine)
    if not inspector.has_table("expedientes"):
        metadata.create_all(engine)

class DatabaseManager:
    def __init__(self, engine):
        self.engine = engine

    def sync_expedientes(self, df):
        with self.engine.connect() as conn:
            for _, row in df.iterrows():
                stmt_select = db.select(expedientes_table).where(expedientes_table.c.numero == row['Numero'])
                result = conn.execute(stmt_select).fetchone()
                if result:
                    stmt_update = db.update(expedientes_table).where(expedientes_table.c.numero == row['Numero']).values(
                        caratula=row['Caratula'], estado=row['Estado'], ultima_novedad_portal=row['Última Novedad'],
                        fecha_novedad_portal=row['Fecha Novedad'], link_portal=row['Link']
                    )
                    conn.execute(stmt_update)
                else:
                    stmt_insert = db.insert(expedientes_table).values(
                        numero=row['Numero'], caratula=row['Caratula'], estado=row['Estado'],
                        ultima_novedad_portal=row['Última Novedad'], fecha_novedad_portal=row['Fecha Novedad'],
                        link_portal=row['Link']
                    )
                    conn.execute(stmt_insert)

    def get_all_data(self):
        with self.engine.connect() as conn:
            expedientes = pd.read_sql_table('expedientes', conn, coerce_float=False)
            tareas = pd.read_sql_table('tareas', conn, coerce_float=False)
            notas = pd.read_sql_table('notas', conn, coerce_float=False)
            movimientos = pd.read_sql_table('movimientos', conn, coerce_float=False)
        if not tareas.empty:
            tareas['fecha_vencimiento'] = pd.to_datetime(tareas['fecha_vencimiento'], errors='coerce').dt.date
            if 'completada' in tareas.columns: tareas['completada'] = tareas['completada'].fillna(False).astype(bool)
        if not notas.empty:
            notas['fecha_creacion'] = pd.to_datetime(notas['fecha_creacion'], errors='coerce')
        if not movimientos.empty:
            movimientos['fecha'] = pd.to_datetime(movimientos['fecha'], errors='coerce').dt.date
        return expedientes, tareas, notas, movimientos

    def update_ficha_expediente(self, numero, data):
        with self.engine.connect() as conn:
            stmt = db.update(expedientes_table).where(expedientes_table.c.numero == numero).values(
                juzgado_nombre=data['juzgado_nombre'], secretaria_nombre=data['secretaria_nombre'],
                medida_cautelar_status=data['medida_cautelar_status'], observaciones=data['observaciones']
            )
            conn.execute(stmt)

    def add_item(self, table_name, data):
        table_map = {
            'movimientos': movimientos_table,
            'tareas': tareas_table,
            'notas': notas_table
        }
        table = table_map.get(table_name)
        if table is None:
            raise ValueError(f"Tabla desconocida: {table_name}")
        with self.engine.connect() as conn:
            stmt = db.insert(table).values(data)
            conn.execute(stmt)

    def update_tarea_status(self, tarea_id, completada):
        with self.engine.connect() as conn:
            stmt = db.update(tareas_table).where(tareas_table.c.id == tarea_id).values(completada=completada)
            conn.execute(stmt)