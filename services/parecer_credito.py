"""Parecer de crédito: capacidade de pagamento (Price + DSCR) e montagem.

Módulo puro — não importa Flask nem DB. Recebe números já computados.
"""
from __future__ import annotations

# Faixas de política de crédito (DSCR) — ajustáveis, não são benchmark zootécnico.
DSCR_APROVAR = 1.30
DSCR_RESSALVA = 1.00


def parcela_price(pv: float, juros_aa: float, n_meses: int) -> float:
    """Parcela mensal por amortização Price. juros_aa nominal anual."""
    if n_meses <= 0 or pv <= 0:
        return 0.0
    i = (1 + juros_aa) ** (1 / 12) - 1
    if i <= 0:
        return pv / n_meses
    return pv * i / (1 - (1 + i) ** (-n_meses))


def credito_maximo(
    geracao_caixa_anual: float,
    juros_aa: float,
    prazo_meses: int,
    carencia_meses: int = 0,
    dividas_mensais: float = 0.0,
    dscr_alvo: float = DSCR_APROVAR,
) -> float:
    """
    Capacidade máxima de endividamento: PV tal que DSCR = dscr_alvo.

    Inverso do Price: parcela_max = caixa_disponivel / 12
    PV_max = parcela_max × (1 − (1+i)^−n) / i
    """
    n = max(prazo_meses - carencia_meses, 0)
    if n <= 0 or juros_aa <= 0 or geracao_caixa_anual <= 0:
        return 0.0
    caixa_disponivel = geracao_caixa_anual / dscr_alvo - 12 * max(dividas_mensais, 0.0)
    if caixa_disponivel <= 0:
        return 0.0
    parcela_max = caixa_disponivel / 12
    i = (1 + juros_aa) ** (1 / 12) - 1
    if i <= 0:
        return round(parcela_max * n, 2)
    return round(parcela_max * (1 - (1 + i) ** (-n)) / i, 2)


def avaliar_capacidade_pagamento(
    geracao_caixa_anual: float,
    credito_valor: float,
    prazo_meses: int,
    juros_aa: float,
    carencia_meses: int = 0,
    dividas_mensais: float = 0.0,
) -> dict:
    n = max(prazo_meses - carencia_meses, 0)
    parcela = parcela_price(credito_valor, juros_aa, n)
    servico_anual = 12 * (parcela + max(dividas_mensais, 0.0))
    cap_max = credito_maximo(geracao_caixa_anual, juros_aa, prazo_meses,
                             carencia_meses, dividas_mensais)

    if servico_anual <= 0:
        return {'dscr': None, 'parcela_mensal': round(parcela, 2),
                'servico_divida_anual': 0.0,
                'geracao_caixa_anual': round(geracao_caixa_anual, 2),
                'capacidade_maxima': cap_max,
                'recomendacao': None, 'faixa': None,
                'justificativa': 'Sem crédito a avaliar.'}

    dscr = geracao_caixa_anual / servico_anual
    if geracao_caixa_anual <= 0:
        rec, just = 'negar', 'Operação não gera caixa positivo — sem capacidade de pagamento.'
    elif dscr >= DSCR_APROVAR:
        rec, just = 'aprovar', f'Cobertura {dscr:.2f} — folga confortável sobre o serviço da dívida.'
    elif dscr >= DSCR_RESSALVA:
        rec, just = 'ressalva', f'Cobertura {dscr:.2f} — operação cobre a dívida com folga estreita.'
    else:
        rec, just = 'negar', f'Cobertura {dscr:.2f} — geração de caixa insuficiente para o serviço da dívida.'

    return {'dscr': round(dscr, 2), 'parcela_mensal': round(parcela, 2),
            'servico_divida_anual': round(servico_anual, 2),
            'geracao_caixa_anual': round(geracao_caixa_anual, 2),
            'capacidade_maxima': cap_max,
            'recomendacao': rec, 'faixa': rec, 'justificativa': just}


def montar_parecer(*, identificacao, composicao, indicadores, benchmarks,
                   consistencia, financeiro, geracao_caixa_anual, credito,
                   fluxo_gep=None, sensibilidade=None, shap_explicacao=None) -> dict:
    def _f(v, default=0.0):
        try: return float(v or default)
        except (TypeError, ValueError): return default
    def _i(v, default=0):
        try: return int(float(v or default))
        except (TypeError, ValueError): return default

    conclusao = avaliar_capacidade_pagamento(
        geracao_caixa_anual=geracao_caixa_anual,
        credito_valor=_f(credito.get('credito_valor')),
        prazo_meses=_i(credito.get('prazo_meses')),
        juros_aa=_f(credito.get('juros_aa')),
        carencia_meses=_i(credito.get('carencia_meses')),
        dividas_mensais=_f(credito.get('dividas_mensais')))

    erros = (consistencia or {}).get('resumo', {}).get('erros', 0)
    if erros and conclusao['recomendacao'] == 'aprovar':
        conclusao = dict(conclusao, recomendacao='ressalva',
                         justificativa=conclusao['justificativa']
                         + f' Rebaixado: {erros} erro(s) de consistência no rebanho declarado invalidam a projeção.')

    return {
        'secoes': ['identificacao', 'composicao', 'indicadores',
                   'consistencia', 'financeiro', 'fluxo_gep', 'sensibilidade',
                   'shap_explicacao', 'conclusao'],
        'identificacao': identificacao,
        'composicao': composicao,
        'indicadores': {'valores': indicadores, 'benchmarks': benchmarks},
        'consistencia': consistencia,
        'financeiro': financeiro,
        'fluxo_gep': fluxo_gep,
        'sensibilidade': sensibilidade,
        'shap_explicacao': shap_explicacao or {},
        'conclusao': conclusao,
    }
