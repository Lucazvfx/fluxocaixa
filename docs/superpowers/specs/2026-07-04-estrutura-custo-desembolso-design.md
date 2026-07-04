# Estrutura de Custo (Desembolso) que alimenta o parecer

**Data:** 2026-07-04
**Bloco:** custo real por componentes → custo_arroba do parecer
**Escopo:** substituir a tabela `CUSTO_S` (custo por categoria animal, níveis
baixo/médio/alto **arbitrados**) por uma **estrutura de desembolso por
componentes** com dados de fonte real (GEP Araguaia / Inttegra), que o app
converte para o `custo_arroba` usado na projeção de caixa e no DSCR do parecer.
**Fora de escopo:** depreciação e remuneração de fatores (custo total CEPEA/CNA);
por ora só o desembolso/custeio. PDF do parecer e multiempresa (blocos futuros).

## Contexto e motivação

Hoje o custo que alimenta o parecer é um **valor único fixo** (`custo_arroba`,
default 57 R$/@·ano, editável no campo `sc-custo`). É opaco: não mostra de onde
vem o custo. Numa consultoria de crédito, o custo precisa ser **decomposto em
partes de gasto** (insumos, mão de obra, administração, etc.) e, idealmente,
comparável a um benchmark real.

O anexo **GEP Araguaia** (`2606 Exercícios GEP ARAGUAIA 2026`, aba
`PERFIL DESEMB`, fonte Terra Desenvolvimento Agropecuário / Inttegra, safra
24/25) traz o **Perfil de Desembolso** em R$/cab/mês por modalidade, com colunas
**Média** e **Top Rentáveis**. Pesquisa externa (CEPEA/Campo Futuro-CNA,
SENAR/IMEA, Embrapa CUSTObov) confirma que essas categorias são o padrão do
setor e que o custeio é conventionalmente medido em R$/cab/mês (o CUSTObov já
expressa também em @).

## Dados de referência (fonte: GEP Araguaia, R$/cab/mês)

Presets por modalidade, `(média, top_rentáveis)`:

| Componente        | CRIA         | RECRIA/ENGORDA | CICLO COMPLETO |
|-------------------|--------------|----------------|----------------|
| Insumos do rebanho| 25,53 / 22,17| 77,46 / 96,53  | 44,92 / 42,18  |
| Mão de obra       | 18,20 / 14,66| 19,62 / 17,04  | 18,10 / 14,39  |
| Administração     | 7,97 / 5,30  | 14,04 / 7,92   | 8,49 / 5,89    |
| Máquinas (custeio+inv.)   | 11,79 / 7,63 | 19,37 / 15,49 | 15,23 / 10,71 |
| Pastagem (custeio+inv.)   | 11,97 / 9,09 | 15,38 / 11,44 | 14,29 / 10,79 |
| Infraestrutura (custeio+inv.)| 11,59 / 7,30 | 18,79 / 12,35 | 13,69 / 8,40 |
| Taxas e impostos  | 2,66 / 2,26  | 5,05 / 5,77    | 3,66 / 3,10    |
| Outros            | 1,17 / 1,22  | 1,03 / 0,74    | 0,76 / 0,62    |
| **TOTAL**         | **90,88 / 69,63** | **170,74 / 167,28** | **119,14 / 96,08** |

## Componentes do sistema

### 1. Módulo backend `services/custos_desembolso.py` (puro, testável)

- `PERFIL_DESEMBOLSO`: dict `modalidade → {componente: (media, top)}` com os
  valores acima. Chaves de componente estáveis:
  `insumos, mao_obra, administracao, maquinas, pastagem, infraestrutura,
  taxas_impostos, outros`. Modalidades: `CRIA`, `RECRIA_ENGORDA`,
  `CICLO_COMPLETO`. Docstring cita a fonte (GEP/Inttegra safra 24/25).
- `COMPONENTES`: lista ordenada `[(chave, rótulo)]` para a UI e para somar.
- `custo_arroba_de_desembolso(desembolso_cab_mes, arrobas_rebanho, total_cabecas) -> float`:
  converte desembolso mensal por cabeça em R$/@·ano exato usando o peso médio
  do rebanho:
  `peso_medio_arroba = arrobas_rebanho / total_cabecas`
  `custo_arroba = desembolso_cab_mes * 12 / peso_medio_arroba`
  Guardas: se `total_cabecas <= 0` ou `peso_medio_arroba <= 0` → retorna 0.0.
- `preset_modalidade(tipo, perfil) -> dict`: dado o `tipo` classificado
  (`CRIA`/`RECRIA`/`ENGORDA`/`CICLO_COMPLETO`) e o perfil (`media`|`top`),
  devolve `{componente: valor}`. Mapeamento: `RECRIA` e `ENGORDA` →
  `RECRIA_ENGORDA`; os demais mapeiam direto.

> As faixas Média/Top são **referência de mercado com fonte**, não número
> zootécnico fabricado — coerentes com a regra "nenhum benchmark inventado".

### 2. Integração no `/api/classificar` (`app.py`)

- Novo campo opcional no `data`: `custo_componentes` — dict
  `{componente: R$/cab/mês}` (os 8 componentes; ausentes contam como 0).
- Se `custo_componentes` vier preenchido (soma > 0):
  - `desembolso = sum(custo_componentes.values())`
  - `arrobas_rebanho = arrobas_categorias(...)` a partir de `v` (mesma
    decomposição de faixas já usada; pesos padrão do motor)
  - `total_cabecas = sum(v)`
  - `custo_arroba = custo_arroba_de_desembolso(desembolso, arrobas_rebanho, total_cabecas)`
  - esse `custo_arroba` substitui o lido de `data.get('custo_arroba', 57)` na
    chamada a `simular_cenario(... custo_arroba=...)` que gera a geração de caixa
    do parecer.
