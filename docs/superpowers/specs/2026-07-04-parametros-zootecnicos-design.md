# Parâmetros zootécnicos reais como defaults de cálculo

**Data:** 2026-07-04
**Feature:** (B) de 2 (a outra é preço diário nacional, spec futuro)
**Escopo:** os defaults zootécnicos dos cálculos passam a vir de **valores reais
com fonte** — ponto médio dos benchmarks nacionais (pptx) para as taxas, e os
pesos por categoria derivados dos dados do GEP (kg vivo → @ carcaça). Um módulo
único e documentado vira a fonte-da-verdade; `ml_engine` e a UI leem dele.
**Fora de escopo:** preço diário (feature A), e mudar as fórmulas do motor —
só trocamos os **números default**, não a lógica.

## Contexto e motivação

Hoje os defaults de cálculo são números soltos no código (ex.: `nat_pct=75`,
`mort_pct=3`, `rendimento_carcaca=52`, `peso_vaca=17`, `peso_boi=20`), sem fonte
declarada. O usuário quer que **todo parâmetro zootécnico dos cálculos seja um
valor real** dos anexos (GEP Araguaia + pptx de Análise de Crédito). Os
benchmarks do pptx já estão em `services/benchmarks_nacionais.py`; o benchmark
regional está em `ml_engine.BENCHMARKS_RO`. Falta consolidar os **defaults**
num lugar sourced e ligar o motor a ele.

**Decisão do usuário:** para as taxas, usar o **ponto médio dos benchmarks
nacionais** (representativo do Brasil), não os valores de uma fazenda só.

## Valores default (com fonte)

### Taxas — ponto médio do benchmark
Regra: quando existe benchmark **nacional** (pptx, `benchmarks_nacionais.py`),
o default é o meio do intervalo consolidado (menor mínimo → maior máximo). Quando
só existe benchmark **regional** (`BENCHMARKS_RO`, sem equivalente nacional), o
default é a banda **"médio"** desse benchmark, com a origem anotada.

| Parâmetro | Default | Origem |
|---|---|---|
| Natalidade | 65% | nacional: faixas 55–75 (Embrapa/Scot/CEPEA/ABCZ), meio |
| Prenhez | 62,5% | nacional: faixas 50–75, meio |
| Desfrute (por modalidade) | CRIA 24 · RECRIA 45 · ENGORDA 100 · CICLO 30 | nacional `DESFRUTE_MODALIDADE`, meio |
| Mortalidade geral | 3% | regional `BENCHMARKS_RO.mortalidade` médio (sem nacional) |
| Taxa de desmame | 82% | regional `BENCHMARKS_RO.desmama` médio |
| Rendimento de carcaça | 52% | regional `BENCHMARKS_RO.rend_carcaca` médio |
| Ganho de peso (recria) | 0,7 @/mês | regional `BENCHMARKS_RO.ganho_peso_arr` médio |
| Relação fêmeas/macho | 2,2:1 | regional `BENCHMARKS_RO.pct` médio |
| % matrizes | 35% | regional `BENCHMARKS_RO.pct_matrizes` médio |

### Pesos por categoria — referência de mercado (kg vivo → @ carcaça)
Mesma lógica "representativo nacional" das taxas: pesos de **referência de
mercado**, não de uma fazenda. Base: boi gordo terminado 500–600 kg vivo com
rendimento de carcaça ~50%; o padrão **CEPEA/B3 do boi gordo é 16–21@** de
carcaça (meio ≈ 18@). Conversão documentada: `@ carcaça = kg_vivo × 0,50 ÷ 15`.

| Categoria | Referência (kg vivo) | @ carcaça | Uso no motor | Fonte |
|---|---|---|---|---|
| Boi terminado | ~540 | **18@** | `peso_boi` | CEPEA boi gordo padrão 16–21@, meio |
| Vaca gorda (descarte) | ~420 | **14@** | `peso_vaca` | vaca gorda ~420kg × 50% ÷ 15 |
| Garrote/novilho (jovem macho vendido) | ~330 | **11@** | `peso_garrote` | novilho recria ~330kg × 50% ÷ 15 |
| Bezerra (jovem fêmea vendida) | ~210 | **7@** | `peso_bezerra` | bezerra desmamada ~210kg × 50% ÷ 15 |

> Rendimento de carcaça de referência = **50%** (CEPEA/mercado; média de abate),
> distinto do rendimento de *engorda* (52% do bloco de taxas, usado no cálculo de
> carcaça da fase de terminação). Todos editáveis na UI; o módulo os traz como
> ponto de partida sourced, não fabricado. São mais leves que os defaults antigos
> (17/20/8/13) para o boi/vaca — o antigo 20@ de boi estava acima do padrão.

