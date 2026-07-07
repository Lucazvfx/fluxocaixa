# Plataforma de Análise de Crédito Pecuário

Sistema especializado em análise técnico-financeira de rebanho bovino para uso em **consultoria de crédito pecuária**. Classifica o tipo de exploração por Machine Learning, projeta a geração de caixa pelo método GEP, avalia a consistência do rebanho declarado e emite um **parecer de crédito** com recomendação (Aprovar / Ressalva / Negar) baseado no DSCR (Debt Service Coverage Ratio).

---

## Sumário

1. [Funcionalidades](#1-funcionalidades)
2. [Fluxo de trabalho](#2-fluxo-de-trabalho)
3. [Classificação ML](#3-classificação-ml)
4. [Indicadores Zootécnicos e Benchmarks](#4-indicadores-zootécnicos-e-benchmarks)
5. [Consistência do Rebanho](#5-consistência-do-rebanho)
6. [Fluxo de Caixa — Metodologia GEP](#6-fluxo-de-caixa--metodologia-gep)
7. [Parecer de Crédito](#7-parecer-de-crédito)
8. [Sensibilidade de Preço](#8-sensibilidade-de-preço)
9. [Capacidade Máxima de Endividamento](#9-capacidade-máxima-de-endividamento)
10. [Ciclo Completo — Simulação Detalhada](#10-ciclo-completo--simulação-detalhada)
11. [Projeção 5 Anos](#11-projeção-5-anos)
12. [Reconciliação de Garantia](#12-reconciliação-de-garantia)
13. [Histórico de Pareceres](#13-histórico-de-pareceres)
14. [Multiempresa e Multiusuário](#14-multiempresa-e-multiusuário)
15. [Importação de Dados](#15-importação-de-dados)
16. [Cotações Automáticas](#16-cotações-automáticas)
17. [Export PDF com Marca da Consultoria](#17-export-pdf-com-marca-da-consultoria)
18. [Tecnologia e Arquitetura](#18-tecnologia-e-arquitetura)
19. [API Principal](#19-api-principal)
20. [Parâmetros de Referência](#20-parâmetros-de-referência)
21. [Instalação e Deploy](#21-instalação-e-deploy)
22. [Testes](#22-testes)
23. [Licença](#23-licença)

---

## 1. Funcionalidades

### Análise técnica
- Classificação automática do ciclo de produção: **Cria / Recria / Engorda / Ciclo Completo** via ensemble de ML
- Indicadores zootécnicos calculados automaticamente (relação F/M, % matrizes, pirâmide etária, bezerros estimados)
- Benchmarks vs. padrão regional (GEP Araguaia) e nacional multifonte (CEPEA, Embrapa, ABCZ, Scot, ASBIA, Inttegra)
- Análise de consistência do rebanho declarado com score de 0–100 e flags categorizados

### Financeiro e crédito
- **Fluxo de caixa método GEP**: resultado operacional (caixa) + variação de estoque do rebanho = resultado econômico total
- **Valoração do rebanho** por categoria com pesos e rendimento de carcaça do GEP Araguaia
- **Parecer de crédito** com DSCR, parcela Price, recomendação e justificativa
- **Análise de sensibilidade** de preço: 3 cenários automáticos (−15% / base / +15%)
- **Capacidade máxima de endividamento**: PV inverso do Price dado DSCR-alvo
- Projeção financeira de 5 anos em 4 cenários (otimista, crescimento, alta venda, conservador)
- Breakeven de preço por ciclo de produção

### Consultoria e operação
- **Multiempresa**: analistas de uma consultoria compartilham clientes; isolamento total entre empresas
- **Marca própria** no PDF: logo e nome da consultoria por empresa
- **Histórico de pareceres** por fazenda com download em PDF
- **Reconciliação de garantia**: cruza ficha sanitária × IR × GTA para detectar rebanho superavaliado
- Retreino do modelo ML com dados confirmados pelos analistas

### Importação
- PDFs de IDARON-RO, INDEA-MT e GTA estadual (extração automática de composição)
- Template Excel (.xlsx) de composição do rebanho
- Múltiplos arquivos simultâneos (soma rebanhos de várias fazendas)

---

## 2. Fluxo de trabalho

```
1. INSERIR DADOS
   └── Fazenda, proprietário, município
   └── Composição do rebanho por faixa etária (manual / PDF / planilha)
   └── Solicitação de crédito (valor, prazo, juros, carência, dívidas existentes)
   └── Cotação automática do dia (boi, vaca, bezerro, bezerra)

2. CLASSIFICAR
   └── ML classifica: Cria / Recria / Engorda / Ciclo Completo
   └── Calcula indicadores, benchmarks e consistência
   └── Gera fluxo de caixa GEP + valoração do rebanho
   └── Emite parecer com DSCR e recomendação
   └── Calcula 3 cenários de sensibilidade de preço

3. RESULTADO
   └── Banner APROVAR / RESSALVA / NEGAR (em destaque)
   └── KPIs: DSCR, parcela/mês, geração de caixa/ano, crédito máximo
   └── Fluxo de caixa GEP com variação de estoque
   └── 3 cards de sensibilidade de preço
   └── Benchmarks, pirâmide etária, indicadores, recomendações técnicas
   └── Valor total do rebanho (R$)

4. SIMULAR CENÁRIOS (Ciclo Completo)
   └── Dashboard, parâmetros, rebanho, reprodução, vendas, financeiro, projeção 5 anos

5. EXPORTAR
   └── PDF do parecer com marca da consultoria
   └── Salvar no histórico da fazenda
```

---

## 3. Classificação ML

### Entrada

Vetor de **10 valores** representando a composição do rebanho por faixa etária e sexo:

```
v = [fêmeas 00–04m,  machos 00–04m,
     fêmeas 05–12m,  machos 05–12m,
     fêmeas 13–24m,  machos 13–24m,
     fêmeas 25–36m,  machos 25–36m,
     fêmeas adultas, machos adultos]
```

### Saída

| Classe | Tipo | Característica |
|--------|------|----------------|
| 0 | **CRIA** | Predomínio de matrizes; produção de bezerros |
| 1 | **RECRIA** | Alta concentração 13–24m; desenvolvimento pós-desmame |
| 2 | **ENGORDA** | Machos adultos dominam; terminação para abate |
| 3 | **CICLO_COMPLETO** | Todas as fases integradas na mesma propriedade |

### Modelo

Ensemble **VotingClassifier** (soft voting — média de probabilidades):
- `RandomForestClassifier` (100 estimadores)
- `GradientBoostingClassifier`
- `XGBClassifier` (quando disponível)
- `MLPClassifier` — rede neural 2 camadas ocultas
- Pré-processamento: `StandardScaler` + `Pipeline` scikit-learn

**Acurácia típica: ~99.8%** sobre dataset sintético de 3.902 amostras.

### Retreino

Cada confirmação ou correção de classificação pelo analista dispara retreino em background. O novo modelo substitui o anterior em disco (`gestao_model.pkl`) se a acurácia melhorar.

---

## 4. Indicadores Zootécnicos e Benchmarks

### Indicadores calculados automaticamente

| Indicador | Fórmula |
|-----------|---------|
| Total do rebanho | soma de todas as categorias |
| Fêmeas / Machos | somas por sexo |
| Cria (0–12m) | v[0]+v[1]+v[2]+v[3] |
| Recria (13–24m) | v[4]+v[5] |
| Adultos (25m+) | v[6]+v[7]+v[8]+v[9] |
| Matrizes adultas | fêmeas adultas (v[8]) |
| Razão ♀/♂ | total_fêmeas / total_machos |
| % Matrizes | matrizes / total |
| Bezerros estimados/ano | matrizes × natalidade |

### Benchmarks regionais — GEP Araguaia (RO/MT)

Comparação de mortalidade, desmama, rendimento de carcaça e ganho de peso com os padrões do GEP Araguaia. Classificação em faixas: **excelente / bom / médio / abaixo**.

### Benchmarks nacionais — multifonte

Fontes: CEPEA/ESALQ, Embrapa, ABCZ, ASBIA, Scot Consultoria, Inttegra.

| Indicador | Parâmetro avaliado | Faixas |
|-----------|--------------------|--------|
| Taxa de natalidade | % bezerros nascidos / matrizes | excelente ≥ 80% |
| Taxa de prenhez | % vacas prenhes | excelente ≥ 82% |
| Desfrute | % animais vendidos / rebanho total | referência nacional |
| Desembolso | R$/cabeça/mês (custo operacional) | benchmarks por fase |

Cada indicador retorna: valor declarado, faixa de benchmark, posição relativa (dentro / acima / abaixo).

---

## 5. Consistência do Rebanho

Sistema de auditoria lógica que atribui um **score de 0–100** ao rebanho declarado.

### Flags gerados automaticamente

| Flag | Tipo | Critério |
|------|------|---------|
| Pirâmide invertida | erro | bezerros > adultos × fator esperado |
| Touro impossível | erro | sem bois com muitas matrizes |
| Matrizes sem bezerros | alerta | matrizes adultas mas zero bezerros |
| Relação F/M anômala | alerta | proporção fora de padrão por ciclo |
| Crescimento implausível | erro | rebanho cresceu > 200% em 12 meses (histórico) |
| Categoria desaparecida | alerta | categoria com > 50 cabeças sumiu no histórico |

### Impacto no parecer

Se `erros > 0` e recomendação seria `aprovar`, o sistema rebaixa automaticamente para `ressalva` e inclui justificativa: _"Rebaixado: X erro(s) de consistência no rebanho declarado invalidam a projeção."_

---

## 6. Fluxo de Caixa — Metodologia GEP

O GEP (Grupo de Estudo em Pecuária de Corte — Araguaia) usa uma metodologia específica de valoração por categoria. O sistema implementa o modelo da **MODELAGEM RESULTADO CC 2** (safra 24/25).

### Categorias e pesos de valoração

| Categoria | Arrobas | Rendimento | Base de cálculo |
|-----------|---------|-----------|-----------------|
| Boi adulto | 20,53@ | 55% RC | preco_boi |
| Vaca/Matriz | 15,33@ | 50% RC | preco_vaca |
| Garrote 13–24m | 10,67@ | 50% RC | média (boi+vaca)/2 |
| Novilha 13–24m | 9,33@ | 50% RC | média (boi+vaca)/2 |
| Bezerro 0–12m | 6,67@ | 50% RC | preco_bezerro (cab) |
| Bezerra 0–12m | 6,00@ | 50% RC | preco_bezerra (cab) |

> **Nota**: todas as arrobas são equivalente-carcaça. Boi com 20,53@ em pé × 55% RC = 11,29@ carcaça. Os pesos e rendimentos vêm diretamente do GEP Araguaia.

### Valoração do rebanho (`valor_rebanho_gep`)

```
valor_matrizes  = matrizes × 15,33 × preco_vaca
valor_bois      = bois     × 20,53 × preco_boi
valor_jovens_f  = jovens_f × 7,67  × ((preco_boi + preco_vaca) / 2)
valor_jovens_m  = jovens_m × 8,67  × ((preco_boi + preco_vaca) / 2)

valor_rebanho   = valor_matrizes + valor_bois + valor_jovens_f + valor_jovens_m
```

### DRE do fluxo de caixa GEP (`calcular_fluxo_gep`)

```
(+) Receita de vendas
(−) Custo operacional
(−) Reposição de reprodutores (opcional)
(=) RESULTADO OPERACIONAL (caixa)         ← geração de caixa para DSCR

(±) Variação de estoque do rebanho        ← valor_rebanho_fim − valor_rebanho_ini
(=) RESULTADO ECONÔMICO TOTAL             ← riqueza criada (caixa + patrimônio)

(−) Serviço da dívida anual (se houver)
(=) FLUXO LIVRE
```

> **Importante**: o DSCR é calculado sobre o **resultado operacional (caixa)**, não sobre o resultado econômico. A variação de estoque representa riqueza real do ativo, mas não é caixa disponível para pagar dívida.

### Estrutura de custo por componente

Presets GEP Araguaia / Inttegra (safra 24/25) em R$/cabeça/mês:

| Componente | Média | Top Rentáveis |
|------------|-------|---------------|
| Insumos do rebanho | 44,92 | — |
| Mão de obra | 18,10 | — |
| Administração | 8,49 | — |
| Máquinas (custeio+inv.) | 15,23 | — |
| Pastagem (custeio+inv.) | 14,29 | — |
| Infraestrutura | 13,69 | — |
| Taxas e impostos | 3,66 | — |
| Outros | 0,76 | — |
| **Total** | **119,14** | — |

Custo configurável por fase (cria, recria, engorda separadamente). Quando preenchido, sobrepõe o custo geral.

---

## 7. Parecer de Crédito

### Parcela Price (sistema francês)

```
i_mensal = (1 + juros_aa)^(1/12) − 1

parcela = PV × i_mensal / (1 − (1 + i_mensal)^(−n))
```

Onde:
- `PV` = valor do crédito solicitado
- `n` = prazo em meses − carência em meses
- `juros_aa` = taxa de juros nominal anual (ex.: 0,10 = 10% a.a.)
- Se `juros_aa = 0`: `parcela = PV / n` (amortização linear)

### Serviço da dívida anual

```
servico_anual = 12 × (parcela + dividas_mensais_existentes)
```

### DSCR — Debt Service Coverage Ratio

```
DSCR = resultado_operacional_anual / servico_anual
```

### Faixas de recomendação

| DSCR | Recomendação |
|------|-------------|
| ≥ 1,30 | **APROVAR** |
| 1,00 a 1,29 | **APROVAR COM RESSALVA** |
| < 1,00 | **NEGAR** |
| — (sem crédito) | Sem conclusão |

> O DSCR de 1,30 significa que o produtor gera 30% mais caixa do que o necessário para pagar a dívida — margem de segurança padrão do mercado de crédito rural.

---

## 8. Sensibilidade de Preço

Após classificar, o sistema gera automaticamente **3 simulações** variando o preço da arroba:

| Cenário | Fator | Descrição |
|---------|-------|-----------|
| ▼ Queda 15% | 0,85 × preço base | pior caso de mercado |
| ● Base | 1,00 × preço base | cotação do dia |
| ▲ Alta 15% | 1,15 × preço base | cenário favorável |

Para cada cenário, recalcula:
- Geração de caixa (resultado operacional)
- DSCR com o mesmo serviço de dívida
- Recomendação (Aprovar / Ressalva / Negar)

Uso: o consultor vê de imediato se o crédito **sobrevive a uma queda de 15% do boi** — principal risco de mercado na pecuária.

---

## 9. Capacidade Máxima de Endividamento

Dado o DSCR-alvo (padrão 1,30), calcula qual o **maior crédito** que a fazenda consegue suportar no prazo e taxa informados — inverso do Price.

### Fórmula

```
caixa_disponivel = resultado_operacional / DSCR_alvo − 12 × dividas_mensais
parcela_max      = caixa_disponivel / 12

PV_max = parcela_max × (1 − (1 + i_mensal)^(−n)) / i_mensal
```

Onde `n = prazo_meses − carencia_meses`.

Exibido no KPI strip do resultado: **Crédito Máximo (R$)**.

---

## 10. Ciclo Completo — Simulação Detalhada

Aba com gestão financeira completa do ciclo de produção. Sub-seções:

### Dashboard
- Composição do rebanho (barras por categoria)
- Animais vendidos (barras)
- Receita por categoria (barras com R$)
- Fluxo de renovação de bois reprodutores

### Parâmetros
Configuração completa:

| Parâmetro | Descrição |
|-----------|-----------|
| Matrizes / Bois adultos / Jovens | Plantel base |
| Taxa natalidade | % bezerros nascidos/ano |
| Proporção boi/matriz | 1 boi : X matrizes |
| Renovação de bois (%) | % bois trocados/ano |
| Descarte de matrizes (%) | % vacas vendidas/ano |
| Venda de bezerras (%) | % bezerras vendidas |
| Cotação do dia | boi (CEPEA), vaca (Scot), bezerro/bezerra |
| Peso boi / vaca / bezerra | em arrobas (@) |
| Preço arroba | R$/@ usados na receita |
| Desembolso | R$/cabeça/mês por fase ou geral |

Parâmetros por ciclo são persistidos no `localStorage` do navegador.

### Reprodução
- Número de bois necessários (matrizes / proporção_boi)
- Bois a renovar no ano (rebanho × renovação)
- Matrizes a descartar (matrizes × descarte)
- Produção de bezerros: `matrizes × natalidade`
- Desmamados: `bezerros × desmama`

### Vendas — cálculo por categoria

```python
bezerros_desmamados = matrizes × natalidade × desmama
machos_desmamados   = bezerros_desmamados × 0,5
femeas_desmamados   = bezerros_desmamados × 0,5

bois_vendidos       = bois_adultos × desfrute_boi
matrizes_descarte   = matrizes × desc_mat_pct
bezerras_vendidas   = femeas_desmamados × venda_bez_pct
```

### Financeiro

```
Receita = bois_vend    × peso_boi  × preco_arroba
        + desc_mat     × peso_vaca × preco_arroba
        + bez_vend     × preco_bezerra (em R$/cab)

Custo   = total_rebanho × desembolso × 12

Resultado = Receita − Custo
```

### Breakeven de preço

```python
peso_medio   = (bois_vend × peso_boi + desc × peso_vaca + ...) / total_vendidos
unidades_arr = total_vendidos × peso_medio
preco_be     = custo_total / unidades_arr   # R$/@ — ciclos completo/recria/engorda
```
Para **CRIA**: resultado em R$/cabeça (venda de bezerros).

---

## 11. Projeção 5 Anos

4 cenários de simulação plurianual com parâmetros editáveis:

| Cenário | Estratégia |
|---------|-----------|
| Otimista | IATF, suplementação, genética melhorada. Alta natalidade. |
| Crescimento Gradual | Expansão sustentável com reinvestimento. |
| Alta Venda | Maximiza venda aproveitando preço favorável (reduz rebanho). |
| Conservador | Manutenção mínima — baixa de preços. |

Cada cenário modifica internamente: natalidade, taxa de descarte, venda de bezerras, mortalidade e fator de expansão/contração.

### Projeção anual (5 iterações)

```python
for ano in range(1, 6):
    bezerros = matrizes × natalidade × (1 − mortalidade)
    bois_vendidos = bois × desfrute
    matrizes_desc = matrizes × descarte
    receita = calcular_receita(bois_vendidos, matrizes_desc, bezerros_vendidos, ...)
    custo   = rebanho × custo_cab_ano
    resultado = receita − custo

    # Rebanho do próximo ano:
    matrizes += bezerros_reposicao − matrizes_desc
    bois     = max(bois + bois_renovados, 0)
```

Resultado: tabela ano a ano com receita, custo, resultado, rebanho total e preço de breakeven.

---

## 12. Reconciliação de Garantia

Cruza o rebanho declarado em **diferentes documentos** para detectar discrepância (rebanho de papel > físico).

| Documento | O que representa |
|-----------|-----------------|
| Ficha Sanitária (IDARON/INDEA) | Piso físico — animais vacinados; não pode ser forjado |
| Imposto de Renda (IR) | Declaração do produtor à Receita Federal |
| GTA (Guia de Trânsito Animal) | Movimentações recentes |

### Alertas gerados

- **Ficha > IR**: rebanho vacinado maior que o declarado no IR → subdeclaração no IR
- **IR > Ficha × 1,5**: IR muito acima da ficha → rebanho "de papel"
- **GTA inconsistente**: movimentações maiores que o rebanho declarado

---

## 13. Histórico de Pareceres

Para fazendas cadastradas como cliente, todos os pareceres gerados são salvos com:
- Data da análise
- Composição do rebanho no momento
- Resultado (tipo ML, DSCR, recomendação)
- Link para download do PDF

Permite acompanhar a **evolução financeira e estrutural da fazenda** ao longo do tempo e comparar rebanhos declarados em datas diferentes (base para o alerta de crescimento implausível).

---

## 14. Multiempresa e Multiusuário

### Estrutura

```
Empresa A (Consultoria X)
├── Analista 1 (admin)
├── Analista 2
└── Fazendas: [Farm1, Farm2, Farm3]

Empresa B (Consultoria Y)
├── Analista 3
└── Fazendas: [Farm4, Farm5]
```

- Isolamento total: analistas da Empresa A **não enxergam** dados da Empresa B
- Um usuário pode ser membro de **múltiplas empresas** e trocar a empresa ativa pelo seletor no header
- O painel `/admin` gerencia empresas, cria vínculos e promove/remove membros
- Quando uma empresa é criada, o criador recebe papel de `admin` automaticamente

### Marca da consultoria no PDF

Configurável por empresa:
- Nome da consultoria (aparece no cabeçalho do PDF)
- Logo em base64 (PNG/JPG, máx ~4cm de largura no PDF)

---

## 15. Importação de Dados

### PDFs suportados

| Documento | Estado | Parser |
|-----------|--------|--------|
| Saldo Atual da Exploração (INDEA) | Mato Grosso | `parsers/indea.py` |
| Declaração de Existência (IDARON) | Rondônia | `parsers/idaron.py` |
| GTA / Ficha de Declaração (IDARON) | Rondônia | `pdf_parsers.py` |

O parser usa `pdfplumber` para extrair texto e identificar categorias por expressões regulares ajustadas ao formato de cada órgão estadual.

Múltiplos PDFs podem ser enviados de uma vez — o sistema **soma os rebanhos** (para fazendas partilhadas ou lotes em propriedades diferentes).

### Planilha Excel (.xlsx)

Template disponível para download na interface (`/api/template/download`). Formato:

```
Faixa Etária | Fêmeas | Machos
00–04 meses  |   300  |   280
05–12 meses  |   400  |   200
...
```

---

## 16. Cotações Automáticas

### Fontes

| Preço | Fonte | Frequência |
|-------|-------|-----------|
| Boi gordo (R$/@) | CEPEA/ESALQ via Notícias Agrícolas | Diária às 8h |
| Vaca gorda (R$/@) | Scot Consultoria | Diária às 8h |
| Bezerro (R$/cab) | Referência editável | Manual |
| Bezerra (R$/cab) | Bezerro × 0,90 | Automático |

### Fluxo

1. Ao iniciar o servidor, `scraper.py` tenta buscar cotações online
2. Preços são salvos em `cotacoes_diarias` no banco
3. Diariamente às 08h o scheduler repete a busca (APScheduler)
4. Frontend carrega os preços via `/api/precos/live` ao abrir a página
5. Campos `cot-boi`, `cot-vaca`, `cot-bezerro`, `cot-bezerra` são preenchidos automaticamente
6. Faixa de cotação exibida acima do botão Classificar confirma os valores em uso

---

## 17. Export PDF com Marca da Consultoria

Gerado com **reportlab** (puro Python, sem dependência de sistema).

### Seções do PDF

1. Logo e nome da consultoria (se configurados)
2. Identificação: fazenda, município, proprietário, data
3. Composição do rebanho
4. Indicadores vs. benchmark
5. Consistência do rebanho (score + flags)
6. Situação financeira (breakeven)
7. **Fluxo de Caixa — Método GEP** (DRE completo)
8. **Sensibilidade de Preço** (tabela 3 cenários)
9. **Conclusão** com banner colorido APROVAR / RESSALVA / NEGAR
   - DSCR, parcela, crédito máximo, justificativa

---

## 18. Tecnologia e Arquitetura

### Stack

| Camada | Tecnologia |
|--------|-----------|
| Backend | Python 3.10 + Flask |
| ML | scikit-learn, XGBoost, LightGBM |
| Banco | PostgreSQL (produção via Railway) / SQLite (desenvolvimento) |
| PDF geração | reportlab |
| PDF leitura | pdfplumber |
| Frontend | HTML/CSS/JS puro (sem framework) |
| Scheduler | APScheduler |
| Deploy | Railway (auto-deploy via push em `main`) |

### Arquitetura de arquivos

```
app.py                      # Flask app — rotas, auth, scheduler
ml_engine.py                # Ensemble ML + simulações financeiras (calcular_ano, simular_cenario)
database.py                 # Abstração cross-DB SQLite/PostgreSQL
scraper.py                  # Coleta diária de cotações (CEPEA/Scot)
pdf_parsers.py              # Parser raiz de PDF (dispatcha para parsers por estado)

services/
  fluxo_caixa_gep.py        # Valoração GEP + DRE (resultado operacional / econômico)
  parecer_credito.py        # Price, DSCR, crédito máximo, montagem do parecer
  parecer_pdf.py            # Geração de PDF do parecer (reportlab)
  consistencia_rebanho.py   # Score de consistência + flags
  parametros_zootecnicos.py # Parâmetros sourced (benchmark nacional/regional)
  custos_desembolso.py      # Presets de desembolso GEP por componente e fase
  pesos_rebanho.py          # Conversão cabeças → arrobas por categoria
  precos_diarios.py         # Parsing puro de cotações (sem rede)
  benchmarks_nacionais.py   # Benchmarks multifonte (CEPEA, Embrapa, ABCZ, ASBIA, Scot)
  reconciliacao.py          # Reconciliação de documentos de garantia

parsers/
  indea.py                  # Parser INDEA-MT (Saldo Atual da Exploração)
  idaron.py                 # Parser IDARON-RO

templates/
  index.html                # SPA — entrada, resultado, cenários, reconciliação, histórico
  admin.html                # Painel de gestão de empresas e usuários
  login.html                # Login
  cadastro.html             # Cadastro de conta

tests/                      # pytest — ~175 testes automatizados
docs/superpowers/
  specs/                    # Design docs de cada feature
  plans/                    # Planos de implementação
```

---

## 19. API Principal

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| POST | `/api/classificar` | Classificar rebanho + gerar parecer completo |
| POST | `/api/cenario` | Projeção de cenário para Ciclo Completo |
| GET  | `/api/precos/live` | Cotações do dia (boi/vaca/bezerro/bezerra) |
| GET  | `/api/empresa/ativa` | Empresa ativa da sessão |
| POST | `/api/empresa/ativa` | Trocar empresa ativa |
| GET/POST | `/api/empresa/perfil` | Marca da consultoria (nome + logo base64) |
| POST | `/api/parecer/pdf` | Gerar PDF do parecer |
| GET  | `/api/fazendas` | Listar fazendas da empresa ativa |
| POST | `/api/fazendas` | Criar nova fazenda |
| GET  | `/api/fazendas/<id>/pareceres` | Histórico de pareceres da fazenda |
| POST | `/api/ler-pdf` | Extrair composição de PDF (INDEA/IDARON) |
| GET  | `/api/template/download` | Download do template Excel |
| POST | `/api/confirmar` | Confirmar/corrigir classificação ML |
| POST | `/api/retreinar` | Retreinar modelo com dados confirmados |
| POST | `/api/reconciliar` | Reconciliar documentos de garantia |

### Exemplo: classificar e obter parecer

```python
import requests

r = requests.post('http://localhost:5050/api/classificar', json={
    # Composição do rebanho: [f00F, f00M, f05F, f05M, f13F, f13M, f25F, f25M, facF, facM]
    'valores': [300, 280, 400, 200, 900, 1200, 250, 80, 600, 40],

    # Cotações (R$/@)
    'preco_boi': 330,
    'preco_vaca': 260,
    'preco_bezerro': 1800,   # R$/cabeça
    'preco_bezerra': 1620,   # R$/cabeça

    # Crédito solicitado
    'credito_valor': 500000,
    'prazo_meses': 24,
    'juros_aa': 0.10,
    'carencia_meses': 0,
    'dividas_mensais': 0,

    # Identificação (opcional)
    'fazenda': 'Fazenda Modelo',
    'municipio': 'Sinop - MT',
    'proprietario': 'João da Silva',
})
p = r.json()

print(p['classificacao'])                           # CICLO_COMPLETO
print(p['confianca'])                               # 98 (%)
print(p['parecer']['conclusao']['recomendacao'])    # aprovar
print(p['parecer']['conclusao']['dscr'])            # ex.: 1.45
print(p['parecer']['conclusao']['capacidade_maxima'])  # crédito máximo (R$)
print(p['fluxo_gep']['resultado_operacional'])      # geração de caixa anual
print(p['fluxo_gep']['variacao_estoque'])           # variação de patrimônio
print(p['sensibilidade'])                           # lista com 3 cenários de preço
```

---

## 20. Parâmetros de Referência

### Parâmetros zootécnicos default (com fonte)

| Parâmetro | Valor default | Fonte |
|-----------|--------------|-------|
| Taxa de natalidade | 65% | Benchmark nacional médio (Embrapa/Scot/CEPEA/ABCZ) |
| Mortalidade geral | 3% | GEP Araguaia |
| Taxa de desmama | 82% | GEP Araguaia |
| Rendimento de carcaça | 52% | GEP Araguaia (benchmark regional) |
| Ganho de peso | 0,55@/mês | GEP Araguaia |
| Proporção boi/matriz | 1:30 | Padrão Ciclo Completo |
| Renovação de bois | 20%/ano | Padrão mercado |
| Descarte de matrizes | 30%/ano | Padrão mercado |
| Peso boi adulto | 18–20@ | CEPEA/B3 (16–21@) |
| Peso vaca descarte | 14–15@ | Mercado MT/RO |
| Peso bezerra | 7@ | Mercado |

### Política de crédito

| Parâmetro | Valor | Descrição |
|-----------|-------|-----------|
| `DSCR_APROVAR` | 1,30 | Mínimo para aprovar sem restrição |
| `DSCR_RESSALVA` | 1,00 | Mínimo para aprovar com ressalva |
| DSCR-alvo (crédito máximo) | 1,30 | Referência para cálculo de PV máximo |

---

## 21. Instalação e Deploy

### Local

```bash
# 1. Dependências
pip install -r requirements.txt

# 2. Rodar
python app.py
# http://localhost:5050

# 3. Criar conta em /cadastro e fazer login
```

### Variáveis de ambiente

| Variável | Descrição |
|----------|-----------|
| `DATABASE_URL` | PostgreSQL URL (Railway). Sem ela, usa SQLite local. |
| `SECRET_KEY` | Chave de sessão Flask (obrigatória em produção) |
| `ADMIN_EMAILS` | E-mails de admin, separados por vírgula |

### Railway (produção)

Push em `main` dispara deploy automático:

```bash
git push origin main
```

O app detecta `DATABASE_URL` e usa PostgreSQL; sem ela, SQLite.

---

## 22. Testes

```bash
# Rodar todos os testes (175 passam)
python -m pytest tests/ -v

# Ignorar testes que precisam de arquivos locais
python -m pytest tests/ -v \
  --ignore=tests/test_pdf_reais_indea.py \
  --ignore=tests/test_csrf_e_limiter.py \
  --ignore=tests/test_benchmarks_reais.py
```

### Cobertura

| Arquivo | O que testa |
|---------|------------|
| `test_parecer_credito.py` | Price, DSCR, crédito máximo, montar_parecer |
| `test_fluxo_caixa_gep.py` | Valoração GEP, DRE completo |
| `test_ml_engine.py` | Classificação, calcular_ano, simular_cenario, benchmarks |
| `test_consistencia.py` | Flags de consistência, score |
| `test_reconciliacao.py` | Reconciliação de documentos |
| `test_pdf_reais_indea.py` | Parsers reais INDEA-MT (requer PDFs locais) |

---

## 23. Licença

© 2026 Lucas Vinicius. Todos os direitos reservados.

Este software é obra intelectual de Lucas Vinicius, protegido pela **Lei 9.610/98 (Lei de Direitos Autorais)** e pela **Lei 9.609/98 (Lei do Software)**, ambas do Brasil.

**É vedado**, sem autorização prévia e expressa por escrito do autor:
- Copiar, modificar, distribuir ou sublicenciar este software no todo ou em parte
- Usar o software para prestar serviços a terceiros sem licença comercial
- Remover ou alterar os avisos de direitos autorais

O registro da autoria e data de criação está documentado no histórico de commits deste repositório (`git log`), constituindo prova de anterioridade nos termos da legislação aplicável.

Para licenciamento comercial: **viniciuslukas353@gmail.com**
