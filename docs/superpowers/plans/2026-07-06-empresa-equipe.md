# Empresa/Equipe Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduzir "empresa" como fronteira de compartilhamento de fazendas/
pareceres entre vários usuários (N:N, com "empresa ativa" na sessão),
substituindo o isolamento atual por `user_id`, sem quebrar dados existentes.

**Architecture:** Duas tabelas novas (`empresas`, `empresa_membros`) e uma
coluna nova (`fazendas.empresa_id`) em `database.py`. Toda função de
fazenda/parecer que hoje recebe `user_id` para controle de acesso passa a
receber `empresa_id`. `app.py` resolve a "empresa ativa" da sessão Flask
(assinada, não forjável) uma vez por request via helper, e a usa em vez de
`current_user.id` nos endpoints afetados. Migração idempotente no boot cobre
usuários pré-existentes; novos usuários ganham empresa pessoal na hora do
cadastro.

**Tech Stack:** Flask (`session`), SQLite/Postgres via `database.py` (padrão
`_exec`/`_PH`/`_AI`/`_NOW`/`_add_column_safe` já estabelecido), pytest.

---

## Fase A — Schema, migração e funções de empresa (`database.py`)

### Task A1: Tabelas `empresas`/`empresa_membros` + coluna `fazendas.empresa_id`

**Files:**
- Modify: `database.py` (dentro de `init_db()`, após o bloco de `pareceres`)
- Test: `tests/test_empresas_schema.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_empresas_schema.py
import database as db

def test_tabelas_empresa_existem_apos_init_db():
    db.init_db()
    # Deve aceitar insert/select sem erro de "no such table"
    eid = db._exec(f"INSERT INTO empresas (nome) VALUES ({db._PH})",
                   ('Teste Schema',), fetch='lastrow', commit=True)
    assert eid
    db._exec(f"INSERT INTO empresa_membros (empresa_id, user_id) VALUES ({db._PH},{db._PH})",
             (eid, 1), commit=True)
    row = db._exec(f"SELECT empresa_id, user_id FROM empresa_membros WHERE empresa_id={db._PH}",
                   (eid,), fetch='one')
    assert row['empresa_id'] == eid

def test_fazendas_tem_coluna_empresa_id():
    db.init_db()
    # Não deve lançar erro de coluna inexistente
    db._exec(f"SELECT empresa_id FROM fazendas LIMIT 1", fetch='all')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_empresas_schema.py -v`
Expected: FAIL (`no such table: empresas` / `no such column: empresa_id`)

- [ ] **Step 3: Implementação — editar `database.py`**

No `init_db()`, logo após o bloco `CREATE TABLE IF NOT EXISTS pareceres (...)`
(antes do bloco de `_add_column_safe`), adicionar:

```python
    # Empresas (consultorias) e vínculo N:N com usuários
    _exec(f'''
        CREATE TABLE IF NOT EXISTS empresas (
            id          {_AI},
            nome        TEXT NOT NULL,
            logo_base64 TEXT DEFAULT '',
            created_at  TIMESTAMP DEFAULT {_NOW}
        )
    ''', commit=True)

    _exec(f'''
        CREATE TABLE IF NOT EXISTS empresa_membros (
            id          {_AI},
            empresa_id  INTEGER NOT NULL,
            user_id     INTEGER NOT NULL,
            created_at  TIMESTAMP DEFAULT {_NOW}
        )
    ''', commit=True)
```

Na lista de `_add_column_safe(...)` já existente (perto de
`_add_column_safe('usuarios', 'logo_base64', ...)`), adicionar:

```python
    _add_column_safe('fazendas', 'empresa_id', 'INTEGER')
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_empresas_schema.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add database.py tests/test_empresas_schema.py
git commit -m "feat: schema de empresas (tabelas + fazendas.empresa_id)"
```

### Task A2: `criar_usuario` cria empresa pessoal automaticamente

**Files:**
- Modify: `database.py:211-220` (função `criar_usuario`)
- Test: `tests/test_empresas_signup.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_empresas_signup.py
import database as db

def test_criar_usuario_ganha_empresa_pessoal():
    db.init_db()
    uid = db.criar_usuario('novosignup@example.com', 'Novo Usuario', 'senha123')
    empresas = db.empresas_do_usuario(uid)
    assert len(empresas) == 1
    assert 'Novo Usuario' in empresas[0]['nome']
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_empresas_signup.py -v`
Expected: FAIL (`AttributeError: module 'database' has no attribute 'empresas_do_usuario'`)

- [ ] **Step 3: Implementação — editar `database.py`**

Função atual (linhas 211-220):

```python
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
```

Substituir por (cria a empresa pessoal logo após o insert do usuário):

```python
def criar_usuario(email: str, nome: str, senha: str,
                  security_question: str = '', security_answer: str = '') -> int:
    ph = _PH
    nome = nome.strip()
    rid = _exec(
        f'INSERT INTO usuarios (email, nome, senha_hash, security_question, security_answer_hash) VALUES ({ph},{ph},{ph},{ph},{ph})',
        (email.lower().strip(), nome, generate_password_hash(senha),
         security_question, generate_password_hash(security_answer.lower().strip()) if security_answer else ''),
        fetch='lastrow', commit=True
    )
    uid = int(rid)
    eid = _exec(f'INSERT INTO empresas (nome) VALUES ({ph})',
                (f'{nome} — Consultoria',), fetch='lastrow', commit=True)
    _exec(f'INSERT INTO empresa_membros (empresa_id, user_id) VALUES ({ph},{ph})',
          (eid, uid), commit=True)
    return uid
```

Adicionar as funções de empresa (podem ficar logo depois de `criar_usuario`,
antes de `resetar_senha`):

