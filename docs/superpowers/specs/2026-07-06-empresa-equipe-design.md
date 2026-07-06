# Empresa/Equipe (multiempresa de verdade)

**Data:** 2026-07-06
**Subprojeto:** #1 de N rumo a "preparar para vender a outras consultorias"
(decomposição: **#1 empresa/equipe [este]**, #2 marca própria — entregue,
#3 cobrança/assinatura, #4 onboarding self-service, #5 painel admin de
clientes, #6 LGPD/jurídico). É o alicerce dos demais.
**Escopo:** introduzir o conceito de **empresa** (consultoria) como fronteira
de compartilhamento de clientes (fazendas) entre vários usuários (analistas).
Um usuário pode pertencer a **várias empresas** e alterna entre elas ("empresa
ativa"). Migração automática dos dados existentes, sem quebra.
**Fora de escopo:** convite self-service por e-mail (subprojeto #4 —
neste spec, só o admin geral vincula usuário↔empresa pelo `/admin`).
Papéis/permissões diferenciadas dentro da empresa (dono vs membro) — sem tela
que precise disso ainda; adiciona quando o #4 exigir. Cobrança (#3).

## Contexto e motivação

Hoje o isolamento de dados é só `user_id`, espalhado em `fazendas` e
`pareceres` (e `registros`, que fica fora de escopo — ver abaixo). Não existe
nenhum conceito de time: dois analistas da mesma consultoria não veem os
clientes um do outro. Isso inviabiliza vender para uma consultoria com mais de
um analista.

## Decisões de escopo (confirmadas com o usuário)

- **N:N, não 1:1** — um usuário pode estar em várias empresas (cobre o caso
  de consultor freelancer atendendo mais de uma firma com o mesmo login).
  Exige "empresa ativa" na sessão, não uma coluna fixa em `usuarios`.
- **Vínculo só pelo admin geral** — sem tela de convite para o dono da
  empresa; `/admin` ganha as telas de gestão de empresa/membro.
- **`registros` (histórico de classificação avulsa) continua privado por
  usuário** — não é "trabalho de cliente" para compartilhar (é alimentação do
  retreino do modelo, que já é global). Só `fazendas` (e, por herança via
  `fazenda_id`, `pareceres`) passam a ser de empresa.
- **`pareceres` não ganha coluna nova** — a visibilidade vem de
  `fazenda_id → fazendas.empresa_id`. Menos superfície de mudança.

## Componentes

### 1. Schema (`database.py`)

```python
_exec(f'''
    CREATE TABLE IF NOT EXISTS empresas (
        id         {_AI},
        nome       TEXT NOT NULL,
        logo_base64 TEXT DEFAULT '',
        created_at TIMESTAMP DEFAULT {_NOW}
    )
''', commit=True)

_exec(f'''
    CREATE TABLE IF NOT EXISTS empresa_membros (
        id         {_AI},
        empresa_id INTEGER NOT NULL,
        user_id    INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT {_NOW}
    )
''', commit=True)

_add_column_safe('fazendas', 'empresa_id', 'INTEGER')
```

`fazendas.user_id` (já existe) passa a significar **"criado por"** (auditoria),
não mais controle de acesso — mantido sem mudança de tipo/valor.

### 2. Migração de dados existentes (dentro de `init_db()`, idempotente)

Para cada usuário que ainda não tem nenhuma linha em `empresa_membros`:

```python
def _migrar_usuarios_para_empresas():
    usuarios_sem_empresa = _exec('''
        SELECT u.id, u.nome, u.nome_consultoria, u.logo_base64 FROM usuarios u
        WHERE NOT EXISTS (SELECT 1 FROM empresa_membros m WHERE m.user_id = u.id)
    ''', fetch='all') or []
    for u in usuarios_sem_empresa:
        nome_empresa = (u.get('nome_consultoria') or '').strip() or f"{u['nome']} — Consultoria"
        eid = _exec(f'INSERT INTO empresas (nome, logo_base64) VALUES ({_PH},{_PH})',
                    (nome_empresa, u.get('logo_base64') or ''), fetch='lastrow', commit=True)
        _exec(f'INSERT INTO empresa_membros (empresa_id, user_id) VALUES ({_PH},{_PH})',
              (eid, u['id']), commit=True)
        _exec(f'UPDATE fazendas SET empresa_id={_PH} WHERE user_id={_PH} AND empresa_id IS NULL',
              (eid, u['id']), commit=True)
```

Chamada ao final de `init_db()`. Idempotente: usuário que já tem
`empresa_membros` não é tocado de novo — seguro rodar em todo boot da app
(mesmo padrão de `_add_column_safe`, sempre `IF NOT EXISTS`/condicional).

Os campos `usuarios.nome_consultoria`/`logo_base64` (subprojeto #2) deixam de
ser lidos/escritos pelo app depois desta migração — servem só de fonte para
ela. Não são removidos (sem `DROP COLUMN`, mesmo padrão do projeto).

### 3. Funções de empresa (`database.py`)

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

### 4. Empresa ativa na sessão (`app.py`)

- `session['empresa_ativa_id']` — protegido pela assinatura de sessão do
  Flask (`itsdangerous`); não pode ser forjado pelo cliente sem a chave
  secreta do servidor.
- Helper `_empresa_ativa_ou_400()`: lê `session.get('empresa_ativa_id')`; se
  ausente ou o usuário não pertence mais a ela (`usuario_pertence_a_empresa`),
  cai para a primeira empresa de `empresas_do_usuario(current_user.id)` e
  atualiza a sessão. Se o usuário não tiver nenhuma empresa (não deveria
  acontecer após a migração, mas defensivo), retorna 400.
- `POST /api/empresa/ativa` `{empresa_id}`: valida
  `usuario_pertence_a_empresa`, seta `session['empresa_ativa_id']`, devolve
  `{ok: True}`. 403 se o usuário não pertence à empresa pedida.
- `GET /api/empresa/ativa`: devolve `{empresas: [...], ativa_id: ...}` — a
  lista de `empresas_do_usuario` + qual está ativa agora, para popular o
  seletor no cabeçalho.
- `GET/POST /api/empresa/perfil` (**substitui** `/api/perfil-consultoria` do
  subprojeto #2): opera sobre a empresa ativa, não mais sobre o usuário —
  `db.atualizar_perfil_empresa(empresa_ativa_id, nome, logo_base64)` /
  `db.buscar_empresa(empresa_ativa_id)`.

### 5. Funções de fazenda/parecer passam a operar por empresa (`database.py`)

Assinaturas alteradas (parâmetro `user_id` de controle de acesso vira
`empresa_id`; onde fizer sentido registrar quem criou, `criado_por` é novo
parâmetro separado):

```python
def criar_fazenda(nome, proprietario='', municipio='', estado='',
                  empresa_id=None, criado_por=None) -> int
def listar_fazendas(empresa_id: int) -> list
def buscar_fazenda(fazenda_id: int, empresa_id: int = None) -> dict | None
def excluir_fazenda(fazenda_id: int, empresa_id: int) -> bool
def historico_fazenda(fazenda_id: int, limit: int = 30) -> list   # sem user_id
def listar_pareceres(fazenda_id: int, limit: int = 30) -> list    # sem user_id
```

`salvar_parecer(user_id, fazenda_id, ...)` mantém `user_id` (quem gerou o
parecer, auditoria) — sem mudança de assinatura, só o call site em `app.py`
passa a validar a fazenda contra a empresa ativa antes de chamar.

A validação de acesso acontece **uma vez**, em `buscar_fazenda(id,
empresa_id)`: se a fazenda pertence à empresa ativa do usuário, tudo dela
(histórico, pareceres) fica visível — independente de qual colega da mesma
empresa criou cada registro.

### 6. Endpoints de `app.py` a atualizar (call sites)

Todo endpoint que hoje chama `db.listar_fazendas(current_user.id)`,
`db.criar_fazenda(..., user_id=current_user.id)`,
`db.buscar_fazenda(fid, current_user.id)`, `db.excluir_fazenda(fid,
current_user.id)`, `db.historico_fazenda(fid, current_user.id)`,
`db.listar_pareceres(fid, current_user.id)` passa a resolver
`empresa_id = _empresa_ativa_ou_400()` primeiro e usar esse valor no lugar de
`current_user.id`. Isso inclui `/api/fazendas` (GET/POST),
`/api/fazendas/<id>/historico`, `/api/fazendas/<id>/pareceres`,
`/api/classificar` (quando salva parecer), e o bloco provisório de
`/api/confirmar` que hoje chama `db.listar_fazendas(current_user.id)`
diretamente (só troca o argumento — não é escopo deste spec limpar aquele
bloco "provisório").

### 7. Painel `/admin` (`templates/admin.html` + `app.py`)

Novas seções, seguindo o padrão visual das já existentes (criar/remover
usuário):
- **Criar empresa** — form com `nome` → `POST /admin/empresas/criar`.
- **Vincular usuário à empresa** — dois selects (usuário, empresa) →
  `POST /admin/empresas/vincular`.
- **Desvincular** — lista `empresa_membros` com botão remover →
  `POST /admin/empresas/desvincular`.
- Todas atrás de `@admin_required` (decorator já existente, mesmo usado nas
  rotas `/admin/*` atuais).

### 8. UI principal (`templates/index.html`)

- **Seletor de empresa ativa** no `<header>`, ao lado do botão "⚙ Marca":
  `<select id="empresa-ativa-select">`, populado via
  `GET /api/empresa/ativa`; ao trocar, `POST /api/empresa/ativa` e recarrega
  fazendas/histórico (`carregarFazendasSelect()`, limpa `#hist-lista`).
  Se o usuário só tem uma empresa, o seletor aparece mas não tem efeito
  prático (não é ocultado — simplicidade, sem lógica condicional extra).
- Botão **"⚙ Marca"** existente: continua igual na interação, mas agora
  chama `GET/POST /api/empresa/perfil` (opera na empresa ativa) em vez de
  `/api/perfil-consultoria`.

## Fluxo de dados

```
Login → empresas_do_usuario(user) → empresa ativa default = primeira em
        ordem alfabética (não há "última usada" persistida entre sessões
        nesta versão; a cada novo login, reinicia na primeira)
Header: seletor de empresa → POST /api/empresa/ativa → session['empresa_ativa_id']

Aba Entrada: GET /api/fazendas → lista SÓ da empresa ativa (compartilhada
             entre todos os membros dessa empresa)
Classificar com fazenda selecionada → valida fazenda pertence à empresa ativa
             → salva parecer (visível a qualquer colega da mesma empresa)

/admin (você): cria empresas, vincula/desvincula usuários — único jeito de
             entrar numa empresa nesta versão (self-service fica pro #4)
```

## Tratamento de erros / bordas

- Usuário sem nenhuma empresa (não deveria ocorrer pós-migração): endpoints
  que dependem de empresa ativa devolvem 400 com mensagem clara.
- Trocar para uma empresa que o usuário não pertence: 403.
- Fazenda de uma empresa diferente da ativa: 404 (mesmo comportamento de
  "não encontrada" já usado hoje para fazenda de outro usuário).
- Migração roda em todo boot mas é idempotente (`NOT EXISTS`) — não duplica
  empresas a cada restart do servidor.

## Testes

`tests/test_empresas_migracao.py`:
- Usuário novo (criado antes da migração rodar de novo) ganha empresa
  pessoal automática, vira membro, suas fazendas existentes são realocadas.
- Rodar a migração duas vezes não duplica empresas.
- `nome_consultoria`/`logo_base64` do subprojeto #2 são herdados pela empresa
  migrada.

`tests/test_empresa_ativa.py`:
- `POST /api/empresa/ativa` com empresa que o usuário pertence → 200, sessão
  atualizada.
- Com empresa que não pertence → 403.
- `GET /api/empresa/ativa` lista as empresas do usuário + qual está ativa.

`tests/test_fazendas_empresa_compartilhada.py`:
- Dois usuários na mesma empresa (via `empresa_membros`): usuário B vê a
  fazenda criada por A (`listar_fazendas(empresa_id)`), vê seu histórico e
  pareceres.
- Usuário de empresa diferente não vê a fazenda (`buscar_fazenda` → None).

`tests/test_empresa_perfil.py`:
- `GET/POST /api/empresa/perfil` opera na empresa ativa (round-trip
  nome/logo).

## Critérios de sucesso

- Dois analistas na mesma empresa compartilham fazendas/pareceres; analistas
  de empresas diferentes não se veem.
- Usuário pode alternar entre empresas às quais pertence sem perder acesso a
  nenhuma.
- Nenhum usuário existente perde acesso ao que já tinha (migração automática
  e idempotente).
- Marca (nome/logo) migrou de usuário para empresa sem perda de dado.
- Vínculo empresa↔usuário só pelo `/admin` nesta versão (self-service é #4).
