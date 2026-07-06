"""
Testes do schema de empresas (tabelas empresas, empresa_membros + coluna empresa_id em fazendas).
Usa SQLite em arquivo temporário para isolar do banco real.
"""
import sys
import os
import tempfile
import importlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def _fresh_db_module():
    """Recarrega o módulo database apontando para um arquivo SQLite temporário."""
    tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
    tmp.close()
    os.environ.pop('DATABASE_URL', None)  # garante backend SQLite
    if 'database' in sys.modules:
        del sys.modules['database']
    import database  # type: ignore
    database._DB_PATH = tmp.name
    database.init_db()
    return database, tmp.name


def test_tabelas_empresa_existem_apos_init_db():
    db, path = _fresh_db_module()
    try:
        # Deve aceitar insert/select sem erro de "no such table"
        eid = db._exec(f"INSERT INTO empresas (nome) VALUES ({db._PH})",
                       ('Teste Schema',), fetch='lastrow', commit=True)
        assert eid
        db._exec(f"INSERT INTO empresa_membros (empresa_id, user_id) VALUES ({db._PH},{db._PH})",
                 (eid, 1), commit=True)
        row = db._exec(f"SELECT empresa_id, user_id FROM empresa_membros WHERE empresa_id={db._PH}",
                       (eid,), fetch='one')
        assert row['empresa_id'] == eid
    finally:
        os.unlink(path)


def test_fazendas_tem_coluna_empresa_id():
    db, path = _fresh_db_module()
    try:
        # Não deve lançar erro de coluna inexistente
        db._exec(f"SELECT empresa_id FROM fazendas LIMIT 1", fetch='all')
    finally:
        os.unlink(path)
