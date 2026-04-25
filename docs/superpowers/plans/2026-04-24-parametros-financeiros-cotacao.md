# Parâmetros Financeiros com Cotação do Dia — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preencher automaticamente os campos de preço da arroba nos painéis de simulação com a cotação do dia, mostrando um badge "↑ cotação hoje" que some quando o usuário edita o campo.

**Architecture:** Apenas frontend em `templates/index.html`. A função utilitária `_setBadgeCotacao` preenche campos zerados e injeta o badge. É chamada: (a) no `DOMContentLoaded` usando `_COTACOES_FALLBACK` (preços do banco via Jinja2); e (b) no intercept existente de `atualizarPrecos` usando preços live. Os campos HTML terão `value="0"` para indicar que precisam ser preenchidos via cotação.

**Tech Stack:** JavaScript vanilla, CSS variables existentes (`var(--fm)`, `var(--g)`)

---

## Arquivos Modificados

| Arquivo | O que muda |
|---|---|
| `templates/index.html` | 4 campos `value="0"`, nova função `_setBadgeCotacao`, `DOMContentLoaded` expandido, intercept expandido |

---

### Task 1: Zerar defaults dos campos de preço e adicionar `_setBadgeCotacao`

**Files:**
- Modify: `templates/index.html`
  - Campos de preço (~linhas 604, 606, 608, 763): `value="340/290"` → `value="0"`
  - Intercept existente (~últimas linhas): adicionar `_setBadgeCotacao` antes do `const _origAP`
  - `DOMContentLoaded` (~linha 930): expandir com fallback

**Contexto:** Os 4 campos que recebem cotação automática são:
- `s-preco-arr-boi` — Preço @ Boi (atualmente `value="340"`)
- `s-preco-arr-vaca` — Preço @ Vaca (atualmente `value="290"`)
- `s-preco-arr` — Preço @ Bezerra (atualmente `value="340"`)
- `sc-preco-arr` — Preço Arroba projeção 5 anos (atualmente `value="340"`)

- [ ] **Step 1: Alterar `value` de `s-preco-arr-boi` de `340` para `0`**

Localizar (painel Cenários → Preços de Venda):
```html
              <div class="field"><label>Preço @ Boi (R$)</label><input type="number" id="s-preco-arr-boi" value="340" min="1" oninput="recalcCiclo()"></div>
```
Substituir por:
```html
              <div class="field"><label>Preço @ Boi (R$)</label><input type="number" id="s-preco-arr-boi" value="0" min="1" oninput="recalcCiclo()"></div>
```

- [ ] **Step 2: Alterar `value` de `s-preco-arr-vaca` de `290` para `0`**

Localizar:
```html
              <div class="field"><label>Preço @ Vaca (R$)</label><input type="number" id="s-preco-arr-vaca" value="290" min="1" oninput="recalcCiclo()"></div>
```
Substituir por:
```html
              <div class="field"><label>Preço @ Vaca (R$)</label><input type="number" id="s-preco-arr-vaca" value="0" min="1" oninput="recalcCiclo()"></div>
```

- [ ] **Step 3: Alterar `value` de `s-preco-arr` de `340` para `0`**

Localizar:
```html
              <div class="field"><label>Preço @ Bezerra (R$)</label><input type="number" id="s-preco-arr" value="340" min="1" oninput="recalcCiclo()"></div>
```
Substituir por:
```html
              <div class="field"><label>Preço @ Bezerra (R$)</label><input type="number" id="s-preco-arr" value="0" min="1" oninput="recalcCiclo()"></div>
```

- [ ] **Step 4: Alterar `value` de `sc-preco-arr` de `340` para `0`**

Localizar (painel Projeção 5 Anos):
```html
            <div class="field"><label>Preço Arroba (R$)</label><input type="number" id="sc-preco-arr" value="340" min="1" oninput="runSc();validarCampo(this,1,2000)"></div>
```
Substituir por:
```html
            <div class="field"><label>Preço Arroba (R$)</label><input type="number" id="sc-preco-arr" value="0" min="1" oninput="runSc();validarCampo(this,1,2000)"></div>
```

- [ ] **Step 5: Adicionar função `_setBadgeCotacao` antes do intercept existente**

Localizar (próximo ao final do arquivo):
```javascript
// Intercepta atualizarPrecos para verificar alertas e preencher calculadora
const _origAP=window.atualizarPrecos;
```

Inserir ANTES dessa linha:
```javascript
function _setBadgeCotacao(inputId,valor){
  const el=document.getElementById(inputId);
  if(!el||(parseFloat(el.value)||0)!==0)return;
  el.value=valor.toFixed(2);
  const field=el.closest('.field');
  if(!field)return;
  const bid='badge-cot-'+inputId;
  if(document.getElementById(bid))return;
  const span=document.createElement('span');
  span.id=bid;span.textContent='↑ cotação hoje';
  span.style.cssText='font-family:var(--fm);font-size:.52rem;color:var(--g);letter-spacing:1px';
  field.appendChild(span);
  el.addEventListener('input',()=>span.remove(),{once:true});
}

```

