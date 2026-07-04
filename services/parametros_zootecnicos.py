"""Parâmetros zootécnicos de referência — defaults sourced dos cálculos.

Fonte-da-verdade dos valores default do motor e da UI. Cada valor tem origem:
- **Taxas** = ponto médio dos benchmarks nacionais (pptx de Análise de Crédito,
  encodados em `services/benchmarks_nacionais.py`); quando não há benchmark
  nacional, usa a banda "médio" do benchmark regional `ml_engine.BENCHMARKS_RO`.
- **Pesos por categoria** = referência de mercado (kg vivo × rendimento de abate
  ÷ 15). Boi terminado segue o padrão CEPEA/B3 (16–21@, meio ≈ 18@).

Módulo puro — só constantes e helpers, sem I/O.
"""
from __future__ import annotations


def midpoint(lo: float, hi: float) -> float:
    """Ponto médio de uma faixa de benchmark."""
    return (lo + hi) / 2.0


# ── Taxas: ponto médio do benchmark ──────────────────────────────────────────
# Natalidade nacional (pptx): faixas 55–75 (Embrapa/Scot/CEPEA/ABCZ) → meio 65.
NATALIDADE_PCT = midpoint(55.0, 75.0)          # 65.0
# Prenhez nacional (pptx): faixas 50–75 → meio 62,5.
PRENHEZ_PCT = midpoint(50.0, 75.0)             # 62.5

# Sem benchmark nacional para estas — banda "médio" do benchmark regional
# (ml_engine.BENCHMARKS_RO), documentada como tal.
MORTALIDADE_PCT = 3.0          # BENCHMARKS_RO.mortalidade médio
DESMAME_PCT = 82.0             # BENCHMARKS_RO.desmama médio
RENDIMENTO_CARCACA_PCT = 52.0  # BENCHMARKS_RO.rend_carcaca médio (engorda)
GANHO_ARROBA_MES = 0.7         # BENCHMARKS_RO.ganho_peso_arr médio
RELACAO_FM = 2.2               # BENCHMARKS_RO.relacao_fm médio
PCT_MATRIZES = 35.0            # BENCHMARKS_RO.pct_matrizes médio

# Desfrute por modalidade (nacional DESFRUTE_MODALIDADE, meio de cada faixa).
DESFRUTE_PCT = {
    'CRIA': midpoint(18.0, 30.0),            # 24.0
    'RECRIA': midpoint(35.0, 55.0),          # 45.0
    'ENGORDA': midpoint(80.0, 120.0),        # 100.0
    'CICLO_COMPLETO': midpoint(20.0, 40.0),  # 30.0
}

# ── Pesos por categoria: referência de mercado ───────────────────────────────
# Rendimento de carcaça de referência de abate (CEPEA/mercado ≈ 50%). Distinto do
# rendimento de engorda (RENDIMENTO_CARCACA_PCT), usado no cálculo da terminação.
RENDIMENTO_ABATE = 0.50
# Pesos vivos de referência (kg) — boi ~540 dá 18@ (padrão CEPEA 16–21@).
PESO_VIVO_KG = {'boi': 540.0, 'vaca': 420.0, 'garrote': 330.0, 'bezerra': 210.0}


def peso_arroba_carcaca(kg_vivo: float, rendimento: float = RENDIMENTO_ABATE) -> float:
    """@ de carcaça = kg vivo × rendimento ÷ 15 (1@ = 15 kg de carcaça)."""
    return kg_vivo * rendimento / 15.0


PESO_BOI_ARR = peso_arroba_carcaca(PESO_VIVO_KG['boi'])          # 18.0
PESO_VACA_ARR = peso_arroba_carcaca(PESO_VIVO_KG['vaca'])        # 14.0
PESO_GARROTE_ARR = peso_arroba_carcaca(PESO_VIVO_KG['garrote'])  # 11.0
PESO_BEZERRA_ARR = peso_arroba_carcaca(PESO_VIVO_KG['bezerra'])  # 7.0
