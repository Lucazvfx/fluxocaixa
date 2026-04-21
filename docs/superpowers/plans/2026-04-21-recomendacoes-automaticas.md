# Recomendações Automáticas Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar card "Análise da Fazenda" no Dashboard com 5 recomendações priorizadas que atualizam em tempo real.

**Architecture:** 100% frontend. A função `gerarRecomendacoes(d)` é chamada no final de `recalcCiclo()`, recebe o objeto `d` de `calcCiclo()` e o breakeven de `_lastScResult`, avalia 5 regras e renderiza o card com semáforo de cores.

**Tech Stack:** HTML/CSS/JavaScript inline em `templates/index.html`. Nenhuma dependência nova.

---

## File Structure

- Modify: `templates/index.html`
  - CSS: adicionar estilos `.rec-item`, `.rec-nivel-*` no bloco `<style>`
  - HTML: adicionar card `#card-recomendacoes` no painel `#scp-dash` (linha ~470)
  - JS: adicionar variável `_lastScResult`, atualizar `renderSc()`, adicionar `gerarRecomendacoes(d)`, chamar no final de `recalcCiclo()`

---

### Task 1: CSS dos itens de recomendação

**Files:**
- Modify: `templates/index.html` — bloco `<style>` (após linha 197, antes do fechamento `</style>`)

- [ ] **Step 1: Adicionar CSS**

Localizar no arquivo a linha:
```
::-webkit-scrollbar{width:5px}...
```
Inserir ANTES dela:

```css
/* ── RECOMENDAÇÕES ── */
.rec-item{display:flex;align-items:flex-start;gap:12px;padding:12px 0;border-bottom:1px solid var(--b)}
.rec-item:last-child{border-bottom:none;padding-bottom:0}
.rec-icon{font-size:1.1rem;flex-shrink:0;margin-top:1px}
.rec-content{flex:1}
.rec-titulo{font-family:var(--fn);font-weight:700;font-size:.85rem;letter-spacing:.3px;margin-bottom:3px}
.rec-desc{font-family:var(--fb);font-size:.78rem;color:var(--sb);line-height:1.5}
.rec-impacto{font-family:var(--fm);font-size:.7rem;margin-top:4px;font-weight:600}
.rec-nivel-critico .rec-titulo{color:var(--rd)}
.rec-nivel-critico .rec-impacto{color:var(--rd)}
.rec-nivel-atencao .rec-titulo{color:var(--am)}
.rec-nivel-atencao .rec-impacto{color:var(--am)}
.rec-nivel-bom .rec-titulo{color:var(--g)}
.rec-nivel-bom .rec-impacto{color:var(--g)}
```

- [ ] **Step 2: Verificar no browser**

Abrir http://localhost:5050 e checar que não houve quebra visual no Dashboard.

---

### Task 2: Card HTML no Dashboard

**Files:**
- Modify: `templates/index.html` — painel `#scp-dash` (linha ~470)

- [ ] **Step 1: Localizar ponto de inserção**

No arquivo, encontrar este trecho (linha ~461–471):
```html
    <div class="g2" style="margin-top:0">
      <div class="card">
        <div class="ch"><div class="ct"><div class="cd" style="background:var(--cy)"></div>Receita por Categoria</div></div>
        <div class="cb" id="s-bar-receita"></div>
      </div>
      <div class="card">
        <div class="ch"><div class="ct"><div class="cd" style="background:var(--pu)"></div>Fluxo de Renovação de Bois</div></div>
        <div class="cb" id="s-flow-bois" style="overflow-x:auto"></div>
      </div>
    </div>
  </div>
```

- [ ] **Step 2: Inserir card após o `.g2` e antes do `</div>` que fecha `#scp-dash`**

Substituir:
```html
    </div>
  </div>

  <!-- ── Parâmetros ── -->
```

Por:
```html
    </div>
    <div class="card" id="card-recomendacoes" style="margin-top:16px">
      <div class="ch">
        <div class="ct"><div class="cd" style="background:var(--am)"></div>Análise da Fazenda</div>
        <span id="rec-badge" style="font-family:var(--fm);font-size:.6rem;color:var(--mu)"></span>
      </div>
      <div class="cb" id="rec-body">
        <div style="color:var(--mu);font-family:var(--fm);font-size:.72rem">Preencha os parâmetros para ver a análise.</div>
      </div>
    </div>
  </div>

  <!-- ── Parâmetros ── -->
```

- [ ] **Step 3: Verificar no browser**

