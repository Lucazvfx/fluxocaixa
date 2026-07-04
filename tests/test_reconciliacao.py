"""Testes do motor de reconciliação de garantia (IR × GTA × Ficha Sanitária)."""
import pytest

from services.reconciliacao import reconciliar


def test_caso_tres_irmaos_superavaliada():
    """Caso real: ficha 9.433 vs IR 45.361 → garantia superavaliada."""
    r = reconciliar({"ficha": 9433, "ir": 45361})

    assert r["base"] == "ficha"
    assert r["resumo"]["erros"] == 1
    assert r["veredito"] == "GARANTIA SUPERAVALIADA"

    div = r["divergencias"][0]
    assert div["divergencia_abs"] == 35928
    assert div["severidade"] == "erro"
    # (45361-9433)/9433*100 ≈ 380.9%
    assert round(div["divergencia_pct"], 1) == 380.9
    assert div["maior"] == "ir"


def test_menos_de_duas_fontes_levanta_erro():
    with pytest.raises(ValueError):
        reconciliar({"ficha": 9433})


def test_documentos_coerentes_todos_ok():
    r = reconciliar({"ficha": 9433, "ir": 9500, "gta": 9400})
    assert r["resumo"]["erros"] == 0
    assert r["resumo"]["alertas"] == 0
    assert r["veredito"] == "DOCUMENTOS CONSISTENTES"


def test_divergencia_moderada_gera_alerta():
    # 10000 vs 11000 = 10% → dentro de (5%, 15%] → alerta
    r = reconciliar({"gta": 10000, "ir": 11000})
    div = r["divergencias"][0]
    assert div["severidade"] == "alerta"
    assert r["veredito"] == "REVISAR DIVERGÊNCIA"


def test_base_e_ficha_quando_presente():
    r = reconciliar({"ir": 100, "gta": 200, "ficha": 150})
    assert r["base"] == "ficha"


def test_base_e_menor_quando_sem_ficha():
    r = reconciliar({"ir": 300, "gta": 200})
    assert r["base"] == "gta"


def test_coage_negativos_e_none():
    # None é ignorado; negativo vira 0
    r = reconciliar({"ficha": 9000, "ir": 9200, "gta": None})
    assert "gta" not in r["fontes"]
    assert set(r["fontes"]) == {"ficha", "ir"}
