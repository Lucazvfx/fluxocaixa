# Peso por Categoria + Validação de Entrada — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Substituir "Preço Boi/Vaca (R$/cab)" por "Peso Boi/Vaca (@)" no Ciclo Completo e adicionar validação inline em tempo real nos campos críticos do formulário.

**Architecture:** Backend: `calcular_ano()` recebe `peso_boi`, `peso_vaca`, `peso_bezerra` ao invés de um único `peso_arroba`; `simular_cenario()` propaga esses valores; `/api/cenario` lê do JSON. Frontend: campos HTML substituídos, `calcCiclo()` atualizado, funções `validarCampo`/`validarTudo` adicionadas com hooks em todos os campos críticos.

**Tech Stack:** Python/Flask, pytest, HTML/JS puro.

---

## Arquivos modificados

| Arquivo | Mudança |
|---------|---------|
| `ml_engine.py` | `calcular_ano()`: trocar `peso_arroba` por `peso_boi`, `peso_vaca`, `peso_bezerra`; `simular_cenario()`: novos parâmetros + peso médio ponderado no breakeven |
| `app.py` | `/api/cenario`: ler `peso_boi` e `peso_vaca` do request |
| `templates/index.html` | Trocar campos HTML; atualizar `calcCiclo()`; adicionar validação JS |
| `tests/test_ml_engine.py` | Testes para nova assinatura de `calcular_ano` |

---

## Task 1: Backend — `calcular_ano` com pesos separados

**Files:**
- Modify: `ml_engine.py` (função `calcular_ano`, linhas 567–614)
- Modify: `ml_engine.py` (função `simular_cenario`, linhas 1008–1113)
- Modify: `tests/test_ml_engine.py`

- [ ] **Passo 1: Escrever testes que falham**

Adicionar ao final de `tests/test_ml_engine.py`:

```python
from ml_engine import calcular_ano


def test_calcular_ano_pesos_separados():
    """calcular_ano deve aceitar peso_boi, peso_vaca, peso_bezerra."""
    r = calcular_ano(
        matrizes=500, femeas_024=300, machos_024=200, bois=20,
        nat_pct=0.75, desc_mat_pct=0.30, prop_boi=30, renov_boi_pct=0.20,
        venda_bez_pct=0.30, mort_pct=0.03,
        preco_arroba=350.0, custo_cab_ano=850.0,
        peso_boi=20.0, peso_vaca=17.0, peso_bezerra=8.0,
    )
    assert r['receita'] > 0
    # bois_vendidos × 20 + desc_mat × 17 + bezerras/machos × 8, tudo × 350
    bois_vend = r['bois_vendidos']
    desc_mat  = r['descarte_matrizes']
    bez_vend  = r['bezerras_vendidas']
    mac_vend  = r['machos_024_vendidos']
    esperado  = (bois_vend * 20 + desc_mat * 17 + (bez_vend + mac_vend) * 8) * 350
    assert abs(r['receita'] - esperado) < 1.0


def test_calcular_ano_sem_peso_arroba():
    """calcular_ano não deve aceitar argumento peso_arroba (removido)."""
    import inspect
    sig = inspect.signature(calcular_ano)
    assert 'peso_arroba' not in sig.parameters
    assert 'peso_boi'    in sig.parameters
    assert 'peso_vaca'   in sig.parameters
    assert 'peso_bezerra' in sig.parameters


def test_simular_cenario_ciclo_completo_peso_boi_vaca():
    """simular_cenario CICLO_COMPLETO deve aceitar e usar peso_boi e peso_vaca."""
    v = [300, 280, 400, 200, 900, 1200, 250, 80, 600, 40]
    r1 = simular_cenario(v, 'crescimento', peso_boi=20.0, peso_vaca=17.0)
    r2 = simular_cenario(v, 'crescimento', peso_boi=25.0, peso_vaca=22.0)
    # Pesos maiores → receita maior
    assert r2['acumulado']['receita'] > r1['acumulado']['receita']
```

