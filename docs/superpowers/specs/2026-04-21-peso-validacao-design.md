# Design: Peso por Categoria + Validação de Entrada

**Data:** 2026-04-21
**Status:** Aprovado

---

## Objetivo

Duas melhorias combinadas:

1. **Peso por categoria** — substituir "Preço Boi/Vaca (R$/cab)" por "Peso Boi/Vaca (@)" nos parâmetros do Ciclo Completo, tornando a receita calculada via `quantidade × peso × preço arroba` (igual ao mercado real)
2. **Validação de entrada** — feedback inline em tempo real nos campos críticos; desabilita o botão Classificar quando há valores inválidos

---

## Parte 1 — Peso por Categoria

### Campos removidos / substituídos

| Removido | Substituído por | Default |
|----------|----------------|---------|
| `s-preco-boi` — Preço Boi (R$/cab) | `s-peso-boi` — Peso Boi (@) | **20** |
| `s-preco-mat` — Preço Matriz (R$/cab) | `s-peso-vaca` — Peso Vaca (@) | **17** |

O campo `s-preco-arr` (Preço Arroba R$) permanece como único preço de referência.

### Nova fórmula de receita

**Frontend `calcCiclo()`:**
```js
const pesoBoi  = gS('s-peso-boi')  || 20;
const pesoVaca = gS('s-peso-vaca') || 17;
const rBoi  = bVend  * pesoBoi  * pArr;
const rMat  = desQ   * pesoVaca * pArr;
const rBez  = bezV   * pBezArr  * pArr;   // já usa arroba — sem mudança
const rBezM = bezMV  * pBezArr  * pArr;
```

**Backend `calcular_ano()`:**
```python
# Assinatura: adicionar peso_boi=20.0, peso_vaca=17.0, remover peso_arroba
receita = (
    bois_vendidos      * peso_boi   +
    desc_mat           * peso_vaca  +
    (bez_vend + machos_024_vend) * peso_bezerra
) * preco_arroba
```

`peso_bezerra` vem do parâmetro existente `peso_arroba` renomeado para `peso_bezerra` (sem quebrar a lógica existente de bezerras/machos jovens).

### Propagação backend

`simular_cenario()` CICLO_COMPLETO recebe dois novos parâmetros:
```python
peso_boi:   float = 20.0,
peso_vaca:  float = 17.0,
```

`/api/cenario` lê `peso_boi` e `peso_vaca` do request JSON e repassa para `simular_cenario`.

`runSc()` no frontend passa esses valores junto com os outros parâmetros.

### Breakeven CICLO_COMPLETO

A unidade do slider continua sendo `vendidos × peso_médio × preco_arroba`. Com pesos separados, o peso médio ponderado é calculado:
```python
peso_medio = (
    bois_vendidos * peso_boi +
    desc_mat * peso_vaca +
    (bez_vend + machos_024_vend) * peso_bezerra
) / max(vendidos, 1)
units = float(max(ano1['vendidos'], 1)) * peso_medio
```

---

## Parte 2 — Validação de Entrada

### Arquitetura JS

**Função central:**
```js
function validarCampo(el, min, max) {
  const v = parseFloat(el.value);
  const ok = !isNaN(v) && v >= min && v <= max;
  el.style.borderColor = ok ? '' : 'var(--rd)';
  // mensagem de erro embaixo do campo
  let msg = el.nextElementSibling;
  if (!msg || !msg.classList.contains('v-err')) {
    msg = document.createElement('div');
    msg.className = 'v-err';
    msg.style.cssText = 'font-family:var(--fm);font-size:.55rem;color:var(--rd);margin-top:3px';
    el.parentNode.insertBefore(msg, el.nextSibling);
  }
  msg.textContent = ok ? '' : `Deve ser entre ${min} e ${max}`;
  return ok;
}

function validarTudo() {
  // Valida apenas campos visíveis (card não display:none)
  // Desabilita #btn-class se algum inválido
}
```

### Campos e regras

| ID do campo | Label | Min | Max |
|-------------|-------|-----|-----|
| `c-nat` | Taxa Natalidade | 1 | 100 |
| `p-desmama` | Taxa de Desmama | 1 | 100 |
| `p-rend-carcaca` | Rendimento Carcaça | 1 | 100 |
| `sc-mort` | Mortalidade | 0 | 15 |
| `s-desc` | Descarte de Matrizes | 0 | 100 |
| `s-vendbez` | Venda de Bezerras | 0 | 100 |
| `s-renovboi` | Renovação de Bois | 0 | 100 |
| `s-propboi` | Proporção Boi/Matriz | 1 | 100 |
| `p-preco-bezerro` | Preço Bezerro | 1 | 99999 |
| `p-custo-dia` | Custo/Cab/Dia | 1 | 9999 |
| `p-custo-cab-mes` | Custo/Cab/Mês | 1 | 9999 |
| `sc-custo` | Custo/Cab/Ano | 1 | 9999 |
| `p-dias-engorda` | Dias de Engorda | 30 | 365 |
| `p-meses-recria` | Meses de Recria | 1 | 36 |
| `s-peso-boi` | Peso Boi | 8 | 30 |
| `s-peso-vaca` | Peso Vaca | 6 | 25 |

### Comportamento

- Validação roda no `oninput` de cada campo
- Campos em cards `display:none` são ignorados por `validarTudo()`
- O botão `#btn-class` fica `disabled` enquanto houver campo inválido
- Ao corrigir o valor, a borda e mensagem somem imediatamente

---

## Arquivos modificados

| Arquivo | Mudança |
|---------|---------|
| `templates/index.html` | Trocar campos `s-preco-boi` / `s-preco-mat` por `s-peso-boi` / `s-peso-vaca`; atualizar `calcCiclo()`; adicionar `validarCampo`, `validarTudo`; adicionar `oninput` em todos os campos da tabela |
| `ml_engine.py` | Atualizar assinatura e corpo de `calcular_ano()`: trocar `peso_arroba` único por `peso_boi`, `peso_vaca`, `peso_bezerra`; atualizar `simular_cenario()` CICLO_COMPLETO |
| `app.py` | Ler `peso_boi` e `peso_vaca` do request em `/api/cenario` e repassar para `simular_cenario` |

---

## Fora do escopo

- Validação backend (desnecessária para uso interno)
- Pesos para CRIA, RECRIA, ENGORDA (usam defaults RO já existentes)
- Histórico de pesos por fazenda
