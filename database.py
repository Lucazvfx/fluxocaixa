"""
BoviML — Camada de persistência
Usa PostgreSQL (via DATABASE_URL) em produção e SQLite localmente.
"""
import json, os
from werkzeug.security import generate_password_hash, check_password_hash

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

    _PH  = '%s'
    _AI  = 'SERIAL PRIMARY KEY'
    _NOW = 'NOW()'
    _ADD_COL = 'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {tipo}'

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

    _PH  = '?'
    _AI  = 'INTEGER PRIMARY KEY AUTOINCREMENT'
    _NOW = "(datetime('now'))"
    _ADD_COL = None   # handled via try/except no SQLite


def _add_column_safe(table, col, tipo):
    """Adiciona coluna ignorando erro se já existir (SQLite não suporta IF NOT EXISTS)."""
    if _USE_PG:
        _exec(_ADD_COL.format(table=table, col=col, tipo=tipo), commit=True)
    else:
        try:
            _exec(f'ALTER TABLE {table} ADD COLUMN {col} {tipo}', commit=True)
        except Exception:
            pass


# ─────────────────────────────────────────────
# SCHEMA
# ─────────────────────────────────────────────
def init_db():
    # Usuários
    _exec(f'''
        CREATE TABLE IF NOT EXISTS usuarios (
            id         {_AI},
            email      TEXT NOT NULL UNIQUE,
            nome       TEXT NOT NULL,
            senha_hash TEXT NOT NULL,
            plano      TEXT DEFAULT 'free',
            created_at TIMESTAMP DEFAULT {_NOW}
        )
    ''', commit=True)

    # Fazendas
    _exec(f'''
        CREATE TABLE IF NOT EXISTS fazendas (
            id         {_AI},
            user_id    INTEGER NOT NULL,
            nome       TEXT NOT NULL,
            proprietario TEXT DEFAULT '',
            municipio  TEXT DEFAULT '',
            estado     TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT {_NOW}
        )
    ''', commit=True)

    # Classificações
    _exec(f'''
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
    ''', commit=True)

    # Colunas adicionadas na feature/auth (retrocompat)
    _add_column_safe('registros', 'user_id',    'INTEGER')
    _add_column_safe('registros', 'fazenda_id', 'INTEGER')


# ─────────────────────────────────────────────
# USUÁRIOS
# ─────────────────────────────────────────────
def criar_usuario(email: str, nome: str, senha: str) -> int:
    ph = _PH
    rid = _exec(
        f'INSERT INTO usuarios (email, nome, senha_hash) VALUES ({ph},{ph},{ph})',
        (email.lower().strip(), nome.strip(), generate_password_hash(senha)),
        fetch='lastrow', commit=True
    )
    return int(rid)


def buscar_usuario_email(email: str) -> dict | None:
    ph = _PH
    return _exec(
        f'SELECT * FROM usuarios WHERE email={ph}',
        (email.lower().strip(),), fetch='one'
    )


def buscar_usuario_id(user_id: int) -> dict | None:
    ph = _PH
    return _exec(
        f'SELECT * FROM usuarios WHERE id={ph}',
        (user_id,), fetch='one'
    )


def verificar_senha(email: str, senha: str) -> dict | None:
    u = buscar_usuario_email(email)
    if u and check_password_hash(u['senha_hash'], senha):
        return u
    return None


# ─────────────────────────────────────────────
# FAZENDAS
# ─────────────────────────────────────────────
def criar_fazenda(user_id: int, nome: str, proprietario: str = '',
                  municipio: str = '', estado: str = '') -> int:
    ph = _PH
    rid = _exec(
        f'''INSERT INTO fazendas (user_id, nome, proprietario, municipio, estado)
            VALUES ({ph},{ph},{ph},{ph},{ph})''',
        (user_id, nome.strip()[:120], proprietario.strip()[:120],
         municipio.strip()[:80], estado.strip()[:40]),
        fetch='lastrow', commit=True
    )
    return int(rid)


