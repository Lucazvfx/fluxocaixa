"""
BoviML — Camada de persistência
Usa PostgreSQL (via DATABASE_URL) em produção e SQLite localmente.
"""
import json, os

_DATABASE_URL = os.environ.get('DATABASE_URL', '')
_USE_PG = bool(_DATABASE_URL)

# ─────────────────────────────────────────────
# BACKENDS
# ─────────────────────────────────────────────
if _USE_PG:
    import psycopg2
    import psycopg2.extras

    def get_conn():
        conn = psycopg2.connect(_DATABASE_URL)
        return conn

    def _exec(sql, params=(), fetch=None, commit=False):
        conn = get_conn()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, params)
                result = None
                if fetch == 'one':
                    result = cur.fetchone()
                elif fetch == 'all':
                    result = cur.fetchall()
                elif fetch == 'lastrow':
                    cur.execute('SELECT lastval()')
                    result = cur.fetchone()['lastval']
                if commit:
                    conn.commit()
                return result
        finally:
            conn.close()

    _PH = '%s'           # placeholder PostgreSQL
    _AI = 'SERIAL PRIMARY KEY'
    _NOW = 'NOW()'

else:
    import sqlite3

    _DB_PATH = os.path.join(os.path.dirname(__file__), 'boviml.db')

    def get_conn():
        conn = sqlite3.connect(_DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    def _exec(sql, params=(), fetch=None, commit=False):
        with get_conn() as conn:
            cur = conn.execute(sql, params)
            result = None
            if fetch == 'one':
                row = cur.fetchone()
                result = dict(row) if row else None
            elif fetch == 'all':
                rows = cur.fetchall()
                result = [dict(r) for r in rows]
            elif fetch == 'lastrow':
                result = cur.lastrowid
            if commit:
                conn.commit()
            return result

    _PH = '?'
    _AI = 'INTEGER PRIMARY KEY AUTOINCREMENT'
    _NOW = "(datetime('now'))"


# ─────────────────────────────────────────────
# SCHEMA
# ─────────────────────────────────────────────
def init_db():
    sql = f'''
        CREATE TABLE IF NOT EXISTS registros (
            id          {_AI},
            valores     TEXT    NOT NULL,
            class_ml    TEXT    NOT NULL,
            class_conf  TEXT,
            confianca   REAL    DEFAULT 0,
            fazenda     TEXT    DEFAULT '',
            municipio   TEXT    DEFAULT '',
            nat_pct     REAL    DEFAULT 75,
            created_at  TIMESTAMP DEFAULT {_NOW}
        )
    '''
    _exec(sql, commit=True)


# ─────────────────────────────────────────────
# OPERAÇÕES
# ─────────────────────────────────────────────
def salvar(valores: list, class_ml: str, confianca: float,
           fazenda: str = '', municipio: str = '', nat_pct: float = 75.0) -> int:
    ph = _PH
    sql = f'''INSERT INTO registros
               (valores, class_ml, confianca, fazenda, municipio, nat_pct)
               VALUES ({ph},{ph},{ph},{ph},{ph},{ph})'''
    params = (json.dumps(valores), class_ml, round(confianca, 2),
              fazenda[:120], municipio[:120], nat_pct)
    rid = _exec(sql, params, fetch='lastrow', commit=True)
    return int(rid)


def confirmar(registro_id: int, class_conf: str):
    VALIDOS = {'CRIA', 'RECRIA', 'ENGORDA', 'CICLO_COMPLETO'}
    if class_conf not in VALIDOS:
        raise ValueError(f'Classificação inválida: {class_conf}')
    ph = _PH
    _exec(f'UPDATE registros SET class_conf={ph} WHERE id={ph}',
          (class_conf, registro_id), commit=True)


def exportar_treino():
    """Retorna (X, y) com apenas registros confirmados pelo usuário."""
    TIPOS = ['CRIA', 'RECRIA', 'ENGORDA', 'CICLO_COMPLETO']
    rows = _exec(
        'SELECT valores, class_conf FROM registros WHERE class_conf IS NOT NULL',
        fetch='all'
    ) or []
    X, y = [], []
    for r in rows:
        t = r['class_conf']
        if t in TIPOS:
            X.append(json.loads(r['valores']))
            y.append(TIPOS.index(t))
    return X, y


def listar(limit: int = 60) -> list:
    ph = _PH
    rows = _exec(
        f'''SELECT id, valores, class_ml, class_conf, confianca,
                   fazenda, municipio, created_at
            FROM registros ORDER BY created_at DESC LIMIT {ph}''',
        (limit,), fetch='all'
    ) or []
    result = []
    for r in rows:
        d = dict(r)
        d['valores'] = json.loads(d['valores'])
        d['created_at'] = str(d.get('created_at', ''))
        result.append(d)
    return result


def stats() -> dict:
    total = (_exec('SELECT COUNT(*) as n FROM registros', fetch='one') or {}).get('n', 0)
    conf  = (_exec(
        'SELECT COUNT(*) as n FROM registros WHERE class_conf IS NOT NULL',
        fetch='one'
    ) or {}).get('n', 0)
    rows = _exec(
        '''SELECT class_conf, COUNT(*) as n FROM registros
           WHERE class_conf IS NOT NULL GROUP BY class_conf''',
        fetch='all'
    ) or []
    return {
        'total':      int(total),
        'confirmados': int(conf),
        'por_tipo':   {r['class_conf']: r['n'] for r in rows},
    }
