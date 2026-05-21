# Ponto de Equilíbrio + Benchmarks RO — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar ponto de equilíbrio com slider interativo e benchmarks regionais de Rondônia ao BoviML.

**Architecture:** Backend adiciona `BENCHMARKS_RO` + `avaliar_benchmarks()` + `calcular_breakeven_simples()` em `ml_engine.py`. Cada função de simulação retorna `preco_breakeven` + dados do slider. `/api/classificar` retorna `benchmarks` + `breakeven_estimado`. Frontend adiciona card de benchmarks + breakeven compacto na aba "Resultado" e card completo com slider na aba "Simular Cenários".

**Tech Stack:** Python/Flask, pytest, HTML/CSS/JS puro.

---

## Arquivos modificados

| Arquivo | Mudança |
|---------|---------|
| `ml_engine.py` | Adicionar `BENCHMARKS_RO`, `_classificar_faixa`, `avaliar_benchmarks`, `calcular_breakeven_simples`; enriquecer funções `_simular_*` e CICLO_COMPLETO com breakeven |
| `app.py` | Atualizar import de `ml_engine`; enriquecer resposta de `/api/classificar` |
| `templates/index.html` | Adicionar `renderBenchmarksHTML`, `renderBreakevenCompactoHTML`, `renderBreakevenHTML`, `atualizarSlider`; atualizar `renderResult` e `renderSc` |
| `tests/test_ml_engine.py` | Criar testes para as novas funções |

---

## Task 1: Benchmarks — constante e função de avaliação

**Files:**
- Modify: `ml_engine.py`
- Create: `tests/test_ml_engine.py`

- [ ] **Passo 1: Criar arquivo de testes**

Criar `tests/__init__.py` (vazio) e `tests/test_ml_engine.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import pytest
from ml_engine import _classificar_faixa, avaliar_benchmarks, BENCHMARKS_RO


def test_classificar_faixa_normal_abaixo():
    faixas = {'abaixo': 65.0, 'medio': 78.0, 'bom': 88.0}
    faixa, proximo, falta = _classificar_faixa(60.0, faixas)
    assert faixa == 'abaixo'
    assert proximo == 'medio'
    assert falta == 5.0


def test_classificar_faixa_normal_medio():
    faixas = {'abaixo': 65.0, 'medio': 78.0, 'bom': 88.0}
    faixa, proximo, falta = _classificar_faixa(70.0, faixas)
    assert faixa == 'medio'
    assert proximo == 'bom'
    assert falta == 8.0


def test_classificar_faixa_normal_bom():
    faixas = {'abaixo': 65.0, 'medio': 78.0, 'bom': 88.0}
    faixa, proximo, falta = _classificar_faixa(82.0, faixas)
    assert faixa == 'bom'
    assert proximo == 'excelente'
    assert falta == 6.0


def test_classificar_faixa_normal_excelente():
    faixas = {'abaixo': 65.0, 'medio': 78.0, 'bom': 88.0}
    faixa, proximo, falta = _classificar_faixa(90.0, faixas)
    assert faixa == 'excelente'
    assert proximo is None
    assert falta == 0.0


def test_classificar_faixa_inverso_abaixo():
    # mortalidade: menor é melhor
    faixas = {'abaixo': 5.0, 'medio': 3.0, 'bom': 1.5}
    faixa, proximo, falta = _classificar_faixa(6.0, faixas, inverso=True)
    assert faixa == 'abaixo'
    assert proximo == 'medio'
    assert falta == 1.0


def test_classificar_faixa_inverso_excelente():
    faixas = {'abaixo': 5.0, 'medio': 3.0, 'bom': 1.5}
    faixa, proximo, falta = _classificar_faixa(1.0, faixas, inverso=True)
    assert faixa == 'excelente'
    assert falta == 0.0


def test_avaliar_benchmarks_cria_filtra_ciclo():
    indicadores = {
        'natalidade': 75.0, 'mortalidade': 3.0, 'desmama': 80.0,
        'relacao_fm': 2.2, 'pct_matrizes': 35.0,
        'ganho_peso_arr': 0.7, 'rend_carcaca': 52.0,
    }
    resultado = avaliar_benchmarks('CRIA', indicadores)
    keys = [r['key'] for r in resultado]
    # CRIA não deve incluir ganho_peso_arr (só RECRIA)
    assert 'ganho_peso_arr' not in keys
    # CRIA deve incluir natalidade e pct_matrizes
    assert 'natalidade' in keys
    assert 'pct_matrizes' in keys


def test_avaliar_benchmarks_engorda_filtra_ciclo():
    indicadores = {
        'natalidade': 75.0, 'mortalidade': 2.0, 'rend_carcaca': 53.0,
        'ganho_peso_arr': 0.7, 'relacao_fm': 2.0, 'pct_matrizes': 30.0,
        'desmama': 80.0,
    }
    resultado = avaliar_benchmarks('ENGORDA', indicadores)
    keys = [r['key'] for r in resultado]
    assert 'rend_carcaca' in keys
    assert 'natalidade' not in keys
    assert 'ganho_peso_arr' not in keys


def test_avaliar_benchmarks_retorna_estrutura_correta():
    indicadores = {'natalidade': 75.0, 'mortalidade': 3.0, 'desmama': 82.0,
                   'relacao_fm': 2.0, 'pct_matrizes': 30.0}
    resultado = avaliar_benchmarks('CRIA', indicadores)
    assert len(resultado) > 0
    item = resultado[0]
    assert 'key' in item
    assert 'label' in item
    assert 'valor' in item
    assert 'unidade' in item
    assert 'faixa' in item
    assert 'proximo_nivel' in item
    assert 'falta' in item
```

