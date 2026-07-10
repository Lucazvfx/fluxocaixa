"""Converte contagem de cabeças por categoria em peso total de arrobas.

Usado para expressar custos em R$/@ (base simétrica à receita, que já é em @).
Pesos default = GEP Araguaia safra 24/25 via parametros_zootecnicos.
"""
from __future__ import annotations

from services.parametros_zootecnicos import (
    PESO_BOI_ARR,
    PESO_VACA_ARR,
    PESO_JOVEM_F_ARR,
    PESO_JOVEM_M_ARR,
)


def arrobas_categorias(*, matrizes=0.0, bois=0.0, jovens_f=0.0, jovens_m=0.0,
                       peso_vaca=PESO_VACA_ARR,   # 15.33@
                       peso_boi=PESO_BOI_ARR,      # 20.53@
                       peso_bezerra=PESO_JOVEM_F_ARR,  # 7.67@ (bezerra+novilha ÷ 2)
                       peso_garrote=PESO_JOVEM_M_ARR   # 8.67@ (bezerro+garrote ÷ 2)
                       ) -> float:
    """Peso total do plantel em @ (soma cabeças×peso_@ por categoria)."""
    return (matrizes * peso_vaca + bois * peso_boi
            + jovens_f * peso_bezerra + jovens_m * peso_garrote)
