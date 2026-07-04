import os
from services.precos_diarios import (
    parse_boi_na, parse_vaca_scot, bezerra_de, valido, FATOR_BEZERRA, BEZERRO_REF,
)

FIX = os.path.join(os.path.dirname(__file__), 'fixtures')


def _fix(nome):
    with open(os.path.join(FIX, nome), encoding='utf-8') as f:
        return f.read()


def test_parse_boi_na_pega_indicador_cepea():
    assert parse_boi_na(_fix('na_boi.html')) == 329.85


def test_parse_vaca_scot():
    assert parse_vaca_scot(_fix('scot_vaca.html')) == 308.5


def test_bezerra_deriva_do_bezerro():
    assert bezerra_de(3000) == round(3000 * FATOR_BEZERRA, 2) == 2700.0


def test_valido_faixa():
    assert valido(330, 100, 600) is True
    assert valido(50, 100, 600) is False
    assert valido(0, 100, 600) is False


def test_bezerro_ref_default():
    assert BEZERRO_REF > 0


def test_parse_boi_na_sem_indicador_retorna_zero():
    assert parse_boi_na('<html><body>nada aqui</body></html>') == 0.0
