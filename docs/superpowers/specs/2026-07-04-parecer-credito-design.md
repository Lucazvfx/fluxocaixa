# Parecer de Crédito + Conclusão de Capacidade de Pagamento

**Data:** 2026-07-04
**Bloco:** 1 de N (rumo "usável em consultoria")
**Escopo deste spec:** (a) padronizar todos os preços/custos em R$/@; (b)
consolidar a análise numa entrega de parecer; (c) adicionar a conclusão de crédito
(capacidade de pagamento). **Fora de escopo:** PDF exportável e multiempresa
(blocos seguintes).

## Contexto e motivação

O app já é um analisador técnico-financeiro de rebanho, mas para uso numa
**consultoria de crédito pecuária** falta a peça que fecha o trabalho: um
**parecer** que junte tudo e conclua sobre a **capacidade de pagamento** do
tomador. Hoje:

- Os cálculos existem, mas espalhados no dashboard (sem uma visão "parecer").
- A **consistência do rebanho declarado** (o diferencial de análise de crédito)
  só roda na importação de PDF (`app.py:671`), não no fluxo principal
  (`/api/classificar`).
- **Não existe** entrada de crédito (valor, prazo, juros, dívidas) nem qualquer
  cálculo que transforme o "resultado da operação" em capacidade de pagamento.

## O que já existe (aproveitado, não recriado)

- **Identificação:** tabela `fazendas` (nome, proprietário, município, estado) +
  histórico por fazenda (`database.py:137`, `historico_fazenda`).
- **Análise técnica:** `/api/classificar` (`app.py:315`) devolve classificação,
  `indicadores`, `benchmarks` (regional+nacional) e `breakeven_simples`.
- **Projeção financeira por cenário:** `ml_engine.CENARIOS` inclui o cenário
  `conservador` ("Manutenção", `ml_engine.py:623`); a projeção devolve
  `anos[].resultado` e `acumulado.resultado` (receita − custo).
- **Consistência:** `services/consistencia_rebanho.analisar_consistencia(v)`
  devolve `score_consistencia` (0–100), `resumo` e `flags` com severidade.

## Componentes

### 0. Padronização de preços em R$/@ (pré-requisito)

Hoje a **receita** já é 100% em arroba (`calcular_ano`, `ml_engine.py:571`):
`receita = (Σ cabeças_vendidas × peso_@) × preco_arroba`. O **único ponto em
R$/cabeça é o custo** (`custo_tot = total_prox × custo_cab_ano`), replicado nas
simulações de cria/recria/engorda.

**Mudança (Opção A — custo simétrico à receita):** o custo passa a ser
`custo_arroba` (R$/@) e o total vira o peso do rebanho em @ vezes esse custo:

```
custo_tot = (Σ cabeças_da_categoria × peso_@_categoria) × custo_arroba
```

- Reusa os pesos por categoria já existentes para valorar também o **plantel
  parado**: matrizes → `peso_vaca`, bois → `peso_boi`, jovens fêmeas/machos →
  `peso_bezerra`/`peso_garrote`. Onde a simulação usa faixas próprias (recria/
  engorda com `peso_entrada_arr`/`peso_saida_arr`), usar o peso médio da fase.
- **Semântica preservada:** continua sendo "custo de carregar o rebanho", só a
  base muda de cabeça para arroba.

**Alcance da mudança:**
- `ml_engine.py`: `calcular_ano`, `_simular_cria`, `_simular_recria`,
  `_simular_engorda` e `calcular_breakeven_simples` trocam `custo_cab_ano`/
  `custo_cab_mes` por `custo_arroba`; o custo passa a multiplicar arrobas, não
  cabeças. `preco_bezerro` (R$/cabeça) também passa a R$/@ × peso do bezerro.
- `app.py`: defaults e leitura dos params (`/api/classificar` linha ~522,
  `/api/cenario`) passam a `custo_arroba`.
- `templates/index.html`: rótulos e campos de custo/preço passam a "R$/@".

**Sem back-compat:** trocamos o campo direto (o app não tem consumidores externos
versionados). O default de `custo_arroba` é um **valor de formulário** (não é
benchmark) escolhido para aproximar o comportamento anterior; documentado como
default ajustável, não como número com fonte.