- [ ] **Passo 2: Rodar — devem falhar**

```
cd c:\Users\Lucas\Downloads\boviml_python\boviml
venv\Scripts\python -m pytest tests/test_ml_engine.py -v -k "pesos_separados or peso_arroba or peso_boi_vaca" 2>&1
```

Esperado: `FAILED` — `calcular_ano` ainda usa `peso_arroba`.

- [ ] **Passo 3: Atualizar `calcular_ano` em `ml_engine.py`**

Localizar (linha ~567):
```python
def calcular_ano(
    matrizes, femeas_024, machos_024, bois,
    nat_pct, desc_mat_pct, prop_boi, renov_boi_pct,
    venda_bez_pct, mort_pct, preco_arroba, custo_cab_ano, peso_arroba,
) -> dict:
```

Substituir por:
```python
def calcular_ano(
    matrizes, femeas_024, machos_024, bois,
    nat_pct, desc_mat_pct, prop_boi, renov_boi_pct,
    venda_bez_pct, mort_pct, preco_arroba, custo_cab_ano,
    peso_boi: float = 20.0, peso_vaca: float = 17.0, peso_bezerra: float = 8.0,
) -> dict:
```

Localizar (linha ~591):
```python
    receita   = vendidos * peso_arroba * preco_arroba
```

Substituir por:
```python
    receita   = (
        bois_vendidos              * peso_boi      +
        desc_mat                   * peso_vaca     +
        (bez_vend + machos_024_vend) * peso_bezerra
    ) * preco_arroba
```

- [ ] **Passo 4: Atualizar `simular_cenario` em `ml_engine.py`**

Localizar a assinatura de `simular_cenario` (linha ~1008) e adicionar dois parâmetros após `dias_engorda`:

```python
    dias_engorda:       int   = 90,
    peso_boi:           float = 20.0,
    peso_vaca:          float = 17.0,
) -> dict:
```

Localizar a chamada a `calcular_ano` dentro do loop CICLO_COMPLETO (linha ~1068):

```python
        r = calcular_ano(
            matrizes=matrizes, femeas_024=femeas_024,
            machos_024=machos_024, bois=bois,
            nat_pct=nat, desc_mat_pct=desc,
            prop_boi=prop_boi, renov_boi_pct=renov_boi_pct/100,
            venda_bez_pct=venda_bez_pct/100,
            mort_pct=mort,
            preco_arroba=preco_arroba * m['preco'],
            custo_cab_ano=custo_cab_ano,
            peso_arroba=peso_arroba,
        )
```

Substituir por:
```python
        r = calcular_ano(
            matrizes=matrizes, femeas_024=femeas_024,
            machos_024=machos_024, bois=bois,
            nat_pct=nat, desc_mat_pct=desc,
            prop_boi=prop_boi, renov_boi_pct=renov_boi_pct/100,
            venda_bez_pct=venda_bez_pct/100,
            mort_pct=mort,
            preco_arroba=preco_arroba * m['preco'],
            custo_cab_ano=custo_cab_ano,
            peso_boi=peso_boi,
            peso_vaca=peso_vaca,
            peso_bezerra=peso_arroba,
        )
```

Localizar o bloco do breakeven CICLO_COMPLETO (linha ~1099):

```python
    result = _montar_resultado(cenario, sc, anos_proj, total_ini, 'CICLO_COMPLETO')
    ano1 = anos_proj[0]
    preco_adj = preco_arroba * m['preco']
    units = float(max(ano1['vendidos'], 1)) * peso_arroba
```

Substituir por:
```python
    result = _montar_resultado(cenario, sc, anos_proj, total_ini, 'CICLO_COMPLETO')
    ano1 = anos_proj[0]
    preco_adj = preco_arroba * m['preco']
    # Peso médio ponderado para o slider de preço
    bv = float(ano1.get('bois_vendidos', 0))
    dv = float(ano1.get('matrizes_descartadas', 0))
    ov = float(max(ano1['vendidos'] - bv - dv, 0))
    peso_medio = (bv * peso_boi + dv * peso_vaca + ov * peso_arroba) / max(ano1['vendidos'], 1)
    units = float(max(ano1['vendidos'], 1)) * peso_medio
```