Recarregar http://localhost:5050. O card "Análise da Fazenda" deve aparecer no Dashboard abaixo dos gráficos, com texto cinza "Preencha os parâmetros para ver a análise."

---

### Task 3: Variável global `_lastScResult` e atualização de `renderSc()`

**Files:**
- Modify: `templates/index.html` — bloco `<script>`, próximo à declaração de variáveis globais e função `renderSc()`

- [ ] **Step 1: Adicionar variável global**

Localizar no script a linha:
```javascript
let _tutStep = 0;
```
Inserir logo abaixo:
```javascript
let _lastScResult = null;
```

- [ ] **Step 2: Atualizar `renderSc()` para salvar o resultado**

Localizar o início de `renderSc(d)`:
```javascript
function renderSc(d){
```

Adicionar como **primeira linha** do corpo da função:
```javascript
  _lastScResult = d;
```

Ficará:
```javascript
function renderSc(d){
  _lastScResult = d;
  // ... resto da função
```

---

### Task 4: Função `gerarRecomendacoes(d)`

**Files:**
- Modify: `templates/index.html` — após o fechamento de `recalcCiclo()` (linha ~1379)

- [ ] **Step 1: Inserir a função completa**

Localizar logo após o fechamento de `recalcCiclo()`:
```javascript
function showScSub(id,btn){
```

Inserir ANTES dessa linha:

