# Classificador de Exploração Bovina & Analise

Sistema Python com Machine Learning para classificar tipo de exploração bovina
(Cria / Recria / Engorda / Ciclo Completo) com simulação de cenários financeiros.

## Tecnologia
- **Backend:** Python + Flask
- **ML:** scikit-learn (Random Forest + Gradient Boosting — Ensemble VotingClassifier)
- **PDF:** pdftotext + pdfplumber
- **Frontend:** HTML/CSS/JS puro (sem framework)

## Instalação

```bash
# 1. Instalar dependências Python
pip install -r requirements.txt

# 2. (Opcional) Para leitura de PDF:
# Ubuntu/Debian:
sudo apt install poppler-utils

# macOS:
brew install poppler
```

## Uso

```bash
python app.py
```
.\venv\Scripts\Activate

Acesse: **http://localhost:5050**

## Integração com agrobr (preços de commodities)

Se quiser que o endpoint `/api/precos/live` retorne cotações diretamente da fonte oficial via `agrobr`, instale a biblioteca:

```powershell
pip install agrobr
```

Passos / exemplo de uso (Python):

```python
from agrobr import datasets
import asyncio

async def buscar_precos():
    df = await datasets.preco_diario('boi')
    print(df.head())

asyncio.run(buscar_precos())
```

No projeto, o endpoint `/api/precos/live` foi configurado para exigir `agrobr` (sem fallback). Se a biblioteca não estiver instalada, a rota retornará um erro 503 com a mensagem de instrução para instalar `agrobr`.

Se preferir continuar usando o scraper HTML como fallback (método atual agendado), não é necessário instalar `agrobr` — a rotina diária que popula o banco (`rotina_diaria_cotacoes`) continuará usando o scraper antigo.

## Testes (parser PDF)

Adicionei um teste útil para validar que o parser `parsear_idaron` consegue processar a sua "Ficha de Gado 5.pdf" corretamente. O teste está em `tests/test_ficha5.py` e procura o PDF nas pastas padrão abaixo (ordem):

- `%HOMEPATH%\Downloads\Ficha de Gado 5.pdf`
- `c:\Users\Lucas\Downloads\Ficha de Gado 5.pdf`

Como correr o teste localmente:

- Usando pytest (recomendado quando tiver `pytest` instalado):
```powershell
pip install -r requirements.txt
pip install pytest
python -m pytest tests/test_ficha5.py -q
```

- Sem pytest (rápido, portátil):
```powershell
python -c "from pdf_parsers import extrair_texto_pdf, parsear_idaron; import os, json, sys
p=r'c:\Users\Lucas\Downloads\Ficha de Gado 5.pdf'
if not os.path.exists(p): print('PDF not found'); sys.exit(0)


# No seu computador, na pasta do projeto
git add .
git commit -m "Descrição das alterações"
```

Se preferir que o repositório contenha o PDF para execução automática em CI, copie `Ficha de Gado 5.pdf` para `tests/fixtures/` e atualize o caminho no teste (ou eu faço isso por você). Isso garante que o teste rode de forma determinística no pipeline.
git push origin main   
# ou a branch que você configurou no Railway

## Funcionalidades

### 📝 Inserir Dados Manualmente
- Tabela por faixa etária (0-4m, 5-12m, 13-24m, 25-36m, Acima 36m)
- Fêmeas e machos separados
- Exemplos pré-carregados (Ciclo Completo, Cria, Recria, Engorda, INDEA)
- Totalizadores em tempo real

### 📋 Ler PDF
- Upload do "Saldo Atual da Exploração"
- Extração automática de todos os dados
- Pré-visualização antes de classificar

### 🧠 Resultado ML
- Tipo de exploração com probabilidades por categoria
- Pirâmide etária do rebanho
- Indicadores zootécnicos (razão F/M, % cria, % recria, etc.)
- Recomendações técnicas específicas

### 📈 Simulação de Cenários (5 anos)
- 4 cenários: Otimista, Crescimento, Especulativo, Conservador
- Parâmetros ajustáveis em tempo real
- Projeção: rebanho, bezerros, vendidos, receita, custo, resultado
- Gráfico de barras + tabela detalhada

## API Endpoints

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET  | `/` | Interface web |
| POST | `/api/classificar` | Classificar rebanho |
| POST | `/api/cenario` | Simular cenário |
| POST | `/api/ler-pdf` | Extrair dados do PDF |
| GET  | `/api/modelo-info` | Info do modelo ML |

### Exemplo de uso da API

```python
import requests

# Classificar
r = requests.post('http://localhost:5050/api/classificar', json={
    'valores': [300,280,400,200,900,1200,250,80,600,40]
    # [f00F, f00M, f05F, f05M, f13F, f13M, f25F, f25M, facF, facM]
})
print(r.json())
# {'tipo': 'CICLO_COMPLETO', 'confianca': 98.3, 'probabilidades': {...}, ...}
```