```python
def empresas_do_usuario(user_id: int) -> list:
    """Empresas às quais o usuário pertence."""
    ph = _PH
    return _exec(f'''SELECT e.id, e.nome, e.logo_base64 FROM empresas e
                     JOIN empresa_membros m ON m.empresa_id = e.id
                     WHERE m.user_id={ph} ORDER BY e.nome''', (user_id,), fetch='all') or []


def usuario_pertence_a_empresa(user_id: int, empresa_id: int) -> bool:
    ph = _PH
    r = _exec(f'SELECT 1 FROM empresa_membros WHERE user_id={ph} AND empresa_id={ph}',
              (user_id, empresa_id), fetch='one')
    return bool(r)


def buscar_empresa(empresa_id: int) -> dict | None:
    ph = _PH
    return _exec(f'SELECT * FROM empresas WHERE id={ph}', (empresa_id,), fetch='one')


def atualizar_perfil_empresa(empresa_id: int, nome: str, logo_base64: str):
    ph = _PH
    _exec(f'UPDATE empresas SET nome={ph}, logo_base64={ph} WHERE id={ph}',
          ((nome or '').strip()[:120], logo_base64 or '', empresa_id), commit=True)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_empresas_signup.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add database.py tests/test_empresas_signup.py
git commit -m "feat: criar_usuario cria empresa pessoal; funções de empresa"
```

### Task A3: Migração idempotente de usuários pré-existentes

**Files:**
- Modify: `database.py` (fim de `init_db()`)
- Test: `tests/test_empresas_migracao.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_empresas_migracao.py
import database as db

def test_migracao_cria_empresa_para_usuario_pre_existente():
    db.init_db()
    ph = db._PH
    # Simula um usuário "antigo": insert direto, sem passar por criar_usuario
    # (que já cria empresa) para reproduzir o estado pré-feature.
    uid = db._exec(
        f'INSERT INTO usuarios (email, nome, senha_hash) VALUES ({ph},{ph},{ph})',
        ('usuarioantigo@example.com', 'Usuario Antigo', 'hash-fake'),
        fetch='lastrow', commit=True)
    assert not db.empresas_do_usuario(uid)  # ainda sem empresa

    db._migrar_usuarios_para_empresas()

    empresas = db.empresas_do_usuario(uid)
    assert len(empresas) == 1

def test_migracao_e_idempotente():
    db.init_db()
    ph = db._PH
    uid = db._exec(
        f'INSERT INTO usuarios (email, nome, senha_hash) VALUES ({ph},{ph},{ph})',
        ('usuarioidempotente@example.com', 'Idempotente', 'hash-fake'),
        fetch='lastrow', commit=True)
    db._migrar_usuarios_para_empresas()
    db._migrar_usuarios_para_empresas()  # roda de novo
    assert len(db.empresas_do_usuario(uid)) == 1  # não duplicou

def test_migracao_herda_marca_e_realoca_fazendas():
    db.init_db()
    ph = db._PH
    uid = db._exec(
        f'''INSERT INTO usuarios (email, nome, senha_hash, nome_consultoria, logo_base64)
            VALUES ({ph},{ph},{ph},{ph},{ph})''',
        ('usuariomarca@example.com', 'Com Marca', 'hash-fake', 'Marca XYZ', 'YWJj'),
        fetch='lastrow', commit=True)
    fid = db._exec(
        f'INSERT INTO fazendas (user_id, nome) VALUES ({ph},{ph})',
        (uid, 'Fazenda Antiga'), fetch='lastrow', commit=True)

    db._migrar_usuarios_para_empresas()

    empresas = db.empresas_do_usuario(uid)
    assert empresas[0]['nome'] == 'Marca XYZ'
    assert empresas[0]['logo_base64'] == 'YWJj'
    f = db._exec(f'SELECT empresa_id FROM fazendas WHERE id={ph}', (fid,), fetch='one')
    assert f['empresa_id'] == empresas[0]['id']
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_empresas_migracao.py -v`
Expected: FAIL (`AttributeError: module 'database' has no attribute '_migrar_usuarios_para_empresas'`)

- [ ] **Step 3: Implementação — editar `database.py`**

Adicionar a função (pode ficar logo antes de `init_db()`, ou logo depois —
desde que definida no módulo antes de ser chamada dentro de `init_db()`):

```python
def _migrar_usuarios_para_empresas():
    """Garante que todo usuário tenha ao menos uma empresa (idempotente).

    Usuários criados após esta feature já ganham empresa em criar_usuario();
    esta função cobre só quem foi criado antes dela existir.
    """
    ph = _PH
    usuarios_sem_empresa = _exec('''
        SELECT u.id, u.nome, u.nome_consultoria, u.logo_base64 FROM usuarios u
        WHERE NOT EXISTS (SELECT 1 FROM empresa_membros m WHERE m.user_id = u.id)
    ''', fetch='all') or []
    for u in usuarios_sem_empresa:
        nome_empresa = (u.get('nome_consultoria') or '').strip() or f"{u['nome']} — Consultoria"
        eid = _exec(f'INSERT INTO empresas (nome, logo_base64) VALUES ({ph},{ph})',
                    (nome_empresa, u.get('logo_base64') or ''), fetch='lastrow', commit=True)
        _exec(f'INSERT INTO empresa_membros (empresa_id, user_id) VALUES ({ph},{ph})',
              (eid, u['id']), commit=True)
        _exec(f'UPDATE fazendas SET empresa_id={ph} WHERE user_id={ph} AND empresa_id IS NULL',
              (eid, u['id']), commit=True)
```

Ao final de `init_db()` (depois do último `_add_column_safe`), adicionar a
chamada:

```python
    _migrar_usuarios_para_empresas()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_empresas_migracao.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add database.py tests/test_empresas_migracao.py
git commit -m "feat: migração idempotente de usuários pré-existentes para empresas"
```

### Task A4: Funções de fazenda/parecer passam a operar por `empresa_id`

