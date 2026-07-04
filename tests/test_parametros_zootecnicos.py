from services.parametros_zootecnicos import (
    NATALIDADE_PCT, PRENHEZ_PCT, DESMAME_PCT, MORTALIDADE_PCT,
    RENDIMENTO_CARCACA_PCT, DESFRUTE_PCT, peso_arroba_carcaca,
    PESO_BOI_ARR, PESO_VACA_ARR, PESO_GARROTE_ARR, PESO_BEZERRA_ARR,
    PESO_VIVO_KG, RENDIMENTO_ABATE, midpoint,
)


def test_taxas_sao_ponto_medio_do_benchmark():
    assert NATALIDADE_PCT == midpoint(55, 75) == 65.0
    assert PRENHEZ_PCT == 62.5
    assert DESFRUTE_PCT['CICLO_COMPLETO'] == 30.0
    assert DESFRUTE_PCT['ENGORDA'] == 100.0
    assert MORTALIDADE_PCT == 3.0 and DESMAME_PCT == 82.0
    assert RENDIMENTO_CARCACA_PCT == 52.0


def test_conversao_peso_arroba_carcaca():
    assert peso_arroba_carcaca(540, 0.50) == 18.0
    assert peso_arroba_carcaca(210, 0.50) == 7.0


def test_pesos_derivam_da_conversao():
    assert PESO_BOI_ARR == PESO_VIVO_KG['boi'] * RENDIMENTO_ABATE / 15
    assert PESO_BOI_ARR == 18.0
    assert PESO_VACA_ARR == 14.0
    assert PESO_GARROTE_ARR == 11.0
    assert PESO_BEZERRA_ARR == 7.0