### 1. Novas entradas — grupo "Solicitação de Crédito" (UI)

Adicionar no formulário de análise um grupo opcional com:

| Campo | Tipo | Observação |
|---|---|---|
| `credito_valor` | R$ | valor solicitado |
| `credito_finalidade` | custeio \| investimento | rótulo informativo |
| `credito_prazo_meses` | inteiro | prazo total |
| `credito_carencia_meses` | inteiro | carência (default 0) |
| `credito_juros_aa` | % a.a. | taxa nominal anual |
| `dividas_mensais` | R$/mês | parcelas já existentes (default 0) |

Se `credito_valor` estiver vazio, o parecer é gerado **sem** a conclusão de
capacidade de pagamento (as demais seções aparecem normalmente).

### 2. Módulo isolado `services/parecer_credito.py`

Função pura, testável, sem dependência de Flask/DB. Recebe os resultados **já
computados** + os inputs de crédito e devolve a conclusão.

```
def avaliar_capacidade_pagamento(
    geracao_caixa_anual: float,   # resultado ano 1 do cenário conservador
    credito_valor: float,
    prazo_meses: int,
    juros_aa: float,
    carencia_meses: int = 0,
    dividas_mensais: float = 0.0,
) -> dict
```

Cálculo:
- **Parcela mensal** por amortização Price:
  `PMT = PV · i / (1 − (1+i)^-n)`, com `i = (1+juros_aa)^(1/12) − 1` e
  `n = prazo_meses − carencia_meses`. Se `juros_aa == 0`, `PMT = PV / n`.
- **Serviço da dívida anual** = `12 · (PMT + dividas_mensais)`.
- **DSCR** = `geracao_caixa_anual / servico_divida_anual`
  (se serviço = 0 → DSCR = None, sem crédito para avaliar).
- **Recomendação** por faixa (constantes ajustáveis no topo do módulo):
  - `DSCR ≥ 1.30` → **aprovar**
  - `1.00 ≤ DSCR < 1.30` → **com ressalva**
  - `DSCR < 1.00` → **negar**
  - `geracao_caixa_anual ≤ 0` → **negar** (operação não gera caixa).

  > As faixas de DSCR são **critério de política de crédito**, não benchmark
  > zootécnico — ficam como constantes documentadas e ajustáveis, coerentes com a
  > regra "nenhum benchmark inventado" (isso não é um número zootécnico fabricado).

Retorno: `{ dscr, parcela_mensal, servico_divida_anual, geracao_caixa_anual,
recomendacao, faixa, justificativa }`, onde `justificativa` é texto automático
(ex.: "Cobertura 1,12 — operação cobre o serviço da dívida com folga estreita").

### 3. Consolidação do parecer (`services/parecer_credito.montar_parecer`)

Função que ordena as seções na sequência que um analista lê e devolve um dict
único `parecer`:

1. **Identificação** — fazenda/proprietário/município/estado.
2. **Composição do rebanho** — total + faixas.
3. **Indicadores técnicos vs benchmark** — reusa `benchmarks`/`benchmarks_nacionais`.
4. **Consistência do rebanho declarado** — `score_consistencia` + flags.
5. **Situação financeira** — breakeven + resultado projetado (conservador).
6. **Conclusão** — saída de `avaliar_capacidade_pagamento` +
   **justificativa agregada** que combina os sinais: recomendação de crédito
   rebaixada para "com ressalva" se houver ERRO de consistência, mesmo com DSCR
   bom (ex.: rebanho inflado invalida a projeção de caixa).

### 4. Integração no `/api/classificar` (`app.py`)

A projeção financeira NÃO roda hoje no `/api/classificar` — ela vive no endpoint
separado `/api/cenario` (`app.py:508`, via `simular_cenario`). Portanto a
orquestração aqui precisa:

- Rodar `analisar_consistencia(v)` também neste fluxo (hoje só no PDF) e incluir
  em `consistencia` na resposta.
- Computar a **geração de caixa** chamando
  `simular_cenario(v, 'conservador', {preco, custo})` e extraindo o resultado do
  **ano 1** (`anos[0]['resultado']`) — é o número recorrente e mais conservador.