**Files:**
- Modify: `database.py:271-377` (`criar_fazenda`, `listar_fazendas`,
  `buscar_fazenda`, `historico_fazenda`, `listar_pareceres`, `excluir_fazenda`)
- Test: `tests/test_fazendas_empresa_compartilhada.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_fazendas_empresa_compartilhada.py
import database as db

def _empresa_de(email, nome):
    u = db.buscar_usuario_email(email)
    uid = u['id'] if u else db.criar_usuario(email, nome, 'senha123')
    empresas = db.empresas_do_usuario(uid)
    return uid, empresas[0]['id']

def test_dois_usuarios_mesma_empresa_compartilham_fazenda():
    db.init_db()
    uid_a, eid = _empresa_de('analista.a@example.com', 'Analista A')
    uid_b, _ = _empresa_de('analista.b@example.com', 'Analista B')
    # Vincula B na mesma empresa de A (simula admin vinculando)
    ph = db._PH
    db._exec(f'INSERT INTO empresa_membros (empresa_id, user_id) VALUES ({ph},{ph})',
             (eid, uid_b), commit=True)

    fid = db.criar_fazenda('Fazenda Compartilhada', empresa_id=eid, criado_por=uid_a)

    # B vê a fazenda de A porque estão na mesma empresa
    fazendas_de_b = db.listar_fazendas(eid)
    assert any(f['id'] == fid for f in fazendas_de_b)
    assert db.buscar_fazenda(fid, eid) is not None

def test_empresa_diferente_nao_ve_a_fazenda():
    db.init_db()
    uid_a, eid_a = _empresa_de('isolado.a@example.com', 'Isolado A')
    uid_c, eid_c = _empresa_de('isolado.c@example.com', 'Isolado C')
    fid = db.criar_fazenda('Fazenda Isolada A', empresa_id=eid_a, criado_por=uid_a)

    assert db.buscar_fazenda(fid, eid_c) is None
    assert not any(f['id'] == fid for f in db.listar_fazendas(eid_c))

def test_historico_e_pareceres_sem_filtro_de_usuario():
    db.init_db()
    uid_a, eid = _empresa_de('historico.a@example.com', 'Historico A')
    fid = db.criar_fazenda('Fazenda Historico', empresa_id=eid, criado_por=uid_a)
    db.salvar_parecer(uid_a, fid, {'credito_valor': 1000},
                      {'conclusao': {'recomendacao': 'aprovar', 'dscr': 2.0}})
    # historico_fazenda/listar_pareceres não recebem mais user_id
    hist = db.historico_fazenda(fid)
    pareceres = db.listar_pareceres(fid)
    assert isinstance(hist, list)
    assert len(pareceres) == 1

def test_excluir_fazenda_exige_empresa_correta():
    db.init_db()
    uid_a, eid_a = _empresa_de('excluir.a@example.com', 'Excluir A')
    _, eid_c = _empresa_de('excluir.c@example.com', 'Excluir C')
    fid = db.criar_fazenda('Fazenda a Excluir', empresa_id=eid_a, criado_por=uid_a)

    assert db.excluir_fazenda(fid, eid_c) is False  # empresa errada não apaga
    assert db.buscar_fazenda(fid, eid_a) is not None  # continua existindo
    assert db.excluir_fazenda(fid, eid_a) is True
    assert db.buscar_fazenda(fid, eid_a) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_fazendas_empresa_compartilhada.py -v`
Expected: FAIL (`criar_fazenda() got an unexpected keyword argument 'empresa_id'`)

- [ ] **Step 3: Implementação — editar `database.py`**

Função `criar_fazenda` (linhas 271-280) — de:

```python
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
```

para:

```python
def criar_fazenda(nome: str, proprietario: str = '', municipio: str = '',
                  estado: str = '', empresa_id: int = None, criado_por: int = None) -> int:
    ph = _PH
    rid = _exec(
        f'''INSERT INTO fazendas (user_id, empresa_id, nome, proprietario, municipio, estado)
            VALUES ({ph},{ph},{ph},{ph},{ph},{ph})''',
        (criado_por, empresa_id, nome.strip()[:120], proprietario.strip()[:120],
         municipio.strip()[:80], estado.strip()[:40]),
        fetch='lastrow', commit=True
    )
    return int(rid)
```

Função `listar_fazendas` — trocar o parâmetro e o `WHERE`:

```python
def listar_fazendas(empresa_id: int) -> list:
    ph = _PH
    rows = _exec(
        f'''SELECT f.id, f.nome, f.proprietario, f.municipio, f.estado,
                   f.created_at,
                   COUNT(r.id) as total_analises,
                   MAX(r.created_at) as ultima_analise
            FROM fazendas f
            LEFT JOIN registros r ON r.fazenda_id = f.id
            WHERE f.empresa_id = {ph}
            GROUP BY f.id, f.nome, f.proprietario, f.municipio, f.estado, f.created_at
            ORDER BY ultima_analise DESC NULLS LAST, f.created_at DESC''',
        (empresa_id,), fetch='all'
    ) or []
    result = []
    for r in rows:
        d = dict(r)
        d['created_at'] = str(d.get('created_at', ''))
        d['ultima_analise'] = str(d.get('ultima_analise', '') or '')
        result.append(d)
    return result
```

Função `buscar_fazenda` — trocar `user_id` por `empresa_id`:

```python
def buscar_fazenda(fazenda_id: int, empresa_id: int = None) -> dict | None:
    ph = _PH
    sql = f'SELECT * FROM fazendas WHERE id={ph}'
    params = [fazenda_id]
    if empresa_id is not None:
        sql += f' AND empresa_id={ph}'
        params.append(empresa_id)
    return _exec(sql, tuple(params), fetch='one')
```

Função `historico_fazenda` — remover o parâmetro `user_id` e o filtro:

