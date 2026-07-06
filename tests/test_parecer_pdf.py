from services.parecer_pdf import gerar_pdf_parecer

PARECER_COMPLETO = {
    'secoes': ['identificacao', 'composicao', 'indicadores', 'consistencia', 'financeiro', 'conclusao'],
    'identificacao': {'fazenda': 'Fazenda Teste', 'municipio': 'Juara - MT', 'proprietario': 'João da Silva'},
    'composicao': {'total': 200, 'valores': [10, 10, 8, 8, 6, 6, 30, 2, 40, 3]},
    'indicadores': {'valores': {'total': 200, 'total_femeas': 120}, 'benchmarks': [
        {'label': 'Taxa de Natalidade', 'faixa': 'bom'}]},
    'consistencia': {'score_consistencia': 90, 'resumo': {'erros': 0, 'alertas': 1, 'ok': 5},
                     'flags': [{'severidade': 'alerta', 'titulo': 'Relação touro:matriz',
                                'mensagem': 'Levemente fora do padrão'}]},
    'financeiro': {'preco_breakeven': 170.88, 'unidade': 'R$/arroba'},
    'conclusao': {'dscr': 1.45, 'parcela_mensal': 12345.67, 'servico_divida_anual': 148148.0,
                  'geracao_caixa_anual': 214814.6, 'recomendacao': 'aprovar', 'faixa': 'aprovar',
                  'justificativa': 'Cobertura 1.45 — folga confortável sobre o serviço da dívida.'},
}

PARECER_SEM_CREDITO = {
    **PARECER_COMPLETO,
    'conclusao': {'dscr': None, 'parcela_mensal': 0.0, 'servico_divida_anual': 0.0,
                  'geracao_caixa_anual': 214814.6, 'recomendacao': None, 'faixa': None,
                  'justificativa': 'Sem crédito a avaliar.'},
}

PARECER_SEM_FLAGS = {
    **PARECER_COMPLETO,
    'consistencia': {'score_consistencia': 100, 'resumo': {'erros': 0, 'alertas': 0, 'ok': 6}, 'flags': []},
}


def test_gerar_pdf_devolve_bytes_pdf_valido():
    pdf = gerar_pdf_parecer(PARECER_COMPLETO)
    assert isinstance(pdf, bytes)
    assert pdf.startswith(b'%PDF')


def test_gerar_pdf_sem_conclusao_de_credito_nao_lanca():
    pdf = gerar_pdf_parecer(PARECER_SEM_CREDITO)
    assert pdf.startswith(b'%PDF')


def test_gerar_pdf_sem_flags_de_consistencia_nao_lanca():
    pdf = gerar_pdf_parecer(PARECER_SEM_FLAGS)
    assert pdf.startswith(b'%PDF')


def test_gerar_pdf_com_nome_consultoria():
    pdf = gerar_pdf_parecer(PARECER_COMPLETO, branding={'nome_consultoria': 'Consultoria X'})
    assert pdf.startswith(b'%PDF')


def test_gerar_pdf_com_logo_base64_invalido_nao_lanca():
    pdf = gerar_pdf_parecer(PARECER_COMPLETO, branding={'logo_base64': 'não-é-base64-válido!!'})
    assert pdf.startswith(b'%PDF')


def test_gerar_pdf_sem_branding_identico_ao_atual():
    pdf = gerar_pdf_parecer(PARECER_COMPLETO, branding=None)
    assert pdf.startswith(b'%PDF')
