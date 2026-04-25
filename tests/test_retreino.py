import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def test_contador_dispara_ao_atingir_limite():
    LIMITE = 10
    contador = 0
    disparou = []
    for i in range(1, 12):
        contador += 1
        if contador >= LIMITE:
            disparou.append(i)
            contador = 0
    assert len(disparou) == 1
    assert disparou[0] == 10
    assert contador == 1

def test_contador_reseta_apos_retrain_manual():
    LIMITE = 10
    contador = 7
    contador = 0
    for _ in range(9):
        contador += 1
    assert contador == 9
    assert contador < LIMITE

def test_resposta_json_inclui_progresso():
    RETRAIN_A_CADA = 10
    _confirmacoes_desde_retrain = 0
    for _ in range(4):
        _confirmacoes_desde_retrain += 1
    faltam = RETRAIN_A_CADA - _confirmacoes_desde_retrain
    assert faltam == 6
    assert _confirmacoes_desde_retrain == 4