```javascript
function gerarRecomendacoes(d) {
  const body   = document.getElementById('rec-body');
  const badge  = document.getElementById('rec-badge');
  if (!body) return;

  // Sem rebanho informado — estado inicial
  if (!d.totReb || d.totReb === 0) {
    body.innerHTML = '<div style="color:var(--mu);font-family:var(--fm);font-size:.72rem">Preencha os parâmetros para ver a análise.</div>';
    if (badge) badge.textContent = '';
    return;
  }

  const fR2 = v => 'R$ ' + Math.abs(Math.round(v)).toLocaleString('pt-BR');
  const recs = [];

  // R1 — Resultado financeiro
  if (d.rTot > 0) {
    const margem = d.res / d.rTot;
    if (d.res < 0) {
      recs.push({
        nivel: 'critico',
        icon: '🔴',
        titulo: 'Fazenda no prejuízo',
        desc: `Resultado negativo de ${fR2(d.res)} no período. Custos superam a receita.`,
        impacto: `Prejuízo: ${fR2(d.res)}`
      });
    } else if (margem < 0.10) {
      recs.push({
        nivel: 'atencao',
        icon: '🟡',
        titulo: 'Margem muito apertada',
        desc: `Margem de ${(margem*100).toFixed(1)}%. Uma queda de preço ou aumento de custo pode gerar prejuízo.`,
        impacto: `Margem atual: ${(margem*100).toFixed(1)}%`
      });
    } else {
      recs.push({
        nivel: 'bom',
        icon: '🟢',
        titulo: 'Resultado positivo',
        desc: `Margem de ${(margem*100).toFixed(1)}%. Fazenda operando com lucro.`,
        impacto: `Resultado: ${fR2(d.res)}`
      });
    }
  }

  // R2 — Custo por cabeça vs receita por animal vendido
  if (d.totReb > 0 && d.totVend > 0) {
    const custoCab    = d.cTot / d.totReb;
    const receitaVend = d.rTot / d.totVend;
    const ratio       = custoCab / receitaVend;
    if (ratio > 1) {
      recs.push({
        nivel: 'critico',
        icon: '🔴',
        titulo: 'Custo por cabeça acima da receita',
        desc: `Custo médio por cabeça (${fR2(custoCab)}) supera a receita por animal vendido (${fR2(receitaVend)}).`,
        impacto: `Custo = ${(ratio*100).toFixed(0)}% da receita por animal`
      });
    } else if (ratio > 0.80) {
      recs.push({
        nivel: 'atencao',
        icon: '🟡',
        titulo: 'Custo por cabeça elevado',
        desc: `Custo médio de ${fR2(custoCab)}/cab representa ${(ratio*100).toFixed(0)}% da receita por animal vendido (${fR2(receitaVend)}).`,
        impacto: `Margem de cobertura: ${((1-ratio)*100).toFixed(0)}%`
      });
    }
  }

  // R3 — Taxa de natalidade vs benchmark RO (75%)
  const natPct = d.nat;
  if (d.mat > 0 && natPct < 0.75) {
    const deficit      = 0.75 - natPct;
    const intervalos5  = deficit / 0.05;
    const impactoAno   = intervalos5 * Math.floor(d.mat * 0.05) * d.pBezCab;
    if (natPct < 0.60) {
      recs.push({
        nivel: 'critico',
        icon: '🔴',
        titulo: 'Natalidade crítica',
        desc: `Taxa de ${(natPct*100).toFixed(0)}% está abaixo do mínimo esperado. Média RO é 75%. Cada 5% de melhora gera aproximadamente ${fR2(Math.floor(d.mat * 0.05) * d.pBezCab)} a mais/ano.`,
        impacto: `Potencial de melhora: ${fR2(impactoAno)}/ano`
      });
    } else {
      recs.push({
        nivel: 'atencao',
        icon: '🟡',
        titulo: 'Natalidade abaixo da média RO',
        desc: `Taxa de ${(natPct*100).toFixed(0)}% vs média de 75% em Rondônia. Cada 5% de melhora equivale a ${fR2(Math.floor(d.mat * 0.05) * d.pBezCab)}/ano.`,
        impacto: `Potencial: ${fR2(impactoAno)}/ano`
      });
    }
  }

  // R4 — Excesso de bois
  if (d.boi > 0 && d.bNec > 0 && d.boi > d.bNec * 1.2) {
    const excesso      = d.boi - d.bNec;
    const receitaExtra = excesso * d.pBoi;
    recs.push({
      nivel: 'atencao',
      icon: '🟡',
      titulo: 'Excesso de bois reprodutores',
      desc: `${d.boi} bois para ${d.mat} matrizes (proporção 1:${Math.round(d.mat / d.boi)}). O ideal é 1:${d.prop}. Vender ${excesso} bois excedentes geraria ${fR2(receitaExtra)}.`,
      impacto: `Receita potencial: ${fR2(receitaExtra)}`
    });
  }

  // R5 — Breakeven vs preço atual
  if (_lastScResult && _lastScResult.preco_breakeven && _lastScResult.preco_usado) {
    const be    = _lastScResult.preco_breakeven;
    const atual = _lastScResult.preco_usado;
    const unid  = _lastScResult.preco_breakeven_unidade || 'R$/@';
    const ratio = be / atual;
    if (ratio > 1.10) {
      recs.push({
        nivel: 'critico',
        icon: '🔴',
        titulo: 'Preço mínimo acima do mercado',
        desc: `Preço mínimo (${fR2(be)} ${unid}) está ${((ratio-1)*100).toFixed(0)}% acima do preço atual (${fR2(atual)} ${unid}).`,
        impacto: `Gap: ${fR2(be - atual)} ${unid}`
      });
    } else if (ratio > 1.0) {
      recs.push({
        nivel: 'atencao',
        icon: '🟡',
        titulo: 'Preço no limite do breakeven',
        desc: `Preço mínimo (${fR2(be)}) próximo ao mercado (${fR2(atual)} ${unid}). Margem de segurança pequena.`,
        impacto: `Gap: ${fR2(be - atual)} ${unid}`
      });
    } else {
      recs.push({
        nivel: 'bom',
        icon: '🟢',
        titulo: 'Preço acima do breakeven',
        desc: `Preço atual (${fR2(atual)}) acima do mínimo necessário (${fR2(be)} ${unid}).`,
        impacto: `Folga: ${fR2(atual - be)} ${unid}`
      });
    }
  }

  // Ordenar: crítico → atenção → bom
  const ordem = { critico: 0, atencao: 1, bom: 2 };
  recs.sort((a, b) => ordem[a.nivel] - ordem[b.nivel]);

  // Máximo 5 itens
  const top = recs.slice(0, 5);

  // Badge de resumo
  const nCrit = top.filter(r => r.nivel === 'critico').length;
  const nAten = top.filter(r => r.nivel === 'atencao').length;
  if (badge) {
    if (nCrit > 0) {
      badge.textContent = `${nCrit} crítico${nCrit>1?'s':''}`;
      badge.style.color = 'var(--rd)';
    } else if (nAten > 0) {
      badge.textContent = `${nAten} atenção`;
      badge.style.color = 'var(--am)';
    } else {
      badge.textContent = 'tudo certo';
      badge.style.color = 'var(--g)';
    }
  }

  // Renderizar
  if (top.length === 0 || top.every(r => r.nivel === 'bom')) {
    body.innerHTML = `<div style="color:var(--g);font-family:var(--fb);font-size:.85rem;display:flex;align-items:center;gap:8px">
      <span style="font-size:1.2rem">✅</span> Fazenda dentro dos parâmetros esperados.
    </div>`;
    return;
  }

  body.innerHTML = top.map(r => `
    <div class="rec-item rec-nivel-${r.nivel}">
      <div class="rec-icon">${r.icon}</div>
      <div class="rec-content">
        <div class="rec-titulo">${r.titulo}</div>
        <div class="rec-desc">${r.desc}</div>
        ${r.impacto ? `<div class="rec-impacto">${r.impacto}</div>` : ''}
      </div>
    </div>
  `).join('');
}
```

