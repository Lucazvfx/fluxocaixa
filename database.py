"""
Fluxo de Gestão — Camada de persistência
Usa PostgreSQL (via DATABASE_URL) em produção e SQLite localmente.
"""
import json, os
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from contextlib import contextmanager

_DATABASE_URL = os.environ.get('DATABASE_URL', '')
_USE_PG = bool(_DATABASE_URL)

# ─────────────────────────────────────────────
# BACKENDS
# ─────────────────────────────────────────────
if _USE_PG:
    import psycopg2
    import psycopg2.extras

    @contextmanager
    def get_conn():
        conn = psycopg2.connect(_DATABASE_URL)
        try:
            yield conn
        finally:
            conn.close()

    def _exec(sql, params=(), fetch=None, commit=False):
        with get_conn() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(sql, params)
                result = None
                if fetch == 'one':
                    row = cur.fetchone()
                    result = dict(row) if row else None
                elif fetch == 'all':
                    rows = cur.fetchall()
                    result = [dict(r) for r in rows]
                elif fetch == 'lastrow':
                    cur.execute('SELECT lastval()')
                    result = cur.fetchone()['lastval']
                if commit:
                    conn.commit()
                return result

    _PH  = '%s'
    _AI  = 'SERIAL PRIMARY KEY'
    _NOW = 'NOW()'
    _ADD_COL = 'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {tipo}'

else:
    import sqlite3

    _DB_PATH = os.path.join(os.path.dirname(__file__), 'gestao.db')

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

    # Nova Tabela: Histórico de Cotações da Arroba (Agora com Boi China)
    _exec(f'''
        CREATE TABLE IF NOT EXISTS cotacao_arroba (
            id           {_AI},
            data_cotacao DATE UNIQUE,
            preco_boi    REAL,
            preco_vaca   REAL,
            preco_boi_china REAL
        )
    ''', commit=True)

    # Colunas adicionadas de forma segura (retrocompatibilidade)
    _add_column_safe('registros', 'user_id',    'INTEGER')
    _add_column_safe('registros', 'fazenda_id', 'INTEGER')
    _add_column_safe('cotacao_arroba', 'preco_boi_china', 'REAL')
    _add_column_safe('usuarios', 'security_question', 'TEXT DEFAULT \'\'')
    _add_column_safe('usuarios', 'security_answer_hash', 'TEXT DEFAULT \'\'')


# ─────────────────────────────────────────────
# USUÁRIOS
# ─────────────────────────────────────────────
def criar_usuario(email: str, nome: str, senha: str,
                  security_question: str = '', security_answer: str = '') -> int:
    ph = _PH
    rid = _exec(
        f'INSERT INTO usuarios (email, nome, senha_hash, security_question, security_answer_hash) VALUES ({ph},{ph},{ph},{ph},{ph})',
        (email.lower().strip(), nome.strip(), generate_password_hash(senha),
         security_question, generate_password_hash(security_answer.lower().strip()) if security_answer else ''),
        fetch='lastrow', commit=True
    )
    return int(rid)

def resetar_senha(email: str, nova_senha: str):
    ph = _PH
    _exec(f'UPDATE usuarios SET senha_hash={ph} WHERE email={ph}',
          (generate_password_hash(nova_senha), email.lower().strip()), commit=True)

def verificar_resposta_seguranca(email: str, resposta: str) -> bool:
    u = buscar_usuario_email(email)
    if not u or not u.get('security_answer_hash'):
        return False
    return check_password_hash(u['security_answer_hash'], resposta.lower().strip())

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
def criar_fazenda(nome: str, proprietario: str = '',
                  municipio: str = '', estado: str = '', user_id: int = None) -> int:
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

def buscar_fazenda(fazenda_id: int, user_id: int = None) -> dict | None:
    ph = _PH
    sql = f'SELECT * FROM fazendas WHERE id={ph}'
    params = [fazenda_id]
    if user_id is not None:
        sql += f' AND user_id={ph}'
        params.append(user_id)
    return _exec(sql, tuple(params), fetch='one')

def historico_fazenda(fazenda_id: int, user_id: int = None, limit: int = 30) -> list:
    ph = _PH
    sql = f'''SELECT r.id, r.valores, r.class_ml, r.class_conf, r.confianca,
                   r.nat_pct, r.created_at
            FROM registros r
            WHERE r.fazenda_id={ph}'''
    params = [fazenda_id]
    if user_id is not None:
        sql += f' AND r.user_id={ph}'
        params.append(user_id)
    
    sql += f' ORDER BY r.created_at DESC LIMIT {ph}'
    params.append(limit)
    
    rows = _exec(sql, tuple(params), fetch='all') or []
    result = []
    for r in rows:
        d = dict(r)
        d['valores'] = json.loads(d['valores'])
        d['created_at'] = str(d.get('created_at', ''))
        result.append(d)
    return result

