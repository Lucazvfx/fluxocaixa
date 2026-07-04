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

## Viabilidade (verificada ao vivo)

- **CEPEA direto bloqueia scraping** (`requests` → HTTP 403) e o **Índice do
  Bezerro do CEPEA é semanal**, não diário.
- **Boi:** ✅ **Notícias Agrícolas** (`/cotacoes/boi-gordo`, 200) republica o
  **indicador CEPEA/ESALQ** do boi de forma limpa e diária (ex.: 329,85).
- **Vaca:** ✅ **Scot** (`/cotacoes/vaca-gorda`, 200) — já usada no scraper;
  passa a ler praça nacional/média em vez de RO.
- **Bezerro:** ❌ **sem fonte diária gratuita scrapeável** — CEPEA bloqueado e
  semanal; Scot bezerro 404; Agrolink carrega via JavaScript (o `requests` não
  pega, e o deploy não roda navegador headless).
- **Bezerra:** deriva do bezerro por fator (fêmea ~5–7% abaixo por @/kg; usamos
  **0,90**, editável).

## Decisões de design

- **Boi e vaca — automáticos diários** (boi: Notícias Agrícolas/CEPEA-ESALQ;
  vaca: Scot), com cascata de fallback: fonte principal → **último valor salvo**
  → default de segurança. Nunca quebra; cada valor carrega sua `fonte`.
- **Bezerro — campo editável com default de referência sourced** (não há diário
  confiável). Default ancorado no mercado/CEPEA (~R$ 3.000/cab desmama), rótulo
  deixa claro que é referência editável, não cotação do dia.
- **Bezerra = bezerro × 0,90** (R$/cabeça).
- **Unidades:** boi e vaca em **R$/@**; bezerro e bezerra em **R$/cabeça**.
- **Nacional, não RO:** remove o forçamento de Rondônia do scraper.

## Componentes

### 1. Coletor `scraper.py` (estendido) + módulo puro de parsing

- Novo `services/precos_diarios.py` (puro, testável — recebe HTML, sem rede):
  - `parse_boi_na(html) -> float`: extrai o indicador **CEPEA/ESALQ** do boi da
    página da Notícias Agrícolas (âncora no texto "Indicador do Boi Gordo Esalq"
    → primeiro valor `\d{3},\d{2}` seguinte).
  - `parse_vaca_scot(html) -> float`: extrai a vaca da Scot (praça de referência
    nacional; primeiro valor válido).
  - `FATOR_BEZERRA = 0.90`; `BEZERRO_REF = 3000.0` (default de referência
    R$/cabeça, editável); `bezerra_de(bezerro) -> round(bezerro*0.90, 2)`.
  - `valido(v, lo, hi)`: sanidade por faixa (boi/vaca 100–600; bezerro 800–6000).
- `scraper.py`: `obter_precos_arroba()` passa a montar, com fallback por
  categoria:
  1. **Boi**: Notícias Agrícolas → (falha) último salvo → default.
  2. **Vaca**: Scot (sem forçar RO) → último salvo → default.
  3. **Bezerro**: último salvo (se o analista já ajustou) → `BEZERRO_REF`.
  4. **Bezerra**: `bezerra_de(bezerro)`.
  Retorna `{boi, vaca, boi_china, bezerro, bezerra, fonte}` (`fonte` = de onde
  veio boi/vaca, p/ rastreabilidade). Cada valor loga a origem.

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

- Novo painel **"Cotação do dia"** mostrando **boi** e **vaca** (com data e
  `fonte` — CEPEA/ESALQ e Scot) e os campos editáveis **bezerro** e **bezerra**
  (rotulados "referência, editável"). Bezerra recalcula ao editar bezerro
  (× 0,90), mas o analista pode sobrescrever.
- **Auto-preenchimento** (editável): ao carregar, busca `/api/cotacao-dia` e
  preenche `Preço Arroba` (projeção e sale-price panel) ← **boi** do dia; um
  botão "usar cotação do dia" reaplica se o analista editou.
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
- `parse_boi_na(html_fixo)` extrai o indicador CEPEA/ESALQ de um HTML de exemplo
  em `tests/fixtures/` (ex.: 329,85).
- `parse_vaca_scot(html_fixo)` extrai a vaca de um HTML de exemplo.
- `bezerra_de(3000) == 2700.0`.
- `valido(v, lo, hi)`: valor fora da faixa é rejeitado.

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
