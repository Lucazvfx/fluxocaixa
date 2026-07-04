"""Testa o controle de acesso por administrador."""
import importlib
import os


def _recarregar_app(admin_env):
    if admin_env is None:
        os.environ.pop('ADMIN_EMAILS', None)
    else:
        os.environ['ADMIN_EMAILS'] = admin_env
    import app
    return importlib.reload(app)


def test_is_admin_reconhece_lista():
    app = _recarregar_app('dono@fazenda.com, gestor@banco.com')
    assert app.is_admin('dono@fazenda.com') is True
    assert app.is_admin('GESTOR@BANCO.COM') is True
    assert app.is_admin('estranho@x.com') is False


def test_is_admin_vazio_nega_todos():
    app = _recarregar_app(None)
    assert app.is_admin('qualquer@x.com') is False


def test_gerar_senha_tem_tamanho_e_e_unica():
    app = _recarregar_app('a@a.com')
    s1 = app.gerar_senha()
    s2 = app.gerar_senha()
    assert len(s1) == 10
    assert s1 != s2
    # sem caracteres ambíguos
    assert not (set(s1) & set('0O1lI'))
