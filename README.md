# Plataforma de Análise de Crédito Pecuário

Sistema especializado em análise técnico-financeira de rebanho bovino para uso em **consultoria de crédito pecuária**. Classifica o tipo de exploração por Machine Learning, projeta a geração de caixa, avalia a consistência do rebanho declarado e emite um **parecer de crédito** com recomendação (Aprovar / Ressalva / Negar) baseada no DSCR (Debt Service Coverage Ratio).

## Funcionalidades

### Análise técnica
- Classificação ML do ciclo de produção: **Cria / Recria / Engorda / Ciclo Completo**
- Ensemble RandomForest + GradientBoosting + XGBoost/LightGBM (quando disponíveis)
- Indicadores zootécnicos vs benchmark regional (GEP Araguaia) e nacional (CEPEA, Embrapa, ABCZ, Scot)
- **Consistência do rebanho declarado** — detecta rebanho biologicamente implausível (bezerros vs matrizes, pirâmide etária, relação touro:matriz) e, quando há histórico da fazenda, compara com a declaração anterior (crescimento implausível, categorias que desaparecem)

### Financeiro e crédito
- Todos os preços e custos em **R$/@ (arroba)** — coerente com a convenção do mercado
- Estrutura de custo por componente (insumos, mão de obra, administração, máquinas, pastagem, infraestrutura, taxas, outros) com presets **Média / Top Rentáveis** do GEP Araguaia / Inttegra (safra 24/25)
- **Cotação diária automática**: boi (CEPEA/ESALQ via Notícias Agrícolas) e vaca (Scot), carregadas às 8h; bezerro/bezerra editáveis com referência de mercado
- Projeção financeira de 5 anos em 4 cenários; cada categoria valorada pelo seu preço do dia
- **Parecer de crédito consolidado**: DSCR, parcela Price, geração de caixa, recomendação com justificativa; rebaixa de "Aprovar" para "Ressalva" automaticamente quando há erros de consistência

### Consultoria e multiusuário
- **Multiempresa**: vários analistas de uma consultoria compartilham clientes (fazendas) por empresa; isolamento total entre empresas distintas
- **Marca própria** no PDF do parecer: logo e nome da consultoria configuráveis por empresa
- **Histórico de pareceres** por fazenda com download de PDF (reportlab, sem dependência de sistema)
- **Painel admin** para criar empresas e vincular/desvincular analistas

### Importação de dados
- Leitura de PDFs de GTAs/Fichas Sanitárias estaduais (IDARON-RO, INDEA-MT, IDARON-declaração)
- Template Excel (.xlsx) de composição do rebanho
- Câmera — leitura de múltiplos PDFs e combinação de rebanhos

## Tecnologia

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

## Instalação local

```bash
# 1. Dependências Python
pip install -r requirements.txt

# 2. (Opcional) Para leitura de PDF nativo:
# Ubuntu/Debian:
sudo apt install poppler-utils
# macOS:
brew install poppler

# 3. Rodar
python app.py
# Acesse: http://localhost:5050
```

## Variáveis de ambiente

| Variável | Descrição |
|----------|-----------|
| `DATABASE_URL` | PostgreSQL URL (ex.: Railway). Sem ela, usa SQLite local. |
| `SECRET_KEY` | Chave de sessão Flask (obrigatória em produção) |
| `ADMIN_EMAILS` | E-mails de administrador separados por vírgula |

## Deploy (Railway)

Push em `main` dispara o deploy automaticamente. O app detecta `DATABASE_URL` e usa PostgreSQL; sem ela, cai para SQLite.

```bash
git push origin main
```

## Arquitetura

