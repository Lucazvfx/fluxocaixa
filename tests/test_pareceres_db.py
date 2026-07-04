import json
import database as db


def test_salvar_e_listar_parecer():
    db.init_db()
    fid = db.criar_fazenda('Faz Teste', user_id=1)
    pid = db.salvar_parecer(user_id=1, fazenda_id=fid,
                            solicitacao={'credito_valor': 100000},
                            parecer={'conclusao': {'recomendacao': 'aprovar', 'dscr': 1.4}})
    assert pid
    itens = db.listar_pareceres(fazenda_id=fid, user_id=1)
    assert itens and itens[0]['recomendacao'] == 'aprovar'
    assert json.loads(itens[0]['solicitacao'])['credito_valor'] == 100000