- [ ] **Step 6: Expandir `DOMContentLoaded` com fallback de preços do banco**

Localizar (primeiro `<script>`, final do arquivo ~linha 930):
```javascript
document.addEventListener('DOMContentLoaded', ()=>{
  atualizarPrecos();
  setInterval(atualizarPrecos, 1000 * 60 * 30);
});
```

Substituir por:
```javascript
document.addEventListener('DOMContentLoaded', ()=>{
  atualizarPrecos();
  setInterval(atualizarPrecos, 1000 * 60 * 30);
  if(_COTACOES_FALLBACK.boi>0){
    _setBadgeCotacao('s-preco-arr-boi',_COTACOES_FALLBACK.boi);
    _setBadgeCotacao('s-preco-arr',_COTACOES_FALLBACK.boi);
    _setBadgeCotacao('sc-preco-arr',_COTACOES_FALLBACK.boi);
    recalcCiclo();runSc();
  }
  if(_COTACOES_FALLBACK.vaca>0)_setBadgeCotacao('s-preco-arr-vaca',_COTACOES_FALLBACK.vaca);
});
```

- [ ] **Step 7: Verificar no browser**

1. Iniciar servidor: `python app.py` em `c:/Users/Lucas/Downloads/boviml_python/boviml/`
2. Abrir `http://localhost:5050`
3. Ir a "Simular Cenários" → aba "Parâmetros" → card "Preços de Venda"
4. Os campos Preço @ Boi, @ Vaca e @ Bezerra devem mostrar os preços do banco com badge "↑ cotação hoje"
5. Ir a "Projeção 5 Anos" → campo Preço Arroba deve ter o preço do boi e badge
6. Editar qualquer campo de preço → badge deve sumir imediatamente

- [ ] **Step 8: Commit**

```bash
git add templates/index.html
git commit -m "feat: campos de preço zerados — preparando para cotação automática"
```

---

### Task 2: Expandir intercept para preencher campos com preço live e disparar recalc

**Files:**
- Modify: `templates/index.html` — intercept `atualizarPrecos` (~últimas linhas do arquivo)

**Contexto:** O intercept existente já chama `/api/precos/live` e preenche `cc-preco-arr`. Precisa também chamar `_setBadgeCotacao` para os 4 campos de simulação e disparar `recalcCiclo()` para atualizar os resultados com os novos preços.

- [ ] **Step 1: Expandir o intercept existente**

Localizar o bloco completo:
```javascript
// Intercepta atualizarPrecos para verificar alertas e preencher calculadora
const _origAP=window.atualizarPrecos;
window.atualizarPrecos=async function(){
  if(_origAP)await _origAP();
  try{
    const r=await fetch('/api/precos/live');const d=await r.json();
    if(d&&d.precos){
      _precoAtual=d.precos;
      const cc=document.getElementById('cc-preco-arr');
      if(cc&&(parseFloat(cc.value)||0)===0&&d.precos.boi>0){cc.value=d.precos.boi.toFixed(2);calcCustos();}
      _alertasVerificar(d.precos);
    }
  }catch(e){}
};
```

Substituir por:
```javascript
// Intercepta atualizarPrecos para verificar alertas e preencher calculadora
const _origAP=window.atualizarPrecos;
window.atualizarPrecos=async function(){
  if(_origAP)await _origAP();
  try{
    const r=await fetch('/api/precos/live');const d=await r.json();
    if(d&&d.precos){
      _precoAtual=d.precos;
      const cc=document.getElementById('cc-preco-arr');
      if(cc&&(parseFloat(cc.value)||0)===0&&d.precos.boi>0){cc.value=d.precos.boi.toFixed(2);calcCustos();}
      if(d.precos.boi>0){
        _setBadgeCotacao('s-preco-arr-boi',d.precos.boi);
        _setBadgeCotacao('s-preco-arr',d.precos.boi);
        _setBadgeCotacao('sc-preco-arr',d.precos.boi);
        recalcCiclo();runSc();
      }
      if(d.precos.vaca>0)_setBadgeCotacao('s-preco-arr-vaca',d.precos.vaca);
      _alertasVerificar(d.precos);
    }
  }catch(e){}
};
```

- [ ] **Step 2: Verificar no browser — preço live**

1. Com o servidor rodando, abrir `http://localhost:5050`
2. Abrir DevTools → Network → filtrar por `precos`
3. A chamada `/api/precos/live` deve retornar preços (`boi > 0`)
4. Os campos de preço de simulação devem mostrar o preço live com badge "↑ cotação hoje"
5. Após 1 hora de uso, o `setInterval` de 30min deve atualizar os badges sem apagar preços editados pelo usuário

- [ ] **Step 3: Verificar testes**

```bash
cd c:/Users/Lucas/Downloads/boviml_python/boviml
python -m pytest -q
```

Esperado: `19 passed` (nenhum teste novo — mudança é puramente frontend)

- [ ] **Step 4: Commit**

```bash
git add templates/index.html
git commit -m "feat: cotação do dia preenche preços de simulação automaticamente"
```
