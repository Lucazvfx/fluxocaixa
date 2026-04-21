# Design: Ponto de Equilíbrio + Benchmarks Rondônia

**Data:** 2026-04-20  
**Status:** Aprovado

---

## Objetivo

Adicionar duas funcionalidades analíticas ao BoviML:
1. **Ponto de equilíbrio** — preço mínimo de venda para cobrir os custos, com slider interativo
2. **Benchmarks Rondônia** — comparação dos indicadores do rebanho com médias regionais

---

## Onde aparece

| Local | Ponto de Equilíbrio | Benchmarks |
|-------|---------------------|------------|
| Aba "Resultado" (pós-classificação) | Card compacto: breakeven + margem atual | Card com barras de progresso por indicador |
| Aba "Simular Cenários" | Card completo + slider interativo | — |

---

## Seção 1 — Ponto de Equilíbrio

### Cálculo (backend)

Cada função de simulação retorna `preco_breakeven` no resultado.

**CRIA:**
```
preco_breakeven = custo_total_ano1 / bezerros_vendidos_ano1
```
Unidade: R$/cabeça

**RECRIA:**
```
preco_breakeven = custo_total_ano1 / (animais_vendidos_ano1 × peso_saida_arr)
```
Unidade: R$/arroba

**ENGORDA:**
```
preco_breakeven = custo_total_ano1 / (bois_abatidos_ano1 × arrobas_por_boi)
```
Unidade: R$/arroba

**CICLO_COMPLETO:**
```
preco_breakeven = custo_total_ano1 / (total_vendido_ano1 × peso_arroba)
```
Unidade: R$/arroba

### API

`POST /api/cenario` passa a retornar:
```json
{
  "ciclo": "ENGORDA",
  "preco_breakeven": 287.50,
  "margem_atual_pct": 14.8,
  "margem_atual_rs": 42300.00,
  "anos": [...],
  "acumulado": {...}
}
```

### Slider (frontend)

- Aparece na aba "Simular Cenários", abaixo da tabela de projeção
- Range: de `preco_breakeven * 0.8` até `preco_breakeven * 1.5`
- Ao mover o slider, recalcula em JS:
  - `receita_nova = unidades × peso × preco_slider`
  - `resultado_novo = receita_nova - custo` (custo não muda)
  - Atualiza: resultado ano 1, resultado acumulado, margem %
- Sem chamada de API — tudo no browser

### Card na aba "Resultado"

Card compacto com:
- Preço de equilíbrio calculado
- Preço atual de mercado (da cotação do dia)
- Margem em % e R$ (verde se positivo, vermelho se negativo)

---

## Seção 2 — Benchmarks Rondônia

### Dados de referência (constante no backend)

```python
BENCHMARKS_RO = {
    'natalidade': {
        'label': 'Taxa de Natalidade',
        'unidade': '%',
        'faixas': {'abaixo': 65, 'medio': 78, 'bom': 88},
        'ciclos': ['CRIA', 'CICLO_COMPLETO'],
    },
    'mortalidade': {
        'label': 'Mortalidade Geral',
        'unidade': '%',
        'faixas': {'abaixo': 5, 'medio': 3, 'bom': 1.5},
        'inverso': True,   # menor é melhor
        'ciclos': ['CRIA', 'RECRIA', 'ENGORDA', 'CICLO_COMPLETO'],
    },
    'desmama': {
        'label': 'Taxa de Desmama',
        'unidade': '%',
        'faixas': {'abaixo': 70, 'medio': 82, 'bom': 90},
        'ciclos': ['CRIA', 'CICLO_COMPLETO'],
    },
    'relacao_fm': {
        'label': 'Relação Fêmeas/Macho Adulto',
        'unidade': ':1',
        'faixas': {'abaixo': 1.8, 'medio': 2.2, 'bom': 2.8},
        'ciclos': ['CRIA', 'CICLO_COMPLETO'],
    },
    'pct_matrizes': {
        'label': '% Matrizes no Rebanho',
        'unidade': '%',
        'faixas': {'abaixo': 28, 'medio': 35, 'bom': 42},
        'ciclos': ['CRIA', 'CICLO_COMPLETO'],
    },
    'ganho_peso_arr': {
        'label': 'Ganho de Peso (@/mês)',
        'unidade': '@/mês',
        'faixas': {'abaixo': 0.5, 'medio': 0.7, 'bom': 0.9},
        'ciclos': ['RECRIA'],
    },
    'rend_carcaca': {
        'label': 'Rendimento de Carcaça',
        'unidade': '%',
        'faixas': {'abaixo': 50, 'medio': 52, 'bom': 54},
        'ciclos': ['ENGORDA', 'CICLO_COMPLETO'],
    },
}
```

### Função de avaliação

```python
def avaliar_benchmarks(indicadores: dict, ciclo: str) -> list:
    """Retorna lista de benchmarks relevantes para o ciclo com classificação."""
```

Retorno por indicador:
```json
{
  "key": "natalidade",
  "label": "Taxa de Natalidade",
  "valor": 75.0,
  "unidade": "%",
  "faixa": "medio",
  "proximo_nivel": "bom",
  "falta": 3.0
}
```

### Integração com `/api/classificar`

A resposta passa a incluir:
```json
{
  "classificacao": "CRIA",
  "benchmarks": [
    {"key": "natalidade", "label": "Taxa de Natalidade", "valor": 75, "faixa": "medio", ...},
    ...
  ]
}
```

Os indicadores são calculados a partir de:
- `taxa_natalidade` recebida no request
- Indicadores derivados do rebanho (`calcular_indicadores`)

### Card na aba "Resultado"

Barra de progresso por indicador:
- **Vermelho** = abaixo da média RO
- **Amarelo** = média RO
- **Verde** = bom
- **Azul** = excelente

Só exibe indicadores relevantes para o ciclo detectado.

---

## Arquivos modificados

| Arquivo | Mudança |
|---------|---------|
| `ml_engine.py` | Adicionar `BENCHMARKS_RO`, `avaliar_benchmarks()`, `preco_breakeven` nas funções de simulação |
| `app.py` | Atualizar `/api/classificar` para incluir `benchmarks`; `/api/cenario` para incluir `preco_breakeven` |
| `templates/index.html` | Card benchmarks na aba Resultado; card breakeven + slider na aba Cenários |

---

## Defaults regionais (Rondônia)

O usuário **não precisa informar pesos** — todos os campos de peso são pré-preenchidos com médias típicas de RO. O usuário só ajusta se tiver dados reais da fazenda.

| Parâmetro | Padrão RO | Usado em |
|-----------|-----------|----------|
| Peso entrada recria | 8 @ | RECRIA |
| Peso saída recria | 14 @ | RECRIA |
| Peso entrada engorda | 300 kg | ENGORDA |
| Peso abate | 520 kg | ENGORDA |
| Rendimento carcaça | 52% | ENGORDA |
| Custo/cab/mês recria | R$ 80 | RECRIA |
| Custo/cab/dia engorda | R$ 12 | ENGORDA |
| Dias de engorda | 90 dias | ENGORDA |

Para CRIA o breakeven é em **R$/cabeça** — sem necessidade de peso.

---

## Fora do escopo

- Benchmarks para outros estados (só RO por ora)
- Comparação histórica (evolução dos benchmarks ao longo do tempo)
- Export dos benchmarks em PDF
