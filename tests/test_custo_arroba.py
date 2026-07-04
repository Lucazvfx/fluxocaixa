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


def test_simular_cria_custo_arroba():
    from ml_engine import _simular_cria
    r = _simular_cria(
        [10,10, 8,8, 6,6, 30,2, 40,3], 'conservador',
        nat_pct=75, mort_pct=3, desmama_pct=85, venda_bez_pct=30,
        preco_arroba_bezerro=300, custo_arroba=57, anos=1,
        peso_matriz=17, peso_bezerra=8)
    ano1 = r['anos'][0]
    # custo = (matrizes×17 + fem_recria×8) × 57
    matrizes = 30 + 40; fem_recria = 10 + 8 + 6
    assert abs(ano1['custo'] - (matrizes*17 + fem_recria*8) * 57) < 1.0
    assert r['preco_breakeven_unidade'] == 'R$/arroba'