```
app.py                      # Flask app, rotas, scheduler
ml_engine.py                # Classificação ML + simulações financeiras
database.py                 # Abstração cross-DB (SQLite/Postgres)
scraper.py                  # Coleta de cotações diárias
pdf_parsers.py              # Parsers de GTA/Ficha por estado

services/
  parecer_credito.py        # Price, DSCR, montagem do parecer
  parecer_pdf.py            # Geração de PDF com marca da consultoria
  consistencia_rebanho.py   # Análise de consistência (declaração + histórico)
  parametros_zootecnicos.py # Parâmetros sourced (benchmark nacional/regional)
  custos_desembolso.py      # Presets de desembolso GEP por componente
  pesos_rebanho.py          # Conversão cabeças → arrobas por categoria
  precos_diarios.py         # Parsing puro de cotações (sem rede)
  benchmarks_nacionais.py   # Benchmarks multifonte (CEPEA, Embrapa, ABCZ...)

templates/index.html        # SPA: entrada, resultado, cenários, histórico
templates/admin.html        # Painel de gestão de empresas e usuários

tests/                      # pytest (~175 testes)
docs/superpowers/
  specs/                    # Design docs de cada feature
  plans/                    # Planos de implementação
```

## API principais

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| POST | `/api/classificar` | Classificar rebanho + gerar parecer |
| POST | `/api/cenario` | Projeção de cenário 5 anos |
| GET  | `/api/empresa/ativa` | Empresa ativa da sessão |
| POST | `/api/empresa/ativa` | Trocar empresa ativa |
| GET/POST | `/api/empresa/perfil` | Marca da consultoria (nome/logo) |
| POST | `/api/parecer/pdf` | Gerar PDF do parecer |
| GET  | `/api/fazendas/<id>/pareceres` | Histórico de pareceres da fazenda |
| GET  | `/api/precos/live` | Cotação do dia (boi/vaca/bezerro/bezerra) |

### Exemplo: classificar e obter parecer

```python
import requests

r = requests.post('http://localhost:5050/api/classificar', json={
    'valores': [300, 280, 400, 200, 900, 1200, 250, 80, 600, 40],
    # [f00F, f00M, f05F, f05M, f13F, f13M, f25F, f25M, facF, facM]
    'preco': 330,           # R$/@ boi
    'custo_arroba': 57,     # R$/@ custo do plantel/ano
    'credito_valor': 500000,
    'prazo_meses': 24,
    'juros_aa': 0.10,
})
p = r.json()
print(p['classificacao'])                         # CICLO_COMPLETO
print(p['parecer']['conclusao']['recomendacao'])  # aprovar / ressalva / negar
print(p['parecer']['conclusao']['dscr'])          # ex.: 1.45
```

## Parâmetros zootécnicos de referência

Todos os parâmetros default têm fonte declarada em `services/parametros_zootecnicos.py`:

| Parâmetro | Valor | Fonte |
|-----------|-------|-------|
| Natalidade | 65% | Benchmark nacional (Embrapa/Scot/CEPEA/ABCZ) |
| Mortalidade | 3% | Benchmark regional (GEP Araguaia) |
| Desmame | 82% | Benchmark regional |
| Rendimento carcaça | 52% | Benchmark regional |
| Peso boi (@) | 18 | Padrão CEPEA/B3 (16–21@) |
| Peso vaca (@) | 14 | Mercado |
| Peso garrote (@) | 11 | Mercado |
| Peso bezerra (@) | 7 | Mercado |

## Testes

```bash
python -m pytest tests/ -v
# ~175 testes passam; ignorar test_pdf_reais_indea (PDFs locais) e test_csrf_e_limiter
```

## Direitos Autorais e Licença

© 2026 Lucas Vinicius. Todos os direitos reservados.

Este software é obra intelectual de Lucas Vinicius, protegido pela **Lei 9.610/98 (Lei de Direitos Autorais)** e pela **Lei 9.609/98 (Lei do Software)**, ambas do Brasil.

**É vedado**, sem autorização prévia e expressa por escrito do autor:
- Copiar, modificar, distribuir ou sublicenciar este software no todo ou em parte
- Usar o software para prestar serviços a terceiros sem licença comercial
- Remover ou alterar os avisos de direitos autorais

O registro da autoria e data de criação está documentado no histórico de commits deste repositório (`git log`), constituindo prova de anterioridade nos termos da legislação aplicável.

Para licenciamento comercial ou dúvidas: **viniciuslukas353@gmail.com**
