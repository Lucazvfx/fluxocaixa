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


def test_criar_e_listar_fazenda_via_endpoint():
    client, u = _login_client('EndpointEmpresa1')
    r = client.post('/api/fazendas', json={'nome': 'Fazenda Endpoint'})
    assert r.status_code == 200
    r2 = client.get('/api/fazendas')
    nomes = [f['nome'] for f in r2.get_json()['fazendas']]
    assert 'Fazenda Endpoint' in nomes


def test_pareceres_de_fazenda_de_outra_empresa_nao_vaza():
    client_a, u_a = _login_client('VazamentoA')
    client_a.post('/api/fazendas', json={'nome': 'Fazenda Vazamento'})
    fid = db.listar_fazendas(db.empresas_do_usuario(u_a['id'])[0]['id'])[0]['id']

    client_b, _ = _login_client('VazamentoB')  # empresa diferente
    r = client_b.get(f'/api/fazendas/{fid}/pareceres')
    assert r.status_code == 404