- [ ] **Passo 5: Atualizar `app.py`**

Localizar em `api_cenario` (linha ~292):
```python
        'peso_arroba':   float(data.get('peso',     16)),
```

Substituir por:
```python
        'peso_arroba':   float(data.get('peso',     16)),
        'peso_boi':      float(data.get('peso_boi',  20)),
        'peso_vaca':     float(data.get('peso_vaca', 17)),
```

- [ ] **Passo 6: Rodar todos os testes — devem passar**

```
venv\Scripts\python -m pytest tests/test_ml_engine.py -v 2>&1
```

Esperado: todos os testes `PASSED` (incluindo os 15 anteriores + 3 novos = 18 total).

- [ ] **Passo 7: Commit**

```bash
git add ml_engine.py app.py tests/test_ml_engine.py
git commit -m "feat: calcular_ano uses peso_boi/peso_vaca/peso_bezerra instead of single peso_arroba"
```

---

## Task 2: Frontend — substituir campos + atualizar `calcCiclo`

**Files:**
- Modify: `templates/index.html`

- [ ] **Passo 1: Substituir campos HTML no card "Preços de Venda"**

Localizar (linha ~468):
```html
              <div class="field"><label>Preço Boi (R$/cab.)</label><input type="number" id="s-preco-boi" value="4500" min="0" oninput="recalcCiclo()"></div>
              <div class="field"><label>Preço Matriz (R$/cab.)</label><input type="number" id="s-preco-mat" value="3200" min="0" oninput="recalcCiclo()"></div>
```

Substituir por:
```html
              <div class="field"><label>Peso Boi (@)</label><input type="number" id="s-peso-boi" value="20" step="0.5" min="8" max="30" oninput="recalcCiclo();validarCampo(this,8,30)"></div>
              <div class="field"><label>Peso Vaca (@)</label><input type="number" id="s-peso-vaca" value="17" step="0.5" min="6" max="25" oninput="recalcCiclo();validarCampo(this,6,25)"></div>
```

- [ ] **Passo 2: Atualizar `calcCiclo()` no JS**

Localizar (linha ~1177):
```js
  const pBoi=gS('s-preco-boi')||4500;
  const pMat=gS('s-preco-mat')||3200;
```

Substituir por:
```js
  const pesoBoi=gS('s-peso-boi')||20;
  const pesoVaca=gS('s-peso-vaca')||17;
  const pBoi=pesoBoi*pArr;
  const pMat=pesoVaca*pArr;
```

- [ ] **Passo 3: Atualizar o retorno de `calcCiclo()` para incluir os pesos**

Localizar (linha ~1201):
```js
  return{mat,fem,mac,boi,nat,prop,rb,des,vbp,niv,totBez,bezF,bezM,bNec,bExc,bRen,bVend,macRest,desQ,bezV,bezMV,femR,cresc,totReb,totVend,pBoi,pMat,pBezCab,rBoi,rMat,rBez,rBezM,rTot,cMat,cBoi,cFem,cMac,cBez,cTot,res};
```

Substituir por:
```js
  return{mat,fem,mac,boi,nat,prop,rb,des,vbp,niv,totBez,bezF,bezM,bNec,bExc,bRen,bVend,macRest,desQ,bezV,bezMV,femR,cresc,totReb,totVend,pesoBoi,pesoVaca,pBoi,pMat,pBezCab,rBoi,rMat,rBez,rBezM,rTot,cMat,cBoi,cFem,cMac,cBez,cTot,res};
```

- [ ] **Passo 4: Atualizar tabela financeira — coluna "Preço Unit." para mostrar peso**

