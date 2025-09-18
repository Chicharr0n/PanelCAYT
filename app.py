# database.py - VERSIÓN FINAL CON CONEXIÓN A TURSO
import streamlit as st
import sqlalchemy as db
import pandas as pd
from datetime import datetime

# --- LÓGICA DE CONEXIÓN ---
# Intenta conectarse a Turso (para producción), si no, usa el archivo local (para desarrollo)
try:
    url = st.secrets["TURSO_DATABASE_URL"]
    token = st.secrets["TURSO_AUTH_TOKEN"]
    # La URL de conexión para Turso con SQLAlchemy es un poco diferente
    conn_url = f"sqlite+{url}/?authToken={token}&secure=true"
    engine = db.create_engine(conn_url, connect_args={'check_same_thread': False}, echo=False)
    st.session_state['db_connection_type'] = "☁️ Turso Cloud"
except Exception:
    DB_FILE = "gestor_definitivo.db"
    engine = db.create_engine(f'sqlite:///{DB_FILE}')
    st.session_state['db_connection_type'] = "💾 Local"

# (El resto del archivo no cambia, es compatible con ambas bases de datos)
def init_db():
    # ... (código de init_db sin cambios)
    metadata = db.MetaData()
    if not engine.dialect.has_table(engine.connect(), "expedientes"):
        db.Table('expedientes', metadata,
            db.Column('numero', db.String, primary_key=True), db.Column('caratula', db.String),
            db.Column('estado', db.String), db.Column('juzgado_nombre', db.String), 
            db.Column('secretaria_nombre', db.String), db.Column('medida_cautelar_status', db.String),
            db.Column('observaciones', db.Text), db.Column('ultima_novedad_portal', db.String), 
            db.Column('fecha_novedad_portal', db.String), db.Column('link_portal', db.String)
        )
        db.Table('movimientos', metadata,
            db.Column('id', db.Integer, primary_key=True, autoincrement=True),
            db.Column('expediente_numero', db.String, db.ForeignKey('expedientes.numero')),
            db.Column('fecha', db.Date, nullable=False), db.Column('descripcion', db.String, nullable=False)
        )
        db.Table('tareas', metadata,
            db.Column('id', db.Integer, primary_key=True, autoincrement=True),
            db.Column('expediente_numero', db.String, db.ForeignKey('expedientes.numero')),
            db.Column('descripcion', db.String, nullable=False), db.Column('fecha_vencimiento', db.Date),
            db.Column('prioridad', db.String), db.Column('completada', db.Boolean, default=False)
        )
        db.Table('notas', metadata,
            db.Column('id', db.Integer, primary_key=True, autoincrement=True),
            db.Column('expediente_numero', db.String, db.ForeignKey('expedientes.numero')),
            db.Column('contenido', db.Text, nullable=False), db.Column('fecha_creacion', db.DateTime, default=datetime.now)
        )
        metadata.create_all(engine)

class DatabaseManager:
    # ... (toda la clase DatabaseManager sin cambios)
    def __init__(self, engine):
        self.engine = engine
    def sync_expedientes(self, df):
        with self.engine.connect() as conn:
            for _, row in df.iterrows():
                stmt = db.text("SELECT * FROM expedientes WHERE numero = :numero")
                if conn.execute(stmt, {"numero": row['Numero']}).fetchone():
                    update_stmt = db.text("UPDATE expedientes SET caratula=:c, estado=:e, ultima_novedad_portal=:un, fecha_novedad_portal=:fn, link_portal=:lp WHERE numero=:n")
                    conn.execute(update_stmt, {"c": row['Caratula'], "e": row['Estado'], "un": row['Última Novedad'], "fn": row['Fecha Novedad'], "lp": row['Link'], "n": row['Numero']})
                else:
                    insert_stmt = db.text("INSERT INTO expedientes (numero, caratula, estado, ultima_novedad_portal, fecha_novedad_portal, link_portal) VALUES (:n, :c, :e, :un, :fn, :lp)")
                    conn.execute(insert_stmt, {"n": row['Numero'], "c": row['Caratula'], "e": row['Estado'], "un": row['Última Novedad'], "fn": row['Fecha Novedad'], "lp": row['Link']})
            conn.commit()
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
            stmt = db.text("UPDATE expedientes SET juzgado_nombre=:jn, secretaria_nombre=:sn, medida_cautelar_status=:mcs, observaciones=:o WHERE numero=:n")
            conn.execute(stmt, {"jn": data['juzgado_nombre'], "sn": data['secretaria_nombre'], "mcs": data['medida_cautelar_status'], "o": data['observaciones'], "n": numero})
            conn.commit()
    def add_item(self, table_name, data):
        with self.engine.connect() as conn:
            table = db.Table(table_name, db.MetaData(), autoload_with=self.engine)
            stmt = db.insert(table).values(data)
            conn.execute(stmt)
            conn.commit()
    def update_tarea_status(self, tarea_id, completada):
        with self.engine.connect() as conn:
            stmt = db.text("UPDATE tareas SET completada=:c WHERE id=:i")
            conn.execute(stmt, {"c": completada, "i": tarea_id})
            conn.commit()

db_manager = DatabaseManager(engine)
