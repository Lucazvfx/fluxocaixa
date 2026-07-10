"""Testes para o helper de peso do rebanho em arrobas."""
from services.pesos_rebanho import arrobas_categorias
from services.parametros_zootecnicos import (
    PESO_BOI_ARR, PESO_VACA_ARR, PESO_JOVEM_F_ARR, PESO_JOVEM_M_ARR,
)


def test_soma_arrobas_por_categoria_explicito():
    """Pesos explícitos (override dos defaults) devem ser usados."""
    total = arrobas_categorias(matrizes=10, bois=2, jovens_f=4, jovens_m=6,
                               peso_vaca=17, peso_boi=20, peso_bezerra=8, peso_garrote=12)
    assert total == 10*17 + 2*20 + 4*8 + 6*12


def test_defaults_sao_pesos_gep():
    """Defaults devem usar pesos GEP Araguaia 24/25 via parametros_zootecnicos."""
    total = arrobas_categorias(matrizes=10, bois=2, jovens_f=4, jovens_m=6)
    esperado = (10 * PESO_VACA_ARR + 2 * PESO_BOI_ARR
                + 4 * PESO_JOVEM_F_ARR + 6 * PESO_JOVEM_M_ARR)
    assert total == esperado