```python
def historico_fazenda(fazenda_id: int, limit: int = 30) -> list:
    ph = _PH
    rows = _exec(
        f'''SELECT r.id, r.valores, r.class_ml, r.class_conf, r.confianca,
                   r.nat_pct, r.created_at
            FROM registros r
            WHERE r.fazenda_id={ph}
            ORDER BY r.created_at DESC LIMIT {ph}''',
        (fazenda_id, limit), fetch='all'
    ) or []
    result = []
    for r in rows:
        d = dict(r)
        d['valores'] = json.loads(d['valores'])
        d['created_at'] = str(d.get('created_at', ''))
        result.append(d)
    return result
```

Função `listar_pareceres` — remover o parâmetro `user_id` e o filtro:

```python
def listar_pareceres(fazenda_id: int, limit: int = 30) -> list:
    ph = _PH
    rows = _exec(
        f'''SELECT id, solicitacao, parecer, recomendacao, dscr, created_at
            FROM pareceres WHERE fazenda_id={ph}
            ORDER BY created_at DESC, id DESC LIMIT {ph}''',
        (fazenda_id, limit), fetch='all'
    ) or []
    for r in rows:
        r['created_at'] = str(r.get('created_at', ''))
    return rows
```

Função `excluir_fazenda` — de:

```python
def excluir_fazenda(fazenda_id: int, user_id: int) -> bool:
    ph = _PH
    # Primeiro apaga registros vinculados para limpar histórico
    _exec(f'DELETE FROM registros WHERE fazenda_id={ph} AND user_id={ph}',
          (fazenda_id, user_id), commit=True)
    _exec(f'DELETE FROM fazendas WHERE id={ph} AND user_id={ph}',
          (fazenda_id, user_id), commit=True)
    return True
```

para (valida a empresa antes de apagar; também limpa `pareceres` órfãos, que
antes não eram limpos):

```python
def excluir_fazenda(fazenda_id: int, empresa_id: int) -> bool:
    ph = _PH
    if not buscar_fazenda(fazenda_id, empresa_id):
        return False
    _exec(f'DELETE FROM registros WHERE fazenda_id={ph}', (fazenda_id,), commit=True)
    _exec(f'DELETE FROM pareceres WHERE fazenda_id={ph}', (fazenda_id,), commit=True)
    _exec(f'DELETE FROM fazendas WHERE id={ph} AND empresa_id={ph}',
          (fazenda_id, empresa_id), commit=True)
    return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_fazendas_empresa_compartilhada.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add database.py tests/test_fazendas_empresa_compartilhada.py
git commit -m "feat: fazendas/pareceres/historico operam por empresa_id"
```

---

## Fase B — Empresa ativa e endpoints (`app.py`)

### Task B1: Helpers de empresa ativa + `GET/POST /api/empresa/ativa`

**Files:**
- Modify: `app.py:13` (import), próximo aos outros helpers de auth (perto de
  `is_admin`/`admin_required`, por volta da linha 82)
- Test: `tests/test_empresa_ativa.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_empresa_ativa.py
import database as db
from app import app


def _login_client(email):
    db.init_db()
    u = db.buscar_usuario_email(email)
    if not u:
        db.criar_usuario(email, 'Empresa Ativa Test', 'senha123')
        u = db.buscar_usuario_email(email)
    client = app.test_client()
    with client.session_transaction() as s:
        s['_user_id'] = str(u['id'])
    return client, u


def test_get_empresa_ativa_lista_e_marca_a_ativa():
    client, u = _login_client('empresaativa1@example.com')
    r = client.get('/api/empresa/ativa')
    assert r.status_code == 200
    d = r.get_json()
    assert len(d['empresas']) >= 1
    assert d['ativa_id'] == d['empresas'][0]['id']


def test_post_empresa_ativa_com_empresa_valida():
    client, u = _login_client('empresaativa2@example.com')
    empresas = db.empresas_do_usuario(u['id'])
    r = client.post('/api/empresa/ativa', json={'empresa_id': empresas[0]['id']})
    assert r.status_code == 200
    assert r.get_json()['ok'] is True


def test_post_empresa_ativa_com_empresa_de_outro_usuario_403():
    client, u = _login_client('empresaativa3@example.com')
    _, outra = _login_client('empresaativa4@example.com')
    empresa_de_outro = db.empresas_do_usuario(outra['id'])[0]['id']
    r = client.post('/api/empresa/ativa', json={'empresa_id': empresa_de_outro})
    assert r.status_code == 403
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_empresa_ativa.py -v`
Expected: FAIL (404 — rota não existe)

- [ ] **Step 3: Implementação — editar `app.py`**

No import do flask (linha 13), adicionar `session`:

```python
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, send_from_directory, send_file, session
```

Perto de `admin_required`/`is_admin` (por volta da linha 82), adicionar:

```python
def _resolver_empresa_ativa():
    """Empresa ativa da sessão; escolhe a primeira se ausente/inválida.
    Devolve None se o usuário não pertence a nenhuma empresa."""
    empresas = db.empresas_do_usuario(current_user.id)
    if not empresas:
        return None
    ativa = session.get('empresa_ativa_id')
    if ativa and any(e['id'] == ativa for e in empresas):
        return ativa
    nova_ativa = empresas[0]['id']
    session['empresa_ativa_id'] = nova_ativa
    return nova_ativa


def _empresa_ativa_ou_400():
    """Para endpoints JSON: devolve (empresa_id, None) ou (None, response_erro)."""
    eid = _resolver_empresa_ativa()
    if eid is None:
        return None, (jsonify({'erro': 'Usuário sem empresa vinculada'}), 400)
    return eid, None
```

Adicionar as rotas (perto das rotas de `/api/fazendas`, por exemplo logo
antes de `@app.route('/api/fazendas', methods=['GET'])`):