def listar_fazendas(user_id: int) -> list:
    ph = _PH
    rows = _exec(
        f'''SELECT f.id, f.nome, f.proprietario, f.municipio, f.estado,
                   f.created_at,
                   COUNT(r.id) as total_analises,
                   MAX(r.created_at) as ultima_analise
            FROM fazendas f
            LEFT JOIN registros r ON r.fazenda_id = f.id
            WHERE f.user_id = {ph}
            GROUP BY f.id, f.nome, f.proprietario, f.municipio, f.estado, f.created_at
            ORDER BY ultima_analise DESC NULLS LAST, f.created_at DESC''',
        (user_id,), fetch='all'
    ) or []
    result = []
    for r in rows:
        d = dict(r)
        d['created_at'] = str(d.get('created_at', ''))
        d['ultima_analise'] = str(d.get('ultima_analise', '') or '')
        result.append(d)
    return result


def buscar_fazenda(fazenda_id: int, user_id: int) -> dict | None:
    ph = _PH
    return _exec(
        f'SELECT * FROM fazendas WHERE id={ph} AND user_id={ph}',
        (fazenda_id, user_id), fetch='one'
    )


def historico_fazenda(fazenda_id: int, user_id: int, limit: int = 30) -> list:
    ph = _PH
    rows = _exec(
        f'''SELECT r.id, r.valores, r.class_ml, r.class_conf, r.confianca,
                   r.nat_pct, r.created_at
            FROM registros r
            JOIN fazendas f ON f.id = r.fazenda_id
            WHERE r.fazenda_id={ph} AND f.user_id={ph}
            ORDER BY r.created_at DESC LIMIT {ph}''',
        (fazenda_id, user_id, limit), fetch='all'
    ) or []
    result = []
    for r in rows:
        d = dict(r)
        d['valores'] = json.loads(d['valores'])
        d['created_at'] = str(d.get('created_at', ''))
        result.append(d)
    return result


# ─────────────────────────────────────────────
# CLASSIFICAÇÕES
# ─────────────────────────────────────────────
def salvar(valores: list, class_ml: str, confianca: float,
           fazenda: str = '', municipio: str = '', nat_pct: float = 75.0,
           user_id: int = None, fazenda_id: int = None) -> int:
    ph = _PH
    sql = f'''INSERT INTO registros
               (valores, class_ml, confianca, fazenda, municipio, nat_pct, user_id, fazenda_id)
               VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})'''
    params = (json.dumps(valores), class_ml, round(confianca, 2),
              fazenda[:120], municipio[:120], nat_pct, user_id, fazenda_id)
    rid = _exec(sql, params, fetch='lastrow', commit=True)
    return int(rid)


def confirmar(registro_id: int, class_conf: str):
    VALIDOS = {'CRIA', 'RECRIA', 'ENGORDA', 'CICLO_COMPLETO'}
    if class_conf not in VALIDOS:
        raise ValueError(f'Classificacao invalida: {class_conf}')
    ph = _PH
    _exec(f'UPDATE registros SET class_conf={ph} WHERE id={ph}',
          (class_conf, registro_id), commit=True)


def exportar_treino():
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


def listar(limit: int = 60, user_id: int = None) -> list:
    ph = _PH
    if user_id:
        rows = _exec(
            f'''SELECT id, valores, class_ml, class_conf, confianca,
                       fazenda, municipio, created_at
                FROM registros WHERE user_id={ph}
                ORDER BY created_at DESC LIMIT {ph}''',
            (user_id, limit), fetch='all'
        ) or []
    else:
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


def stats(user_id: int = None) -> dict:
    ph = _PH
    where = f'WHERE user_id={ph}' if user_id else ''
    params = (user_id,) if user_id else ()
    total = (_exec(f'SELECT COUNT(*) as n FROM registros {where}',
                   params, fetch='one') or {}).get('n', 0)
    conf_where = f'WHERE user_id={ph} AND class_conf IS NOT NULL' if user_id else 'WHERE class_conf IS NOT NULL'
    conf = (_exec(f'SELECT COUNT(*) as n FROM registros {conf_where}',
                  params, fetch='one') or {}).get('n', 0)
    rows = _exec(
        f'''SELECT class_conf, COUNT(*) as n FROM registros
            {'WHERE user_id='+ph+' AND' if user_id else 'WHERE'} class_conf IS NOT NULL
            GROUP BY class_conf''',
        params, fetch='all'
    ) or []
    return {
        'total':       int(total),
        'confirmados': int(conf),
        'por_tipo':    {r['class_conf']: r['n'] for r in rows},
    }
