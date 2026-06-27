# Recomendações Automáticas — Design Spec

**Data:** 2026-04-21
**Status:** Aprovado

---

## Objetivo

Adicionar um card "Análise da Fazenda" no Dashboard que exibe de 3 a 5 recomendações priorizadas, atualizadas em tempo real conforme o usuário digita os parâmetros. Cada recomendação inclui semáforo de prioridade, título, explicação e impacto financeiro estimado em R$.

---

## Arquitetura

Implementação 100% no frontend (JavaScript). Nenhuma chamada de API nova necessária — todos os dados já estão disponíveis na função `calcCiclo()` e nos campos existentes.

**Fluxo:**
1. `recalcCiclo()` já é chamada a cada mudança de parâmetro
2. Ao final de `recalcCiclo()`, chamar `gerarRecomendacoes(d)` passando o objeto retornado por `calcCiclo()`
3. `gerarRecomendacoes(d)` avalia os dados, monta a lista de recomendações e renderiza no card

---

## Arquivo modificado

- `templates/index.html` — novo card HTML + função JS `gerarRecomendacoes(d)`

---

## Regras de recomendação (5 regras)

### R1 — Resultado financeiro
- **Dados:** `d.res` (resultado = receita - custo)
- **Crítico** se `d.res < 0`: *"Fazenda operando no prejuízo. Resultado negativo de R$ X no período."*
- **Atenção** se margem < 10%: *"Margem apertada (X%). Pequenas variações de preço podem gerar prejuízo."*
- **Bom** se margem ≥ 10%

### R2 — Custo por cabeça vs receita por cabeça
- **Dados:** `d.cTot / d.totReb` vs `d.rTot / max(d.totVend, 1)`
- **Crítico** se custo/cab > receita/animal vendido
- **Atenção** se custo/cab > 80% da receita/animal
- Mostra: *"Custo médio por cabeça (R$ X) representa Y% da receita por animal vendido."*

### R3 — Taxa de natalidade
- **Dados:** `d.nat * 100`
- Benchmark RO: média 75%
- **Crítico** se < 60%: *"Natalidade crítica (X%). Média RO é 75%. Cada 5% de melhora equivale a +R$ Y/ano."*
- **Atenção** se 60–74%: mesma fórmula de impacto
- **Bom** se ≥ 75%
- Impacto estimado: `(0.75 - nat) / 0.05 * bezerros_por_5pct * pBezCab`

### R4 — Proporção boi/matriz
- **Dados:** `d.prop` (proporção atual), `d.bNec` (bois necessários), `d.boi` (bois atuais)
- **Atenção** se `d.boi > d.bNec * 1.2`: *"Excesso de bois: X bois para Y matrizes (proporção 1:Z). Vender N bois excedentes geraria R$ W."*
- Impacto: bois excedentes × `d.pBoi`

### R5 — Breakeven vs preço atual
- **Dados:** `preco_breakeven` do objeto `simular_cenario` (já disponível via `runSc()`)
- Armazenado em variável global `_lastScResult`
- **Crítico** se `preco_breakeven > preco_atual * 1.1`: *"Preço mínimo (R$ X/@) está Y% acima do mercado (R$ Z/@)."*
- **Atenção** se `preco_breakeven` entre 100–110% do preço atual
- **Bom** se `preco_breakeven < preco_atual`

---

## Card HTML

Inserido no painel Dashboard (`#scp-dash`), abaixo dos cards existentes de gráficos, antes do fechamento do painel.

```html
<div class="card" id="card-recomendacoes" style="margin-top:16px">
  <div class="ch">
    <div class="ct"><div class="cd" style="background:var(--am)"></div>Análise da Fazenda</div>
    <span id="rec-badge" style="font-family:var(--fm);font-size:.6rem;color:var(--mu)"></span>
  </div>
  <div class="cb" id="rec-body">
    <div style="color:var(--mu);font-family:var(--fm);font-size:.72rem">
      Preencha os parâmetros para ver a análise.
    </div>
  </div>
</div>
```

---

## Função JS

```javascript
function gerarRecomendacoes(d) {
  // d = objeto retornado por calcCiclo()
  // Avalia R1–R5, monta array de recomendações ordenadas por prioridade
  // Renderiza no #rec-body
}
```

Cada item da lista de recomendações:
```javascript
{ nivel: 'critico'|'atencao'|'bom', titulo: string, desc: string, impacto: string|null }
```

Renderização: ícone colorido + título em negrito + descrição + impacto em verde/vermelho.

---

## Prioridade de exibição

1. Críticos primeiro
2. Atenções depois
3. Bons por último
4. Máximo 5 itens exibidos
5. Se todos bons: mensagem *"Fazenda dentro dos parâmetros esperados."*

---

## Testes

- Rebanho com resultado negativo → R1 crítico
- Natalidade 55% → R3 crítico com impacto calculado
- Bois em excesso → R4 atenção com valor de venda
- Todos parâmetros ideais → mensagem positiva
- Rebanho zerado → card mostra mensagem de espera (sem erro JS)