```python
@app.route('/api/empresa/ativa', methods=['GET'])
@login_required
def api_empresa_ativa_get():
    empresas = db.empresas_do_usuario(current_user.id)
    ativa_id = _resolver_empresa_ativa()
    return jsonify({'empresas': empresas, 'ativa_id': ativa_id})

@app.route('/api/empresa/ativa', methods=['POST'])
@login_required
def api_empresa_ativa_post():
    empresa_id = (request.json or {}).get('empresa_id')
    if not db.usuario_pertence_a_empresa(current_user.id, empresa_id):
        return jsonify({'erro': 'Você não pertence a essa empresa'}), 403
    session['empresa_ativa_id'] = empresa_id
    return jsonify({'ok': True})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_empresa_ativa.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_empresa_ativa.py
git commit -m "feat: empresa ativa na sessão + GET/POST /api/empresa/ativa"
```

### Task B2: `GET/POST /api/empresa/perfil` substitui `/api/perfil-consultoria`

**Files:**
- Modify: `app.py` (rota `/api/perfil-consultoria` existente; rota
  `/api/parecer/pdf` existente, para buscar branding da empresa)
- Test: `tests/test_empresa_perfil.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_empresa_perfil.py
import database as db
from app import app


def _login_client(email):
    db.init_db()
    u = db.buscar_usuario_email(email)
    if not u:
        db.criar_usuario(email, 'Empresa Perfil Test', 'senha123')
        u = db.buscar_usuario_email(email)
    client = app.test_client()
    with client.session_transaction() as s:
        s['_user_id'] = str(u['id'])
    return client


def test_empresa_perfil_post_e_get():
    client = _login_client('empresaperfil1@example.com')
    r = client.post('/api/empresa/perfil', json={
        'nome_consultoria': 'Consultoria Empresa Teste', 'logo_base64': 'YWJj'})
    assert r.status_code == 200
    r2 = client.get('/api/empresa/perfil')
    d = r2.get_json()
    assert d['nome_consultoria'] == 'Consultoria Empresa Teste'
    assert d['logo_base64'] == 'YWJj'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_empresa_perfil.py -v`
Expected: FAIL (404)

- [ ] **Step 3: Implementação — editar `app.py`**

Localizar e **remover completamente** a rota antiga (procurar por
`/api/perfil-consultoria`):

```python
@app.route('/api/perfil-consultoria', methods=['GET', 'POST'])
@login_required
def api_perfil_consultoria():
    if request.method == 'POST':
        data = request.json or {}
        db.atualizar_perfil_consultoria(
            current_user.id,
            data.get('nome_consultoria', ''),
            data.get('logo_base64', ''))
        return jsonify({'ok': True})
    u = db.buscar_usuario_id(current_user.id)
    return jsonify({
        'nome_consultoria': (u.get('nome_consultoria') or '') if u else '',
        'logo_base64': (u.get('logo_base64') or '') if u else '',
    })
```

Substituir por:

```python
@app.route('/api/empresa/perfil', methods=['GET', 'POST'])
@login_required
def api_empresa_perfil():
    empresa_id, erro = _empresa_ativa_ou_400()
    if erro:
        return erro
    if request.method == 'POST':
        data = request.json or {}
        db.atualizar_perfil_empresa(
            empresa_id, data.get('nome_consultoria', ''), data.get('logo_base64', ''))
        return jsonify({'ok': True})
    e = db.buscar_empresa(empresa_id)
    return jsonify({
        'nome_consultoria': (e.get('nome') or '') if e else '',
        'logo_base64': (e.get('logo_base64') or '') if e else '',
    })
```

Na rota `/api/parecer/pdf`, trocar a busca de branding (hoje via
`db.buscar_usuario_id`) para vir da empresa ativa. Código atual:

```python
    u = db.buscar_usuario_id(current_user.id)
    branding = {'nome_consultoria': u.get('nome_consultoria') or '',
                'logo_base64': u.get('logo_base64') or ''} if u else None
    pdf_bytes = gerar_pdf_parecer(parecer, branding=branding)
```

Substituir por:

```python
    empresa_id = _resolver_empresa_ativa()
    e = db.buscar_empresa(empresa_id) if empresa_id else None
    branding = {'nome_consultoria': e.get('nome') or '',
                'logo_base64': e.get('logo_base64') or ''} if e else None
    pdf_bytes = gerar_pdf_parecer(parecer, branding=branding)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_empresa_perfil.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_empresa_perfil.py
git rm tests/test_perfil_consultoria.py
git commit -m "feat: /api/empresa/perfil substitui /api/perfil-consultoria"
```

> Nota: `tests/test_perfil_consultoria.py` testa a rota removida — apagar
> junto (`git rm`) neste passo evita suíte quebrada.

### Task B3: Endpoints de fazenda/parecer resolvem empresa ativa

**Files:**
- Modify: `app.py` — `api_listar_fazendas`, `api_criar_fazenda`,
  `api_historico_fazenda`, `api_fazenda_pareceres`, `index()`, bloco de
  `/api/classificar` que salva parecer, `/api/confirmar` (bloco provisório),
  `/api/historico`
- Test: `tests/test_fazendas_endpoints_empresa.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_fazendas_endpoints_empresa.py
import database as db
from app import app


def _login_client(email):
    db.init_db()
    u = db.buscar_usuario_email(email)
    if not u:
        db.criar_usuario(email, 'Endpoint Empresa Test', 'senha123')
        u = db.buscar_usuario_email(email)
    client = app.test_client()
    with client.session_transaction() as s:
        s['_user_id'] = str(u['id'])
    return client, u


def test_criar_e_listar_fazenda_via_endpoint():
    client, u = _login_client('endpointempresa1@example.com')
    r = client.post('/api/fazendas', json={'nome': 'Fazenda Endpoint'})
    assert r.status_code == 200
    r2 = client.get('/api/fazendas')
    nomes = [f['nome'] for f in r2.get_json()['fazendas']]
    assert 'Fazenda Endpoint' in nomes


def test_pareceres_de_fazenda_de_outra_empresa_nao_vaza():
    client_a, u_a = _login_client('vazamento.a@example.com')
    client_a.post('/api/fazendas', json={'nome': 'Fazenda Vazamento'})
    fid = db.listar_fazendas(db.empresas_do_usuario(u_a['id'])[0]['id'])[0]['id']

    client_b, _ = _login_client('vazamento.b@example.com')  # empresa diferente
    r = client_b.get(f'/api/fazendas/{fid}/pareceres')
    assert r.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_fazendas_endpoints_empresa.py -v`