- [ ] **Passo 2: Rodar os testes — devem falhar**

```
cd c:\Users\Lucas\Downloads\boviml_python\boviml
python -m pytest tests/test_ml_engine.py -v
```

Esperado: `ImportError` ou `AttributeError` — funções ainda não existem.

- [ ] **Passo 3: Adicionar `BENCHMARKS_RO`, `_classificar_faixa` e `avaliar_benchmarks` em `ml_engine.py`**

Adicionar ANTES da linha `CENARIOS = {` (buscar essa linha):

```python
# ───────────────────────────────────────────��─
# BENCHMARKS — Médias Regionais Rondônia
# ─────────────────────────────────────────────
BENCHMARKS_RO = {
    'natalidade': {
        'label': 'Taxa de Natalidade',
        'unidade': '%',
        'faixas': {'abaixo': 65.0, 'medio': 78.0, 'bom': 88.0},
        'inverso': False,
        'ciclos': ['CRIA', 'CICLO_COMPLETO'],
    },
    'mortalidade': {
        'label': 'Mortalidade Geral',
        'unidade': '%',
        'faixas': {'abaixo': 5.0, 'medio': 3.0, 'bom': 1.5},
        'inverso': True,
        'ciclos': ['CRIA', 'RECRIA', 'ENGORDA', 'CICLO_COMPLETO'],
    },
    'desmama': {
        'label': 'Taxa de Desmama',
        'unidade': '%',
        'faixas': {'abaixo': 70.0, 'medio': 82.0, 'bom': 90.0},
        'inverso': False,
        'ciclos': ['CRIA', 'CICLO_COMPLETO'],
    },
    'relacao_fm': {
        'label': 'Relação Fêmeas/Macho Adulto',
        'unidade': ':1',
        'faixas': {'abaixo': 1.8, 'medio': 2.2, 'bom': 2.8},
        'inverso': False,
        'ciclos': ['CRIA', 'CICLO_COMPLETO'],
    },
    'pct_matrizes': {
        'label': '% Matrizes no Rebanho',
        'unidade': '%',
        'faixas': {'abaixo': 28.0, 'medio': 35.0, 'bom': 42.0},
        'inverso': False,
        'ciclos': ['CRIA', 'CICLO_COMPLETO'],
    },
    'ganho_peso_arr': {
        'label': 'Ganho de Peso (@/mês)',
        'unidade': '@/mês',
        'faixas': {'abaixo': 0.5, 'medio': 0.7, 'bom': 0.9},
        'inverso': False,
        'ciclos': ['RECRIA'],
    },
    'rend_carcaca': {
        'label': 'Rendimento de Carcaça',
        'unidade': '%',
        'faixas': {'abaixo': 50.0, 'medio': 52.0, 'bom': 54.0},
        'inverso': False,
        'ciclos': ['ENGORDA', 'CICLO_COMPLETO'],
    },
}


def _classificar_faixa(valor: float, faixas: dict, inverso: bool = False) -> tuple:
    """Retorna (faixa, proximo_nivel, falta) comparando valor com thresholds regionais."""
    t_a, t_m, t_b = faixas['abaixo'], faixas['medio'], faixas['bom']
    if not inverso:
        if valor >= t_b:
            return 'excelente', None, 0.0
        elif valor >= t_m:
            return 'bom', 'excelente', round(t_b - valor, 2)
        elif valor >= t_a:
            return 'medio', 'bom', round(t_m - valor, 2)
        else:
            return 'abaixo', 'medio', round(t_a - valor, 2)
    else:
        if valor <= t_b:
            return 'excelente', None, 0.0
        elif valor <= t_m:
            return 'bom', 'excelente', round(valor - t_b, 2)
        elif valor <= t_a:
            return 'medio', 'bom', round(valor - t_m, 2)
        else:
            return 'abaixo', 'medio', round(valor - t_a, 2)


def avaliar_benchmarks(ciclo: str, indicadores: dict) -> list:
    """Avalia indicadores do rebanho contra benchmarks regionais de Rondônia."""
    resultado = []
    for key, cfg in BENCHMARKS_RO.items():
        if ciclo not in cfg['ciclos']:
            continue
        valor = indicadores.get(key)
        if valor is None:
            continue
        faixa, proximo, falta = _classificar_faixa(
            float(valor), cfg['faixas'], cfg.get('inverso', False)
        )
        resultado.append({
            'key': key,
            'label': cfg['label'],
            'valor': round(float(valor), 2),
            'unidade': cfg['unidade'],
            'faixa': faixa,
            'proximo_nivel': proximo,
            'falta': falta,
        })
    return resultado
```