def excluir_registro(registro_id: int, user_id: int) -> bool:
    ph = _PH
    _exec(f'DELETE FROM registros WHERE id={ph} AND user_id={ph}',
          (registro_id, user_id), commit=True)
    return True

def excluir_fazenda(fazenda_id: int, user_id: int) -> bool:
    ph = _PH
    # Primeiro apaga registros vinculados para limpar histórico
    _exec(f'DELETE FROM registros WHERE fazenda_id={ph} AND user_id={ph}',
          (fazenda_id, user_id), commit=True)
    _exec(f'DELETE FROM fazendas WHERE id={ph} AND user_id={ph}',
          (fazenda_id, user_id), commit=True)
    return True


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
    sql = 'SELECT id, valores, class_ml, class_conf, confianca, fazenda, municipio, created_at FROM registros'
    params = []
    if user_id is not None:
        sql += f' WHERE user_id={ph}'
        params.append(user_id)
    
    sql += f' ORDER BY created_at DESC LIMIT {ph}'
    params.append(limit)
    
    rows = _exec(sql, tuple(params), fetch='all') or []
    result = []
    for r in rows:
        d = dict(r)
        d['valores'] = json.loads(d['valores'])
        d['created_at'] = str(d.get('created_at', ''))
        result.append(d)
    return result

def stats(user_id: int = None) -> dict:
    ph = _PH
    sql_tot = 'SELECT COUNT(*) as n FROM registros'
    sql_conf = 'SELECT COUNT(*) as n FROM registros WHERE class_conf IS NOT NULL'
    sql_tipo = 'SELECT class_conf, COUNT(*) as n FROM registros WHERE class_conf IS NOT NULL GROUP BY class_conf'
    
    params = []
    if user_id is not None:
        sql_tot += f' WHERE user_id={ph}'
        sql_conf += f' AND user_id={ph}'
        sql_tipo = sql_tipo.replace('GROUP BY', f' AND user_id={ph} GROUP BY')
        params.append(user_id)
        
    total = (_exec(sql_tot, tuple(params), fetch='one') or {}).get('n', 0)
    conf = (_exec(sql_conf, tuple(params), fetch='one') or {}).get('n', 0)
    rows = _exec(sql_tipo, tuple(params), fetch='all') or []
    
    return {
        'total':       int(total),
        'confirmados': int(conf),
        'por_tipo':    {r['class_conf']: r['n'] for r in rows},
    }

# ─────────────────────────────────────────────
# COTAÇÕES DA ARROBA (FINANÇAS)
# ─────────────────────────────────────────────
def guardar_cotacao_diaria(precos: dict):
    """
    Insere ou atualiza o preço da arroba para a data atual.
    Compatível com PostgreSQL e SQLite através da função abstrata _exec.
    """
    hoje = datetime.now().strftime('%Y-%m-%d')
    ph = _PH
    boi = float(precos.get('boi', 0.0))
    vaca = float(precos.get('vaca', 0.0))
    china = float(precos.get('boi_china', 0.0))

    # Verifica se já existe um registro para o dia de hoje
    existente = _exec(f'SELECT id FROM cotacao_arroba WHERE data_cotacao={ph}', (hoje,), fetch='one')

    if existente:
        # Se existir, atualiza (Evita erros de constraint UNIQUE na data)
        _exec(f'''UPDATE cotacao_arroba 
                  SET preco_boi={ph}, preco_vaca={ph}, preco_boi_china={ph}
                  WHERE id={ph}''', 
              (boi, vaca, china, existente['id']), commit=True)
    else:
        # Se não existir, insere um novo registro histórico
        _exec(f'''INSERT INTO cotacao_arroba (data_cotacao, preco_boi, preco_vaca, preco_boi_china) 
                  VALUES ({ph}, {ph}, {ph}, {ph})''', 
              (hoje, boi, vaca, china), commit=True)

def obter_cotacoes_atuais() -> dict:
    """
    Busca o preço mais recente no banco de dados.
    Retorna dicionário {'boi': valor, 'vaca': valor, 'boi_china': valor}
    """
    try:
        resultado = _exec('SELECT preco_boi, preco_vaca, preco_boi_china FROM cotacao_arroba ORDER BY data_cotacao DESC LIMIT 1', fetch='one')
        if resultado:
            return {
                'boi': float(resultado['preco_boi'] or 0.0), 
                'vaca': float(resultado['preco_vaca'] or 0.0),
                'boi_china': float(resultado.get('preco_boi_china') or 0.0)
            }
    except Exception as e:
        print(f"[Erro DB Cotação]: {e}")
        
    # Preços de segurança (fallback) caso o banco esteja vazio
    return {'boi': 0.0, 'vaca': 0.0, 'boi_china': 0.0}