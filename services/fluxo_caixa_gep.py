"""
Fluxo de caixa completo — metodologia GEP Araguaia.

Diferencial: inclui variação de estoque do rebanho na análise de crédito pecuária.
Nenhum sistema de crédito rural mainstream calcula isso. O rebanho é um ativo
vivo — quando cresce, cria riqueza que não aparece no caixa mas é real.

Fonte dos pesos e rendimentos: MODELAGEM RESULTADO CC 2
(GEP Araguaia — Merck Sharp Down / Fazenda Alvorada, safra 24/25).
"""
from __future__ import annotations

# ── Parâmetros por categoria (GEP Araguaia, safra 24/25) ─────────────────────
# peso_kg: peso vivo de referência para venda/abate
# rendimento: rendimento de carcaça (RC%) — boi terminado 55%, demais 50%
# arroba_eq: arrobas-equivalentes = peso_kg × rendimento / 15
# Expressão em R$/@ carcaça é o padrão do setor para comparar categorias.
CATEGORIAS_GEP = {
    'bezerra': {'peso_kg': 180.0, 'rendimento': 0.50, 'arroba_eq': 6.00,  'label': 'Bezerra'},
    'bezerro': {'peso_kg': 200.0, 'rendimento': 0.50, 'arroba_eq': 6.67,  'label': 'Bezerro'},
    'novilha': {'peso_kg': 280.0, 'rendimento': 0.50, 'arroba_eq': 9.33,  'label': 'Novilha'},
    'garrote': {'peso_kg': 320.0, 'rendimento': 0.50, 'arroba_eq': 10.67, 'label': 'Garrote'},
    'vaca':    {'peso_kg': 460.0, 'rendimento': 0.50, 'arroba_eq': 15.33, 'label': 'Matriz/Vaca'},
    'boi':     {'peso_kg': 560.0, 'rendimento': 0.55, 'arroba_eq': 20.53, 'label': 'Boi Terminado'},
}

# Fatores de preço relativo quando preço da categoria não é informado
_FATOR_VACA     = 0.85   # preço vaca ≈ 85% do boi
_FATOR_BEZERRA  = 0.90   # bezerra ≈ 90% da vaca
_FATOR_BEZERRO  = 1.05   # bezerro ≈ 105% da bezerra (macho premium)

# Arrobas-equivalentes médias para jovens agregados (val_fim do simulador)
_ARR_JOVEM_F = (CATEGORIAS_GEP['bezerra']['arroba_eq'] + CATEGORIAS_GEP['novilha']['arroba_eq']) / 2  # 7.67@
_ARR_JOVEM_M = (CATEGORIAS_GEP['bezerro']['arroba_eq'] + CATEGORIAS_GEP['garrote']['arroba_eq']) / 2  # 8.67@


