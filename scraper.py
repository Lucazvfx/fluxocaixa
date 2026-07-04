import requests
import re
import asyncio
import importlib
import math

def extrair_valores_especificos(texto, praca_alvo):
    """
    Busca uma praça específica e extrai os dois primeiros valores financeiros 
    que aparecem após o nome dela.
    """
    # Regex que ignora espaços e tags entre a praça e os valores
    padrao = re.compile(rf'{praca_alvo}.*?(\d{{2,3}},\d{{2}}).*?(\d{{2,3}},\d{{2}})', re.IGNORECASE | re.DOTALL)
    match = padrao.search(texto)
    if match:
        v_vista = float(match.group(1).replace(',', '.'))
        v_30d = float(match.group(2).replace(',', '.'))
        return v_vista, v_30d
    return 0.0, 0.0
def _obter_via_agrobr():
    """Tenta obter preços usando a biblioteca `agrobr` se disponível.

    Retorna dict {'boi': float, 'vaca': float, 'boi_china': float} ou None se falhar.
    """
    try:
        agrobr = importlib.import_module('agrobr')
    except Exception:
        return None

    try:
        # datasets é assíncrono conforme documentação
        datasets = agrobr.datasets
        # Executa a coroutine e obtém um DataFrame pandas
        df = asyncio.run(datasets.preco_diario('boi'))
        import pandas as pd
        if not isinstance(df, pd.DataFrame) or df.empty:
            return None

        # Identifica coluna de data e coluna de preço
        cols = [c for c in df.columns]
        date_col = next((c for c in cols if 'data' in c.lower() or 'date' in c.lower()), None)
        price_col = next((c for c in cols if 'preco' in c.lower() or 'valor' in c.lower() or 'price' in c.lower()), None)

        if price_col is None:
            # tenta usar a segunda coluna como fallback
            price_col = cols[1] if len(cols) > 1 else cols[0]

        # Ordena por data se possível e pega o valor mais recente
        if date_col:
            try:
                df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
                df = df.sort_values(date_col, ascending=False)
            except Exception:
                pass

        # Limpa e converte o valor
        val_raw = df[price_col].dropna().iloc[0]
        if isinstance(val_raw, str):
            val = float(str(val_raw).replace('.', '').replace(',', '.'))
        else:
            val = float(val_raw)

        # Retorna preço encontrado; vaca e boi_china não são fornecidos por agrobr -> fallback 0
        return {'boi': float(val), 'vaca': 0.0, 'boi_china': 0.0}
    except Exception:
        return None


_HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
_DEFAULTS = {'boi': 328.0, 'vaca': 308.0, 'boi_china': 340.0}
_URL_BOI_NA = "https://www.noticiasagricolas.com.br/cotacoes/boi-gordo"
_URL_VACA_SCOT = "https://www.scotconsultoria.com.br/cotacoes/vaca-gorda/?ref=smnb"


def obter_precos_arroba():
    """Cotação diária nacional por categoria, com fallback por categoria.

    Boi: indicador CEPEA/ESALQ republicado pela Notícias Agrícolas.
    Vaca: Scot Consultoria (praça de referência nacional).
    Bezerro: último valor salvo (se o analista ajustou) ou referência de mercado.
    Bezerra: derivada do bezerro (× 0,90).

    Retorna {'boi','vaca','boi_china','bezerro','bezerra','fonte'}. Nunca lança;
    cai para último salvo → default quando a fonte falha.
    """
    from services.precos_diarios import (
        parse_boi_na, parse_vaca_scot, bezerra_de, valido,
        FAIXA_BEZERRO, BEZERRO_REF,
    )
    try:
        import database as db
        ultimo = db.obter_cotacoes_atuais() or {}
    except Exception:
        ultimo = {}

    # ── BOI — Notícias Agrícolas (CEPEA/ESALQ) ──
    boi, fonte_boi = 0.0, ''
    try:
        html = requests.get(_URL_BOI_NA, headers=_HEADERS, timeout=20).text
        boi = parse_boi_na(html)
        if boi:
            fonte_boi = 'CEPEA/ESALQ (Notícias Agrícolas)'
    except Exception:
        pass
    if not boi:
        boi = float(ultimo.get('boi') or 0) or _DEFAULTS['boi']
        fonte_boi = 'último salvo' if ultimo.get('boi') else 'default'

    # ── VACA — Scot ──
    vaca, fonte_vaca = 0.0, ''
    try:
        html = requests.get(_URL_VACA_SCOT, headers=_HEADERS, timeout=20).text
        vaca = parse_vaca_scot(html)
        if vaca:
            fonte_vaca = 'Scot Consultoria'
    except Exception:
        pass
    if not vaca:
        vaca = float(ultimo.get('vaca') or 0) or _DEFAULTS['vaca']
        fonte_vaca = 'último salvo' if ultimo.get('vaca') else 'default'

    # ── BEZERRO — último salvo (analista) ou referência; BEZERRA derivada ──
    bezerro = float(ultimo.get('bezerro') or 0)
    if not valido(bezerro, *FAIXA_BEZERRO):
        bezerro = BEZERRO_REF
    bezerra = bezerra_de(bezerro)

    boi_china = float(ultimo.get('boi_china') or 0) or _DEFAULTS['boi_china']
    fonte = f'boi: {fonte_boi}; vaca: {fonte_vaca}; bezerro: referência/editável'
    print(f"[Cotação] boi {boi} ({fonte_boi}) | vaca {vaca} ({fonte_vaca}) | "
          f"bezerro {bezerro} | bezerra {bezerra}")
    return {'boi': boi, 'vaca': vaca, 'boi_china': boi_china,
            'bezerro': bezerro, 'bezerra': bezerra, 'fonte': fonte}


def obter_precos_agrobr_strict():
    """Força a obtenção de preços apenas via `agrobr`.

    Retorna dicionário {'boi','vaca','boi_china'} ou lança RuntimeError se não for possível.
    """
    res = _obter_via_agrobr()
    if not res:
        raise RuntimeError("agrobr não disponível ou falha ao obter dados — instale 'agrobr' e dependências.")
    return res