- [ ] **Passo 4: Rodar os testes — devem passar**

```
python -m pytest tests/test_ml_engine.py -v
```

Esperado: todos os 9 testes `PASSED`.

- [ ] **Passo 5: Commit**

```bash
git add tests/__init__.py tests/test_ml_engine.py ml_engine.py
git commit -m "feat: add BENCHMARKS_RO and avaliar_benchmarks for Rondônia regional benchmarks"
```

---

## Task 2: Ponto de equilíbrio nas funções de simulação

**Files:**
- Modify: `ml_engine.py`
- Modify: `tests/test_ml_engine.py`

- [ ] **Passo 1: Adicionar testes de breakeven**

Adicionar ao final de `tests/test_ml_engine.py`:

```python
from ml_engine import simular_cenario, calcular_breakeven_simples


def test_simular_cria_retorna_breakeven():
    v = [300, 280, 200, 80, 100, 40, 150, 10, 600, 15]
    result = simular_cenario(v, 'crescimento', ciclo='CRIA', preco_bezerro=1800,
                             nat_pct=75, mort_pct=3, desmama_pct=80,
                             venda_bez_pct=60, custo_cab_ano=850)
    assert 'preco_breakeven' in result
    assert result['preco_breakeven'] > 0
    assert result['preco_breakeven_unidade'] == 'R$/cabeça'
    assert 'slider_units' in result
    assert 'slider_custo_ano1' in result
    assert 'margem_atual_pct' in result


def test_simular_engorda_retorna_breakeven():
    v = [10, 8, 20, 18, 50, 80, 20, 120, 10, 400]
    result = simular_cenario(v, 'crescimento', ciclo='ENGORDA', preco_arroba=330,
                             mort_pct=2, peso_entrada_kg=300, peso_saida_kg=520,
                             rendimento_carcaca=52, custo_cab_dia=12, dias_engorda=90)
    assert 'preco_breakeven' in result
    assert result['preco_breakeven_unidade'] == 'R$/arroba'
    assert result['preco_breakeven'] < result['preco_usado']  # deve ser lucrativo


def test_simular_recria_retorna_breakeven():
    v = [50, 45, 80, 70, 400, 600, 100, 80, 80, 20]
    result = simular_cenario(v, 'crescimento', ciclo='RECRIA', preco_arroba=300,
                             mort_pct=2, peso_entrada_arr=8, peso_saida_arr=14,
                             meses_recria=12, custo_cab_mes=80)
    assert 'preco_breakeven' in result
    assert result['preco_breakeven_unidade'] == 'R$/arroba'


def test_simular_ciclo_completo_retorna_breakeven():
    v = [300, 280, 400, 200, 900, 1200, 250, 80, 600, 40]
    result = simular_cenario(v, 'crescimento')
    assert 'preco_breakeven' in result
    assert result['preco_breakeven'] > 0


def test_calcular_breakeven_simples_cria():
    v = [300, 280, 200, 80, 100, 40, 150, 10, 600, 15]
    result = calcular_breakeven_simples(v, 'CRIA')
    assert 'preco_breakeven' in result
    assert result['unidade'] == 'R$/cabeça'
    assert result['preco_breakeven'] > 0


def test_calcular_breakeven_simples_engorda():
    v = [10, 8, 20, 18, 50, 80, 20, 120, 10, 400]
    result = calcular_breakeven_simples(v, 'ENGORDA')
    assert result['unidade'] == 'R$/arroba'
    assert result['preco_breakeven'] > 0
```

