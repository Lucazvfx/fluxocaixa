"""Reconciliação de garantia: cruza o rebanho declarado em documentos distintos.

Diferencial de mercado: um analista de crédito recebe o rebanho declarado em
fontes que deveriam bater — Ficha Sanitária estadual (animais efetivamente
vacinados), Imposto de Renda (bens declarados) e GTA (trânsito) — e precisa
detectar quando a garantia oferecida está superavaliada (rebanho de papel maior
que o rebanho físico).

A Ficha Sanitária é o piso físico mais confiável (animal vacinado existe), então
ela é a base de comparação quando presente; sem ela, a menor fonte é a base
conservadora.

REGRA DE INTEGRIDADE: os benchmarks técnicos vêm de fonte institucional. Aqui, ao
contrário, as tolerâncias (5% alerta, 15% erro) são HEURÍSTICAS OPERACIONAIS de
análise de crédito, não números extraídos dos anexos — margem de mortalidade,
nascimento e erro de contagem entre documentos de datas diferentes.
"""
from __future__ import annotations

_FONTES_VALIDAS = ("ficha", "ir", "gta")

_NOME_FONTE = {
    "ficha": "Ficha Sanitária",
    "ir": "Imposto de Renda",
    "gta": "GTA",
}


def _coagir(valor) -> int | None:
    """Converte para inteiro não-negativo; None/'' viram None; negativo vira 0."""
    if valor in (None, ""):
        return None
    try:
        n = int(round(float(valor)))
    except (TypeError, ValueError):
        return None
    return max(n, 0)


def reconciliar(totais: dict, *, tol_alerta: float = 0.05,
                tol_erro: float = 0.15) -> dict:
    """Reconcilia o total de rebanho declarado em fontes distintas.

    Args:
        totais: Dict com quaisquer de 'ficha', 'ir', 'gta' (inteiros ≥ 0).
            Fontes ausentes, None ou '' são ignoradas.
        tol_alerta: Divergência relativa até a qual o par é considerado 'ok'
            (padrão 5%). Heurística operacional.
        tol_erro: Divergência relativa até a qual o par é 'alerta'; acima é
            'erro' (padrão 15%). Heurística operacional.

    Returns:
        Dict com fontes, base, divergencias (par a par), resumo e veredito.

    Raises:
        ValueError: Se houver menos de duas fontes com valor válido.
    """
    fontes = {
        k: _coagir(totais.get(k))
        for k in _FONTES_VALIDAS
        if _coagir(totais.get(k)) is not None
    }
    if len(fontes) < 2:
        raise ValueError(
            "Reconciliação exige pelo menos duas fontes com valor válido "
            f"(recebidas: {list(fontes)})."
        )

    if "ficha" in fontes:
        base = "ficha"
    else:
        base = min(fontes, key=fontes.get)

    nomes = sorted(fontes)
    divergencias = []
    resumo = {"ok": 0, "alertas": 0, "erros": 0}

    for i in range(len(nomes)):
        for j in range(i + 1, len(nomes)):
            a, b = nomes[i], nomes[j]
            va, vb = fontes[a], fontes[b]
            abs_diff = abs(va - vb)
            menor = min(va, vb)
            pct = (abs_diff / menor * 100) if menor > 0 else (
                0.0 if abs_diff == 0 else float("inf")
            )

            if pct <= tol_alerta * 100:
                sev = "ok"
                resumo["ok"] += 1
            elif pct <= tol_erro * 100:
                sev = "alerta"
                resumo["alertas"] += 1
            else:
                sev = "erro"
                resumo["erros"] += 1

            divergencias.append({
                "par": (a, b),
                "a": va,
                "b": vb,
                "divergencia_abs": abs_diff,
                "divergencia_pct": round(pct, 1),
                "severidade": sev,
                "maior": a if va > vb else (b if vb > va else None),
            })

    if resumo["erros"] > 0:
        veredito = "GARANTIA SUPERAVALIADA"
    elif resumo["alertas"] > 0:
        veredito = "REVISAR DIVERGÊNCIA"
    else:
        veredito = "DOCUMENTOS CONSISTENTES"

    return {
        "fontes": fontes,
        "nomes": _NOME_FONTE,
        "base": base,
        "divergencias": divergencias,
        "resumo": resumo,
        "veredito": veredito,
    }
