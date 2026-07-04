# Parecer de Crédito + Preços em R$/@ — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Padronizar todos os custos em R$/@ e entregar um parecer de crédito consolidado com conclusão de capacidade de pagamento (DSCR).

**Architecture:** Toda a lógica nova (pesos em @, Price, DSCR, montagem do parecer) vive em módulos puros e testáveis em `services/`. `ml_engine.py` troca a base de custo de cabeça para arroba. `app.py` só orquestra. A UI ganha um grupo "Solicitação de Crédito" e uma seção "Parecer".

**Tech Stack:** Python, Flask, pytest, numpy; frontend em JS/template literals no `templates/index.html`; DB via `database.py` (SQLite/Postgres, placeholders `_AI`/`_NOW`).

**Convenção de custo:** `custo_arroba` = **R$/@ de peso vivo por ano**. Fases com duração (recria em meses, engorda em dias) aplicam o custo pró-rata: `× (meses/12)` ou `× (dias/365)`. Default de formulário: `57.0` (≈ antigo R$850/cab ÷ ~15@; é default de UI, não benchmark).

**Pesos de categoria do plantel (@):** matrizes→`peso_vaca` (17), bois→`peso_boi` (20), jovens fêmeas→`peso_bezerra` (8), jovens machos→`peso_garrote` (12). Reusa os pesos já existentes em `calcular_ano`.

---

## Fase A — Padronização de custos em R$/@

### Task A1: Helper de peso do rebanho em arrobas

**Files:**
- Create: `services/pesos_rebanho.py`
- Test: `tests/test_pesos_rebanho.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pesos_rebanho.py
from services.pesos_rebanho import arrobas_categorias

def test_soma_arrobas_por_categoria():
    # 10 matrizes×17 + 2 bois×20 + 4 fêmeas jovens×8 + 6 machos jovens×12
    total = arrobas_categorias(matrizes=10, bois=2, jovens_f=4, jovens_m=6,
                               peso_vaca=17, peso_boi=20, peso_bezerra=8, peso_garrote=12)
    assert total == 10*17 + 2*20 + 4*8 + 6*12
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pesos_rebanho.py -v`
Expected: FAIL (ModuleNotFoundError / função inexistente)

- [ ] **Step 3: Write minimal implementation**

```python
# services/pesos_rebanho.py
"""Converte contagem de cabeças por categoria em peso total de arrobas.

Usado para expressar custos em R$/@ (base simétrica à receita, que já é em @).
"""
from __future__ import annotations


def arrobas_categorias(*, matrizes=0.0, bois=0.0, jovens_f=0.0, jovens_m=0.0,
                       peso_vaca=17.0, peso_boi=20.0, peso_bezerra=8.0,
                       peso_garrote=12.0) -> float:
    """Peso total do plantel em @ (soma cabeças×peso_@ por categoria)."""
    return (matrizes * peso_vaca + bois * peso_boi
            + jovens_f * peso_bezerra + jovens_m * peso_garrote)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pesos_rebanho.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/pesos_rebanho.py tests/test_pesos_rebanho.py
git commit -m "feat: helper de peso do rebanho em arrobas"
```

### Task A2: `calcular_ano` usa custo_arroba

**Files:**
- Modify: `ml_engine.py:535-577` (assinatura e cálculo de custo)
- Test: `tests/test_custo_arroba.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_custo_arroba.py
from ml_engine import calcular_ano

def test_calcular_ano_custo_em_arroba():
    r = calcular_ano(
        matrizes=100, femeas_024=40, machos_024=40, bois=5,
        nat_pct=0.75, desc_mat_pct=0.15, prop_boi=25, renov_boi_pct=0.2,
        venda_bez_pct=0.3, mort_pct=0.03, preco_arroba=320, custo_arroba=57,
        peso_boi=20, peso_vaca=17, peso_bezerra=8, peso_garrote=12,
    )
    # custo = arrobas do rebanho projetado × 57 (não mais cabeças × 850)
    from services.pesos_rebanho import arrobas_categorias
    arrobas = arrobas_categorias(
        matrizes=r['matrizes_prox'], bois=r['bois_prox'],
        jovens_f=r['femeas_024_prox'], jovens_m=r['machos_024_prox'],
        peso_vaca=17, peso_boi=20, peso_bezerra=8, peso_garrote=12)
    assert abs(r['custo'] - arrobas * 57) < 1.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_custo_arroba.py::test_calcular_ano_custo_em_arroba -v`
