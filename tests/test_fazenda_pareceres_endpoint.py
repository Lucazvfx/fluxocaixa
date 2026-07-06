import database as db
from app import app


def _login_client(email):
    db.init_db()
    u = db.buscar_usuario_email(email)
    if not u:
        db.criar_usuario(email, 'Fazenda Pareceres Test', 'senha123')
        u = db.buscar_usuario_email(email)
    client = app.test_client()
    with client.session_transaction() as s:
        s['_user_id'] = str(u['id'])
    return client, u


def test_fazenda_pareceres_lista_mais_recente_primeiro():
    client, u = _login_client('fazendapareceres@example.com')
    fid = db.criar_fazenda('Faz Pareceres Teste', user_id=u['id'])
    db.salvar_parecer(u['id'], fid, {'credito_valor': 100000},
                      {'conclusao': {'recomendacao': 'ressalva', 'dscr': 1.1}})
    db.salvar_parecer(u['id'], fid, {'credito_valor': 200000},
                      {'conclusao': {'recomendacao': 'aprovar', 'dscr': 1.5}})
    r = client.get(f'/api/fazendas/{fid}/pareceres')
    assert r.status_code == 200
    itens = r.get_json()['pareceres']
    assert len(itens) == 2
    assert itens[0]['recomendacao'] == 'aprovar'