- [ ] **Step 2: Verificar no browser**

Abrir http://localhost:5050 e conferir que não há erro de JavaScript no console (F12).

---

### Task 5: Chamar `gerarRecomendacoes(d)` no final de `recalcCiclo()`

**Files:**
- Modify: `templates/index.html` — final da função `recalcCiclo()` (linha ~1379)

- [ ] **Step 1: Localizar o fechamento de `recalcCiclo()`**

Encontrar este trecho (última linha antes do `}` de `recalcCiclo()`):
```javascript
  const resBox=ki('s-res-box');
  if(resBox){const pos=d.res>=0;resBox.innerHTML=...}
}
```

- [ ] **Step 2: Adicionar chamada antes do `}`**

Substituir o `}` final de `recalcCiclo()` por:
```javascript
  gerarRecomendacoes(d);
}
```

- [ ] **Step 3: Testar manualmente**

1. Abrir http://localhost:5050
2. Ir para aba **Parâmetros**
3. Digitar: Matrizes=500, Fêmeas=300, Machos=200, Bois=20, Natalidade=55
4. Voltar ao **Dashboard**
5. O card "Análise da Fazenda" deve mostrar:
   - 🔴 "Natalidade crítica" com impacto em R$
   - Outros alertas conforme os valores

- [ ] **Step 4: Testar rebanho zerado**

Deixar todos os campos em 0. O card deve mostrar "Preencha os parâmetros para ver a análise." sem erro no console.

- [ ] **Step 5: Testar parâmetros ideais**

Digitar: Matrizes=500, Natalidade=78, Bois=17, Preço@=350 (acima do breakeven).
O card deve mostrar "✅ Fazenda dentro dos parâmetros esperados."

- [ ] **Step 6: Commit**

```bash
git add templates/index.html
git commit -m "feat: card Análise da Fazenda com recomendações automáticas em tempo real"
```

---

### Task 6: Teste automatizado da lógica de recomendações

**Files:**
- Modify: `tests/test_ml_engine.py` — adicionar testes de integração frontend não é possível em pytest; verificar manualmente os 5 cenários abaixo no browser.

- [ ] **Step 1: Checklist de testes manuais**

| Cenário | Parâmetros | Esperado |
|---|---|---|
| Prejuízo | Matrizes=100, Bois=5, Preço@=100 | 🔴 "Fazenda no prejuízo" |
| Natalidade crítica | Matrizes=500, Nat=50% | 🔴 "Natalidade crítica" com R$ |
| Excesso de bois | Matrizes=100, Bois=20, Proporção=30 | 🟡 "Excesso de bois" |
| Margem apertada | Ajustar até margem ~5% | 🟡 "Margem muito apertada" |
| Tudo certo | Matrizes=500, Nat=80%, preços bons | ✅ mensagem positiva |

- [ ] **Step 2: Verificar badge no cabeçalho do card**

Confirmar que o badge muda de cor: vermelho para críticos, amarelo para atenções, verde para tudo certo.

- [ ] **Step 3: Push final**

```bash
git push origin main
```

---

## Self-Review

**Spec coverage:**
- ✅ R1 resultado financeiro — Task 4
- ✅ R2 custo vs receita — Task 4
- ✅ R3 natalidade — Task 4
- ✅ R4 excesso de bois — Task 4
- ✅ R5 breakeven vs preço — Task 4
- ✅ Card HTML — Task 2
- ✅ CSS semáforo — Task 1
- ✅ Badge de resumo — Task 4
- ✅ Ordenação crítico→atenção→bom — Task 4
- ✅ Máximo 5 itens — Task 4
- ✅ Mensagem positiva quando tudo ok — Task 4
- ✅ Estado vazio (rebanho=0) — Task 4
- ✅ `_lastScResult` para R5 — Task 3

**Placeholder scan:** Nenhum TBD ou TODO.

**Type consistency:** `gerarRecomendacoes(d)` usa `d` de `calcCiclo()` consistentemente em todas as regras. `_lastScResult` declarado em Task 3 e usado em Task 4 (R5).
