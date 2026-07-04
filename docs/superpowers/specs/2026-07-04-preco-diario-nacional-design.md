# Preço diário nacional (boi, vaca, bezerro, bezerra)

**Data:** 2026-07-04
**Feature:** (A) de 2 (a (B), parâmetros zootécnicos, já foi entregue)
**Escopo:** puxar diariamente o preço de **média nacional** de boi, vaca, bezerro
e bezerra de fonte que credita o **CEPEA/ESALQ**, armazenar, e alimentar os
preços usados no cálculo (hoje um preço de arroba único fixo).
**Fora de escopo:** refatorar a projeção plurianual do motor para valorar cada
categoria pelo seu preço (o `simular_cenario` segue usando o preço da arroba,
agora preenchido com o boi do dia). O calculador local por categoria já usa
preços por categoria e passa a receber os do dia.

## Contexto e motivação

O usuário quer que o preço de cada categoria **siga a cotação diária nacional**,
não um número fixo. Já existe base: `scraper.py` (`obter_precos_arroba`) faz
scraping diário (lib `agrobr` + fallback **Scot Consultoria**), grava boi/vaca/
boi_china em `cotacao_arroba` via `db.guardar_cotacao_diaria`, com scheduler
`apscheduler` às 08h. **Limitações:** calibrado para **Rondônia** (força valores
RO) e **sem bezerro/bezerra**.

## Viabilidade (verificada)

- **CEPEA direto bloqueia scraping** (`requests` → HTTP 403). Não dá para bater
  na fonte primária.
- **Notícias Agrícolas** (`noticiasagricolas.com.br/cotacoes/boi-gordo`) responde
  200, **republica o indicador CEPEA/ESALQ** do boi e traz vaca e bezerro na
  página → é a fonte scrapeável que preserva a credibilidade CEPEA.
- **Bezerra** não tem índice diário próprio; deriva do bezerro por fator
  documentado (fêmea ~5–7% abaixo do macho por @/kg; usamos **0,90**,
  conservador e editável).

## Decisões de design

- **Fonte:** Notícias Agrícolas (indicador CEPEA/ESALQ) como **principal**;
  cascata de fallback: Scot (já no código) → **último valor salvo** no banco →
  default de segurança. Nunca quebra; sempre devolve algo com proveniência.
- **Categorias e unidades:** boi e vaca em **R$/@**; bezerro em **R$/cabeça**
  (convenção de mercado do índice); **bezerra = bezerro × 0,90** (R$/cabeça).
- **Nacional, não RO:** remove o forçamento de Rondônia; usa o indicador
  nacional CEPEA/ESALQ do boi. Vaca nacional idem; sem "calibração RO".

## Componentes

### 1. Coletor `scraper.py` (estendido) + módulo puro de parsing

- Novo `services/precos_diarios.py` (puro, testável): recebe o **HTML** e
  extrai `{boi, vaca, bezerro}` com regex/seletor da Notícias Agrícolas, e
  aplica `bezerra = round(bezerro * FATOR_BEZERRA, 2)` (`FATOR_BEZERRA = 0.90`).
  Função `parse_precos_na(html) -> dict`. Sem I/O (recebe o HTML já baixado) —
  assim testamos o parsing com um HTML fixo sem depender da rede.
- `scraper.py`: `obter_precos_arroba()` passa a tentar, em ordem:
  1. Notícias Agrícolas (baixa HTML → `parse_precos_na`).
  2. Scot (comportamento atual, mas **sem forçar RO** — praça nacional/média).
  3. Último salvo no banco (`db.buscar_cotacao_recente`).
  4. Defaults de segurança (constantes documentadas).
  Retorna `{boi, vaca, boi_china, bezerro, bezerra, fonte}` (novo campo `fonte`
  para rastreabilidade). Cada valor obtido loga a origem.

### 2. Persistência (`database.py`)

- `cotacao_arroba` ganha colunas `preco_bezerro REAL` e `preco_bezerra REAL`
  (via `_add_column_safe`, retrocompatível SQLite/Postgres).
