from services.consistencia_rebanho import analisar_consistencia_historica


def test_crescimento_implicavel_gera_erro():
    ant = [50, 50, 40, 40, 30, 30, 200, 10, 300, 20]
    # duplica o rebanho — 100% de crescimento, acima do limite de 40%
    atu = [x * 2 for x in ant]
    flags = analisar_consistencia_historica(atu, ant)
    erros = [f for f in flags if f['severidade'] == 'erro' and 'crescimento' in f['codigo']]
    assert erros, "Deve gerar flag de crescimento implausível"


def test_crescimento_normal_sem_flag():
    ant = [50, 50, 40, 40, 30, 30, 200, 10, 300, 20]
    # crescimento de 10% — dentro do limite
    atu = [round(x * 1.10) for x in ant]
    flags = analisar_consistencia_historica(atu, ant)
    erros = [f for f in flags if 'crescimento' in f['codigo']]
    assert not erros, f"Não deve gerar flag de crescimento para 10%: {erros}"


def test_categoria_desaparece_gera_erro():
    ant = [60, 50, 40, 40, 30, 30, 200, 10, 300, 20]
    atu = [0, 50, 40, 40, 30, 30, 200, 10, 300, 20]  # fêmeas 0-4m zeraram
    flags = analisar_consistencia_historica(atu, ant)
    erros = [f for f in flags if 'desaparecimento' in f['codigo']]
    assert erros, "Deve gerar flag de desaparecimento"


def test_sem_historico_retorna_lista_vazia():
    v = [10, 10, 8, 8, 6, 6, 30, 2, 40, 3]
    assert analisar_consistencia_historica(v, []) == []


def test_desaparecimento_pequeno_sem_flag():
    ant = [10, 10, 8, 8, 6, 6, 30, 2, 40, 3]  # fêmeas 0-4m só 10 (<30)
    atu = [0, 10, 8, 8, 6, 6, 30, 2, 40, 3]
    flags = analisar_consistencia_historica(atu, ant)
    erros = [f for f in flags if 'desaparecimento' in f['codigo']]
    assert not erros, "Não deve sinalizar desaparecimento de faixa pequena (<30 animais)"
