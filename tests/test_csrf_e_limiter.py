"""
Testes da proteção CSRF e do rate-limit nos forms públicos.
"""
import sys
import os
import re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from app import app, limiter


@pytest.fixture
def client():
    app.config['TESTING'] = True
    # Reseta o storage do limiter entre testes pra evitar acumular contagens
    limiter.reset()
    with app.test_client() as c:
        yield c


def _csrf_token_da_pagina(html: str) -> str:
    m = re.search(r'name="csrf_token"\s+value="([^"]+)"', html)
    assert m, 'csrf_token não encontrado na página'
    return m.group(1)


# ─────────────────────────────────────────────
# CSRF
# ─────────────────────────────────────────────
def test_login_get_renderiza_csrf_token(client):
    r = client.get('/login')
    assert r.status_code == 200
    assert b'csrf_token' in r.data


def test_register_get_renderiza_csrf_token(client):
    r = client.get('/register')
    assert r.status_code == 200
    assert b'csrf_token' in r.data


def test_esqueci_senha_get_renderiza_csrf_token(client):
    r = client.get('/esqueci-senha')
    assert r.status_code == 200
    assert b'csrf_token' in r.data


def test_login_post_sem_token_eh_rejeitado(client):
    r = client.post('/login', data={'email': 'x@y.com', 'senha': 'abc123'})
    # Sem token CSRF → 400 (ou 403 dependendo da versão do flask-wtf)
    assert r.status_code in (400, 403)


def test_register_post_sem_token_eh_rejeitado(client):
    r = client.post('/register', data={
        'nome': 'X', 'email': 'a@b.com', 'senha': 'abc123',
        'security_question': 'Q?', 'security_answer': 'a',
    })
    assert r.status_code in (400, 403)


def test_api_post_nao_exige_csrf(client):
    """Rotas /api/* são JSON e ficam isentas de CSRF (sessão SameSite=Lax)."""
    # Sem login dá 401/302; mas o importante é NÃO retornar 400/403 por CSRF
    r = client.post('/api/classificar', json={'valores': [1] * 10})
    assert r.status_code not in (400, 403)


# ─────────────────────────────────────────────
# RATE LIMITING
# ─────────────────────────────────────────────
def test_login_rate_limit_dispara_apos_excesso(client):
    # /login: 10 por minuto
    last = None
    for _ in range(11):
        last = client.post('/login', data={'email': 'x@y.com', 'senha': 'z'})
    assert last.status_code == 429, \
        f'Esperado 429 após 11 tentativas, obtido {last.status_code}'


def test_register_rate_limit_dispara_apos_excesso(client):
    # /register: 5 por minuto
    last = None
    for _ in range(6):
        last = client.post('/register', data={
            'nome': 'X', 'email': 'a@b.com', 'senha': '123456',
            'security_question': 'Q?', 'security_answer': 'a',
        })
    assert last.status_code == 429, \
        f'Esperado 429 após 6 tentativas, obtido {last.status_code}'


def test_get_login_nao_eh_rate_limitado(client):
    """O limit é só para POST. GET pode ser chamado livremente."""
    for _ in range(20):
        r = client.get('/login')
        assert r.status_code == 200