- Se `custo_componentes` não vier, mantém o comportamento atual
  (`custo_arroba` do campo único, default 57) — retrocompatível.
- A resposta JSON ganha `custo_desembolso`:
  `{componentes, desembolso_cab_mes, custo_arroba, peso_medio_arroba}` para a UI
  exibir as duas unidades sem recomputar.

### 3. Frontend (`templates/index.html`)

**Fonte única de custo.** O novo painel de componentes passa a ser a **única**
origem de custo da tela — alimenta o parecer, a projeção de cenário e o
preview local. Some o campo antigo `sc-custo` (R$/@ único) e a tabela `CUSTO_S`.

- **Remover** a tabela `CUSTO_S`, suas funções (`renderCostTableS`,
  `hlCostLevel`), o const `CUSTO_S`, o input `sc-custo` e o input `s-nivel`
  (níveis baixo/médio/alto deixam de existir).
- **Novo painel "Estrutura de Custo (Desembolso)"** na aba de entrada
  (perto de "Solicitação de Crédito"):
  - 8 linhas (os componentes), input em R$/cab/mês (ids `cd-insumos`,
    `cd-mao_obra`, `cd-administracao`, `cd-maquinas`, `cd-pastagem`,
    `cd-infraestrutura`, `cd-taxas_impostos`, `cd-outros`), editáveis.
  - Botões de preset: "Média" e "Top Rentáveis" — preenchem os 8 campos com o
    preset da **modalidade classificada** (ou CICLO COMPLETO enquanto não houver
    classificação). Presets embutidos via JS const `PERFIL_DESEMBOLSO`
    espelhando o módulo backend (comentário citando a fonte GEP/Inttegra).
  - Rodapé ao vivo: **Total R$/cab/mês** e **≈ R$/@·ano**.
- **Helper JS `custoArrobaDerivado()`**: retorna o R$/@·ano a partir dos 8
  campos e da composição atual, com a **mesma fórmula do backend**:
  `pesoMedio = arrobasRebanho(v) / totalCabeças`;
  `custoArroba = (Σ componentes × 12) / pesoMedio`. Usa os pesos do motor
  (boi 20 / vaca 17 / bezerra 8 / garrote 12). Guarda: se total ≤ 0 → 0.
- **Usos do helper:**
  - Rodapé do painel (exibe as duas unidades).
  - `runSc()` (aba Projeção, `/api/cenario`): envia `custo: custoArrobaDerivado()`
    no lugar de `document.getElementById('sc-custo').value`.
  - `calcCiclo()` (preview local): o "Custo Total do Rebanho" passa a ser
    `totReb × desembolsoTotalMensal × 12` (custo anual do rebanho); remove a
    lógica `CUSTO_S[niv]` e o retorno de `cMat/cBoi/...`.
- No `fetch` de `/api/classificar`, enviar `custo_componentes`
  `{componente: valor}` com os 8 valores (0 quando vazio).
- `renderParecer` já mostra a geração de caixa; nenhuma mudança obrigatória lá,
  mas a conclusão passa a refletir o custo real por componentes.

## Fluxo de dados

```
Painel Estrutura de Custo (8 componentes R$/cab/mês, preset Média/Top)
        │  (rodapé mostra Total R$/cab/mês e ≈ R$/@·ano)
        │  POST /api/classificar { ..., custo_componentes }
        ▼
custos_desembolso: desembolso = Σ componentes
                   custo_arroba = desembolso×12 / (arrobas_rebanho/cabeças)
        ▼
simular_cenario(... custo_arroba) → geração de caixa
        ▼
montar_parecer → DSCR e conclusão refletem o custo real
resposta JSON { ..., custo_desembolso, parecer }
```

## Tratamento de erros / bordas

- **Sem componentes informados:** usa `custo_arroba` do campo/único default 57
  (retrocompatível).
- **Rebanho vazio / peso médio 0:** `custo_arroba_de_desembolso` retorna 0.0;
  o parecer trata custo 0 normalmente (não quebra).
- **Modalidade sem preset:** cai em `CICLO_COMPLETO`.
- **Componente ausente no dict:** conta como 0 na soma.

## Testes

`tests/test_custos_desembolso.py`:
- Conversão: desembolso conhecido + rebanho montado → `custo_arroba` bate num
  cálculo à mão (ex.: 100 R$/cab/mês, peso médio 15@ → 100×12/15 = 80 R$/@·ano).
- Borda: `total_cabecas = 0` → 0.0.
- Presets: `preset_modalidade('RECRIA', 'top')` devolve os 8 valores do bloco
  RECRIA_ENGORDA/top; soma dos presets bate com o TOTAL da tabela (integridade
  da fonte).
- Mapeamento: `ENGORDA` e `RECRIA` mapeiam para `RECRIA_ENGORDA`.

`tests/test_classificar_parecer.py` (estender):
- POST com `custo_componentes` → resposta traz `custo_desembolso` e o
  `custo_arroba` derivado ≠ 57 (confirma que os componentes dirigem o parecer).

## Critérios de sucesso

- A tabela `CUSTO_S` arbitrada some; o custo do parecer vem de **8 componentes
  com fonte real** (GEP), com presets Média/Top por modalidade.
- O analista preenche em R$/cab/mês e vê o equivalente em R$/@·ano; o motor usa
  o R$/@ derivado exato (sem supor peso).
- Aparece no frontend (novo painel) e alimenta a conclusão de crédito.
- Módulo de conversão/preset puro e coberto por testes; retrocompatível quando
  não há componentes.