- [ ] **Passo 2: Rodar — devem falhar**

```
python -m pytest tests/test_ml_engine.py -v -k "breakeven"
```

Esperado: `FAILED` — funções ainda não retornam esses campos.

- [ ] **Passo 3: Adicionar dados de breakeven em `_simular_cria`**

Localizar o `return result` final de `_simular_cria` e substituir por:

```python
    result = _montar_resultado(cenario, sc, anos_proj, total_ini, 'CRIA')
    ano1 = anos_proj[0]
    units = float(max(ano1['vendidos'], 1))
    result.update({
        'preco_breakeven':          round(ano1['custo'] / units, 2),
        'preco_breakeven_unidade':  'R$/cabeça',
        'preco_usado':              preco_bz,
        'slider_units':             units,
        'slider_custo_ano1':        ano1['custo'],
        'margem_atual_pct':         round(ano1['resultado'] / max(ano1['custo'], 1) * 100, 1),
        'margem_atual_rs':          round(ano1['resultado'], 2),
    })
    return result
```

- [ ] **Passo 4: Adicionar dados de breakeven em `_simular_recria`**

Localizar o `return result` final de `_simular_recria` e substituir por:

```python
    result = _montar_resultado(cenario, sc, anos_proj, total_ini, 'RECRIA')
    ano1 = anos_proj[0]
    units = float(max(ano1['vendidos'], 1)) * peso_saida_arr
    result.update({
        'preco_breakeven':          round(ano1['custo'] / max(units, 1), 2),
        'preco_breakeven_unidade':  'R$/arroba',
        'preco_usado':              preco,
        'slider_units':             round(units, 2),
        'slider_custo_ano1':        ano1['custo'],
        'margem_atual_pct':         round(ano1['resultado'] / max(ano1['custo'], 1) * 100, 1),
        'margem_atual_rs':          round(ano1['resultado'], 2),
    })
    return result
```

- [ ] **Passo 5: Adicionar dados de breakeven em `_simular_engorda`**

Localizar o `return result` final de `_simular_engorda` e substituir por:

```python
    result = _montar_resultado(cenario, sc, anos_proj, total_ini, 'ENGORDA')
    ano1 = anos_proj[0]
    arrobas_por_boi_be = (peso_saida_kg * rend) / 15.0
    units = float(max(ano1['vendidos'], 1)) * arrobas_por_boi_be
    result.update({
        'preco_breakeven':          round(ano1['custo'] / max(units, 1), 2),
        'preco_breakeven_unidade':  'R$/arroba',
        'preco_usado':              preco,
        'slider_units':             round(units, 2),
        'slider_custo_ano1':        ano1['custo'],
        'margem_atual_pct':         round(ano1['resultado'] / max(ano1['custo'], 1) * 100, 1),
        'margem_atual_rs':          round(ano1['resultado'], 2),
    })
    return result
```

- [ ] **Passo 6: Adicionar dados de breakeven no CICLO_COMPLETO**

Localizar `return _montar_resultado(cenario, sc, anos_proj, total_ini, 'CICLO_COMPLETO')` e substituir por:

```python
    result = _montar_resultado(cenario, sc, anos_proj, total_ini, 'CICLO_COMPLETO')
    ano1 = anos_proj[0]
    preco_adj = preco_arroba * m['preco']
    units = float(max(ano1['vendidos'], 1)) * peso_arroba
    result.update({
        'preco_breakeven':          round(ano1['custo'] / max(units, 1), 2),
        'preco_breakeven_unidade':  'R$/arroba',
        'preco_usado':              preco_adj,
        'slider_units':             round(units, 2),
        'slider_custo_ano1':        ano1['custo'],
        'margem_atual_pct':         round(ano1['resultado'] / max(ano1['custo'], 1) * 100, 1),
        'margem_atual_rs':          round(ano1['resultado'], 2),
    })
    return result
```

- [ ] **Passo 7: Adicionar `calcular_breakeven_simples` em `ml_engine.py`**

Adicionar logo após `avaliar_benchmarks`:

