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
    return client


def test_empresa_perfil_post_e_get():
    client = _login_client('EmpresaPerfil1')
    r = client.post('/api/empresa/perfil', json={
        'nome_consultoria': 'Consultoria Empresa Teste', 'logo_base64': 'YWJj'})
    assert r.status_code == 200
    r2 = client.get('/api/empresa/perfil')
    d = r2.get_json()
    assert d['nome_consultoria'] == 'Consultoria Empresa Teste'
    assert d['logo_base64'] == 'YWJj'
