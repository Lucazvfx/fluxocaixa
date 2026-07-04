"""Testes para o helper de peso do rebanho em arrobas."""
from services.pesos_rebanho import arrobas_categorias


def test_soma_arrobas_por_categoria():
    """Deve somar cabeças × peso_@ por categoria."""
    total = arrobas_categorias(matrizes=10, bois=2, jovens_f=4, jovens_m=6,
                               peso_vaca=17, peso_boi=20, peso_bezerra=8, peso_garrote=12)
    assert total == 10*17 + 2*20 + 4*8 + 6*12
