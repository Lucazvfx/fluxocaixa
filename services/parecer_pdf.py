"""Geração de PDF do parecer de crédito — documento profissional para anexar
a um processo de crédito (não o tema escuro do dashboard).

Módulo puro: recebe o dict do parecer (mesma estrutura de
`services.parecer_credito.montar_parecer`), devolve os bytes do PDF. Sem
dependência de sistema (reportlab é puro Python/wheels), funciona igual em
qualquer alvo de deploy.
"""
from __future__ import annotations
import io
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
)

_COR_RECOMENDACAO = {
    'aprovar': colors.HexColor('#2E7D32'),
    'ressalva': colors.HexColor('#B8860B'),
    'negar': colors.HexColor('#C62828'),
}
_LABEL_RECOMENDACAO = {
    'aprovar': 'APROVAR', 'ressalva': 'APROVAR COM RESSALVA', 'negar': 'NEGAR',
}


def _styles():
    ss = getSampleStyleSheet()
    ss.add(ParagraphStyle('Titulo', parent=ss['Heading1'], fontSize=16, spaceAfter=4))
    ss.add(ParagraphStyle('Subtitulo', parent=ss['Normal'], fontSize=9, textColor=colors.grey))
    ss.add(ParagraphStyle('SecaoTitulo', parent=ss['Heading2'], fontSize=12, spaceBefore=14, spaceAfter=6))
    ss.add(ParagraphStyle('Corpo', parent=ss['Normal'], fontSize=10, leading=14))
    return ss


def _fmt_moeda(v) -> str:
    try:
        return f"R$ {float(v):,.2f}".replace(',', '_').replace('.', ',').replace('_', '.')
    except (TypeError, ValueError):
        return '—'


def gerar_pdf_parecer(parecer: dict) -> bytes:
    ss = _styles()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            topMargin=2*cm, bottomMargin=2*cm,
                            leftMargin=2*cm, rightMargin=2*cm)
    story = []

    ident = parecer.get('identificacao') or {}
    story.append(Paragraph('Parecer de Crédito — Análise Técnico-Financeira', ss['Titulo']))
    fazenda = ident.get('fazenda') or '—'
    municipio = ident.get('municipio') or '—'
    proprietario = ident.get('proprietario') or '—'
    story.append(Paragraph(
        f"{fazenda} · {municipio} · {proprietario} — emitido em "
        f"{datetime.now().strftime('%d/%m/%Y')}", ss['Subtitulo']))
    story.append(HRFlowable(width='100%', color=colors.HexColor('#CCCCCC'), spaceBefore=8, spaceAfter=4))

    composicao = parecer.get('composicao') or {}
    story.append(Paragraph('Composição do Rebanho', ss['SecaoTitulo']))
    story.append(Paragraph(f"Total de animais: {composicao.get('total', '—')}", ss['Corpo']))

    indicadores = parecer.get('indicadores') or {}
    benchmarks = indicadores.get('benchmarks') or []
    if benchmarks:
        story.append(Paragraph('Indicadores Técnicos vs. Benchmark', ss['SecaoTitulo']))
        linhas = [['Indicador', 'Faixa']]
        for b in benchmarks:
            linhas.append([b.get('label', '—'), str(b.get('faixa', '—')).capitalize()])
        t = Table(linhas, colWidths=[10*cm, 6*cm])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#EEEEEE')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#DDDDDD')),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
        ]))
        story.append(t)

    consistencia = parecer.get('consistencia') or {}
    story.append(Paragraph('Consistência do Rebanho Declarado', ss['SecaoTitulo']))
    score = consistencia.get('score_consistencia', '—')
    resumo = consistencia.get('resumo') or {}
    story.append(Paragraph(
        f"Score: {score} — {resumo.get('erros', 0)} erro(s), "
        f"{resumo.get('alertas', 0)} alerta(s), {resumo.get('ok', 0)} ok", ss['Corpo']))
    for f in (consistencia.get('flags') or []):
        story.append(Paragraph(
            f"• <b>{f.get('titulo', '')}</b>: {f.get('mensagem', '')}", ss['Corpo']))

    financeiro = parecer.get('financeiro') or {}
    if financeiro:
        story.append(Paragraph('Situação Financeira', ss['SecaoTitulo']))
        be = financeiro.get('preco_breakeven')
        if be is not None:
            story.append(Paragraph(
                f"Preço de equilíbrio (breakeven): {_fmt_moeda(be)} "
                f"{financeiro.get('unidade', '')}", ss['Corpo']))

    conclusao = parecer.get('conclusao') or {}
    story.append(Paragraph('Conclusão — Capacidade de Pagamento', ss['SecaoTitulo']))
    rec = conclusao.get('recomendacao')
    if rec:
        cor = _COR_RECOMENDACAO.get(rec, colors.grey)
        label = _LABEL_RECOMENDACAO.get(rec, rec.upper())
        t = Table([[Paragraph(f"<b>{label}</b>", ParagraphStyle('r', parent=ss['Corpo'], textColor=colors.white, fontSize=12))]],
                  colWidths=[16*cm])
        t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), cor),
                               ('TOPPADDING', (0, 0), (-1, -1), 8),
                               ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                               ('LEFTPADDING', (0, 0), (-1, -1), 10)]))
        story.append(t)
        story.append(Spacer(1, 6))
        story.append(Paragraph(
            f"DSCR: {conclusao.get('dscr')} · Parcela mensal: "
            f"{_fmt_moeda(conclusao.get('parcela_mensal'))}", ss['Corpo']))
        story.append(Paragraph(conclusao.get('justificativa', ''), ss['Corpo']))
    else:
        story.append(Paragraph(
            conclusao.get('justificativa') or 'Sem solicitação de crédito informada.', ss['Corpo']))

    doc.build(story)
    return buf.getvalue()
