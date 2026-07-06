import uuid

import database as db
from app import app


def _login_client(nome):
    db.init_db()
    email = f'{nome}-{uuid.uuid4().hex[:8]}@example.com'
    db.criar_usuario(email, nome, 'senha123')
    u = db.buscar_usuario_email(email)
    client = app.test_client()
    with client.session_transaction() as s:
        s['_user_id'] = str(u['id'])
    return client, u


def test_get_empresa_ativa_lista_e_marca_a_ativa():
    client, u = _login_client('EmpresaAtiva1')
    r = client.get('/api/empresa/ativa')
    assert r.status_code == 200
    d = r.get_json()
    assert len(d['empresas']) >= 1
    assert d['ativa_id'] == d['empresas'][0]['id']


def test_post_empresa_ativa_com_empresa_valida():
    client, u = _login_client('EmpresaAtiva2')
    empresas = db.empresas_do_usuario(u['id'])
    r = client.post('/api/empresa/ativa', json={'empresa_id': empresas[0]['id']})
    assert r.status_code == 200
    assert r.get_json()['ok'] is True


def test_post_empresa_ativa_com_empresa_de_outro_usuario_403():
    client, u = _login_client('EmpresaAtiva3')
    _, outra = _login_client('EmpresaAtiva4')
    empresa_de_outro = db.empresas_do_usuario(outra['id'])[0]['id']
    r = client.post('/api/empresa/ativa', json={'empresa_id': empresa_de_outro})
    assert r.status_code == 403
