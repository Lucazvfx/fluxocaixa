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
