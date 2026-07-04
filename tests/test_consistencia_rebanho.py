"""Testes da detecção de inconsistências no rebanho declarado."""
import pytest

from services.consistencia_rebanho import analisar_consistencia, ERRO, ALERTA, OK


def _cod(res, codigo):
    return next(f for f in res["flags"] if f["codigo"] == codigo)


def test_vetor_invalido():
    with pytest.raises(ValueError):
        analisar_consistencia([0, 0, 0])


def test_rebanho_coerente_score_alto():
    # 300 matrizes, ~200 bezerros (natalidade ~67%), 10 touros, reposição saudável.
    v = [100, 100, 40, 40, 60, 60, 50, 50, 250, 10]
    res = analisar_consistencia(v)
    assert res["resumo"]["erros"] == 0
    assert res["score_consistencia"] >= 90
    assert _cod(res, "bezerros_vs_esperado")["severidade"] == OK


def test_bezerros_sem_matrizes_e_erro():
    v = [50, 50, 0, 0, 0, 0, 0, 0, 0, 0]
    res = analisar_consistencia(v)
    assert _cod(res, "bezerros_vs_esperado")["severidade"] == ERRO
    assert res["resumo"]["erros"] >= 1


def test_bezerros_acima_do_plausivel_e_erro():
    # 100 matrizes mas 300 bezerros -> muito acima do teto biológico.
    v = [150, 150, 0, 0, 0, 0, 0, 0, 100, 5]
    res = analisar_consistencia(v)
    f = _cod(res, "bezerros_vs_esperado")
    assert f["severidade"] == ERRO
    assert f["divergencia_pct"] > 0


def test_proporcao_sexual_atipica_alerta():
    # 90 fêmeas x 10 machos de bezerro -> razão 9.0.
    v = [90, 10, 0, 0, 0, 0, 0, 0, 150, 6]
    res = analisar_consistencia(v)
    assert _cod(res, "prop_sexual_bezerros")["severidade"] == ALERTA


def test_poucos_touros_alerta():
    # 600 matrizes, 1 touro -> 600:1.
    v = [200, 200, 0, 0, 0, 0, 100, 0, 500, 1]
    res = analisar_consistencia(v)
    assert _cod(res, "touro_matriz")["severidade"] == ALERTA


def test_piramide_descontinua_alerta():
    # machos 13-24 (200) muito acima de 5-12 (10) sem compra.
    v = [0, 0, 0, 10, 0, 200, 0, 0, 50, 3]
    res = analisar_consistencia(v)
    assert _cod(res, "piramide_etaria")["severidade"] == ALERTA


def test_reposicao_insuficiente_alerta():
    # 300 matrizes, quase nenhuma novilha de reposição.
    v = [80, 80, 0, 0, 2, 0, 0, 0, 300, 12]
    res = analisar_consistencia(v)
    assert _cod(res, "reposicao_femeas")["severidade"] == ALERTA


def test_score_cai_com_erros():
    bom = analisar_consistencia([100, 100, 40, 40, 60, 60, 50, 50, 250, 10])
    ruim = analisar_consistencia([300, 10, 0, 0, 0, 0, 0, 0, 50, 0])
    assert ruim["score_consistencia"] < bom["score_consistencia"]