```python
def calcular_breakeven_simples(v: list, ciclo: str) -> dict:
    """Estimativa rápida do breakeven usando parâmetros padrão RO. Não precisa de simulação completa."""
    va = np.array(v, dtype=float)
    custo_cab_ano = 850.0

    if ciclo == 'CRIA':
        matrizes  = float(va[6] + va[8])
        total     = float(va.sum()) or 1.0
        custo     = total * custo_cab_ano
        bezerros  = matrizes * 0.75 * 0.80 * 0.60
        if bezerros <= 0:
            return {}
        return {'preco_breakeven': round(custo / bezerros, 2), 'unidade': 'R$/cabeça'}

    if ciclo == 'RECRIA':
        be = round((12 * 80.0) / 14.0, 2)
        return {'preco_breakeven': be, 'unidade': 'R$/arroba'}

    if ciclo == 'ENGORDA':
        arrobas = (520.0 * 0.52) / 15.0
        be = round((90 * 12.0) / arrobas, 2)
        return {'preco_breakeven': be, 'unidade': 'R$/arroba'}

    # CICLO_COMPLETO
    total   = float(va.sum()) or 1.0
    custo   = total * custo_cab_ano
    units   = total * 0.30 * 16.0
    return {'preco_breakeven': round(custo / max(units, 1), 2), 'unidade': 'R$/arroba'}
```

- [ ] **Passo 8: Rodar testes — devem passar**

```
python -m pytest tests/test_ml_engine.py -v
```

Esperado: todos os testes `PASSED`.

- [ ] **Passo 9: Commit**

```bash
git add ml_engine.py tests/test_ml_engine.py
git commit -m "feat: add preco_breakeven and slider data to all simulation functions"
```

---

## Task 3: Atualizar app.py

**Files:**
- Modify: `app.py`

- [ ] **Passo 1: Atualizar import de `ml_engine`**

Localizar:
```python
from ml_engine import (
    treinar_modelo, classificar, calcular_indicadores,
    simular_cenario, retrain_com_dados, carregar_modelo, CENARIOS
)
```

Substituir por:
```python
from ml_engine import (
    treinar_modelo, classificar, calcular_indicadores,
    simular_cenario, retrain_com_dados, carregar_modelo, CENARIOS,
    avaliar_benchmarks, calcular_breakeven_simples,
)
```

- [ ] **Passo 2: Enriquecer resposta de `/api/classificar`**

Localizar em `api_classificar`:
```python
    return jsonify({**result, 'indicadores': ind, 'valores': v, 'registro_id': registro_id})
```

Substituir por:
```python
    ciclo = result['classificacao']
    taxa_nat = float(data.get('taxa_natalidade', 0.75)) * 100
    indicadores_bench = {
        'natalidade':    taxa_nat,
        'mortalidade':   3.0,
        'desmama':       80.0,
        'relacao_fm':    float(ind.get('ratio_fm', 0)),
        'pct_matrizes':  float(ind.get('pct_matrizes', 0)),
        'ganho_peso_arr': 0.6,
        'rend_carcaca':  52.0,
    }
    benchmarks       = avaliar_benchmarks(ciclo, indicadores_bench)
    breakeven_est    = calcular_breakeven_simples(v, ciclo)
    return jsonify({**result, 'indicadores': ind, 'valores': v,
                    'registro_id': registro_id,
                    'benchmarks': benchmarks,
                    'breakeven_estimado': breakeven_est})
```

- [ ] **Passo 3: Verificar que o servidor sobe sem erro**

```
python app.py
```

Esperado: servidor inicia em `http://localhost:5050` sem traceback.

- [ ] **Passo 4: Testar endpoint manualmente**

```
curl -s -X POST http://localhost:5050/api/classificar \
  -H "Content-Type: application/json" \
  -d "{\"valores\":[300,280,200,80,100,40,150,10,600,15]}" | python -m json.tool | findstr "benchmarks\|breakeven"
```

Esperado: resposta contém `"benchmarks"` com lista e `"breakeven_estimado"` com `preco_breakeven`.

- [ ] **Passo 5: Commit**

```bash
git add app.py
git commit -m "feat: /api/classificar returns benchmarks and breakeven_estimado"
```

---

## Task 4: Frontend — benchmarks + breakeven compacto na aba "Resultado"

**Files:**
- Modify: `templates/index.html`

- [ ] **Passo 1: Adicionar funções JS `renderBenchmarksHTML` e `renderBreakevenCompactoHTML`**

