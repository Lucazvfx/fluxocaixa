from services.parecer_credito import avaliar_capacidade_pagamento


def test_price_com_juros():
    r = avaliar_capacidade_pagamento(
        geracao_caixa_anual=120000, credito_valor=100000,
        prazo_meses=12, juros_aa=0.12)
    assert r['parcela_mensal'] > 100000/12  # com juros, parcela > principal/n


def test_price_sem_juros():
    r = avaliar_capacidade_pagamento(
        geracao_caixa_anual=120000, credito_valor=120000,
        prazo_meses=12, juros_aa=0.0)
    assert abs(r['parcela_mensal'] - 10000) < 0.01


def test_dscr_aprovar():
    r = avaliar_capacidade_pagamento(200000, 100000, 24, 0.10)
    assert r['recomendacao'] == 'aprovar' and r['dscr'] >= 1.30


def test_dscr_ressalva():
    r = avaliar_capacidade_pagamento(60000, 100000, 24, 0.10)
    assert r['recomendacao'] == 'ressalva' and 1.0 <= r['dscr'] < 1.30


def test_dscr_negar():
    r = avaliar_capacidade_pagamento(20000, 100000, 12, 0.10)
    assert r['recomendacao'] == 'negar' and r['dscr'] < 1.0


def test_geracao_negativa_nega():
    r = avaliar_capacidade_pagamento(-5000, 100000, 12, 0.10)
    assert r['recomendacao'] == 'negar'


def test_sem_credito_sem_conclusao():
    r = avaliar_capacidade_pagamento(120000, 0, 12, 0.10)
    assert r['dscr'] is None and r['recomendacao'] is None
