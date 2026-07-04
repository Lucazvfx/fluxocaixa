from ml_engine import calcular_ano
from services.pesos_rebanho import arrobas_categorias


def test_calcular_ano_custo_em_arroba():
    r = calcular_ano(
        matrizes=100, femeas_024=40, machos_024=40, bois=5,
        nat_pct=0.75, desc_mat_pct=0.15, prop_boi=25, renov_boi_pct=0.2,
        venda_bez_pct=0.3, mort_pct=0.03, preco_arroba=320, custo_arroba=57,
        peso_boi=20, peso_vaca=17, peso_bezerra=8, peso_garrote=12,
    )
    # custo = arrobas do rebanho projetado × 57 (não mais cabeças × 850)
    arrobas = arrobas_categorias(
        matrizes=r['matrizes_prox'], bois=r['bois_prox'],
        jovens_f=r['femeas_024_prox'], jovens_m=r['machos_024_prox'],
        peso_vaca=17, peso_boi=20, peso_bezerra=8, peso_garrote=12)
    assert abs(r['custo'] - arrobas * 57) < 1.0
