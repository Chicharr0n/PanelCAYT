import streamlit as st
import sqlalchemy as db
import pandas as pd
from datetime import datetime

# ----------------------------------------------------------------------
# Motor de base de datos (Turso primero, si falla usa SQLite local)
# ----------------------------------------------------------------------
def get_engine():
    try:
        url = st.secrets["TURSO_DATABASE_URL"]
        token = st.secrets["TURSO_AUTH_TOKEN"]

        # Intentar con sqlalchemy-libsql
        try:
            conn_url = f"sqlite+libsql:///?authToken={token}&url={url}"
            engine = db.create_engine(conn_url, echo=False)
            st.session_state['db_connection_type'] = "☁️ Turso Cloud (libsql)"
            return engine
        except Exception:
            # Fallback a libsql-experimental
            conn_url = f"libsql://{url}?authToken={token}"
            engine = db.create_engine(conn_url, echo=False)
            st.session_state['db_connection_type'] = "☁️ Turso Cloud (experimental)"
            return engine

    except Exception:
        # Fallback final a SQLite local
        DB_FILE = "gestor_definitivo.db"
        engine = db.create_engine(f"sqlite:///{DB_FILE}")
        st.session_state['db_connection_type'] = "💾 Local"
        return engine


# ----------------------------------------------------------------------
# Inicialización de tablas
# ----------------------------------------------------------------------
def init_db(engine):
    metadata = db.MetaData()
    if not engine.dialect.has_table(engine.connect(), "expedientes"):
        db.Table('expedientes', metadata,
            db.Column('numero', db.String, primary_key=True),
            db.Column('caratula', db.String),
            db.Column('estado', db.String),
            db.Column('juzgado_nombre', db.String),
            db.Column('secretaria_nombre', db.String),
            db.Column('medida_cautelar_status', db.String),
            db.Column('observaciones', db.Text),
            db.Column('ultima_novedad_portal', db.String),
            db.Column('fecha_novedad_portal', db.String),
            db.Column('link_portal', db.String)
        )
        db.Table('movimientos', metadata,
            db.Column('id', db.Integer, primary_key=True, autoincrement=True),
            db.Column('expediente_numero', db.String, db.ForeignKey('expedientes.numero')),
            db.Column('fecha', db.Date, nullable=False),
            db.Column('descripcion', db.String, nullable=False)
        )
        db.Table('tareas', metadata,
            db.Column('id', db.Integer, primary_key=True, autoincrement=True),
            db.Column('expediente_numero', db.String, db.ForeignKey('expedientes.numero')),
            db.Column('descripcion', db.String, nullable=False),
            db.Column('fecha_vencimiento', db.Date),
            db.Column('prioridad', db.String),
            db.Column('completada', db.Boolean, default=False)
        )
        db.Table('notas', metadata,
            db.Column('id', db.Integer, primary_key=True, autoincrement=True),
            db.Column('expediente_numero', db.String, db.ForeignKey('expedientes.numero')),
            db.Column('contenido', db.Text, nullable=False),
            db.Column('fecha_creacion', db.DateTime, default=datetime.now)
        )
        metadata.create_all(engine)


# ----------------------------------------------------------------------
# Gestor de base de datos
# ----------------------------------------------------------------------
class DatabaseManager:
    def __init__(self, engine):
        self.engine = engine

    def sync_expedientes(self, df):
        with self.engine.connect() as conn:
            for _, row in df.iterrows():
                stmt = db.text("SELECT * FROM expedientes WHERE numero = :numero")
                if conn.execute(stmt, {"numero": row['Numero']}).fetchone():
                    update_stmt = db.text("""
                        UPDATE expedientes
                        SET caratula=:c, estado=:e, ultima_novedad_portal=:un,
                            fecha_novedad_portal=:fn, link_portal=:lp
                        WHERE numero=:n
                    """)
                    conn.execute(update_stmt, {
                        "c": row['Caratula'], "e": row['Estado'],
                        "un": row['Última Novedad'], "fn": row['Fecha Novedad'],
                        "lp": row['Link'], "n": row['Numero']
                    })
                else:
                    insert_stmt = db.text("""
                        INSERT INTO expedientes (numero, caratula, estado,
                            ultima_novedad_portal, fecha_novedad_portal, link_portal)
                        VALUES (:n, :c, :e, :un, :fn, :lp)
                    """)
                    conn.execute(insert_stmt, {
                        "n": row['Numero'], "c": row['Caratula'],
                        "e": row['Estado'], "un": row['Última Novedad'],
                        "fn": row['Fecha Novedad'], "lp": row['Link']
                    })
            conn.commit()

    def get_all_data(self):
        with self.engine.connect() as conn:
            expedientes = pd.read_sql_table('expedientes', conn, coerce_float=False)
            tareas = pd.read_sql_table('tareas', conn, coerce_float=False)
            notas = pd.read_sql_table('notas', conn, coerce_float=False)
            movimientos = pd.read_sql_table('movimientos', conn, coerce_float=False)
        return expedientes, tareas, notas, movimientos

    def update_tarea_status(self, tarea_id, completada):
        with self.engine.connect() as conn:
            stmt = db.text("UPDATE tareas SET completada=:c WHERE id=:i")
            conn.execute(stmt, {"c": completada, "i": tarea_id})
            conn.commit()


# ----------------------------------------------------------------------
# Instancia global de db_manager
# ----------------------------------------------------------------------
_engine = get_engine()
init_db(_engine)
db_manager = DatabaseManager(_engine)
