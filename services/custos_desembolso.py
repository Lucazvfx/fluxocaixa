"""Estrutura de custo por desembolso (perfil de gasto) → custo_arroba do parecer.

Módulo puro — não importa Flask nem DB. Converte o desembolso mensal por
cabeça (R$/cab/mês, padrão do setor) no custo em R$/@·ano que o motor usa,
usando o peso médio do rebanho declarado (sem supor peso).

Fonte dos presets: GEP Araguaia / Inttegra (Terra Desenvolvimento Agropecuário),
"Perfil de Desembolso" safra 24/25, por modalidade, colunas Média e Top Rentáveis.
"""
from __future__ import annotations

# Componentes na ordem de exibição: (chave, rótulo).
COMPONENTES = [
    ('insumos',        'Insumos do rebanho'),
    ('mao_obra',       'Mão de obra permanente'),
    ('administracao',  'Administração'),
    ('maquinas',       'Máquinas (custeio+inv.)'),
    ('pastagem',       'Pastagem (custeio+inv.)'),
    ('infraestrutura', 'Infraestrutura (custeio+inv.)'),
    ('taxas_impostos', 'Taxas e impostos'),
    ('outros',         'Outros'),
]

# modalidade -> {componente: (media, top_rentaveis)} em R$/cab/mês.
PERFIL_DESEMBOLSO = {
    'CRIA': {
        'insumos':        (25.53, 22.17),
        'mao_obra':       (18.20, 14.66),
        'administracao':  (7.97, 5.30),
        'maquinas':       (11.79, 7.63),
        'pastagem':       (11.97, 9.09),
        'infraestrutura': (11.59, 7.30),
        'taxas_impostos': (2.66, 2.26),
        'outros':         (1.17, 1.22),
    },  # TOTAL: média 90,88 · top 69,63
    'RECRIA_ENGORDA': {
        'insumos':        (77.46, 96.53),
        'mao_obra':       (19.62, 17.04),
        'administracao':  (14.04, 7.92),
        'maquinas':       (19.37, 15.49),
        'pastagem':       (15.38, 11.44),
        'infraestrutura': (18.79, 12.35),
        'taxas_impostos': (5.05, 5.77),
        'outros':         (1.03, 0.74),
    },  # TOTAL: média 170,74 · top 167,28
    'CICLO_COMPLETO': {
        'insumos':        (44.92, 42.18),
        'mao_obra':       (18.10, 14.39),
        'administracao':  (8.49, 5.89),
        'maquinas':       (15.23, 10.71),
        'pastagem':       (14.29, 10.79),
        'infraestrutura': (13.69, 8.40),
        'taxas_impostos': (3.66, 3.10),
        'outros':         (0.76, 0.62),
    },  # TOTAL: média 119,14 · top 96,08
}


def custo_arroba_de_desembolso(desembolso_cab_mes: float,
                               arrobas_rebanho: float,
                               total_cabecas: float) -> float:
    """Converte desembolso (R$/cab/mês) em custo R$/@·ano exato.

    custo_arroba = desembolso × 12 / peso_médio_@, onde
    peso_médio_@ = arrobas_rebanho / total_cabecas (da composição declarada).
    """
    if total_cabecas <= 0:
        return 0.0
    peso_medio_arroba = arrobas_rebanho / total_cabecas
    if peso_medio_arroba <= 0:
        return 0.0
    return desembolso_cab_mes * 12.0 / peso_medio_arroba


def preset_modalidade(tipo: str, perfil: str) -> dict:
    """Devolve {componente: valor R$/cab/mês} do preset da modalidade.

    tipo: CRIA | RECRIA | ENGORDA | CICLO_COMPLETO (RECRIA/ENGORDA agrupam).
    perfil: 'media' | 'top'.
    """
    mod = 'RECRIA_ENGORDA' if tipo in ('RECRIA', 'ENGORDA') else tipo
    if mod not in PERFIL_DESEMBOLSO:
        mod = 'CICLO_COMPLETO'
    idx = 0 if perfil == 'media' else 1
    return {k: v[idx] for k, v in PERFIL_DESEMBOLSO[mod].items()}