Localizar (linha ~1269):
```js
  if(tRec){tRec.innerHTML=[['Bois',d.bVend,fR(d.pBoi),d.rBoi],['Matrizes',d.desQ,fR(d.pMat),d.rMat],['Bezerras',d.bezV,fR(d.pBezCab),d.rBez],['Bezerros M.',d.bezMV,fR(d.pBezCab),d.rBezM]].map(([c,q,p,t])=>
```

Substituir por:
```js
  if(tRec){tRec.innerHTML=[['Bois',d.bVend,`${d.pesoBoi}@ · ${fR(d.pBoi)}`,d.rBoi],['Matrizes',d.desQ,`${d.pesoVaca}@ · ${fR(d.pMat)}`,d.rMat],['Bezerras',d.bezV,`${gS('s-bez-arr')}@ · ${fR(d.pBezCab)}`,d.rBez],['Bezerros M.',d.bezMV,`${gS('s-bez-arr')}@ · ${fR(d.pBezCab)}`,d.rBezM]].map(([c,q,p,t])=>
```

- [ ] **Passo 5: Atualizar `runSc()` para enviar os novos campos ao backend**

Localizar em `runSc()` a linha que tem `peso_saida_kg`:
```js
      peso_saida_kg:gv('p-peso-sai-kg'),
      rendimento_carcaca:gv('p-rend-carcaca'),
```

Adicionar após `rendimento_carcaca`:
```js
      rendimento_carcaca:gv('p-rend-carcaca'),
      peso_boi:gv('s-peso-boi'),
      peso_vaca:gv('s-peso-vaca'),
```

- [ ] **Passo 6: Verificar no browser**

1. Iniciar: `venv\Scripts\python app.py`
2. Abrir `http://localhost:5050`
3. Ir em Simular Cenários → Parâmetros
4. Verificar que os campos mostram "Peso Boi (@)" = 20 e "Peso Vaca (@)" = 17
5. Clicar em Recalcular — verificar que a receita muda ao alterar os pesos
6. Ir em Financeiro — verificar que a coluna "Preço Unit." mostra "20@ · R$ 7.000"

- [ ] **Passo 7: Commit**

```bash
git add templates/index.html
git commit -m "feat: replace preco_boi/mat fields with peso_boi/vaca in CICLO_COMPLETO dashboard"
```

---

## Task 3: Validação inline

**Files:**
- Modify: `templates/index.html`

- [ ] **Passo 1: Adicionar funções `validarCampo` e `validarTudo`**

Localizar `function gS(id){` e adicionar ANTES dela:

```js
function validarCampo(el, min, max) {
  const v = parseFloat(el.value);
  const ok = !isNaN(v) && v >= min && v <= max;
  el.style.borderColor = ok ? '' : 'var(--rd)';
  let msg = el.parentNode.querySelector('.v-err');
  if (!msg) {
    msg = document.createElement('div');
    msg.className = 'v-err';
    msg.style.cssText = 'font-family:var(--fm);font-size:.55rem;color:var(--rd);margin-top:3px';
    el.parentNode.appendChild(msg);
  }
  msg.textContent = ok ? '' : `Deve ser entre ${min} e ${max}`;
  validarTudo();
  return ok;
}

const _REGRAS_VALIDACAO = [
  ['c-nat',           1,   100],
  ['p-desmama',       1,   100],
  ['p-rend-carcaca',  1,   100],
  ['sc-mort',         0,    15],
  ['s-desc',          0,   100],
  ['s-vendbez',       0,   100],
  ['s-renovboi',      0,   100],
  ['s-propboi',       1,   100],
  ['p-preco-bezerro', 1, 99999],
  ['p-custo-dia',     1,  9999],
  ['p-custo-cab-mes', 1,  9999],
  ['sc-custo',        1,  9999],
  ['p-dias-engorda',  30,  365],
  ['p-meses-recria',  1,    36],
  ['s-peso-boi',      8,    30],
  ['s-peso-vaca',     6,    25],
];

function validarTudo() {
  let invalido = false;
  _REGRAS_VALIDACAO.forEach(([id, min, max]) => {
    const el = document.getElementById(id);
    if (!el) return;
    // Ignorar campos em cards ocultos
    const card = el.closest('[id^="card-params-"]');
    if (card && card.style.display === 'none') return;
    const v = parseFloat(el.value);
    if (!isNaN(v) && (v < min || v > max)) invalido = true;
  });
  const btn = document.getElementById('btn-class');
  if (btn) btn.disabled = invalido;
}
```

