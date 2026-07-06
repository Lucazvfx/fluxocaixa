import database as db
from app import app


def test_atualizar_perfil_consultoria_round_trip():
    db.init_db()
    email = 'perfilconsultoria@example.com'
    u = db.buscar_usuario_email(email)
    uid = u['id'] if u else db.criar_usuario(email, 'Perfil Test', 'senha123')
    db.atualizar_perfil_consultoria(uid, 'Consultoria Exemplo', 'YmFzZTY0Zm9v')
    u = db.buscar_usuario_id(uid)
    assert u['nome_consultoria'] == 'Consultoria Exemplo'
    assert u['logo_base64'] == 'YmFzZTY0Zm9v'


def _login_client(email):
    db.init_db()
    u = db.buscar_usuario_email(email)
    if not u:
        db.criar_usuario(email, 'Perfil Endpoint Test', 'senha123')
        u = db.buscar_usuario_email(email)
    client = app.test_client()
    with client.session_transaction() as s:
        s['_user_id'] = str(u['id'])
    return client


def test_perfil_consultoria_post_e_get():
    client = _login_client('perfilendpoint@example.com')
    r = client.post('/api/perfil-consultoria', json={
        'nome_consultoria': 'Consultoria Endpoint', 'logo_base64': 'YWJj'})
    assert r.status_code == 200
    assert r.get_json()['ok'] is True

    r2 = client.get('/api/perfil-consultoria')
    assert r2.status_code == 200
    d = r2.get_json()
    assert d['nome_consultoria'] == 'Consultoria Endpoint'
    assert d['logo_base64'] == 'YWJj'


def test_perfil_consultoria_get_sem_configuracao_devolve_vazio():
    client = _login_client('perfilvazio@example.com')
    r = client.get('/api/perfil-consultoria')
    assert r.status_code == 200
    d = r.get_json()
    assert d['nome_consultoria'] == ''
    assert d['logo_base64'] == ''
