# Fluxo de Gestão — Classificador e Gestão de Exploração Bovina

Sistema Python com Machine Learning para classificar o tipo de exploração bovina
(Cria / Recria / Engorda / Ciclo Completo) e simular cenários financeiros específicos para cada ciclo.

---

## Os Quatro Ciclos da Pecuária

### 🐄 CRIA

**O que é:** A fazenda mantém matrizes (vacas) para produzir bezerros. O produto final vendido é o **bezerro desmamado**, vendido por cabeça.

**Como funciona:**
- As matrizes são cobertas (monta natural ou IATF) e produzem bezerros
- Os bezerros ficam com a mãe até o desmame (~6–8 meses)
- Parte dos bezerros é vendida; as bezerras mais bonitas ficam para reposição das matrizes

**Composição típica do rebanho:**
- Muitas matrizes adultas (vacas)
- Bezerros 0–12 meses em grande quantidade
- Poucos machos adultos (touros ou bois reprodutores)

**Como o sistema calcula a receita:**
```
Receita = Bezerros vendidos × Preço por cabeça (R$/cab)
```

**Parâmetros que influenciam:**
| Parâmetro | O que significa |
|-----------|----------------|
| Taxa de Natalidade | % das matrizes que parem por ano |
| Taxa de Desmama | % dos bezerros nascidos que sobrevivem até o desmame |
| % Bezerros Vendidos | Quanto vende vs. quanto retém para reposição |
| Preço Bezerro (R$/cab) | Valor pago por bezerro desmamado no mercado |

---

### 🐂 RECRIA

**O que é:** A fazenda **compra bezerros desmamados** (ou usa os próprios) e os cria até o ponto de venda como garrote/novilho. Ela **não produz bezerros nem abate** — seu produto é o animal mais pesado.

**Como funciona:**
- Entrada: bezerros/garrotes leves (~8 arrobas)
- Os animais ficam no pasto por 12–18 meses ganhando peso
- Saída: garrotes/novilhos vendidos para fazendas de engorda (~14 arrobas)
- A receita é **por arroba**, mas com o preço do novilho (menor que o boi gordo)

**Composição típica do rebanho:**
- Concentração de machos jovens (13–24 meses)
- Poucas ou nenhuma matriz adulta
- Sem bois adultos para abate

**Como o sistema calcula a receita:**
```
Receita = Animais vendidos × Peso de saída (arrobas) × Preço arroba novilho
```

**Parâmetros que influenciam:**
| Parâmetro | O que significa |
|-----------|----------------|
| Peso Entrada (@) | Peso do animal quando chega na fazenda |
| Peso Saída (@) | Peso do animal quando é vendido |
| Meses de Recria | Tempo que o animal fica na fazenda |
| Custo/Cabeça/Mês | Custo de manutenção mensal por animal |

---

### 🥩 ENGORDA

**O que é:** A fazenda recebe animais já recriados (garrotes/novilhos pesados) e os **termina para o abate**. O produto final é o **boi gordo**, vendido por arroba de carcaça.

**Como funciona:**
- Entrada: novilhos/garrotes (~300 kg)
- Os animais engordão em pasto intensivo ou confinamento por 90–180 dias
- Abate: ~520 kg vivos → rendimento de carcaça ~52% → ~17–18 arrobas de carne
- A receita usa o **preço do boi gordo**, que é o mais alto da cadeia

**Composição típica do rebanho:**
- Quase só machos adultos (25 meses+)
- Sem matrizes, sem bezerros

**Como o sistema calcula a receita:**
```
Arrobas por boi = (Peso abate em kg × Rendimento carcaça) ÷ 15
Receita = Bois abatidos × Arrobas por boi × Preço arroba boi gordo
```

**Parâmetros que influenciam:**
| Parâmetro | O que significa |
|-----------|----------------|
| Peso Entrada (kg) | Peso do animal ao entrar na engorda |
| Peso Abate (kg) | Peso do animal ao sair para o frigorífico |
| Rendimento Carcaça (%) | % do peso vivo que vira carne (~52%) |
| Custo/Cab/Dia | Custo diário por animal (ração, pasto, etc.) |
| Dias de Engorda | Dias que o animal fica na fase de terminação |
| Lotes por ano | Calculado automaticamente: 365 ÷ dias de engorda |

---

### 🔄 CICLO COMPLETO

**O que é:** A fazenda realiza **as três fases** — cria, recria e engorda — dentro da mesma propriedade. É o modelo mais complexo e o que exige mais capital e gestão.

**Como funciona:**
- As matrizes produzem bezerros (cria)
- Os bezerros machos passam pela recria dentro da fazenda
- Os novilhos são terminados para abate (engorda)
- As bezerras fêmeas ficam para reposição das matrizes
- A fazenda vende boi gordo, além de eventualmente vender bezerros/novilhos excedentes

**Composição típica do rebanho:**
- Todas as faixas etárias representadas
- Matrizes adultas em número expressivo
- Machos em todas as fases (0–36m+)

**Como o sistema calcula a receita:**
```
Receita = (Bois vendidos + Matrizes de descarte + Bezerros/novilhos vendidos)
          × Peso médio × Preço arroba
```