Localizar `function mr(k,v,c){` e adicionar ANTES dela:

```js
const _FAIXA_COR   = {abaixo:'var(--rd)', medio:'var(--am)', bom:'var(--g)', excelente:'#22D3EE'};
const _FAIXA_LABEL = {abaixo:'Abaixo da média RO', medio:'Média RO', bom:'Bom ✓', excelente:'Excelente ★'};
const _FAIXA_PCT   = {abaixo:15, medio:42, bom:72, excelente:100};

function renderBenchmarksHTML(benchmarks) {
  if (!benchmarks || !benchmarks.length) return '';
  const itens = benchmarks.map(b => {
    const cor  = _FAIXA_COR[b.faixa];
    const pct  = _FAIXA_PCT[b.faixa];
    const prox = b.proximo_nivel
      ? `Faltam ${b.falta} ${b.unidade} para <strong>${b.proximo_nivel}</strong>`
      : 'Nível máximo atingido ✓';
    return `
      <div style="margin-bottom:14px">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:5px">
          <span style="font-family:var(--fb);font-size:.83rem">${b.label}</span>
          <span style="font-family:var(--fm);font-size:.65rem;color:${cor};background:${cor}1A;padding:2px 9px;border-radius:4px;border:1px solid ${cor}40">${_FAIXA_LABEL[b.faixa]}</span>
        </div>
        <div style="height:7px;background:var(--c2);border-radius:4px;overflow:hidden;border:1px solid var(--b)">
          <div style="width:${pct}%;height:100%;background:${cor};border-radius:3px;transition:width .9s cubic-bezier(.34,1.2,.64,1)"></div>
        </div>
        <div style="display:flex;justify-content:space-between;margin-top:4px">
          <span style="font-family:var(--fm);font-size:.58rem;color:var(--tx)">${b.valor} ${b.unidade}</span>
          <span style="font-family:var(--fm);font-size:.58rem;color:var(--sb)">${prox}</span>
        </div>
      </div>`;
  }).join('');
  return `
    <div class="card" style="margin-top:16px">
      <div class="ch"><div class="ct"><div class="cd" style="background:var(--cy)"></div>Benchmarks — Rondônia</div>
        <span style="font-family:var(--fm);font-size:.55rem;color:var(--mu)">Médias regionais RO · Embrapa/SEAGRI</span>
      </div>
      <div class="cb">${itens}</div>
    </div>`;
}

function renderBreakevenCompactoHTML(be) {
  if (!be || !be.preco_breakeven) return '';
  return `
    <div class="card" style="margin-top:16px">
      <div class="ch"><div class="ct"><div class="cd" style="background:var(--am)"></div>Ponto de Equilíbrio — Estimativa</div>
        <span style="font-family:var(--fm);font-size:.55rem;color:var(--mu)">baseado em custos padrão RO</span>
      </div>
      <div class="cb" style="display:flex;align-items:center;gap:24px">
        <div style="text-align:center">
          <div style="font-family:var(--fm);font-size:.55rem;color:var(--mu);margin-bottom:4px;letter-spacing:1px;text-transform:uppercase">Preço Mínimo</div>
          <div style="font-family:var(--fn);font-weight:800;font-size:2rem;color:var(--rd)">R$&nbsp;${Math.round(be.preco_breakeven).toLocaleString('pt-BR')}</div>
          <div style="font-family:var(--fm);font-size:.6rem;color:var(--mu);margin-top:2px">${be.unidade}</div>
        </div>
        <div style="font-family:var(--fb);font-size:.8rem;color:var(--sb);flex:1">
          Se vender acima desse valor, a operação é lucrativa. Execute a simulação na aba <strong>Simular Cenários</strong> para ver o slider com o preço real do mercado.
        </div>
      </div>
    </div>`;
}
```

- [ ] **Passo 2: Chamar as funções no final de `renderResult`**

Localizar no final de `renderResult`, logo antes do `}` de fechamento (após o `setTimeout` das `dist-bars`):

```js
  },200);
}
```

Substituir por:

```js
  },200);
  if(data.benchmarks && data.benchmarks.length){
    document.getElementById('result-wrap').insertAdjacentHTML('beforeend', renderBenchmarksHTML(data.benchmarks));
  }
  if(data.breakeven_estimado && data.breakeven_estimado.preco_breakeven){
    document.getElementById('result-wrap').insertAdjacentHTML('beforeend', renderBreakevenCompactoHTML(data.breakeven_estimado));
  }
}
```

