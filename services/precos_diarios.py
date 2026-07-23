"""Parsing puro de preços diários (sem rede) + derivações e sanidade.

O download HTTP fica no `scraper.py`; aqui só transformamos HTML → número, para
que o parsing seja testável com HTML fixo (sem depender de rede/site no ar).

Fontes: boi = indicador CEPEA/ESALQ republicado pela Notícias Agrícolas;
vaca = Scot Consultoria (praça de referência nacional);
bezerro = CEPEA/ESALQ indicador de bezerro (cepea.org.br/br/indicador/bezerro.aspx);
bezerra = bezerro × fator (fêmea ~10% abaixo do macho).
"""
from __future__ import annotations
import re

FATOR_BEZERRA = 0.90        # bezerra = bezerro × 0,90 (desconto da fêmea)
BEZERRO_REF = 3400.0        # R$/cabeça — CEPEA MS média jul/2026 (~R$3.379); atualizar safra a safra

# Faixas de sanidade por categoria (rejeita valor absurdo pego de outra seção).
FAIXA_ARROBA = (100.0, 600.0)     # boi/vaca R$/@
FAIXA_BEZERRO = (800.0, 6000.0)   # bezerro R$/cabeça


def _num(txt: str) -> float:
    """Converte '1.234,56' ou '329,85' em float."""
    return float(txt.replace('.', '').replace(',', '.'))


def valido(v: float, lo: float, hi: float) -> bool:
    """True se v está dentro da faixa de sanidade [lo, hi]."""
    return lo <= v <= hi


def parse_boi_na(html: str) -> float:
    """Extrai o indicador CEPEA/ESALQ do boi da página da Notícias Agrícolas.

    Âncora no texto 'Indicador do Boi Gordo Esalq' e pega o primeiro valor
    R$ nnn,nn seguinte (a coluna 'à vista'). Retorna 0.0 se não achar.
    """
    low = html.lower()
    i = low.find('indicador do boi gordo esalq')
    if i < 0:
        return 0.0
    trecho = re.sub(r'<[^>]+>', ' ', html[i:i + 800])
    m = re.search(r'(\d{2,3},\d{2})', trecho)
    if not m:
        return 0.0
    v = _num(m.group(1))
    return v if valido(v, *FAIXA_ARROBA) else 0.0


def parse_vaca_scot(html: str) -> float:
    """Extrai a vaca da Scot: praça de referência (São Paulo) ou 1º valor válido."""
    texto = re.sub(r'<[^>]+>', ' ', html)
    # Preferência: praça de referência nacional (São Paulo).
    m = re.search(r'são paulo.*?(\d{2,3},\d{2})', texto, re.IGNORECASE | re.DOTALL)
    if m:
        v = _num(m.group(1))
        if valido(v, *FAIXA_ARROBA):
            return v
    # Fallback: primeiro valor dentro da faixa de arroba.
    for cand in re.findall(r'(\d{2,3},\d{2})', texto):
        v = _num(cand)
        if valido(v, *FAIXA_ARROBA):
            return v
    return 0.0


def parse_bezerro_cepea(html: str) -> float:
    """Extrai o indicador CEPEA do bezerro (R$/cabeça, desmamado, MS).

    Âncora na tabela de indicadores da página do CEPEA: busca o primeiro
    valor monetário plausível para R$/cabeça após remover tags HTML.
    Retorna 0.0 se não achar ou valor fora da faixa de sanidade.
    """
    texto = re.sub(r'<[^>]+>', ' ', html)
    # Valores de bezerro: tipicamente 1.000 a 6.000 R$/cab
    # Formato: "1.234,56" ou "2.300,00"
    for cand in re.findall(r'(\d{1,2}\.\d{3},\d{2})', texto):
        v = _num(cand)
        if valido(v, *FAIXA_BEZERRO):
            return v
    # Fallback: valor sem separador de milhar (ex: "2350,00")
    for cand in re.findall(r'(\d{3,4},\d{2})', texto):
        v = _num(cand)
        if valido(v, *FAIXA_BEZERRO):
            return v
    return 0.0


def bezerra_de(bezerro: float) -> float:
    """Preço da bezerra derivado do bezerro (R$/cabeça)."""
    return round(bezerro * FATOR_BEZERRA, 2)