Expected: FAIL (`calcular_ano` ainda recebe `custo_cab_ano` e multiplica cabeças)

- [ ] **Step 3: Implementação — editar `ml_engine.py`**

Na assinatura de `calcular_ano` (linha 538), trocar `custo_cab_ano` por `custo_arroba`.
Substituir a linha 577:

```python
# ANTES:
#   custo_tot = total_prox * custo_cab_ano
# DEPOIS:
from services.pesos_rebanho import arrobas_categorias  # topo do módulo
arrobas_rebanho = arrobas_categorias(
    matrizes=mat_prox, bois=bois_prox,
    jovens_f=femeas_024_prx, jovens_m=machos_024_prx,
    peso_vaca=peso_vaca, peso_boi=peso_boi,
    peso_bezerra=peso_bezerra, peso_garrote=peso_garrote)
custo_tot = arrobas_rebanho * custo_arroba
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_custo_arroba.py::test_calcular_ano_custo_em_arroba -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ml_engine.py tests/test_custo_arroba.py
git commit -m "feat: calcular_ano usa custo em R$/@"
```

### Task A3: `_simular_cria` — custo e preço do bezerro em @

**Files:**
- Modify: `ml_engine.py:646-712`
- Test: `tests/test_custo_arroba.py`

- [ ] **Step 1: Write the failing test**

```python
def test_simular_cria_custo_arroba():
    from ml_engine import _simular_cria
    r = _simular_cria(
        [10,10, 8,8, 6,6, 30,2, 40,3], 'conservador',
        nat_pct=75, mort_pct=3, desmama_pct=85, venda_bez_pct=30,
        preco_arroba_bezerro=300, custo_arroba=57, anos=1,
        peso_matriz=17, peso_bezerra=8)
    ano1 = r['anos'][0]
    # custo = (matrizes×17 + fem_recria×8) × 57
    matrizes = 30 + 40; fem_recria = 10 + 8 + 6
    assert abs(ano1['custo'] - (matrizes*17 + fem_recria*8) * 57) < 1.0
    assert r['preco_breakeven_unidade'] == 'R$/arroba'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_custo_arroba.py::test_simular_cria_custo_arroba -v`
Expected: FAIL (assinatura antiga com `preco_bezerro`/`custo_cab_ano`)

- [ ] **Step 3: Implementação — editar `ml_engine.py`**

Assinatura (linha 646-649):

```python
def _simular_cria(
    v, cenario, nat_pct, mort_pct, desmama_pct, venda_bez_pct,
    preco_arroba_bezerro, custo_arroba, anos,
    peso_matriz=17.0, peso_bezerra=8.0,
):
```

Trocar linha 658 (`preco_bz`) e 678-679 (receita/custo):

```python
preco_bz = (preco_arroba_bezerro * m['preco']) * peso_bezerra   # R$/cabeça derivado de R$/@
...
receita   = vez_vendidos * preco_bz
custo     = (matrizes * peso_matriz + fem_recria * peso_bezerra) * custo_arroba
```

Trocar o breakeven (linhas 702-706) para base @:

```python
units = float(max(ano1['vendidos'], 1)) * peso_bezerra
result.update({
    'preco_breakeven':         round(ano1['custo'] / max(units, 1), 2),
    'preco_breakeven_unidade': 'R$/arroba',
    'preco_usado':             preco_bz,
    ...
})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_custo_arroba.py::test_simular_cria_custo_arroba -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ml_engine.py tests/test_custo_arroba.py
git commit -m "feat: _simular_cria em R$/@ (custo e preço do bezerro)"
```

### Task A4: `_simular_recria` e `_simular_engorda` — custo em @ pró-rata