- [ ] **Passo 3: Testar no browser**

1. Abrir `http://localhost:5050`
2. Clicar em "Cria" (exemplo pré-carregado)
3. Classificar
4. Na aba "Resultado", verificar que aparecem os cards "Benchmarks — Rondônia" e "Ponto de Equilíbrio — Estimativa"

- [ ] **Passo 4: Commit**

```bash
git add templates/index.html
git commit -m "feat: add benchmarks and breakeven compact cards to Resultado tab"
```

---

## Task 5: Frontend — breakeven completo com slider na aba "Simular Cenários"

**Files:**
- Modify: `templates/index.html`

- [ ] **Passo 1: Adicionar variável `sliderData` e funções do slider**

Localizar `let lastVals=null, curSc='otimista', curCiclo='CICLO_COMPLETO';` e substituir por:

```js
let lastVals=null, curSc='otimista', curCiclo='CICLO_COMPLETO', sliderData=null;
```

Localizar `function atualizarParamsCiclo(ciclo){` e adicionar ANTES dela:

```js
function renderBreakevenHTML(d) {
  if (!d.preco_breakeven) return '';
  const be    = d.preco_breakeven;
  const unid  = d.preco_breakeven_unidade || 'R$/arroba';
  const usado = d.preco_usado || be;
  const marg  = d.margem_atual_pct || 0;
  const corM  = marg >= 0 ? 'var(--g)' : 'var(--rd)';
  const slMin = Math.round(be * 0.80);
  const slMax = Math.round(be * 1.50);
  return `
    <div class="card" style="margin-top:16px">
      <div class="ch"><div class="ct"><div class="cd" style="background:var(--am)"></div>Ponto de Equilíbrio — Simulação de Preço</div></div>
      <div class="cb">
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:20px">
          <div style="background:var(--c2);border:1px solid var(--b);border-radius:var(--rs);padding:14px;text-align:center">
            <div style="font-family:var(--fm);font-size:.52rem;letter-spacing:2px;text-transform:uppercase;color:var(--mu);margin-bottom:6px">Preço Mínimo</div>
            <div style="font-family:var(--fn);font-weight:800;font-size:1.5rem;color:var(--rd)">${fR(be)}</div>
            <div style="font-family:var(--fm);font-size:.6rem;color:var(--mu);margin-top:2px">${unid}</div>
          </div>
          <div style="background:var(--c2);border:1px solid var(--b);border-radius:var(--rs);padding:14px;text-align:center">
            <div style="font-family:var(--fm);font-size:.52rem;letter-spacing:2px;text-transform:uppercase;color:var(--mu);margin-bottom:6px">Preço Simulado</div>
            <div style="font-family:var(--fn);font-weight:800;font-size:1.5rem;color:var(--cy)">${fR(usado)}</div>
            <div style="font-family:var(--fm);font-size:.6rem;color:var(--mu);margin-top:2px">${unid}</div>
          </div>
          <div style="background:var(--c2);border:1px solid var(--b);border-radius:var(--rs);padding:14px;text-align:center">
            <div style="font-family:var(--fm);font-size:.52rem;letter-spacing:2px;text-transform:uppercase;color:var(--mu);margin-bottom:6px">Margem Ano 1</div>
            <div style="font-family:var(--fn);font-weight:800;font-size:1.5rem;color:${corM}">${marg>0?'+':''}${marg}%</div>
            <div style="font-family:var(--fm);font-size:.6rem;color:var(--mu);margin-top:2px">${fR(d.margem_atual_rs||0)}</div>
          </div>
        </div>
        <div style="background:var(--c2);border:1px solid var(--b);border-radius:var(--rs);padding:16px">
          <div style="font-family:var(--fm);font-size:.6rem;letter-spacing:2px;text-transform:uppercase;color:var(--mu);margin-bottom:12px">Mover o slider para simular variação de preço</div>
          <input type="range" id="slider-preco" min="${slMin}" max="${slMax}" value="${Math.round(usado)}" step="1"
            style="width:100%;accent-color:var(--g);cursor:pointer;height:6px"
            oninput="atualizarSlider(this.value)">
          <div style="display:flex;justify-content:space-between;margin-top:6px;font-family:var(--fm);font-size:.58rem;color:var(--mu)">
            <span>${fR(slMin)}</span>
            <span id="slider-label" style="color:var(--tx);font-weight:700;font-size:.65rem">${fR(Math.round(usado))}</span>
            <span>${fR(slMax)}</span>
          </div>
          <div style="margin-top:16px;display:grid;grid-template-columns:1fr 1fr;gap:10px">
            <div style="background:var(--c);border:1px solid var(--b);border-radius:10px;padding:14px;text-align:center">
              <div style="font-family:var(--fm);font-size:.52rem;color:var(--mu);margin-bottom:6px">RESULTADO ANO 1</div>
              <div id="slider-res-ano1" style="font-family:var(--fn);font-weight:800;font-size:1.4rem">—</div>
            </div>
            <div style="background:var(--c);border:1px solid var(--b);border-radius:10px;padding:14px;text-align:center">
              <div style="font-family:var(--fm);font-size:.52rem;color:var(--mu);margin-bottom:6px">RESULTADO 5 ANOS</div>
              <div id="slider-res-acum" style="font-family:var(--fn);font-weight:800;font-size:1.4rem">—</div>
            </div>
          </div>
        </div>
      </div>
    </div>`;
}

function atualizarSlider(precoStr) {
  if (!sliderData) return;
  const p = parseFloat(precoStr);
  const lbl = document.getElementById('slider-label');
  if (lbl) lbl.textContent = fR(p);

  const receita1 = p * sliderData.units;
  const result1  = receita1 - sliderData.custo_ano1;
  const el1 = document.getElementById('slider-res-ano1');
  if (el1) { el1.textContent = fR(result1); el1.style.color = result1 >= 0 ? 'var(--g)' : 'var(--rd)'; }

  const ratio     = sliderData.preco_usado > 0 ? p / sliderData.preco_usado : 1;
  const recAcum   = sliderData.acumulado_receita * ratio;
  const resAcum   = recAcum - sliderData.acumulado_custo;
  const el2 = document.getElementById('slider-res-acum');
  if (el2) { el2.textContent = fR(resAcum); el2.style.color = resAcum >= 0 ? 'var(--g)' : 'var(--rd)'; }
}
```

