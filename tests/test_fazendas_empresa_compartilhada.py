import database as db
import uuid

def _empresa_de(nome_base):
    email = f'{nome_base}-{uuid.uuid4().hex[:8]}@example.com'
    uid = db.criar_usuario(email, nome_base, 'senha123')
    empresas = db.empresas_do_usuario(uid)
    return uid, empresas[0]['id']

def test_dois_usuarios_mesma_empresa_compartilham_fazenda():
    db.init_db()
    uid_a, eid = _empresa_de('Analista A')
    uid_b, _ = _empresa_de('Analista B')
    # Vincula B na mesma empresa de A (simula admin vinculando)
    ph = db._PH
    db._exec(f'INSERT INTO empresa_membros (empresa_id, user_id) VALUES ({ph},{ph})',
             (eid, uid_b), commit=True)

    fid = db.criar_fazenda('Fazenda Compartilhada', empresa_id=eid, criado_por=uid_a)

    # B vê a fazenda de A porque estão na mesma empresa
    fazendas_de_b = db.listar_fazendas(eid)
    assert any(f['id'] == fid for f in fazendas_de_b)
    assert db.buscar_fazenda(fid, eid) is not None

def test_empresa_diferente_nao_ve_a_fazenda():
    db.init_db()
    uid_a, eid_a = _empresa_de('Isolado A')
    uid_c, eid_c = _empresa_de('Isolado C')
    fid = db.criar_fazenda('Fazenda Isolada A', empresa_id=eid_a, criado_por=uid_a)

    assert db.buscar_fazenda(fid, eid_c) is None
    assert not any(f['id'] == fid for f in db.listar_fazendas(eid_c))

def test_historico_e_pareceres_sem_filtro_de_usuario():
    db.init_db()
    uid_a, eid = _empresa_de('Historico A')
    fid = db.criar_fazenda('Fazenda Historico', empresa_id=eid, criado_por=uid_a)
    db.salvar_parecer(uid_a, fid, {'credito_valor': 1000},
                      {'conclusao': {'recomendacao': 'aprovar', 'dscr': 2.0}})
    # historico_fazenda/listar_pareceres não recebem mais user_id
    hist = db.historico_fazenda(fid)
    pareceres = db.listar_pareceres(fid)
    assert isinstance(hist, list)
    assert len(pareceres) == 1

def test_excluir_fazenda_exige_empresa_correta():
    db.init_db()
    uid_a, eid_a = _empresa_de('Excluir A')
    _, eid_c = _empresa_de('Excluir C')
    fid = db.criar_fazenda('Fazenda a Excluir', empresa_id=eid_a, criado_por=uid_a)

    assert db.excluir_fazenda(fid, eid_c) is False  # empresa errada não apaga
    assert db.buscar_fazenda(fid, eid_a) is not None  # continua existindo
    assert db.excluir_fazenda(fid, eid_a) is True
    assert db.buscar_fazenda(fid, eid_a) is None