**Files:**
- Modify: `ml_engine.py:714-781` (recria) e `783-859` (engorda)
- Test: `tests/test_custo_arroba.py`

- [ ] **Step 1: Write the failing test**

```python
def test_simular_recria_custo_arroba_prorata():
    from ml_engine import _simular_recria
    r = _simular_recria(
        [0,0, 0,50, 0,30, 0,0, 0,0], 'conservador', mort_pct=3,
        preco_arroba=320, peso_entrada_arr=8, peso_saida_arr=14,
        meses_recria=12, custo_arroba=57, anos=1)
    ano1 = r['anos'][0]
    animais = 50 + 30; peso_medio = (8 + 14) / 2
    esperado = animais * peso_medio * 57 * (12/12)
    assert abs(ano1['custo'] - esperado) < 1.0

def test_simular_engorda_custo_arroba_prorata():
    from ml_engine import _simular_engorda
    r = _simular_engorda(
        [0,0, 0,0, 0,0, 0,20, 0,10], 'conservador', mort_pct=3,
        preco_arroba=320, peso_entrada_kg=350, peso_saida_kg=500,
        rendimento_carcaca=54, custo_arroba=57, dias_engorda=120, anos=1)
    ano1 = r['anos'][0]
    assert ano1['custo'] > 0  # sanidade: custo em @ pró-rata calculado
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_custo_arroba.py -k prorata -v`
Expected: FAIL (assinaturas antigas com `custo_cab_mes`/`custo_cab_dia`)

- [ ] **Step 3: Implementação — editar `ml_engine.py`**

Recria — assinatura (linha 714-717) troca `custo_cab_mes` por `custo_arroba`; linha 745:

```python
peso_medio = (peso_entrada_arr + peso_saida_arr) / 2.0
custo      = animais * peso_medio * custo_arroba * (meses_recria / 12.0)
```

Engorda — assinatura (linha 783-786) troca `custo_cab_dia` por `custo_arroba`; linha 820:

```python
arrobas_media = (arrobas_saida + (peso_entrada_kg * rend) / 15.0) / 2.0
custo         = bois_no_ano * arrobas_media * custo_arroba * (dias_engorda / 365.0)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_custo_arroba.py -k prorata -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add ml_engine.py tests/test_custo_arroba.py
git commit -m "feat: recria e engorda com custo em R$/@ pró-rata"
```

### Task A5: `simular_cenario`, `calcular_breakeven_simples` e defaults

**Files:**
- Modify: `ml_engine.py:861-960` (`simular_cenario`) e `1180-1216` (`calcular_breakeven_simples`)
- Test: `tests/test_custo_arroba.py`

- [ ] **Step 1: Write the failing test**

```python
def test_simular_cenario_aceita_custo_arroba():
    from ml_engine import simular_cenario
    r = simular_cenario([10,10, 8,8, 6,6, 30,2, 40,3], 'conservador',
                        preco_arroba=320, custo_arroba=57)
    assert 'anos' in r and r['anos'][0]['custo'] > 0

def test_breakeven_simples_em_arroba():
    from ml_engine import calcular_breakeven_simples
    r = calcular_breakeven_simples([10,10, 8,8, 6,6, 30,2, 40,3], 'CRIA')
    assert r['preco_breakeven'] > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_custo_arroba.py -k "cenario or breakeven" -v`
Expected: FAIL (`simular_cenario` passa `custo_cab_ano`/`custo_cab_mes` às sub-funções)

- [ ] **Step 3: Implementação — editar `ml_engine.py`**

Em `simular_cenario`: trocar os params `custo_cab_ano=850.0`, `custo_cab_mes=80.0`
e o `custo_cab_dia` correspondente por um único `custo_arroba: float = 57.0`.
Ajustar as chamadas às sub-funções (linhas ~901, ~906, ~939) para passar
`custo_arroba=custo_arroba` e, em cria, `preco_arroba_bezerro` (novo param, default
`preco_arroba` se não informado) e `peso_matriz`/`peso_bezerra`.
Em `calcular_breakeven_simples` (linha ~1190 e ~1215): trocar
`custo_cab_ano = 850.0` por `custo_arroba = 57.0` e `custo = total * custo_cab_ano`
por:

