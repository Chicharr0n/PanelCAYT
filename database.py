import sqlalchemy as db
import pandas as pd
from datetime import datetime

DB_FILE = "gestor_definitivo.db"
engine = db.create_engine(f'sqlite:///{DB_FILE}')

def init_db():
    metadata = db.MetaData()
    if not engine.dialect.has_table(engine.connect(), "expedientes"):
        # --- TABLA MODIFICADA ---
        db.Table('expedientes', metadata,
            db.Column('numero', db.String, primary_key=True), db.Column('caratula', db.String),
            db.Column('estado', db.String), 
            db.Column('juzgado_nombre', db.String), # NUEVO
            db.Column('secretaria_nombre', db.String), # NUEVO
            db.Column('medida_cautelar_status', db.String),
            db.Column('ultima_novedad_portal', db.String), db.Column('fecha_novedad_portal', db.String)
        )
        # (El resto de las tablas no cambian)
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
    # (El código de la clase DatabaseManager necesita una pequeña modificación)
    def __init__(self, engine):
        self.engine = engine

    def sync_expedientes(self, df):
        with self.engine.connect() as conn:
            for _, row in df.iterrows():
                stmt = db.text("SELECT * FROM expedientes WHERE numero = :numero")
                if conn.execute(stmt, {"numero": row['Numero']}).fetchone():
                    update_stmt = db.text("UPDATE expedientes SET caratula=:c, estado=:e, ultima_novedad_portal=:un, fecha_novedad_portal=:fn WHERE numero=:n")
                    conn.execute(update_stmt, {"c": row['Caratula'], "e": row['Estado'], "un": row['Última Novedad'], "fn": row['Fecha Novedad'], "n": row['Numero']})
                else:
                    insert_stmt = db.text("INSERT INTO expedientes (numero, caratula, estado, ultima_novedad_portal, fecha_novedad_portal) VALUES (:n, :c, :e, :un, :fn)")
                    conn.execute(insert_stmt, {"n": row['Numero'], "c": row['Caratula'], "e": row['Estado'], "un": row['Última Novedad'], "fn": row['Fecha Novedad']})
            conn.commit()

    def get_all_data(self):
        # (Sin cambios aquí)
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

    # --- MÉTODO MODIFICADO ---
    def update_ficha_expediente(self, numero, data):
        with self.engine.connect() as conn:
            stmt = db.text("UPDATE expedientes SET juzgado_nombre=:j, secretaria_nombre=:s, medida_cautelar_status=:mc WHERE numero=:n")
            conn.execute(stmt, {"j": data['juzgado_nombre'], "s": data['secretaria_nombre'], "mc": data['medida_cautelar_status'], "n": numero})
            conn.commit()

    def add_item(self, table_name, data):
        # (Sin cambios aquí)
        with self.engine.connect() as conn:
            table = db.Table(table_name, db.MetaData(), autoload_with=self.engine)
            stmt = db.insert(table).values(data)
            conn.execute(stmt)
            conn.commit()

    def update_tarea_status(self, tarea_id, completada):
        # (Sin cambios aquí)
        with self.engine.connect() as conn:
            stmt = db.text("UPDATE tareas SET completada=:c WHERE id=:i")
            conn.execute(stmt, {"c": completada, "i": tarea_id})
            conn.commit()

db_manager = DatabaseManager(engine)