Expected: FAIL (`TypeError: criar_fazenda() got an unexpected keyword argument 'user_id'`,
ou o teste de vazamento falhando com 200 em vez de 404 — o endpoint atual
não valida a fazenda antes de listar pareceres)

- [ ] **Step 3: Implementação — editar `app.py`**

`api_listar_fazendas` (de `db.listar_fazendas(current_user.id)` para):

```python
@app.route('/api/fazendas', methods=['GET'])
@login_required
def api_listar_fazendas():
    empresa_id, erro = _empresa_ativa_ou_400()
    if erro:
        return erro
    return jsonify({'fazendas': db.listar_fazendas(empresa_id)})
```

`api_criar_fazenda` — de `db.criar_fazenda(user_id=current_user.id, ...)`
para:

```python
@app.route('/api/fazendas', methods=['POST'])
@login_required
def api_criar_fazenda():
    empresa_id, erro = _empresa_ativa_ou_400()
    if erro:
        return erro
    data = request.json
    nome = (data.get('nome') or '').strip()
    if not nome:
        return jsonify({'erro': 'Nome obrigatório'}), 400
    fid = db.criar_fazenda(
        nome=nome,
        proprietario=data.get('proprietario', ''),
        municipio=data.get('municipio', ''),
        estado=data.get('estado', ''),
        empresa_id=empresa_id,
        criado_por=current_user.id,
    )
    return jsonify({'ok': True, 'id': fid})
```

`api_historico_fazenda` — de `db.buscar_fazenda(fid, current_user.id)` /
`db.historico_fazenda(fid, current_user.id)` para:

```python
@app.route('/api/fazendas/<int:fid>/historico', methods=['GET'])
@login_required
def api_historico_fazenda(fid):
    empresa_id, erro = _empresa_ativa_ou_400()
    if erro:
        return erro
    f = db.buscar_fazenda(fid, empresa_id)
    if not f:
        return jsonify({'erro': 'Fazenda não encontrada'}), 404
    hist = db.historico_fazenda(fid)
    return jsonify({'fazenda': dict(f), 'historico': hist})
```

`api_fazenda_pareceres` — **importante**: hoje não valida a fazenda antes de
listar (a query antiga se protegia sozinha filtrando por `user_id`; agora
`listar_pareceres` não filtra mais, então a validação precisa vir explícita
aqui, senão vaza pareceres de fazenda de outra empresa):

```python
@app.route('/api/fazendas/<int:fid>/pareceres', methods=['GET'])
@login_required
def api_fazenda_pareceres(fid):
    empresa_id, erro = _empresa_ativa_ou_400()
    if erro:
        return erro
    if not db.buscar_fazenda(fid, empresa_id):
        return jsonify({'erro': 'Fazenda não encontrada'}), 404
    itens = db.listar_pareceres(fazenda_id=fid)
    return jsonify({'pareceres': itens})
```

`index()` — de `fazendas = db.listar_fazendas(current_user.id)` para:

```python
@app.route('/')
@login_required
def index():
    empresa_id = _resolver_empresa_ativa()
    fazendas = db.listar_fazendas(empresa_id) if empresa_id else []
    cotacoes_dia = db.obter_cotacoes_atuais()
    return render_template('index.html', model_stats=stats, cenarios=CENARIOS,
                           usuario=current_user, fazendas=fazendas, cotacoes=cotacoes_dia,
                           eh_admin=is_admin(current_user.email))
```

No bloco de `/api/classificar` que salva o parecer — código atual:

```python
    fazenda_id = data.get('fazenda_id')
    if fazenda_id and data.get('credito_valor'):
        db.salvar_parecer(current_user.id, int(fazenda_id),
                          solicitacao=credito_inputs, parecer=parecer)
```

Substituir por (valida que a fazenda pertence à empresa ativa antes de
salvar — mesmo raciocínio de segurança do item anterior):

```python
    fazenda_id = data.get('fazenda_id')
    if fazenda_id and data.get('credito_valor'):
        empresa_id = _resolver_empresa_ativa()
        if empresa_id and db.buscar_fazenda(int(fazenda_id), empresa_id):
            db.salvar_parecer(current_user.id, int(fazenda_id),
                              solicitacao=credito_inputs, parecer=parecer)
```

No bloco provisório de `/api/confirmar` — código atual:

```python
    fazendas_do_user = db.listar_fazendas(current_user.id)
    if not any(f['nome'] == fazenda_nome for f in fazendas_do_user):
```

Substituir por (só troca o argumento, não mexe no resto do bloco):

```python
    empresa_id = _resolver_empresa_ativa()
    fazendas_do_user = db.listar_fazendas(empresa_id) if empresa_id else []
    if not any(f['nome'] == fazenda_nome for f in fazendas_do_user):
```

Em `/api/historico` — código atual:

```python
    fazendas = db.listar_fazendas(current_user.id)
```

Substituir por:

```python
    empresa_id = _resolver_empresa_ativa()
    fazendas = db.listar_fazendas(empresa_id) if empresa_id else []
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_fazendas_endpoints_empresa.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_fazendas_endpoints_empresa.py
git commit -m "feat: endpoints de fazenda/parecer/histórico resolvem empresa ativa"
```

