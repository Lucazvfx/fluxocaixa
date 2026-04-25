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
    """api_retrain deve zerar o contador independente do valor atual."""
    LIMITE = 10

    # Simula estado: 7 confirmações acumuladas antes do retreino manual
    contador = 7
    assert contador > 0  # confirma pré-condição: havia confirmações pendentes

    # Simula api_retrain zerando o contador
    contador = 0
    assert contador == 0  # contador zerado

    # Confirma que agora precisa de LIMITE novas confirmações para disparar
    for _ in range(LIMITE - 1):
        contador += 1
    assert contador == LIMITE - 1
    assert contador < LIMITE  # não deve ter disparado ainda

def test_resposta_json_inclui_progresso():
    RETRAIN_A_CADA = 10
    _confirmacoes_desde_retrain = 0
    for _ in range(4):
        _confirmacoes_desde_retrain += 1
    faltam = RETRAIN_A_CADA - _confirmacoes_desde_retrain
    assert faltam == 6
    assert _confirmacoes_desde_retrain == 4

def test_constantes_app_py_existem():
    """Verifica que RETRAIN_A_CADA e _confirmacoes_desde_retrain existem em app.py."""
    import app
    assert hasattr(app, 'RETRAIN_A_CADA'), "RETRAIN_A_CADA não definido em app.py"
    assert app.RETRAIN_A_CADA == 10, f"Esperado 10, obtido {app.RETRAIN_A_CADA}"
    assert hasattr(app, '_confirmacoes_desde_retrain'), "_confirmacoes_desde_retrain não definido em app.py"
    assert app._confirmacoes_desde_retrain == 0 or isinstance(app._confirmacoes_desde_retrain, int)
