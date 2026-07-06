import database as db
import uuid

def test_criar_usuario_ganha_empresa_pessoal():
    db.init_db()
    # Use a unique email to avoid conflicts with existing data
    unique_email = f'signup-{uuid.uuid4().hex[:8]}@example.com'
    uid = db.criar_usuario(unique_email, 'Novo Usuario', 'senha123')
    empresas = db.empresas_do_usuario(uid)
    assert len(empresas) == 1
    assert 'Novo Usuario' in empresas[0]['nome']