---

## Fase C — Painel admin

### Task C1: `/admin` ganha criar empresa e vincular/desvincular usuário

**Files:**
- Modify: `app.py` (rota `/admin` GET, novas rotas `/admin/empresas/*`)
- Modify: `templates/admin.html`
- Test: `tests/test_admin_empresas.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_admin_empresas.py
import database as db
import app as app_module
from app import app


def _login_admin_client():
    """`is_admin` checa o e-mail contra app._ADMIN_EMAILS (populado via env
    var ADMIN_EMAILS em produção); em teste, adiciona direto no set."""
    db.init_db()
    email = 'admintest@example.com'
    app_module._ADMIN_EMAILS.add(email)
    u = db.buscar_usuario_email(email)
    if not u:
        db.criar_usuario(email, 'Admin Test', 'senha123')
        u = db.buscar_usuario_email(email)
    client = app.test_client()
    with client.session_transaction() as s:
        s['_user_id'] = str(u['id'])
    return client


def test_admin_cria_empresa():
    client = _login_admin_client()
    r = client.post('/admin/empresas/criar', data={'nome': 'Empresa Via Admin'})
    assert r.status_code in (200, 302)


def test_admin_vincula_e_desvincula_usuario():
    db.init_db()
    client = _login_admin_client()
    eid = db._exec(f"INSERT INTO empresas (nome) VALUES ({db._PH})",
                   ('Empresa Vinculo',), fetch='lastrow', commit=True)
    alvo_id = db.criar_usuario('alvovinculo@example.com', 'Alvo Vinculo', 'senha123')

    r = client.post('/admin/empresas/vincular', data={'user_id': alvo_id, 'empresa_id': eid})
    assert r.status_code in (200, 302)
    assert db.usuario_pertence_a_empresa(alvo_id, eid)

    r2 = client.post('/admin/empresas/desvincular', data={'user_id': alvo_id, 'empresa_id': eid})
    assert r2.status_code in (200, 302)
    assert not db.usuario_pertence_a_empresa(alvo_id, eid)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_admin_empresas.py -v`
Expected: FAIL (404 — rotas `/admin/empresas/*` ainda não existem)

- [ ] **Step 3: Implementação — editar `app.py`**

Adicionar rotas (perto das rotas `/admin/*` já existentes, por exemplo logo
após `/admin/remover/<int:uid>`):

```python
@app.route('/admin/empresas/criar', methods=['POST'])
@admin_required
def admin_criar_empresa():
    nome = (request.form.get('nome') or '').strip()
    if nome:
        db._exec(f"INSERT INTO empresas (nome) VALUES ({db._PH})", (nome,), commit=True)
    return redirect(url_for('admin'))

@app.route('/admin/empresas/vincular', methods=['POST'])
@admin_required
def admin_vincular_empresa():
    user_id = request.form.get('user_id')
    empresa_id = request.form.get('empresa_id')
    if user_id and empresa_id and not db.usuario_pertence_a_empresa(int(user_id), int(empresa_id)):
        db._exec(f"INSERT INTO empresa_membros (empresa_id, user_id) VALUES ({db._PH},{db._PH})",
                 (int(empresa_id), int(user_id)), commit=True)
    return redirect(url_for('admin'))

@app.route('/admin/empresas/desvincular', methods=['POST'])
@admin_required
def admin_desvincular_empresa():
    user_id = request.form.get('user_id')
    empresa_id = request.form.get('empresa_id')
    if user_id and empresa_id:
        db._exec(f"DELETE FROM empresa_membros WHERE user_id={db._PH} AND empresa_id={db._PH}",
                 (int(user_id), int(empresa_id)), commit=True)
    return redirect(url_for('admin'))
```

A rota `/admin` (GET) atual (linhas 230-238):

```python
@app.route('/admin')
@admin_required
def admin():
    return render_template(
        'admin.html',
        usuarios=db.listar_usuarios(),
        usuario=current_user,
        nova_conta=None,
    )
```

Substituir por:

```python
@app.route('/admin')
@admin_required
def admin():
    return render_template(
        'admin.html',
        usuarios=db.listar_usuarios(),
        usuario=current_user,
        nova_conta=None,
        empresas=db._exec('SELECT * FROM empresas ORDER BY nome', fetch='all') or [],
        membros=db._exec('''SELECT m.empresa_id, m.user_id, e.nome as empresa_nome,
                            u.email as user_email FROM empresa_membros m
                            JOIN empresas e ON e.id=m.empresa_id
                            JOIN usuarios u ON u.id=m.user_id ORDER BY e.nome''', fetch='all') or [],
    )
```

- [ ] **Step 4: Implementação — editar `templates/admin.html`**

O template atual termina assim (linhas 99-102, logo depois da tabela de
usuários):

```html
        </div>
    </div>
</body>
</html>
```

Substituir por (mantém a tabela de usuários existente intacta, insere as
três novas seções antes do fechamento):

