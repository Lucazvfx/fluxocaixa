"""
Testes do parser PDF genérico universal.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from pdf_parsers import parsear_generico, _faixa_generica


def test_faixa_generica_reconhece_variacoes():
    assert _faixa_generica("0 a 6 meses") == 'f00'
    assert _faixa_generica("00 - 06") == 'f00'
    assert _faixa_generica("até 6") == 'f00'
    assert _faixa_generica("7 a 12 meses") == 'f05'
    assert _faixa_generica("13 a 24") == 'f13'
    assert _faixa_generica("25 a 36") == 'f25'
    assert _faixa_generica("acima de 36") == 'fac'
    assert _faixa_generica("> 36") == 'fac'
    assert _faixa_generica("maior que 36") == 'fac'
    assert _faixa_generica("0 a 12") == 'f00_12'


GENERICO_TXT = """
Relatório personalizado — Fazenda Boa Esperança
Município: Cuiabá
Saldo em 12/05/2026

Bezerra 0 a 6 meses                                              45
Bezerro macho 0 a 6 meses                                        50
Fêmea 7 a 12 meses                                              100
Macho 7 a 12 meses                                               90
Fêmea 13 a 24 meses                                             200
Macho 13 a 24 meses                                             180
Fêmea 25 a 36 meses                                             120
Macho 25 a 36 meses                                              60
Vaca acima de 36                                                400
Touro acima de 36                                                25
"""


def test_parsear_generico_layout_basico():
    r = parsear_generico(GENERICO_TXT)
    assert r['valores'] == [45, 50, 100, 90, 200, 180, 120, 60, 400, 25]
    assert r['total'] == 1270


def test_parsear_generico_extrai_metadados():
    r = parsear_generico(GENERICO_TXT)
    assert 'BOA ESPERANÇA' in r['fazenda'].upper() or 'ESPERANCA' in r['fazenda'].upper()
    assert 'CUIABÁ' in r['municipio'].upper() or 'CUIABA' in r['municipio'].upper()
    assert r['data_saldo'] == '12/05/2026'


def test_parsear_generico_categoria_zootecnica_sem_faixa():
    """Sem faixa explícita, usa palavra-chave (vaca/touro/bezerro)."""
    txt = """
    Vaca                                300
    Touro                                15
    Bezerra fêmea                        80
    """
    r = parsear_generico(txt)
    assert r['animais']['fac_F'] == 300  # vaca
    assert r['animais']['fac_M'] == 15   # touro


def test_parsear_generico_faixa_unificada_0_a_12():
    txt = """
    Fêmea 0 a 12 meses                  100
    Macho 0 a 12 meses                   80
    """
    r = parsear_generico(txt)
    # 100 fêmeas dividido em 50 / 50; 80 machos em 40 / 40
    assert r['animais']['f00_F'] == 50
    assert r['animais']['f05_F'] == 50
    assert r['animais']['f00_M'] == 40
    assert r['animais']['f05_M'] == 40


def test_parsear_generico_ignora_qtd_invalida():
    txt = "Macho 13 a 24 meses                              999999"
    r = parsear_generico(txt)
    assert r['valores'][5] == 0


def test_parsear_generico_sem_dados():
    r = parsear_generico("documento sem nenhum dado relevante")
    assert r['total'] == 0