- `guardar_cotacao_diaria(precos)` grava também bezerro/bezerra.
- `buscar_cotacao_recente()` devolve também bezerro/bezerra.

### 3. Endpoint (`app.py`)

- `GET /api/cotacao-dia` (novo ou estende o existente): devolve
  `{boi, vaca, bezerro, bezerra, data, fonte}` — a UI lê para preencher os
  campos de preço. A rotina diária (`rotina_diaria_cotacoes`) já existe; só
  passa a salvar as novas categorias.

### 4. UI (`templates/index.html`)

- Novo painel/rótulo **"Cotação do dia (CEPEA/nacional)"** mostrando os 4 preços
  e a data/fonte.
- **Auto-preenchimento** (editável): ao carregar, busca `/api/cotacao-dia` e
  preenche:
  - `Preço Arroba` (projeção e sale-price panel) ← **boi** do dia.
  - No calculador local (Preços de Venda), os valores por categoria passam a
    poder usar boi/vaca do dia (R$/@) e bezerro/bezerra do dia (R$/cabeça).
  - Um botão "usar cotação do dia" reaplica os valores se o analista editou.
- Se a cotação falhar, os campos mantêm os defaults sourced da feature (B).

## Fluxo de dados

```
Scheduler 08h  ──►  scraper.obter_precos_arroba()
                      ├─ Notícias Agrícolas (CEPEA/ESALQ)  [principal]
                      ├─ Scot (nacional)                    [fallback]
                      ├─ último salvo                       [fallback]
                      └─ defaults                           [fallback]
                            │  {boi,vaca,bezerro,bezerra,fonte}
                            ▼
                 db.guardar_cotacao_diaria → cotacao_arroba
                            ▼
UI  ──GET /api/cotacao-dia──►  preenche Preço Arroba (boi) + preços por categoria
                                (editáveis)  →  cálculo e parecer usam o preço do dia
```

## Tratamento de erros / bordas

- **Fonte principal fora do ar / layout mudou:** cai para Scot → último salvo →
  default. O campo `fonte` diz de onde veio; a UI mostra a origem e a data.
- **Valor absurdo** (ex.: pegou um número de outra seção): sanidade por faixa
  (boi/vaca 100–600 R$/@; bezerro 800–6000 R$/cab); fora da faixa → ignora e
  cai para o próximo fallback.
- **Sem rede / primeiro deploy sem cotação:** usa defaults de segurança
  documentados (últimos conhecidos), nunca zero.

## Testes

`tests/test_precos_diarios.py` (parsing puro, sem rede):
- `parse_precos_na(html_fixo)` extrai boi/vaca/bezerro corretos de um HTML de
  exemplo salvo em `tests/fixtures/`.
- `bezerra == round(bezerro * 0.90, 2)`.
- Sanidade de faixa: valor fora da faixa é rejeitado.

`tests/test_cotacao_db.py`:
- `guardar_cotacao_diaria` + `buscar_cotacao_recente` fazem round-trip de
  bezerro/bezerra (novas colunas), em SQLite.

`tests/test_cotacao_endpoint.py`:
- `GET /api/cotacao-dia` devolve as 4 categorias + data + fonte.

> Scraping ao vivo **não** é testado no CI (rede/fragilidade); o parsing é
> testado com HTML fixo. Um teste opcional marcado `@pytest.mark.network` pode
> bater na fonte real localmente.

## Critérios de sucesso

- Boi, vaca, bezerro, bezerra têm **cotação diária nacional** (CEPEA/ESALQ via
  Notícias Agrícolas), com fallback robusto e proveniência (`fonte`).
- Some o forçamento de Rondônia; os preços do cálculo passam a vir do dia,
  editáveis, com os defaults sourced da (B) como rede de segurança.
- Parsing puro coberto por teste com HTML fixo; persistência e endpoint testados.
- Nenhuma quebra quando a fonte falha.