```python
from services.pesos_rebanho import arrobas_categorias
arrobas = arrobas_categorias(matrizes=..., bois=..., jovens_f=..., jovens_m=...)
custo   = arrobas * custo_arroba
```

(usar a mesma decomposição de `v` que a função já faz para `total`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_custo_arroba.py -v`
Expected: PASS (toda a suíte de custo)

- [ ] **Step 5: Commit**

```bash
git add ml_engine.py tests/test_custo_arroba.py
git commit -m "feat: simular_cenario e breakeven em R$/@ (default 57/@ ano)"
```

---

## Fase B — Módulo de parecer de crédito

### Task B1: Capacidade de pagamento (Price + DSCR)

**Files:**
- Create: `services/parecer_credito.py`
- Test: `tests/test_parecer_credito.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_parecer_credito.py
from services.parecer_credito import avaliar_capacidade_pagamento

def test_price_com_juros():
    r = avaliar_capacidade_pagamento(
        geracao_caixa_anual=120000, credito_valor=100000,
        prazo_meses=12, juros_aa=0.12)
    assert r['parcela_mensal'] > 100000/12  # com juros, parcela > principal/n

def test_price_sem_juros():
    r = avaliar_capacidade_pagamento(
        geracao_caixa_anual=120000, credito_valor=120000,
        prazo_meses=12, juros_aa=0.0)
    assert abs(r['parcela_mensal'] - 10000) < 0.01

def test_dscr_aprovar():
    r = avaliar_capacidade_pagamento(200000, 100000, 24, 0.10)
    assert r['recomendacao'] == 'aprovar' and r['dscr'] >= 1.30

def test_dscr_ressalva():
    r = avaliar_capacidade_pagamento(60000, 100000, 24, 0.10)
    assert r['recomendacao'] == 'ressalva' and 1.0 <= r['dscr'] < 1.30

def test_dscr_negar():
    r = avaliar_capacidade_pagamento(20000, 100000, 12, 0.10)
    assert r['recomendacao'] == 'negar' and r['dscr'] < 1.0

def test_geracao_negativa_nega():
    r = avaliar_capacidade_pagamento(-5000, 100000, 12, 0.10)
    assert r['recomendacao'] == 'negar'

def test_sem_credito_sem_conclusao():
    r = avaliar_capacidade_pagamento(120000, 0, 12, 0.10)
    assert r['dscr'] is None and r['recomendacao'] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_parecer_credito.py -v`
Expected: FAIL (módulo inexistente)

- [ ] **Step 3: Write minimal implementation**

```python
# services/parecer_credito.py
"""Parecer de crédito: capacidade de pagamento (Price + DSCR) e montagem.

Módulo puro — não importa Flask nem DB. Recebe números já computados.
"""
from __future__ import annotations

# Faixas de política de crédito (DSCR) — ajustáveis, não são benchmark zootécnico.
DSCR_APROVAR = 1.30
DSCR_RESSALVA = 1.00


def parcela_price(pv: float, juros_aa: float, n_meses: int) -> float:
    """Parcela mensal por amortização Price. juros_aa nominal anual."""
    if n_meses <= 0 or pv <= 0:
        return 0.0
    i = (1 + juros_aa) ** (1 / 12) - 1
    if i <= 0:
        return pv / n_meses
    return pv * i / (1 - (1 + i) ** (-n_meses))


def avaliar_capacidade_pagamento(
    geracao_caixa_anual: float,
    credito_valor: float,
    prazo_meses: int,
    juros_aa: float,
    carencia_meses: int = 0,
    dividas_mensais: float = 0.0,
) -> dict:
    n = max(prazo_meses - carencia_meses, 0)
    parcela = parcela_price(credito_valor, juros_aa, n)
    servico_anual = 12 * (parcela + max(dividas_mensais, 0.0))

    if servico_anual <= 0:
        return {'dscr': None, 'parcela_mensal': round(parcela, 2),
                'servico_divida_anual': 0.0,
                'geracao_caixa_anual': round(geracao_caixa_anual, 2),
                'recomendacao': None, 'faixa': None,
                'justificativa': 'Sem crédito a avaliar.'}

    dscr = geracao_caixa_anual / servico_anual
    if geracao_caixa_anual <= 0:
        rec, just = 'negar', 'Operação não gera caixa positivo — sem capacidade de pagamento.'
    elif dscr >= DSCR_APROVAR:
        rec, just = 'aprovar', f'Cobertura {dscr:.2f} — folga confortável sobre o serviço da dívida.'
    elif dscr >= DSCR_RESSALVA:
        rec, just = 'ressalva', f'Cobertura {dscr:.2f} — operação cobre a dívida com folga estreita.'
    else:
        rec, just = 'negar', f'Cobertura {dscr:.2f} — geração de caixa insuficiente para o serviço da dívida.'

    return {'dscr': round(dscr, 2), 'parcela_mensal': round(parcela, 2),
            'servico_divida_anual': round(servico_anual, 2),
            'geracao_caixa_anual': round(geracao_caixa_anual, 2),
            'recomendacao': rec, 'faixa': rec, 'justificativa': just}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_parecer_credito.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/parecer_credito.py tests/test_parecer_credito.py
git commit -m "feat: capacidade de pagamento (Price + DSCR)"
```

### Task B2: Montagem do parecer + rebaixamento por consistência

**Files:**
- Modify: `services/parecer_credito.py`
- Test: `tests/test_parecer_credito.py`

- [ ] **Step 1: Write the failing test**

```python
def test_montar_parecer_ordena_e_conclui():
    from services.parecer_credito import montar_parecer
    p = montar_parecer(
        identificacao={'fazenda': 'X', 'proprietario': 'Y'},
        composicao={'total': 200}, indicadores={}, benchmarks=[],
        consistencia={'score_consistencia': 90, 'flags': [], 'resumo': {'erros': 0}},
        financeiro={'preco_breakeven': 50},
        geracao_caixa_anual=200000,
        credito={'credito_valor': 100000, 'prazo_meses': 24,
                 'juros_aa': 0.10, 'carencia_meses': 0, 'dividas_mensais': 0})
    assert p['conclusao']['recomendacao'] == 'aprovar'
    assert list(p['secoes']) == ['identificacao', 'composicao', 'indicadores',
                                 'consistencia', 'financeiro', 'conclusao']

def test_erro_consistencia_rebaixa_para_ressalva():
    from services.parecer_credito import montar_parecer
    p = montar_parecer(
        identificacao={}, composicao={}, indicadores={}, benchmarks=[],
        consistencia={'score_consistencia': 40, 'flags': [], 'resumo': {'erros': 2}},
        financeiro={}, geracao_caixa_anual=500000,
        credito={'credito_valor': 100000, 'prazo_meses': 24,
                 'juros_aa': 0.10, 'carencia_meses': 0, 'dividas_mensais': 0})
    assert p['conclusao']['recomendacao'] == 'ressalva'
    assert 'consistência' in p['conclusao']['justificativa'].lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_parecer_credito.py -k montar -v`
Expected: FAIL (`montar_parecer` inexistente)

- [ ] **Step 3: Write minimal implementation (append em `services/parecer_credito.py`)**

```python
def montar_parecer(*, identificacao, composicao, indicadores, benchmarks,
                   consistencia, financeiro, geracao_caixa_anual, credito) -> dict:
    conclusao = avaliar_capacidade_pagamento(
        geracao_caixa_anual=geracao_caixa_anual,
        credito_valor=float(credito.get('credito_valor') or 0),
        prazo_meses=int(credito.get('prazo_meses') or 0),
        juros_aa=float(credito.get('juros_aa') or 0),
        carencia_meses=int(credito.get('carencia_meses') or 0),
        dividas_mensais=float(credito.get('dividas_mensais') or 0))

    erros = (consistencia or {}).get('resumo', {}).get('erros', 0)
    if erros and conclusao['recomendacao'] == 'aprovar':
        conclusao = dict(conclusao, recomendacao='ressalva',
                         justificativa=conclusao['justificativa']
                         + f' Rebaixado: {erros} erro(s) de consistência no rebanho declarado invalidam a projeção.')

    return {
        'secoes': ['identificacao', 'composicao', 'indicadores',
                   'consistencia', 'financeiro', 'conclusao'],
        'identificacao': identificacao,
        'composicao': composicao,
        'indicadores': {'valores': indicadores, 'benchmarks': benchmarks},
        'consistencia': consistencia,
        'financeiro': financeiro,
        'conclusao': conclusao,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_parecer_credito.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/parecer_credito.py tests/test_parecer_credito.py
git commit -m "feat: montar_parecer com rebaixamento por consistência"
```

---

## Fase C — Persistência por fazenda

### Task C1: Tabela `pareceres` + funções de gravação/listagem

**Files:**
- Modify: `database.py` (bloco de `CREATE TABLE`, ~linha 180, e novas funções ao final)
- Test: `tests/test_pareceres_db.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pareceres_db.py
import json, database as db

def test_salvar_e_listar_parecer(tmp_path, monkeypatch):
    db.init_db()
    fid = db.criar_fazenda('Faz Teste', user_id=1)
    pid = db.salvar_parecer(user_id=1, fazenda_id=fid,
                            solicitacao={'credito_valor': 100000},
                            parecer={'conclusao': {'recomendacao': 'aprovar', 'dscr': 1.4}})
    assert pid
    itens = db.listar_pareceres(fazenda_id=fid, user_id=1)
    assert itens and itens[0]['recomendacao'] == 'aprovar'
    assert json.loads(itens[0]['solicitacao'])['credito_valor'] == 100000
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_pareceres_db.py -v`
Expected: FAIL (`salvar_parecer` inexistente)

- [ ] **Step 3: Implementação — editar `database.py`**

Adicionar no `init_db` (após a tabela `meta`, ~linha 180):

```python
_exec(f'''
    CREATE TABLE IF NOT EXISTS pareceres (
        id           {_AI},
        fazenda_id   INTEGER,
        user_id      INTEGER NOT NULL,
        solicitacao  TEXT,
        parecer      TEXT,
        recomendacao TEXT,
        dscr         REAL,
        created_at   TIMESTAMP DEFAULT {_NOW}
    )
''', commit=True)
```

Adicionar ao final do módulo:

```python
def salvar_parecer(user_id, fazenda_id, solicitacao: dict, parecer: dict) -> int:
    import json
    concl = (parecer or {}).get('conclusao', {})
    return _exec(
        '''INSERT INTO pareceres (fazenda_id, user_id, solicitacao, parecer,
                                  recomendacao, dscr)
           VALUES (?, ?, ?, ?, ?, ?)''',
        (fazenda_id, user_id, json.dumps(solicitacao), json.dumps(parecer),
         concl.get('recomendacao'), concl.get('dscr')),
        commit=True, return_id=True)


def listar_pareceres(fazenda_id, user_id, limit: int = 30) -> list:
    rows = _exec(
        '''SELECT id, solicitacao, parecer, recomendacao, dscr, created_at
           FROM pareceres WHERE fazenda_id = ? AND user_id = ?
           ORDER BY created_at DESC LIMIT ?''',
        (fazenda_id, user_id, limit), fetch='all')
    return [dict(r) for r in rows] if rows else []
```

> Se `_exec` não suportar `return_id`/`fetch`, seguir o padrão já usado por
> `criar_fazenda`/`historico_fazenda` (ler essas funções em `database.py:248` e
> `:291` e replicar a mesma mecânica de cursor/commit).

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_pareceres_db.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add database.py tests/test_pareceres_db.py
git commit -m "feat: persistência de pareceres por fazenda"
```

---

## Fase D — Integração no endpoint

### Task D1: `/api/classificar` roda consistência + monta e salva parecer

**Files:**
- Modify: `app.py:315-379`
- Test: `tests/test_classificar_parecer.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_classificar_parecer.py
import json
from app import app

def test_classificar_retorna_parecer_e_consistencia():
    client = app.test_client()
    # login fictício depende do helper de teste existente; se houver fixture de
    # auth em tests/, reutilizá-la. Aqui validamos o shape da resposta.
    payload = {'valores': [10,10, 8,8, 6,6, 30,2, 40,3],
               'preco': 320, 'custo_arroba': 57,
               'credito_valor': 100000, 'prazo_meses': 24,
               'juros_aa': 0.10}
    with client.session_transaction() as s:
        s['_user_id'] = '1'  # ajustar conforme o mecanismo de login dos testes
    r = client.post('/api/classificar', json=payload)
    data = r.get_json()
    assert 'consistencia' in data
    assert 'parecer' in data and 'conclusao' in data['parecer']
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_classificar_parecer.py -v`
Expected: FAIL (resposta ainda sem `parecer`/`consistencia`)

- [ ] **Step 3: Implementação — editar `app.py`**

Em `api_classificar`, após computar `benchmarks`/`breakeven` e antes do `return`:

```python
from services.consistencia_rebanho import analisar_consistencia
from services.parecer_credito import montar_parecer
from ml_engine import simular_cenario

consistencia = analisar_consistencia(v)

_cx = simular_cenario(v, 'conservador',
                      preco_arroba=float(data.get('preco', 320)),
                      custo_arroba=float(data.get('custo_arroba', 57)))
geracao_caixa_anual = _cx['anos'][0]['resultado']

parecer = montar_parecer(
    identificacao={'fazenda': fazenda, 'municipio': municipio,
                   'proprietario': data.get('proprietario', '')},
    composicao={'total': int(sum(v)), 'valores': v},
    indicadores=ind, benchmarks=benchmarks,
    consistencia=consistencia, financeiro=breakeven,
    geracao_caixa_anual=geracao_caixa_anual,
    credito={k: data.get(k) for k in
             ('credito_valor', 'prazo_meses', 'juros_aa',
              'carencia_meses', 'dividas_mensais')})

fazenda_id = data.get('fazenda_id')
if fazenda_id and data.get('credito_valor'):
    db.salvar_parecer(current_user.id, int(fazenda_id),
                      solicitacao={k: data.get(k) for k in
                                   ('credito_valor', 'prazo_meses', 'juros_aa',
                                    'carencia_meses', 'dividas_mensais')},
                      parecer=parecer)
```

Adicionar `consistencia` e `parecer` ao dict do `jsonify` (linha 370-378).

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_classificar_parecer.py -v`
Expected: PASS (ajustar o mock de login ao helper real de `tests/` se necessário)

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_classificar_parecer.py
git commit -m "feat: /api/classificar monta consistência + parecer e persiste"
```

---

## Fase E — UI

### Task E1: Grupo "Solicitação de Crédito" no formulário

**Files:**
- Modify: `templates/index.html` (formulário de entrada; enviar os campos no fetch de `/api/classificar`)

- [ ] **Step 1: Adicionar os inputs**

No formulário de análise, adicionar um bloco (mesmo estilo dos demais grupos):

```html
<div class="card" style="margin-bottom:24px">
  <div class="ch"><div class="ct">Solicitação de Crédito</div></div>
  <div class="cb" style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
    <label>Valor solicitado (R$) <input id="credito_valor" type="number" min="0"></label>
    <label>Prazo (meses) <input id="credito_prazo" type="number" min="1"></label>
    <label>Carência (meses) <input id="credito_carencia" type="number" min="0" value="0"></label>
    <label>Juros (% a.a.) <input id="credito_juros" type="number" step="0.1" min="0"></label>
    <label>Dívidas mensais (R$/mês) <input id="dividas_mensais" type="number" min="0" value="0"></label>
    <label>Finalidade
      <select id="credito_finalidade"><option>custeio</option><option>investimento</option></select>
    </label>
  </div>
</div>
```

- [ ] **Step 2: Enviar os campos no fetch**

No corpo do POST para `/api/classificar`, incluir:

```javascript
credito_valor: +document.getElementById('credito_valor').value || 0,
prazo_meses: +document.getElementById('credito_prazo').value || 0,
carencia_meses: +document.getElementById('credito_carencia').value || 0,
juros_aa: (+document.getElementById('credito_juros').value || 0) / 100,
dividas_mensais: +document.getElementById('dividas_mensais').value || 0,
credito_finalidade: document.getElementById('credito_finalidade').value,
```

- [ ] **Step 3: Verificar no navegador**

Abrir a app, preencher, enviar e confirmar no painel de rede que os campos chegam
ao `/api/classificar` e que a resposta traz `parecer`.

- [ ] **Step 4: Commit**

```bash
git add templates/index.html
git commit -m "feat: formulário de Solicitação de Crédito"
```

### Task E2: Seção "Parecer" (destaque na conclusão)

**Files:**
- Modify: `templates/index.html` (nova função `renderParecer(data)` + card na render)

- [ ] **Step 1: Render da seção**

Adicionar um card que chama `renderParecer(data)` e a função:

```javascript
function renderParecer(data){
  const p = data.parecer; if(!p) return '';
  const c = p.conclusao;
  const cor = {aprovar:'#4ADE80', ressalva:'#FBBF24', negar:'#F87171'}[c.recomendacao] || '#8891A5';
  const concl = c.recomendacao
    ? `<div style="padding:14px;border-radius:8px;border:1px solid ${cor}55;background:${cor}12">
         <div style="font-weight:800;text-transform:uppercase;color:${cor}">${c.recomendacao}</div>
         <div style="font-family:var(--fm);font-size:.7rem;color:var(--mu)">
           DSCR ${c.dscr} · parcela ${fR(c.parcela_mensal)}/mês</div>
         <div style="margin-top:6px">${c.justificativa}</div>
       </div>`
    : `<div class="mrow"><span class="mk" style="opacity:.6">Informe a solicitação de crédito para a conclusão.</span></div>`;
  return `<div style="font-weight:700;margin-bottom:8px">Parecer</div>${concl}`;
}
```

- [ ] **Step 2: Verificar no navegador**

Rodar um caso aprovar, um ressalva (com erro de consistência) e um negar; conferir
cor e texto da conclusão.

- [ ] **Step 3: Commit**

```bash
git add templates/index.html
git commit -m "feat: seção Parecer com conclusão de crédito destacada"
```

### Task E3: Rótulos de custo/preço em R$/@

**Files:**
- Modify: `templates/index.html` (labels dos campos de custo) e envio do campo `custo_arroba`

- [ ] **Step 1: Trocar rótulos e o nome do campo**

Renomear o input de custo para `custo_arroba`, rótulo "Custo (R$/@·ano)", e no fetch
enviar `custo_arroba: +document.getElementById('custo_arroba').value || 57`.
Garantir que nenhum rótulo diga "R$/cabeça".

- [ ] **Step 2: Verificar no navegador**

Conferir que a análise usa o custo em @ e o breakeven aparece em R$/@.

- [ ] **Step 3: Commit**

```bash
git add templates/index.html
git commit -m "feat: custo/preço da UI em R$/@"
```

---

## Fase F — Fechamento

### Task F1: Suíte completa + smoke manual

- [ ] **Step 1: Rodar toda a suíte**

Run: `python -m pytest tests/ -v`
Expected: PASS (novos testes + regressões existentes de benchmarks/ml_engine).
Se algum teste antigo assumir `custo_cab_ano`, atualizá-lo para `custo_arroba`.

- [ ] **Step 2: Smoke no navegador**

Fluxo completo: importar/inserir composição → preencher solicitação de crédito →
ver parecer com conclusão → confirmar persistência (nova linha em `pareceres`).

- [ ] **Step 3: Commit final (se houver ajustes de teste)**

```bash
git add -A
git commit -m "test: alinhar suíte à base de custo em R$/@"
```
