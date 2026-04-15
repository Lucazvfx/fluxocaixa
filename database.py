"""
BoviML — Camada de persistência SQLite
Armazena classificações para retreinamento progressivo do modelo ML.
"""
import sqlite3, json, os

DB_PATH = os.path.join(os.path.dirname(__file__), 'boviml.db')


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_conn() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS registros (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                valores     TEXT    NOT NULL,
                class_ml    TEXT    NOT NULL,
                class_conf  TEXT,
                confianca   REAL    DEFAULT 0,
                fazenda     TEXT    DEFAULT '',
                municipio   TEXT    DEFAULT '',
                nat_pct     REAL    DEFAULT 75,
                created_at  TEXT    DEFAULT (datetime('now'))
            )
        ''')
        conn.commit()


def salvar(valores: list, class_ml: str, confianca: float,
           fazenda: str = '', municipio: str = '', nat_pct: float = 75.0) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            '''INSERT INTO registros
               (valores, class_ml, confianca, fazenda, municipio, nat_pct)
               VALUES (?,?,?,?,?,?)''',
            (json.dumps(valores), class_ml, round(confianca, 2),
             fazenda[:120], municipio[:120], nat_pct)
        )
        conn.commit()
        return cur.lastrowid


def confirmar(registro_id: int, class_conf: str):
    VALIDOS = {'CRIA', 'RECRIA', 'ENGORDA', 'CICLO_COMPLETO'}
    if class_conf not in VALIDOS:
        raise ValueError(f'Classificação inválida: {class_conf}')
    with get_conn() as conn:
        conn.execute(
            'UPDATE registros SET class_conf=? WHERE id=?',
            (class_conf, registro_id)
        )
        conn.commit()


def exportar_treino():
    """Retorna (X, y) com apenas registros confirmados pelo usuário."""
    TIPOS = ['CRIA', 'RECRIA', 'ENGORDA', 'CICLO_COMPLETO']
    with get_conn() as conn:
        rows = conn.execute(
            'SELECT valores, class_conf FROM registros WHERE class_conf IS NOT NULL'
        ).fetchall()
    X, y = [], []
    for r in rows:
        t = r['class_conf']
        if t in TIPOS:
            X.append(json.loads(r['valores']))
            y.append(TIPOS.index(t))
    return X, y


def listar(limit: int = 60) -> list:
    with get_conn() as conn:
        rows = conn.execute(
            '''SELECT id, valores, class_ml, class_conf, confianca,
                      fazenda, municipio, created_at
               FROM registros ORDER BY created_at DESC LIMIT ?''',
            (limit,)
        ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d['valores'] = json.loads(d['valores'])
        result.append(d)
    return result


def stats() -> dict:
    with get_conn() as conn:
        total = conn.execute('SELECT COUNT(*) FROM registros').fetchone()[0]
        conf  = conn.execute(
            'SELECT COUNT(*) FROM registros WHERE class_conf IS NOT NULL'
        ).fetchone()[0]
        por_tipo = conn.execute(
            '''SELECT class_conf, COUNT(*) n FROM registros
               WHERE class_conf IS NOT NULL GROUP BY class_conf'''
        ).fetchall()
    return {
        'total':      total,
        'confirmados': conf,
        'por_tipo':   {r['class_conf']: r['n'] for r in por_tipo},
    }
