import uuid
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import database as db


def test_migracao_cria_empresa_para_usuario_pre_existente():
    db.init_db()
    ph = db._PH
    # Simula um usuário "antigo": insert direto, sem passar por criar_usuario
    # (que já cria empresa) para reproduzir o estado pré-feature.
    uid = db._exec(
        f'INSERT INTO usuarios (email, nome, senha_hash) VALUES ({ph},{ph},{ph})',
        (f'usuarioantigo-{uuid.uuid4().hex[:8]}@example.com', 'Usuario Antigo', 'hash-fake'),
        fetch='lastrow', commit=True)
    assert not db.empresas_do_usuario(uid)  # ainda sem empresa

    db._migrar_usuarios_para_empresas()

    empresas = db.empresas_do_usuario(uid)
    assert len(empresas) == 1


def test_migracao_e_idempotente():
    db.init_db()
    ph = db._PH
    uid = db._exec(
        f'INSERT INTO usuarios (email, nome, senha_hash) VALUES ({ph},{ph},{ph})',
        (f'usuarioidempotente-{uuid.uuid4().hex[:8]}@example.com', 'Idempotente', 'hash-fake'),
        fetch='lastrow', commit=True)
    db._migrar_usuarios_para_empresas()
    db._migrar_usuarios_para_empresas()  # roda de novo
    assert len(db.empresas_do_usuario(uid)) == 1  # não duplicou


def test_migracao_herda_marca_e_realoca_fazendas():
    db.init_db()
    ph = db._PH
    uid = db._exec(
        f'''INSERT INTO usuarios (email, nome, senha_hash, nome_consultoria, logo_base64)
            VALUES ({ph},{ph},{ph},{ph},{ph})''',
        (f'usuariomarca-{uuid.uuid4().hex[:8]}@example.com', 'Com Marca', 'hash-fake', 'Marca XYZ', 'YWJj'),
        fetch='lastrow', commit=True)
    fid = db._exec(
        f'INSERT INTO fazendas (user_id, nome) VALUES ({ph},{ph})',
        (uid, 'Fazenda Antiga'), fetch='lastrow', commit=True)

    db._migrar_usuarios_para_empresas()

    empresas = db.empresas_do_usuario(uid)
    assert empresas[0]['nome'] == 'Marca XYZ'
    assert empresas[0]['logo_base64'] == 'YWJj'
    f = db._exec(f'SELECT empresa_id FROM fazendas WHERE id={ph}', (fid,), fetch='one')
    assert f['empresa_id'] == empresas[0]['id']