- Chamar `montar_parecer(...)` passando os resultados já computados + a geração de
  caixa + os inputs de crédito do `data`; incluir `parecer` na resposta JSON.
- `app.py` continua fino: `simular_cenario` já existe; toda a lógica **nova**
  (Price, DSCR, recomendação, montagem) mora em `services/parecer_credito.py`,
  que permanece puro (recebe a geração de caixa como número, não chama Flask).

### 5. Seção "Parecer" na UI (`templates/index.html`)

Nova seção/aba que renderiza `data.parecer` na ordem acima. A **Conclusão** é o
destaque: cartão com recomendação (verde/âmbar/vermelho conforme a faixa), DSCR,
parcela estimada e a justificativa agregada.

### 6. Persistência por fazenda (`database.py`)

Nova tabela `pareceres` (histórico consultável por cliente):

```
CREATE TABLE IF NOT EXISTS pareceres (
    id          {_AI},
    fazenda_id  INTEGER,
    user_id     INTEGER NOT NULL,
    solicitacao TEXT,        -- JSON dos inputs de crédito
    parecer     TEXT,        -- JSON do parecer consolidado
    recomendacao TEXT,       -- aprovar | ressalva | negar (para listar rápido)
    dscr        REAL,
    created_at  TIMESTAMP DEFAULT {_NOW}
)
```

- `db.salvar_parecer(user_id, fazenda_id, solicitacao, parecer)` grava.
- `db.listar_pareceres(fazenda_id, user_id)` lista o histórico (para a tela de
  histórico da fazenda evoluir depois).
- Segue o padrão cross-DB existente (`_AI`, `_NOW`), funciona em SQLite e Postgres.

## Fluxo de dados

```
Formulário (composição + indicadores + Solicitação de Crédito)
        │  POST /api/classificar
        ▼
classificar + calcular_indicadores + avaliar_benchmarks + breakeven
        + analisar_consistencia            (todos já existentes / integrados)
        ▼
parecer_credito.montar_parecer(resultados, inputs_credito)
        │  → avaliar_capacidade_pagamento (DSCR, recomendação)
        ▼
resposta JSON { ..., consistencia, parecer }
        ├─ UI renderiza a seção "Parecer"
        └─ db.salvar_parecer(...) grava no histórico da fazenda
```

## Tratamento de erros / bordas

- **Sem crédito informado:** parecer sem conclusão de capacidade; demais seções
  normais.
- **Serviço da dívida = 0 / prazo inválido:** DSCR = None, conclusão informa
  "sem crédito a avaliar".
- **Geração de caixa ≤ 0:** recomendação = negar, justificativa explícita.
- **ERRO de consistência:** rebaixa a recomendação e cita o motivo.
- **`fazenda_id` ausente** (análise avulsa sem fazenda cadastrada): parecer é
  gerado e exibido, mas **não persistido** (persistência exige fazenda).

## Testes

`tests/test_custo_arroba.py` (padronização em @):
- `calcular_ano` com `custo_arroba`: custo total = peso do rebanho em @ × custo/@;
  bater o número num caso montado à mão.
- Regressão: com custo/@ equivalente ao antigo custo/cabeça, o `resultado` fica na
  mesma ordem de grandeza (sanidade da migração).
- Breakeven continua em R$/@ e coerente com a nova base de custo.

`tests/test_parecer_credito.py`:
- Price: parcela correta para juros > 0 e para juros = 0.
- DSCR e faixa: um caso **aprovar** (DSCR ≥ 1,3), um **ressalva** (1,0–1,3), um
  **negar** (< 1,0).
- Borda: geração de caixa ≤ 0 → negar; crédito zero → conclusão vazia.
- `montar_parecer`: rebaixamento para "com ressalva" quando há ERRO de
  consistência apesar de DSCR bom.

## Critérios de sucesso

- Todos os preços/custos da UI e do motor estão em **R$/@**; não sobra nenhum
  campo em R$/cabeça.
- A partir de uma composição + solicitação de crédito, o app produz um **parecer
  consolidado** com recomendação justificada de crédito.
- A consistência do rebanho passa a aparecer no fluxo principal, não só no PDF.
- O parecer fica salvo no histórico da fazenda.
- `app.py` não engorda: lógica nova isolada e coberta por testes.