```html
        </div>

        <div class="card">
            <h3>Criar empresa</h3>
            <form method="POST" action="{{ url_for('admin_criar_empresa') }}">
                <div class="row">
                    <div class="form-group">
                        <label>Nome da empresa</label>
                        <input type="text" name="nome" required>
                    </div>
                    <div class="form-group" style="flex:0">
                        <button type="submit">Criar</button>
                    </div>
                </div>
            </form>
        </div>

        <div class="card">
            <h3>Vincular usuário a empresa</h3>
            <form method="POST" action="{{ url_for('admin_vincular_empresa') }}">
                <div class="row">
                    <div class="form-group">
                        <label>Usuário</label>
                        <select name="user_id" required>
                            {% for u in usuarios %}
                            <option value="{{ u.id }}">{{ u.nome }} ({{ u.email }})</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Empresa</label>
                        <select name="empresa_id" required>
                            {% for e in empresas %}
                            <option value="{{ e.id }}">{{ e.nome }}</option>
                            {% endfor %}
                        </select>
                    </div>
                    <div class="form-group" style="flex:0">
                        <button type="submit">Vincular</button>
                    </div>
                </div>
            </form>
        </div>

        <div class="card">
            <h3>Membros por empresa ({{ membros|length }})</h3>
            <table>
                <thead><tr><th>Empresa</th><th>Usuário</th><th></th></tr></thead>
                <tbody>
                {% for m in membros %}
                    <tr>
                        <td>{{ m.empresa_nome }}</td>
                        <td>{{ m.user_email }}</td>
                        <td style="text-align:right">
                            <form method="POST" action="{{ url_for('admin_desvincular_empresa') }}"
                                  onsubmit="return confirm('Desvincular {{ m.user_email }} de {{ m.empresa_nome }}?')" style="margin:0">
                                <input type="hidden" name="user_id" value="{{ m.user_id }}">
                                <input type="hidden" name="empresa_id" value="{{ m.empresa_id }}">
                                <button type="submit" class="btn-del">Desvincular</button>
                            </form>
                        </td>
                    </tr>
                {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_admin_empresas.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app.py templates/admin.html tests/test_admin_empresas.py
git commit -m "feat: painel admin gerencia empresas e vínculos de usuário"
```

---

## Fase D — UI principal

### Task D1: Seletor de empresa ativa + marca aponta para `/api/empresa/perfil`

**Files:**
- Modify: `templates/index.html`

- [ ] **Step 1: Adicionar o seletor no header**

No `<header>`, ao lado do botão "⚙ Marca" (procurar por
`onclick="abrirMarcaModal()"` em `templates/index.html`), adicionar antes
dele:

```html
<select id="empresa-ativa-select" class="ml-acc" style="cursor:pointer;background:rgba(96,165,250,.07);color:var(--cy);border:1px solid rgba(96,165,250,.2);border-radius:8px;padding:4px 8px;font-family:var(--fm);font-size:.58rem" onchange="trocarEmpresaAtiva()"></select>
```

- [ ] **Step 2: JS de carregar/trocar empresa ativa**

Perto do bloco `// ================== MARCA DA CONSULTORIA` (procurar por
esse comentário em `templates/index.html`), adicionar antes dele:

```javascript
// ================== EMPRESA ATIVA ==================
async function carregarEmpresaAtiva(){
  try{
    const r = await fetch('/api/empresa/ativa');
    const d = await r.json();
    const sel = document.getElementById('empresa-ativa-select');
    if(!sel) return;
    sel.innerHTML = (d.empresas||[]).map(e=>`<option value="${e.id}" ${e.id===d.ativa_id?'selected':''}>${e.nome}</option>`).join('');
  }catch(e){}
}
async function trocarEmpresaAtiva(){
  const eid = document.getElementById('empresa-ativa-select').value;
  try{
    await fetch('/api/empresa/ativa', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({empresa_id: +eid})});
    await carregarFazendasSelect();
    document.getElementById('hist-lista').innerHTML = '';
    showToast('Empresa ativa trocada.');
  }catch(e){ showToast('Erro ao trocar empresa.', true); }
}
```

- [ ] **Step 3: Apontar o modal de marca para o novo endpoint**

Em `abrirMarcaModal()` e `salvarMarcaConsultoria()` (procurar por
`/api/perfil-consultoria` em `templates/index.html`), trocar as duas
ocorrências de `/api/perfil-consultoria` por `/api/empresa/perfil`.

- [ ] **Step 4: Chamar `carregarEmpresaAtiva()` no init**

Perto de `carregarFazendasSelect();` no bloco de INIT (fim do script),
adicionar logo abaixo:

```javascript
carregarEmpresaAtiva();
```

- [ ] **Step 5: Verificar sintaxe e no navegador**

```bash
python -c "
import re
html=open('templates/index.html',encoding='utf-8').read()
js=''.join(re.findall(r'<script>(.*?)</script>', html, re.S))
open('_check.js','w',encoding='utf-8').write(js)
"
node --check _check.js && echo OK
rm -f _check.js
```

Depois, subir o app localmente e confirmar visualmente:
1. Login com dois usuários de teste vinculados à mesma empresa (via
   `/admin`) → ambos veem a mesma lista de fazendas.
2. Trocar a empresa ativa no seletor → lista de fazendas muda.
3. Botão "⚙ Marca" continua funcionando (agora contra `/api/empresa/perfil`).

- [ ] **Step 6: Commit**

```bash
git add templates/index.html
git commit -m "feat: seletor de empresa ativa na UI; marca usa /api/empresa/perfil"
```

---

## Fase E — Fechamento

### Task E1: Suíte completa + smoke manual de isolamento entre empresas

- [ ] **Step 1: Rodar toda a suíte**

Run: `python -m pytest tests/ -v --ignore=tests/test_benchmarks_reais.py --ignore=tests/test_csrf_e_limiter.py`
Expected: PASS (só as 5 falhas pré-existentes de PDF/retreino, já conhecidas
e fora de escopo).

- [ ] **Step 2: Smoke manual no navegador (crítico — é mudança de isolamento de dados)**

Criar dois usuários de teste, vincular ambos à mesma empresa via `/admin`,
confirmar que um vê as fazendas/pareceres criados pelo outro. Criar um
terceiro usuário em empresa diferente e confirmar que ele **não** vê nada
dos dois primeiros (nem por URL direta de `/api/fazendas/<id>/pareceres`
com o ID de uma fazenda alheia — deve dar 404).

- [ ] **Step 3: Commit final (se houver ajustes)**

```bash
git add -A
git commit -m "test: ajustes finais de suíte para empresa/equipe"
```