- [ ] **Passo 2: Adicionar `oninput` de validação nos campos críticos**

Localizar e adicionar `validarCampo(this,1,100)` nos campos de percentual da aba Condições:

```html
<!-- ANTES -->
<input type="number" id="c-nat" placeholder="75" min="1" max="100" step="1" oninput="upd()">

<!-- DEPOIS -->
<input type="number" id="c-nat" placeholder="75" min="1" max="100" step="1" oninput="upd();validarCampo(this,1,100)">
```

Localizar e atualizar `p-desmama` (dentro de `card-params-cria`):
```html
<!-- ANTES -->
<input type="number" id="p-desmama" value="80" min="1" max="100" oninput="runSc()">

<!-- DEPOIS -->
<input type="number" id="p-desmama" value="80" min="1" max="100" oninput="runSc();validarCampo(this,1,100)">
```

Localizar e atualizar `p-rend-carcaca` (dentro de `card-params-engorda`):
```html
<!-- ANTES -->
<input type="number" id="p-rend-carcaca" value="52" min="1" max="100" oninput="runSc()">

<!-- DEPOIS -->
<input type="number" id="p-rend-carcaca" value="52" min="1" max="100" oninput="runSc();validarCampo(this,1,100)">
```

Localizar e atualizar `p-preco-bezerro`:
```html
<!-- ANTES -->
<input type="number" id="p-preco-bezerro" value="1800" min="0" oninput="runSc()">

<!-- DEPOIS -->
<input type="number" id="p-preco-bezerro" value="1800" min="1" oninput="runSc();validarCampo(this,1,99999)">
```

Localizar e atualizar `p-custo-dia` (dentro de `card-params-engorda`):
```html
<!-- ANTES -->
<input type="number" id="p-custo-dia" value="12" min="0" oninput="runSc()">

<!-- DEPOIS -->
<input type="number" id="p-custo-dia" value="12" min="1" oninput="runSc();validarCampo(this,1,9999)">
```

Localizar e atualizar `p-dias-engorda`:
```html
<!-- ANTES -->
<input type="number" id="p-dias-engorda" value="90" min="30" max="365" oninput="runSc()">

<!-- DEPOIS -->
<input type="number" id="p-dias-engorda" value="90" min="30" max="365" oninput="runSc();validarCampo(this,30,365)">
```

Localizar e atualizar `p-custo-cab-mes`:
```html
<!-- ANTES -->
<input type="number" id="p-custo-cab-mes" value="80" min="0" oninput="runSc()">

<!-- DEPOIS -->
<input type="number" id="p-custo-cab-mes" value="80" min="1" oninput="runSc();validarCampo(this,1,9999)">
```

Localizar e atualizar `p-meses-recria`:
```html
<!-- ANTES -->
<input type="number" id="p-meses-recria" value="12" min="1" max="36" oninput="runSc()">

<!-- DEPOIS -->
<input type="number" id="p-meses-recria" value="12" min="1" max="36" oninput="runSc();validarCampo(this,1,36)">
```

