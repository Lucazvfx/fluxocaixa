# 🐄 BoviML — Classificador de Exploração Bovina

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

## Funcionalidades

### 📝 Inserir Dados Manualmente
- Tabela por faixa etária (0-4m, 5-12m, 13-24m, 25-36m, Acima 36m)
- Fêmeas e machos separados
- Exemplos pré-carregados (Ciclo Completo, Cria, Recria, Engorda, INDEA)
- Totalizadores em tempo real

### 📋 Ler PDF do INDEA
- Upload do "Saldo Atual da Exploração" (INDEA-MT)
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
