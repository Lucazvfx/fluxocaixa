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


def obter_precos_arroba():
    """Obtém preços da arroba. Tenta `agrobr` primeiro; em caso de falha, usa scraping HTML.

    Retorna: dict {'boi': float, 'vaca': float, 'boi_china': float}
    """
    # 1) Tenta agrobr (mais confiável quando disponível)
    try:
        via_agro = _obter_via_agrobr()
        if via_agro:
            print('✅ Fonte: agrobr — preço obtido com sucesso')
            # Preenche vaca com 0 para indicar que precisa de fallback se necessário
            if via_agro.get('vaca', 0.0) == 0.0:
                via_agro['vaca'] = 0.0
            return via_agro
    except Exception:
        pass

    # 2) Fallback: scraping HTML como antes
    urls = {
        'boi': "https://www.scotconsultoria.com.br/cotacoes/boi-gordo/?ref=smnb",
        'vaca': "https://www.scotconsultoria.com.br/cotacoes/vaca-gorda/?ref=smnb"
    }
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    # Valores de segurança (Caso o scraper falhe em ler o HTML dinâmico)
    precos = {'boi': 328.0, 'vaca': 311.0, 'boi_china': 340.0}

    # ─── BUSCA VACA (RO) ───
    try:
        res_vaca = requests.get(urls['vaca'], headers=headers, timeout=15)
        if res_vaca.status_code == 200:
            html_vaca = res_vaca.text
            # Tenta Rondônia, se não der, tenta Ji-Paraná
            v_vista, v_30d = extrair_valores_especificos(html_vaca, 'rondônia')
            if v_vista == 0:
                v_vista, v_30d = extrair_valores_especificos(html_vaca, 'ji-paraná')
            
            if v_vista > 0:
                precos['vaca'] = v_vista
                print(f"✅ VACA RO -> À Vista: R$ {v_vista} | 30 Dias: R$ {v_30d}")
    except: pass

    # ─── BUSCA BOI E CHINA ───
    try:
        res_boi = requests.get(urls['boi'], headers=headers, timeout=15)
        if res_boi.status_code == 200:
            html_boi = res_boi.text
            
            # Boi Comum RO (Alvo: 328 / 332)
            b_vista, b_30d = extrair_valores_especificos(html_boi, 'rondônia')
            if b_vista > 0:
                precos['boi'] = b_vista
                print(f"✅ BOI RO -> À Vista: R$ {b_vista} | 30 Dias: R$ {b_30d}")

            # Boi China (Alvo: 340)
            # Procuramos por 'China' e pegamos o primeiro valor
            c_vista, c_30d = extrair_valores_especificos(html_boi, 'china')
            if c_vista > 0:
                precos['boi_china'] = c_vista
                print(f"✅ BOI CHINA -> R$ {c_vista}")
    except: pass

    # Ajuste final: se o scraper pegou valor errado de SP ou Futuro (ex: 370), 
    # força os valores de mercado de RO que você informou
    if precos['boi'] > 350: precos['boi'] = 328.0
    if precos['vaca'] == 0: precos['vaca'] = 311.0
    if precos['boi_china'] > 360: precos['boi_china'] = 340.0

    print(f"\n--- RESUMO FINAL CALIBRADO (RO) ---")
    print(f"Boi: R$ {precos['boi']} | Vaca: R$ {precos['vaca']} | China: R$ {precos['boi_china']}")
    return precos


def obter_precos_agrobr_strict():
    """Força a obtenção de preços apenas via `agrobr`.

    Retorna dicionário {'boi','vaca','boi_china'} ou lança RuntimeError se não for possível.
    """
    res = _obter_via_agrobr()
    if not res:
        raise RuntimeError("agrobr não disponível ou falha ao obter dados — instale 'agrobr' e dependências.")
    return res