Localizar e atualizar campos da aba Parâmetros (Simular Cenários):
```html
<!-- s-desc ANTES -->
<input type="number" id="s-desc" value="30" min="0" max="100" oninput="recalcCiclo()">
<!-- DEPOIS -->
<input type="number" id="s-desc" value="30" min="0" max="100" oninput="recalcCiclo();validarCampo(this,0,100)">

<!-- s-vendbez ANTES -->
<input type="number" id="s-vendbez" value="30" min="0" max="100" oninput="recalcCiclo()">
<!-- DEPOIS -->
<input type="number" id="s-vendbez" value="30" min="0" max="100" oninput="recalcCiclo();validarCampo(this,0,100)">

<!-- s-renovboi ANTES -->
<input type="number" id="s-renovboi" value="20" min="0" max="100" oninput="recalcCiclo()">
<!-- DEPOIS -->
<input type="number" id="s-renovboi" value="20" min="0" max="100" oninput="recalcCiclo();validarCampo(this,0,100)">

<!-- s-propboi ANTES -->
<input type="number" id="s-propboi" value="30" min="1" max="100" oninput="recalcCiclo()">
<!-- DEPOIS -->
<input type="number" id="s-propboi" value="30" min="1" max="100" oninput="recalcCiclo();validarCampo(this,1,100)">

<!-- sc-mort ANTES -->
<input type="number" id="sc-mort" value="3" min="0" max="15" oninput="runSc()">
<!-- DEPOIS -->
<input type="number" id="sc-mort" value="3" min="0" max="15" oninput="runSc();validarCampo(this,0,15)">

<!-- sc-custo ANTES -->
<input type="number" id="sc-custo" value="850" min="200" max="3000" oninput="runSc()">
<!-- DEPOIS -->
<input type="number" id="sc-custo" value="850" min="1" max="9999" oninput="runSc();validarCampo(this,1,9999)">
```

- [ ] **Passo 3: Testar validação no browser**

1. Abrir `http://localhost:5050`
2. Expandir "Condições de Classificação", digitar `200` em Taxa Natalidade
3. Verificar: campo fica com borda vermelha, texto "Deve ser entre 1 e 100" aparece embaixo, botão Classificar fica desabilitado
4. Corrigir para `75` — borda some, texto some, botão reabilita
5. Ir em Simular Cenários → Parâmetros, digitar `0` em Descarte de Matrizes — sem erro (0 é válido)
6. Digitar `150` em Descarte de Matrizes — erro aparece
7. Em card-params-engorda (oculto): digitar valor inválido via console (`document.getElementById('p-rend-carcaca').value='200'`) — botão NÃO deve ficar desabilitado (card oculto é ignorado)

- [ ] **Passo 4: Commit**

```bash
git add templates/index.html
git commit -m "feat: add inline validation for all critical form fields"
```

---

## Self-Review

**Cobertura do spec:**
- ✅ `s-preco-boi` / `s-preco-mat` → `s-peso-boi` / `s-peso-vaca` (Task 2 Passo 1)
- ✅ `calcCiclo()` usa `pesoBoi * pArr` e `pesoVaca * pArr` (Task 2 Passos 2–3)
- ✅ Tabela financeira mostra "20@ · R$ 7.000" (Task 2 Passo 4)
- ✅ `runSc()` passa `peso_boi` e `peso_vaca` ao backend (Task 2 Passo 5)
- ✅ `calcular_ano()` com três pesos separados (Task 1 Passo 3)
- ✅ `simular_cenario()` propaga `peso_boi`, `peso_vaca` (Task 1 Passo 4)
- ✅ Breakeven usa peso médio ponderado (Task 1 Passo 4)
- ✅ `/api/cenario` lê os novos campos (Task 1 Passo 5)
- ✅ Validação inline com `validarCampo` + `validarTudo` (Task 3)
- ✅ Campos em cards ocultos ignorados (Task 3 Passo 1 — `card.style.display === 'none'`)
- ✅ Defaults: peso_boi=20, peso_vaca=17 (Task 1 e Task 2)

**Consistência de tipos:**
- `calcular_ano`: `peso_boi: float = 20.0`, `peso_vaca: float = 17.0`, `peso_bezerra: float = 8.0`
- `simular_cenario`: `peso_boi: float = 20.0`, `peso_vaca: float = 17.0` — consistente
- `gS('s-peso-boi')` retorna float (parseFloat interno) — consistente com backend

**Sem placeholders:** todo código está completo em cada passo.
