"""Benchmarks nacionais de pecuária de corte para análise de crédito.

Diferencial do produto: em vez de uma faixa opaca única, cada indicador é
confrontado contra *cada fonte institucional nomeada* (Embrapa, Scot, CEPEA-USP,
ABCZ, ASBIA) e contra o benchmark financeiro nacional de desembolso
(Inttegra 2025, Média vs Top Rentáveis). Aplica-se ao Brasil todo — as fontes
são referências nacionais, não estaduais.

REGRA DE INTEGRIDADE: todo número aqui vem de fonte real (PPTX "Análise Crédito
Pecuária" e XLSX GEP Araguaia / Inttegra 2025). Nada é estimado. Onde não há
dado real, o indicador simplesmente não é avaliado (ver LACUNAS no material).

Faixas em porcentagem (0–100). Modalidades: CRIA, RECRIA, ENGORDA,
CICLO_COMPLETO (mesmas strings de `ml_engine`/`BENCHMARKS_RO`).
"""
from __future__ import annotations

# --- Taxa de prenhez, por fonte (PPTX slide 3) --------------------------------
PRENHEZ_FONTES = {
    "Embrapa": (50.0, 65.0),
    "Scot Consultoria": (60.0, 60.0),
    "CEPEA-USP": (55.0, 60.0),
    "ABCZ": (65.0, 75.0),
    "ASBIA": (65.0, 65.0),
}

# --- Taxa de natalidade, por fonte (PPTX slide 4) -----------------------------
NATALIDADE_FONTES = {
    "Embrapa": (55.0, 65.0),
    "Scot Consultoria": (60.0, 60.0),
    "CEPEA-USP": (55.0, 60.0),
    "ABCZ": (65.0, 75.0),
}

_MULTIFONTE = {"prenhez": PRENHEZ_FONTES, "natalidade": NATALIDADE_FONTES}

# --- Prenhez por sistema de produção (PPTX slide 3) ---------------------------
PRENHEZ_SISTEMA = {
    "extensivo": (60.0, 75.0),
    "semi_intensivo": (75.0, 85.0),
    "intensivo": (85.0, 100.0),
}

# --- Desfrute por modalidade (PPTX slides 5–6) --------------------------------
DESFRUTE_MODALIDADE = {
    "CRIA": (18.0, 30.0),
    "RECRIA": (35.0, 55.0),
    "RECRIA_ENGORDA": (60.0, 85.0),
    "ENGORDA": (80.0, 120.0),
    "CICLO_COMPLETO": (20.0, 40.0),
}

# Escala geral de interpretação do desfrute (PPTX slide 5), independente de
# modalidade: (teto_exclusivo, classe).
_DESFRUTE_ESCALA = [
    (18.0, "muito_baixo"),
    (30.0, "baixo"),
    (55.0, "medio"),
    (85.0, "alto"),
    (float("inf"), "muito_alto"),
]

# --- Desembolso R$/cab/mês — Inttegra 2025 (XLSX GEP, aba PERFIL DESEMB) -------
# Média = produtor médio; Top = 25% mais rentáveis. Menor é melhor.
DESEMBOLSO_INTTEGRA = {
    "CRIA":           {"media": 90.88,  "top": 69.63},
    "RECRIA":         {"media": 100.50, "top": 77.40},   # desagregado de RECRIA_ENGORDA
    "ENGORDA":        {"media": 182.60, "top": 177.30},  # desagregado de RECRIA_ENGORDA
    "RECRIA_ENGORDA": {"media": 170.74, "top": 167.28},  # alias legado
    "CICLO_COMPLETO": {"media": 119.14, "top": 96.08},
}
FONTE_DESEMBOLSO = "GEP Araguaia / Inttegra (2025)"

_MAP_DESEMBOLSO = {
    "CRIA":           "CRIA",
    "RECRIA":         "RECRIA",
    "ENGORDA":        "ENGORDA",
    "RECRIA_ENGORDA": "RECRIA_ENGORDA",
    "CICLO_COMPLETO": "CICLO_COMPLETO",
}

# --- COE R$/@ vendida — Campo Futuro / CNA Brasil (agosto 2025, Para) ---------
# Paineis realizados em 3 municipios do PA. Unidade: R$/arroba VENDIDA.
# COE = Custo Operacional Efetivo / total de arrobas comercializadas no ano.
# O sistema converte: coe_calculado = custo_operacional / arrobas_vendidas_est
# onde arrobas_vendidas_est ~= receita_vendas / preco_arroba_ref.
COE_CAMPO_FUTURO = {
    "CICLO_COMPLETO": {
        "local": "Santana do Araguaia, PA",
        "coe_arroba": 164.61,
        "descricao": "5.100 cab . ciclo completo (cria + recria + engorda)",
        "maiores_itens_pct": {"Suplem. mineral": 51.3, "Mao de obra": 16.5},
    },
    "CRIA": {
        "local": "Altamira, PA",
        "coe_arroba": 189.76,
        "descricao": "150 matrizes . producao de bezerros",
        "maiores_itens_pct": {"Mao de obra": 18.2, "Suplem. mineral": 15.4},
    },
    "RECRIA_ENGORDA": {
        "local": "Paragominas, PA",
        "coe_arroba": 183.50,
        "descricao": "500 ha pastagem . recria e terminacao a pasto",
        "maiores_itens_pct": {"Reposicao animais": 62.2, "Suplem. mineral": 10.5},
    },
}
FONTE_COE = "Campo Futuro / CNA Brasil, agosto 2025 (Para)"


def posicao_valor(valor: float, lo: float, hi: float) -> str:
    """Posição do valor frente a uma faixa: 'abaixo', 'dentro' ou 'acima'."""
    if valor < lo:
        return "abaixo"
    if valor > hi:
        return "acima"
    return "dentro"


