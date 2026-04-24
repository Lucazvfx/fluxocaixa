# Design: Histórico de Análises por Fazenda

**Data:** 2026-04-24  
**Status:** Aprovado

## Contexto

O BovIML já salva cada classificação no banco (`registros`) com `fazenda_id` e `user_id`, e o `database.py` já tem `listar_fazendas()`, `criar_fazenda()` e `historico_fazenda()` implementados. O que falta é expor esses dados via rotas Flask e construir o frontend correspondente.

## Objetivo

Permitir que o usuário vincule cada análise a uma fazenda, visualize o histórico de análises por fazenda num painel dedicado, e recarregue uma análise passada no formulário.

## Arquitetura

### Backend — Novos Endpoints (`app.py`)

Todos com `@login_required`. Nenhuma mudança no `database.py` necessária.

| Rota | Método | Implementação |
|---|---|---|
| `/api/fazendas` | GET | `db.listar_fazendas(current_user.id)` |
| `/api/fazendas` | POST | `db.criar_fazenda(nome, municipio, proprietario, user_id=current_user.id)` — body JSON `{nome, municipio?, proprietario?}` |
| `/api/fazendas/<int:id>/historico` | GET | `db.historico_fazenda(id, user_id=current_user.id)` — valida que a fazenda pertence ao usuário |

O endpoint `/api/classificar` já aceita e persiste `fazenda_id` — nenhuma mudança necessária.

### Frontend — Dropdown de Fazenda (`templates/index.html`)

Localização: painel "Inserir Dados", acima dos campos de texto Fazenda/Município/Proprietário.

**Elementos:**
- `<select id="sel-fazenda">` com opção padrão "— Sem vínculo —" (value vazio)
- Opções dinâmicas populadas via `GET /api/fazendas` no carregamento da página
- Última opção fixa: "＋ Nova Fazenda..." (value `"__nova"`)
- Mini-modal inline (`<div id="modal-nova-fazenda">`) com campo nome e botão Criar — visível só quando `"__nova"` é selecionado
- Ao criar: `POST /api/fazendas` → adiciona opção no select e a seleciona → fecha mini-modal
- Ao classificar: inclui `fazenda_id: parseInt(sel.value) || null` no payload JSON
- Quando PDF é carregado: tenta pré-selecionar pelo nome (`data.fazenda`) usando comparação case-insensitive com as opções existentes; se não encontrar, mantém "— Sem vínculo —"

### Frontend — Painel "Minhas Fazendas" (`templates/index.html`)

Novo item de navegação na sidebar que exibe `panel-fazendas`.

**Vista: lista de fazendas**
- Cards com: nome, município, `total_analises`, `ultima_analise`
- Botão "Ver histórico" por fazenda
- Carrega via `GET /api/fazendas` ao abrir o painel

**Vista: histórico da fazenda**
- Cabeçalho com nome da fazenda + botão "← Voltar"
- Tabela com colunas: Data | Tipo | Total Animais | Confiança | Ação
- Badge colorido para tipo (usa mesmas cores `TC` do app: verde=CRIA, etc.)
- Botão "Recarregar" por linha: popula `valores[]` no formulário de inserção de dados e rola até o painel
- Carrega via `GET /api/fazendas/<id>/historico` ao clicar em "Ver histórico"
- Máximo 30 registros (limite do backend, sem paginação)

## Fluxo de Dados

```
Carrega página
  → GET /api/fazendas → popula sel-fazenda

Usuário seleciona "+ Nova Fazenda" → digita nome → Criar
  → POST /api/fazendas → nova opção selecionada no sel-fazenda

Usuário carrega PDF → parser extrai dados
  → compara data.fazenda com opções do sel-fazenda → pré-seleciona se encontrar

Usuário clica Classificar
  → payload inclui fazenda_id → db.salvar(... fazenda_id=...)

Usuário abre "Minhas Fazendas"
  → GET /api/fazendas → lista de cards

Usuário clica "Ver histórico"
  → GET /api/fazendas/<id>/historico → tabela de análises

Usuário clica "Recarregar"
  → popula formulário com valores[] da análise → scroll até painel inserir
```

## O Que Não Muda

- `database.py` — nenhuma alteração
- Endpoint `/api/classificar` — nenhuma alteração
- Lógica de classificação ML
- Estilo visual geral (CSS variables, card/table existentes)
- Autenticação e multi-usuário
