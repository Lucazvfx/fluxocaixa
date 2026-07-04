"""Testa a whitelist de e-mails de acesso."""
import importlib
import os


def _recarregar_app(valor_env):
    if valor_env is None:
        os.environ.pop('EMAILS_PERMITIDOS', None)
    else:
        os.environ['EMAILS_PERMITIDOS'] = valor_env
    import app
    return importlib.reload(app)


def test_whitelist_vazia_acesso_aberto():
    app = _recarregar_app(None)
    assert app.email_permitido('qualquer@x.com') is True


def test_whitelist_bloqueia_nao_listado():
    app = _recarregar_app('dono@fazenda.com, analista@banco.com')
    assert app.email_permitido('dono@fazenda.com') is True
    assert app.email_permitido('estranho@x.com') is False


def test_whitelist_ignora_caixa_e_espaco():
    app = _recarregar_app('  Dono@Fazenda.com ')
    assert app.email_permitido('DONO@fazenda.COM') is True
