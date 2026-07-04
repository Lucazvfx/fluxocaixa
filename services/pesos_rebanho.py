"""Converte contagem de cabeças por categoria em peso total de arrobas.

Usado para expressar custos em R$/@ (base simétrica à receita, que já é em @).
"""
from __future__ import annotations


def arrobas_categorias(*, matrizes=0.0, bois=0.0, jovens_f=0.0, jovens_m=0.0,
                       peso_vaca=17.0, peso_boi=20.0, peso_bezerra=8.0,
                       peso_garrote=12.0) -> float:
    """Peso total do plantel em @ (soma cabeças×peso_@ por categoria)."""
    return (matrizes * peso_vaca + bois * peso_boi
            + jovens_f * peso_bezerra + jovens_m * peso_garrote)