- [ ] **Passo 2: Chamar `renderBreakevenHTML` no final de `renderSc`**

Localizar o final de `renderSc`:

```js
    </div>`;
}
```

(o `}` que fecha `renderSc` após o `</div>` final do innerHTML)

Substituir por:

```js
    </div>`;

  if (d.preco_breakeven) {
    sliderData = {
      units:             d.slider_units,
      custo_ano1:        d.slider_custo_ano1,
      preco_usado:       d.preco_usado || d.preco_breakeven,
      acumulado_receita: d.acumulado.receita,
      acumulado_custo:   d.acumulado.custo,
    };
    document.getElementById('sc-result').insertAdjacentHTML('beforeend', renderBreakevenHTML(d));
    atualizarSlider(d.preco_usado || d.preco_breakeven);
  }
}
```

- [ ] **Passo 3: Testar o slider no browser**

1. Abrir `http://localhost:5050`
2. Classificar um rebanho (qualquer exemplo)
3. Ir para aba "Simular Cenários"
4. Clicar em qualquer cenário
5. Verificar que o card "Ponto de Equilíbrio" aparece abaixo da tabela
6. Mover o slider e verificar que "Resultado Ano 1" e "Resultado 5 Anos" atualizam em tempo real
7. Mover o slider abaixo do breakeven — verificar que os valores ficam vermelhos

- [ ] **Passo 4: Commit**

```bash
git add templates/index.html
git commit -m "feat: add breakeven card with interactive price slider to Simular Cenários tab"
```

---

## Self-Review

**Cobertura do spec:**
- ✅ Ponto de equilíbrio calculado no backend por ciclo
- ✅ Slider interativo em "Simular Cenários"
- ✅ Card compacto de breakeven em "Resultado"
- ✅ Benchmarks Rondônia por indicador
- ✅ Filtro de indicadores por ciclo (ENGORDA não vê taxa de desmama, etc.)
- ✅ Barras de progresso com cores por faixa
- ✅ Defaults regionais RO usados quando usuário não tem dados de peso
- ✅ Testes cobrindo faixas normal e inverso (mortalidade)

**Tipos consistentes:**
- `avaliar_benchmarks(ciclo: str, indicadores: dict) -> list` — usado em Task 3
- `calcular_breakeven_simples(v: list, ciclo: str) -> dict` — usado em Task 3
- `sliderData.units` / `sliderData.custo_ano1` — definidos em Task 5, usados em `atualizarSlider`
- `fR()` já existe no frontend para formatar R$

**Sem placeholders:** todo o código está completo.
