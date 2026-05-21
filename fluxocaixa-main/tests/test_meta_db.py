"""
Testes da KV de metadados (database.get_meta / set_meta / incr_meta).
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


def test_get_meta_default_quando_chave_inexistente():
    db, path = _fresh_db_module()
    try:
        assert db.get_meta('nao_existe') == '0'
        assert db.get_meta('nao_existe', default='42') == '42'
    finally:
        os.unlink(path)


def test_set_e_get_meta_roundtrip():
    db, path = _fresh_db_module()
    try:
        db.set_meta('contador', 7)
        assert db.get_meta('contador') == '7'
        db.set_meta('contador', 99)
        assert db.get_meta('contador') == '99'
    finally:
        os.unlink(path)


def test_incr_meta_a_partir_de_zero():
    db, path = _fresh_db_module()
    try:
        assert db.incr_meta('c1') == 1
        assert db.incr_meta('c1') == 2
        assert db.incr_meta('c1') == 3
    finally:
        os.unlink(path)


def test_incr_meta_com_delta_customizado():
    db, path = _fresh_db_module()
    try:
        assert db.incr_meta('c2', 5) == 5
        assert db.incr_meta('c2', 3) == 8
        assert db.incr_meta('c2', -2) == 6
    finally:
        os.unlink(path)


def test_reset_meta_zera_contador():
    db, path = _fresh_db_module()
    try:
        db.incr_meta('c3', 10)
        assert db.get_meta('c3') == '10'
        db.reset_meta('c3')
        assert db.get_meta('c3') == '0'
        # depois de reset o incr volta a contar do zero
        assert db.incr_meta('c3') == 1
    finally:
        os.unlink(path)


def test_meta_chaves_sao_independentes():
    db, path = _fresh_db_module()
    try:
        db.incr_meta('a', 5)
        db.incr_meta('b', 7)
        assert db.get_meta('a') == '5'
        assert db.get_meta('b') == '7'
    finally:
        os.unlink(path)