def avaliar_multifonte(indicador: str, valor: float) -> list:
    """Confronta um indicador contra cada fonte institucional que o publica.

    Args:
        indicador: 'prenhez' ou 'natalidade'.
        valor: Valor observado, em % (0–100).

    Returns:
        Lista de `{fonte, faixa, posicao}`, uma por fonte.

    Raises:
        ValueError: Se o indicador não tiver benchmark multi-fonte.
    """
    fontes = _MULTIFONTE.get(indicador)
    if fontes is None:
        raise ValueError(
            f"Sem benchmark multi-fonte para '{indicador}'. "
            f"Disponíveis: {', '.join(_MULTIFONTE)}."
        )
    return [
        {"fonte": nome, "faixa": (lo, hi), "posicao": posicao_valor(valor, lo, hi)}
        for nome, (lo, hi) in fontes.items()
    ]


def _classe_desfrute(valor: float) -> str:
    for teto, classe in _DESFRUTE_ESCALA:
        if valor < teto:
            return classe
    return "muito_alto"


def avaliar_desfrute(modalidade: str, valor: float) -> dict | None:
    """Avalia o desfrute frente à faixa esperada da modalidade.

    Returns:
        `{modalidade, faixa, posicao, classe, fonte}` ou None se a modalidade
        não tiver faixa de desfrute conhecida.
    """
    faixa = DESFRUTE_MODALIDADE.get(modalidade)
    if faixa is None:
        return None
    lo, hi = faixa
    return {
        "modalidade": modalidade,
        "valor": round(valor, 1),
        "faixa": faixa,
        "posicao": posicao_valor(valor, lo, hi),
        "classe": _classe_desfrute(valor),
        "fonte": "Metodologia Análise Crédito Pecuária",
    }


def avaliar_desembolso(modalidade: str, valor_real: float) -> dict | None:
    """Confronta o desembolso (R$/cab/mês) contra Média e Top Rentáveis.

    Menor é melhor: abaixo do Top = excelente; entre Top e Média = bom;
    acima da Média = atenção (custo acima do produtor médio nacional).

    Returns:
        `{modalidade, valor, media, top, nivel, fonte}` ou None se não houver
        perfil financeiro para a modalidade.
    """
    chave = _MAP_DESEMBOLSO.get(modalidade)
    ref = DESEMBOLSO_INTTEGRA.get(chave) if chave else None
    if ref is None:
        return None
    if valor_real <= ref["top"]:
        nivel = "excelente"
    elif valor_real <= ref["media"]:
        nivel = "bom"
    else:
        nivel = "atencao"
    return {
        "modalidade": modalidade,
        "valor": round(valor_real, 2),
        "media": ref["media"],
        "top": ref["top"],
        "nivel": nivel,
        "fonte": FONTE_DESEMBOLSO,
    }


def avaliar_coe(modalidade: str, coe_calculado: float) -> dict | None:
    """Compara o COE calculado (R$/@ vendida) com referencia Campo Futuro 2025.

    coe_calculado = custo_operacional_anual / arrobas_vendidas_estimadas
    Referencia e para sistemas extensivos do Para - serve como piso de
    comparacao; sistemas mais intensivos tendem a ter COE maior.
    """
    ref_key = modalidade if modalidade in COE_CAMPO_FUTURO else (
        "RECRIA_ENGORDA" if modalidade in ("RECRIA", "ENGORDA") else None
    )
    ref = COE_CAMPO_FUTURO.get(ref_key) if ref_key else None
    if ref is None or coe_calculado <= 0:
        return None
    coe_ref = ref["coe_arroba"]
    delta_pct = (coe_calculado - coe_ref) / coe_ref * 100
    if coe_calculado <= coe_ref * 0.90:
        nivel = "excelente"
    elif coe_calculado <= coe_ref:
        nivel = "bom"
    elif coe_calculado <= coe_ref * 1.20:
        nivel = "atencao"
    else:
        nivel = "alto"
    return {
        "coe_calculado":  round(coe_calculado, 2),
        "coe_referencia": coe_ref,
        "local_ref":      ref["local"],
        "descricao_ref":  ref["descricao"],
        "delta_pct":      round(delta_pct, 1),
        "nivel":          nivel,
        "fonte":          FONTE_COE,
    }


def avaliar_nacional(modalidade: str, dados: dict) -> dict:
    """Monta o painel nacional a partir dos indicadores disponíveis.

    Args:
        modalidade: CRIA, RECRIA, ENGORDA ou CICLO_COMPLETO.
        dados: Dict com quaisquer de `prenhez`, `natalidade` (% 0–100),
            `desfrute` (% 0–100) e `desembolso` (R$/cab/mês). Só o que estiver
            presente é avaliado.

    Returns:
        `{modalidade, multifonte, desfrute, desembolso}`.
    """
    multifonte = []
    for indicador in ("prenhez", "natalidade"):
        if dados.get(indicador) is not None:
            multifonte.append({
                "indicador": indicador,
                "valor": round(float(dados[indicador]), 1),
                "fontes": avaliar_multifonte(indicador, float(dados[indicador])),
            })

    desfrute = None
    if dados.get("desfrute") is not None:
        desfrute = avaliar_desfrute(modalidade, float(dados["desfrute"]))

    desembolso = None
    if dados.get("desembolso") is not None:
        desembolso = avaliar_desembolso(modalidade, float(dados["desembolso"]))

    return {
        "modalidade": modalidade,
        "multifonte": multifonte,
        "desfrute": desfrute,
        "desembolso": desembolso,
    }
