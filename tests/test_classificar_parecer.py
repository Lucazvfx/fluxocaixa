import database as db
from app import app


def _login_client():
    db.init_db()
    email = 'd1test@example.com'
    u = db.buscar_usuario_email(email)
    if not u:
        db.criar_usuario(email, 'D1 Test', 'senha123')
        u = db.buscar_usuario_email(email)
    client = app.test_client()
    with client.session_transaction() as s:
        s['_user_id'] = str(u['id'])
    return client


def test_classificar_retorna_parecer_e_consistencia():
    client = _login_client()
    payload = {'valores': [10, 10, 8, 8, 6, 6, 30, 2, 40, 3],
               'preco': 320, 'custo_arroba': 57,
               'credito_valor': 100000, 'prazo_meses': 24, 'juros_aa': 0.10}
    r = client.post('/api/classificar', json=payload)
    assert r.status_code == 200, f'status {r.status_code}'
    data = r.get_json()
    assert 'consistencia' in data
    assert 'parecer' in data and 'conclusao' in data['parecer']


def test_classificar_custo_por_componentes_dirige_o_parecer():
    client = _login_client()
    payload = {'valores': [10, 10, 8, 8, 6, 6, 30, 2, 40, 3],
               'preco': 320,
               'custo_componentes': {
                   'insumos': 44.92, 'mao_obra': 18.10, 'administracao': 8.49,
                   'maquinas': 15.23, 'pastagem': 14.29, 'infraestrutura': 13.69,
                   'taxas_impostos': 3.66, 'outros': 0.76},
               'credito_valor': 100000, 'prazo_meses': 24, 'juros_aa': 0.10}
    r = client.post('/api/classificar', json=payload)
    assert r.status_code == 200, f'status {r.status_code}'
    data = r.get_json()
    cd = data.get('custo_desembolso')
    assert cd is not None
    assert abs(cd['desembolso_cab_mes'] - 119.14) < 0.01  # TOTAL ciclo completo média
    # custo derivado dos componentes, diferente do default fixo 57
    assert cd['custo_arroba'] > 0 and abs(cd['custo_arroba'] - 57) > 1
