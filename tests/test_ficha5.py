import os
import json
import pytest

from pdf_parsers import extrair_texto_pdf, parsear_idaron


PDF_PATHS = [
    os.path.join(os.path.expanduser('~'), 'Downloads', 'Ficha de Gado 5.pdf'),
    r'c:\Users\Lucas\Downloads\Ficha de Gado 5.pdf',
]


def _find_pdf():
    for p in PDF_PATHS:
        if os.path.exists(p):
            return p
    return None


def test_parsear_ficha5_idaron():
    p = _find_pdf()
    if not p:
        pytest.skip('Ficha de Gado 5.pdf não encontrada em Downloads — pule este teste localmente.')

    text = extrair_texto_pdf(p)
    # parse usando pdf_path para ativar extração por tabela (pdfplumber)
    res = parsear_idaron(text, pdf_path=p)

    # Valores esperados observados manualmente ao processar o PDF
    assert res['total'] == 821
    # checar algumas faixas conhecidas
    assert res['animais']['f05_M'] == 88
    assert res['animais']['f13_M'] == 316
    assert res['animais']['f25_F'] == 13
    assert res['animais']['f25_M'] == 404
