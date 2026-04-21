import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime

def obter_precos_boi_scot_ro():
    """
    Extrai da página do Boi Gordo da Scot Consultoria os preços para Rondônia.
    Retorna dicionário com 'boi_china_ro' e 'indicador_ro'.
    """
    url = "https://www.scotconsultoria.com.br/cotacoes/boi-gordo/"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    resultado = {'boi_china_ro': 0.0, 'indicador_ro': 0.0}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        for tr in soup.find_all('tr'):
            celulas = tr.find_all(['td', 'th'])
            for idx, cel in enumerate(celulas):
                if 'Rondônia' in cel.get_text():
                    if idx + 1 < len(celulas):
                        texto_china = celulas[idx + 1].get_text().strip()
                        preco_china = re.search(r'(\d{1,3}(?:\.\d{3})*,\d{2})', texto_china)
                        if preco_china:
                            resultado['boi_china_ro'] = float(preco_china.group(1).replace('.', '').replace(',', '.'))
                    if idx + 2 < len(celulas):
                        texto_indicador = celulas[idx + 2].get_text().strip()
                        preco_indicador = re.search(r'(\d{1,3}(?:\.\d{3})*,\d{2})', texto_indicador)
                        if preco_indicador:
                            resultado['indicador_ro'] = float(preco_indicador.group(1).replace('.', '').replace(',', '.'))
                    break
            if resultado['boi_china_ro'] != 0 or resultado['indicador_ro'] != 0:
                break
    except Exception as e:
        print(f"[Scraper Boi] Erro: {e}")
    return resultado

def obter_preco_vaca_scot_ro():
    """
    Extrai da página da Vaca Gorda da Scot Consultoria o preço para Rondônia.
    Retorna o preço da vaca gorda à vista.
    """
    url = "https://www.scotconsultoria.com.br/cotacoes/vaca-gorda/"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        for tr in soup.find_all('tr'):
            celulas = tr.find_all(['td', 'th'])
            for idx, cel in enumerate(celulas):
                if 'RO Sudeste' in cel.get_text():
                    # O primeiro número após o nome da região é o preço à vista
                    if idx + 1 < len(celulas):
                        texto_preco = celulas[idx + 1].get_text().strip()
                        preco = re.search(r'(\d{1,3}(?:\.\d{3})*,\d{2})', texto_preco)
                        if preco:
                            return float(preco.group(1).replace('.', '').replace(',', '.'))
                    break
    except Exception as e:
        print(f"[Scraper Vaca] Erro: {e}")
    return 0.0

def obter_preco_boi_cepea():
    """Fallback: busca o preço do boi gordo no Cepea."""
    url = "https://www.cepea.esalq.usp.br/br/indicador/boi-gordo.aspx"
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        tabela = soup.find('table', class_='tabela-indicador')
        if tabela:
            linhas = tabela.find_all('tr')
            if len(linhas) > 1:
                celulas = linhas[1].find_all('td')
                if celulas:
                    texto = celulas[0].get_text().strip()
                    preco = re.search(r'(\d{1,3}(?:\.\d{3})*,\d{2})', texto)
                    if preco:
                        return float(preco.group(1).replace('.', '').replace(',', '.'))
    except Exception as e:
        print(f"[Scraper Cepea] Erro: {e}")
    return 0.0

def obter_precos_arroba():
    """
    Função principal orquestradora.
    Retorna dicionário com os preços formatado para a API.
    """
    # Tenta obter da Scot
    precos_boi = obter_precos_boi_scot_ro()
    boi_china = precos_boi['boi_china_ro']
    indicador = precos_boi['indicador_ro']
    preco_vaca = obter_preco_vaca_scot_ro()

    # Se todos falharam, tenta Cepea como fallback para o boi gordo
    if boi_china == 0 and indicador == 0:
        preco_cepea = obter_preco_boi_cepea()
        boi_china = preco_cepea
        indicador = preco_cepea
        fonte = "Cepea (fallback)"
    else:
        fonte = "Scot Consultoria"

    return {
        'boi': boi_china,
        'vaca': preco_vaca,
        'boi_china': boi_china,
        'indicador': indicador,
        'fonte': fonte,
        'data_hora': datetime.now().isoformat()
    }

if __name__ == "__main__":
    print(obter_precos_arroba())