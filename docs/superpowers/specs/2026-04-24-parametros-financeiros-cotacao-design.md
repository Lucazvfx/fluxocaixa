# Design: Parâmetros Financeiros com Cotação do Dia

**Data:** 2026-04-24  
**Status:** Aprovado

## Contexto

O scraper já busca preços de arroba (boi gordo, vaca gorda) da Scot Consultoria diariamente e os armazena no banco. A função `atualizarPrecos()` já exibe esses preços nos badges do header. Porém os campos de simulação (`s-preco-arr-boi`, `s-preco-arr-vaca`, `s-preco-arr`, `sc-preco-arr`) ficam com valores hardcoded mesmo quando há cotação disponível.

## Objetivo

Preencher automaticamente os campos de preço nos painéis de simulação com a cotação do dia, mantendo os campos editáveis, e mostrar um badge visual "↑ cotação hoje" que some quando o usuário edita o valor.

## Arquitetura

### Apenas frontend — `templates/index.html`

Nenhuma mudança no backend. Toda a lógica usa dados já disponíveis:
- `_COTACOES_FALLBACK` — objeto Jinja2 com preços do banco no carregamento da página
- `atualizarPrecos()` intercept existente — já faz a chamada `/api/precos/live`

### Campos Preenchidos

| ID | Preço | Contexto |
|---|---|---|
| `s-preco-arr-boi` | `p.boi` | Cenários → Preços de Venda → Preço @ Boi |
| `s-preco-arr-vaca` | `p.vaca` | Cenários → Preços de Venda → Preço @ Vaca |
| `s-preco-arr` | `p.boi` | Cenários → Preços de Venda → Preço @ Bezerra |
| `sc-preco-arr` | `p.boi` | Projeção 5 Anos → Preço Arroba |
| `cc-preco-arr` | `p.boi` | Custo/Cab. (já preenchido pelo intercept, sem mudança) |

Regra: preencher **somente se o campo atual for 0 ou vazio** — nunca sobrescreve valor digitado pelo usuário.

### Função utilitária `_setBadgeCotacao(inputId, valor)`

```javascript
function _setBadgeCotacao(inputId, valor) {
  const el = document.getElementById(inputId);
  if (!el || (parseFloat(el.value) || 0) !== 0) return;
  el.value = valor.toFixed(2);
  const field = el.closest('.field');
  if (!field) return;
  const badgeId = 'badge-cot-' + inputId;
  if (!document.getElementById(badgeId)) {
    const span = document.createElement('span');
    span.id = badgeId;
    span.textContent = '↑ cotação hoje';
    span.style.cssText = 'font-family:var(--fm);font-size:.52rem;color:var(--g);letter-spacing:1px';
    field.appendChild(span);
    el.addEventListener('input', () => span.remove(), { once: true });
  }
}
```

### Expansão do Intercept Existente

O intercept no final de `index.html` já faz uma chamada `/api/precos/live` para alertas e `cc-preco-arr`. Expandir para também chamar `_setBadgeCotacao` para os 4 campos novos.

### Fallback com `_COTACOES_FALLBACK`

No `DOMContentLoaded` existente (no primeiro `<script>`), após `atualizarPrecos()`, chamar `_setBadgeCotacao` com os valores de `_COTACOES_FALLBACK`. Isso garante que a página já carrega com os preços do banco visíveis, sem esperar a resposta live. Como `_setBadgeCotacao` está definida no segundo `<script>`, o `DOMContentLoaded` garante que ela já existe quando é chamada.

O `DOMContentLoaded` atual:
```javascript
document.addEventListener('DOMContentLoaded', ()=>{
  atualizarPrecos();
  setInterval(atualizarPrecos, 1000 * 60 * 30);
});
```

Passa a ser:
```javascript
document.addEventListener('DOMContentLoaded', ()=>{
  atualizarPrecos();
  setInterval(atualizarPrecos, 1000 * 60 * 30);
  if(_COTACOES_FALLBACK.boi > 0) {
    _setBadgeCotacao('s-preco-arr-boi', _COTACOES_FALLBACK.boi);
    _setBadgeCotacao('s-preco-arr', _COTACOES_FALLBACK.boi);
    _setBadgeCotacao('sc-preco-arr', _COTACOES_FALLBACK.boi);
  }
  if(_COTACOES_FALLBACK.vaca > 0)
    _setBadgeCotacao('s-preco-arr-vaca', _COTACOES_FALLBACK.vaca);
});
```

## Fluxo de Dados

```
Página carrega (DOMContentLoaded)
  → _COTACOES_FALLBACK disponível via Jinja2
  → _setBadgeCotacao para cada campo (se boi > 0 e vaca > 0)
  → campos preenchidos com preços do banco, badge "↑ cotação hoje" aparece

atualizarPrecos() chamado (imediatamente + a cada 30min)
  → GET /api/precos/live
  → sucesso: chama _setBadgeCotacao com preços live
  → falha: campos já preenchidos pelo fallback, nada muda

Usuário edita qualquer campo de preço
  → listener 'input' { once: true } remove o badge automaticamente
  → campo fica com valor do usuário, sem indicador
```

## O Que Não Muda

- Backend e endpoints — nenhuma alteração
- HTML dos campos de preço — nenhuma alteração
- Lógica de cálculo das simulações — nenhuma alteração
- `cc-preco-arr` — já funciona, sem mudança na lógica existente