**Parâmetros que influenciam:**
- Todos os parâmetros das três fases anteriores
- Proporção Boi/Matriz (quantas vacas cada touro cobre)
- Taxa de renovação de touros
- Descarte anual de matrizes

---

## Como o ML classifica o ciclo

O modelo analisa a **composição etária do rebanho** (10 variáveis: fêmeas e machos em 5 faixas de idade) e extrai indicadores como:

- Proporção de matrizes adultas → aponta CRIA
- Concentração de machos jovens (13–24m) → aponta RECRIA
- Domínio de machos adultos (25m+) → aponta ENGORDA
- Todas faixas equilibradas → aponta CICLO_COMPLETO

O ensemble usa Random Forest + Gradient Boosting com regras híbridas para casos limítrofes.

---

## ⚡ Novos Recursos (Superpowers)

### 📈 Benchmarks Rondônia
O sistema agora compara os indicadores da sua fazenda com as médias regionais de Rondônia (Embrapa/SEAGRI). 
- Identifique se sua natalidade, mortalidade e rendimento de carcaça estão acima ou abaixo da média.
- Visualize o quanto falta para atingir o próximo nível de eficiência.

### ⚖️ Ponto de Equilíbrio (Breakeven) Interativo
Simule o impacto das variações de preço do mercado em tempo real.
- Slider interativo para ajustar o preço da arroba e ver o lucro projetado instantaneamente.
- Cálculo automático do preço mínimo de venda para não ter prejuízo.

### 🧠 Recomendações Inteligentes
O motor de análise gera sugestões automáticas baseadas nos dados do seu rebanho:
- Alertas de prejuízo ou margens apertadas.
- Identificação de excesso de bois reprodutores.
- Sugestões técnicas para melhorar a natalidade e conversão alimentar.

### ✅ Validação de Dados em Tempo Real
Interface aprimorada com validação inline para garantir que os parâmetros zootécnicos e financeiros estejam dentro de limites realistas, evitando erros de simulação.

---

## Tecnologia

- **Backend:** Python + Flask
- **ML:** scikit-learn + XGBoost (Ensemble VotingClassifier)
- **Banco:** PostgreSQL (produção) / SQLite (local)
- **Cotações:** Scraper automático do scotconsultoria.com.br (boi gordo, vaca gorda, boi china)
- **PDF:** pdftotext + pdfplumber (parsers IDARON-RO e INDEA-MT)
- **Frontend:** HTML/CSS/JS puro

---

## Instalação

```bash
# 1. Instalar dependências
pip install -r requirements.txt

# 2. (Opcional) Para leitura de PDF — Ubuntu/Debian:
sudo apt install poppler-utils
# macOS:
brew install poppler
```

## Uso

```bash
# Windows (ativar venv antes):
.\venv\Scripts\Activate
python app.py
```

Acesse: **http://localhost:5050**

---

## API Endpoints

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| GET  | `/` | Interface web |
| POST | `/api/classificar` | Classificar rebanho |
| POST | `/api/cenario` | Simular cenário financeiro por ciclo |
| POST | `/api/ler-pdf` | Extrair dados do PDF (IDARON / INDEA) |
| GET  | `/api/precos/live` | Cotações ao vivo (boi gordo, vaca gorda, boi china) |
| GET  | `/api/modelo-info` | Métricas do modelo ML |

### Exemplo — Classificar

```python
import requests

r = requests.post('http://localhost:5050/api/classificar', json={
    'valores': [300,280,400,200,900,1200,250,80,600,40]
    # [f00F, f00M, f05F, f05M, f13F, f13M, f25F, f25M, facF, facM]
})
print(r.json())
# {'tipo': 'CICLO_COMPLETO', 'confianca': 98.3, ...}
```

### Exemplo — Simular cenário ENGORDA

```python
r = requests.post('http://localhost:5050/api/cenario', json={
    'valores': [10,8,20,18,50,80,20,120,10,400],
    'cenario': 'otimista',
    'ciclo': 'ENGORDA',
    'preco': 330,              # R$/arroba boi gordo
    'peso_entrada_kg': 300,
    'peso_saida_kg': 520,
    'rendimento_carcaca': 52,
    'custo_cab_dia': 12,
    'dias_engorda': 90,
})
print(r.json()['acumulado'])
# {'receita': ..., 'custo': ..., 'resultado': ...}
```

### Exemplo — Simular cenário CRIA

```python
r = requests.post('http://localhost:5050/api/cenario', json={
    'valores': [300,280,200,80,100,40,150,10,600,15],
    'cenario': 'crescimento',
    'ciclo': 'CRIA',
    'nat': 75,                 # taxa de natalidade %
    'preco_bezerro': 1800,     # R$ por cabeça
    'desmama_pct': 80,         # % que sobrevive ao desmame
    'vendbez': 60,             # % dos bezerros que vende
    'custo': 850,              # R$/cab/ano
})
```

---

## Deploy (Railway / Neon)

```bash
git add .
git commit -m "ATT"
git push origin main
```

Configure as variáveis de ambiente:
- `DATABASE_URL` — string de conexão PostgreSQL (Neon)
- `SECRET_KEY` — chave secreta Flask (obrigatória em produção)