## Componentes

### 1. Módulo `services/parametros_zootecnicos.py` (puro, testável)

- Constantes com docstring citando a fonte de cada valor:
  `NATALIDADE_PCT=65.0`, `PRENHEZ_PCT=62.5`, `MORTALIDADE_PCT=3.0`,
  `DESMAME_PCT=82.0`, `RENDIMENTO_CARCACA_PCT=52.0`, `GANHO_ARROBA_MES=0.7`,
  `RELACAO_FM=2.2`, `PCT_MATRIZES=35.0`.
- `DESFRUTE_PCT = {'CRIA':24.0,'RECRIA':45.0,'ENGORDA':100.0,'CICLO_COMPLETO':30.0}`.
- Pesos vivos de referência de mercado (kg) e derivados em @:
  `RENDIMENTO_ABATE = 0.50` (rendimento de carcaça de referência de mercado);
  `PESO_VIVO_KG = {'boi':540,'vaca':420,'garrote':330,'bezerra':210}` e
  `peso_arroba_carcaca(kg, rendimento=RENDIMENTO_ABATE) -> float` (= kg×rend/15).
  Constantes derivadas (arredondadas para o inteiro de referência):
  `PESO_BOI_ARR=18`, `PESO_VACA_ARR=14`, `PESO_GARROTE_ARR=11`,
  `PESO_BEZERRA_ARR=7`.
- `midpoint(lo, hi) -> float` helper para documentar como as faixas viram o meio.

### 2. Fiação no `ml_engine.py`

- `PARAMS_POR_CICLO`: `nat_pct` passa de 75 → `NATALIDADE_PCT` (65); mantém as
  demais chaves (prop_boi, renov, desc, venda_bez) — essas são operacionais, não
  zootécnicas, e ficam como estão.
- Defaults de `simular_cenario`: `mort_pct` 3 (já bate), `rendimento_carcaca`
  52 (já bate), `desmama_pct` 80 → `DESMAME_PCT` (82), `peso_boi`/`peso_vaca`/
  `peso_arroba`(bezerra)/`peso_garrote` passam a ler os `PESO_*_ARR` do módulo.
- `calcular_ano`: os defaults de peso idem.

> Só troca de **valor default**. Assinaturas e lógica intactas — a suíte de
> `test_custo_arroba`/`test_ml_engine` continua válida (ajustar só asserts que
> fixam um peso antigo, se houver).

### 3. UI (`templates/index.html`)

- Os `value=` dos campos zootécnicos passam a refletir os novos defaults:
  `s-nat` (75→65), `s-bez-arr`/`s-boi-arr`/`s-mat-arr` (pesos), `sc-mort`,
  `sc-peso`, e os campos de "Condições de Classificação" que tenham default.
- Um rótulo/hint curto "valores de referência (GEP/benchmark nacional)" perto do
  bloco, para o analista saber que são defaults sourced e editáveis.

## Fluxo de dados

```
services/parametros_zootecnicos.py  (fonte única, sourced)
        │  importado por
        ├─ ml_engine (PARAMS_POR_CICLO, defaults de simular_cenario/calcular_ano)
        └─ (valores espelhados nos value= da UI)
                 ▼
   cálculos usam defaults reais; benchmark nacional segue mostrando a faixa ao lado
```

## Tratamento de erros / bordas

- O módulo é só constantes + 2 helpers puros; sem I/O, sem falha em runtime.
- Usuário edita qualquer campo na UI → sobrescreve o default normalmente.
- Nenhuma mudança de contrato de API; retrocompatível.

## Testes

`tests/test_parametros_zootecnicos.py`:
- Cada constante de taxa bate com o ponto médio documentado (ex.: `NATALIDADE_PCT
  == midpoint(55,75) == 65`).
- `peso_arroba_carcaca(540, 0.50) == 18.0`; `(210, 0.50) == 7.0`.
- Os `PESO_*_ARR` derivam de `PESO_VIVO_KG × RENDIMENTO_ABATE ÷ 15` (sem número
  mágico solto).

`tests/test_ml_engine.py` (ajuste): se algum teste fixa `peso_*` antigo ou
`nat_pct=75`, alinhar ao novo default sourced.

## Critérios de sucesso

- Todo default zootécnico do motor tem **fonte declarada** no módulo (GEP ou
  benchmark nacional/regional) — nenhum número solto sem origem.
- Taxas = ponto médio do benchmark nacional (ou regional quando não há nacional);
  pesos = GEP convertido kg→@, documentado.
- `ml_engine` e a UI leem do módulo; resultados mudam de forma coerente e
  rastreável; suíte verde.