def valor_rebanho_gep(
    matrizes: float,
    bois: float,
    preco_boi: float,
    preco_vaca: float = None,
    # Modo granular — val_ini (composição declarada pelo usuário)
    novilhas: float = 0,            # f13F → 9.33@ × preco_vaca
    garrotes: float = 0,            # f13M → 10.67@ × preco_boi
    bezerras: float = 0,            # f00F+f05F → R$/cab direto
    bezerros: float = 0,            # f00M+f05M → R$/cab direto
    preco_bezerra_cab: float = None, # R$/cab (cotação bezerra)
    preco_bezerro_cab: float = None, # R$/cab (cotação bezerro)
    # Modo legado — val_fim (simulador retorna jovens agregados 0–24m)
    jovens_f: float = 0,
    jovens_m: float = 0,
) -> dict:
    """
    Avalia o estoque do rebanho em R$ pelo método GEP.

    Modo granular (val_ini): split correto por categoria.
      - matrizes / bois (25m+): precificados por @ (R$/@)
      - novilhas / garrotes (13–24m): precificados por @ (R$/@)
      - bezerras / bezerros (0–12m): precificados por cabeça (R$/cab)

    Modo legado (val_fim): simulador não separa cria/recria,
      jovens_f/m usam @ médio (7.67 / 8.67) × preco_vaca/boi — unidades consistentes.
    """
    _pb = float(preco_boi)
    _pv = float(preco_vaca) if preco_vaca else _pb * _FATOR_VACA

    # Adultos (25m+) — R$/@
    val_matrizes = matrizes * CATEGORIAS_GEP['vaca']['arroba_eq'] * _pv   # 15.33@ × pv
    val_bois     = bois     * CATEGORIAS_GEP['boi']['arroba_eq']  * _pb   # 20.53@ × pb

    # Recria (13–24m) — R$/@
    val_novilhas = novilhas * CATEGORIAS_GEP['novilha']['arroba_eq'] * _pv  # 9.33@ × pv
    val_garrotes = garrotes * CATEGORIAS_GEP['garrote']['arroba_eq'] * _pb  # 10.67@ × pb

    # Cria (0–12m) — R$/cab direto (bezerros são negociados por cabeça no mercado)
    _default_bezerra = _pv * CATEGORIAS_GEP['bezerra']['arroba_eq'] * _FATOR_BEZERRA
    _default_bezerro = _pb * CATEGORIAS_GEP['bezerro']['arroba_eq'] * _FATOR_BEZERRO
    _pzc = float(preco_bezerra_cab) if preco_bezerra_cab else _default_bezerra
    _pmc = float(preco_bezerro_cab) if preco_bezerro_cab else _default_bezerro
    val_bezerras = bezerras * _pzc
    val_bezerros = bezerros * _pmc

    # Legado — jovens 0–24m agregados (val_fim): usa @ médio × preco_vaca/boi
    val_jovens_f = jovens_f * _ARR_JOVEM_F * _pv
    val_jovens_m = jovens_m * _ARR_JOVEM_M * _pb

    total   = (val_matrizes + val_bois + val_novilhas + val_garrotes
               + val_bezerras + val_bezerros + val_jovens_f + val_jovens_m)
    cabecas = int(matrizes + bois + novilhas + garrotes
                  + bezerras + bezerros + jovens_f + jovens_m)

    return {
        'valor_matrizes': round(val_matrizes, 2),
        'valor_bois':     round(val_bois, 2),
        'valor_novilhas': round(val_novilhas, 2),
        'valor_garrotes': round(val_garrotes, 2),
        'valor_bezerras': round(val_bezerras, 2),
        'valor_bezerros': round(val_bezerros, 2),
        'valor_jovens_f': round(val_jovens_f, 2),
        'valor_jovens_m': round(val_jovens_m, 2),
        'valor_total':    round(total, 2),
        'cabecas':        cabecas,
        'valor_cab':      round(total / max(cabecas, 1), 2),
    }


def calcular_fluxo_gep(
    receita_caixa: float,
    custo_caixa: float,
    valor_rebanho_ini: float,
    valor_rebanho_fim: float,
    servico_divida_anual: float = 0.0,
    reposicao_reprodutores: float = 0.0,
) -> dict:
    """
    DRE pecuário completo — metodologia GEP Araguaia.

    Fluxo de caixa:
      + Receita de vendas
      - Custo operacional (desembolso)
      - Reposição de reprodutores
      = RESULTADO OPERACIONAL  ← base do DSCR (é caixa real)

    Resultado econômico (não caixa, mas real):
      + Resultado operacional
      ± Variação de estoque do rebanho
      = RESULTADO ECONÔMICO TOTAL

    Crédito:
      + Resultado operacional
      - Serviço da dívida (Price + dívidas existentes)
      = FLUXO LIVRE para reinvestimento
    """
    resultado_operacional = receita_caixa - custo_caixa - reposicao_reprodutores
    variacao_estoque      = valor_rebanho_fim - valor_rebanho_ini
    resultado_economico   = resultado_operacional + variacao_estoque

    fluxo_livre = None
    dscr        = None
    if servico_divida_anual > 0:
        fluxo_livre = resultado_operacional - servico_divida_anual
        dscr = round(resultado_operacional / servico_divida_anual, 2) if resultado_operacional > 0 else 0.0

    return {
        'receita_vendas':         round(receita_caixa, 2),
        'custo_operacional':      round(custo_caixa, 2),
        'reposicao_reprodutores': round(reposicao_reprodutores, 2),
        'resultado_operacional':  round(resultado_operacional, 2),
        'variacao_estoque':       round(variacao_estoque, 2),
        'resultado_economico':    round(resultado_economico, 2),
        'valor_rebanho_ini':      round(valor_rebanho_ini, 2),
        'valor_rebanho_fim':      round(valor_rebanho_fim, 2),
        'servico_divida_anual':   round(servico_divida_anual, 2),
        'fluxo_livre':            round(fluxo_livre, 2) if fluxo_livre is not None else None,
        'dscr_operacional':       dscr,
    }
