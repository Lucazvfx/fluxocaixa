"""
Testes que confirmam que /api/classificar agora calcula benchmarks
a partir dos indicadores reais informados pelo usuário (e não de
placeholders fixos como antes).
"""
import sys
import os
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from app import app, limiter
import database as db


@pytest.fixture
def client_logado():
    """Cliente autenticado: registra usuário e faz login."""
    app.config['TESTING'] = True
    limiter.reset()
    with app.test_client() as c:
        # Pega token CSRF e registra
        page = c.get('/register')
        import re
        m = re.search(rb'name="csrf_token"\s+value="([^"]+)"', page.data)
        token = m.group(1).decode() if m else ''
        # Email único pra evitar colisão entre runs
        import uuid
        email = f'bench_{uuid.uuid4().hex[:8]}@t.com'
        c.post('/register', data={
            'csrf_token': token,
            'nome': 'Bench Tester',
            'email': email,
            'senha': 'abc12345',
            'security_question': 'Q?',
            'security_answer': 'a',
        })
        yield c


def _classifica(client, payload):
    r = client.post('/api/classificar', json=payload)
    return r


def test_benchmarks_recebe_indicadores_reais_do_usuario(client_logado):
    """Quando o usuário envia mortalidade=8 (alta), o benchmark deve
    refletir esse valor — não mais o placeholder fixo de 3.0."""
    r = _classifica(client_logado, {
        'valores': [300, 280, 200, 80, 100, 40, 150, 10, 600, 15],
        'taxa_natalidade': 0.70,
        'mortalidade_pct': 8.0,
        'desmama_pct': 65.0,
        'rend_carcaca_pct': 49.0,
        'ganho_peso_kg_dia': 0.4,
    })
    assert r.status_code == 200, f'erro inesperado: {r.status_code} {r.data}'
    body = r.get_json()
    ind_bench = body.get('indicadores_benchmark', {})
    assert ind_bench['mortalidade'] == 8.0
    assert ind_bench['desmama'] == 65.0
    assert ind_bench['rend_carcaca'] == 49.0
    assert ind_bench['ganho_peso_arr'] == 0.4
    assert ind_bench['natalidade'] == 70.0  # taxa_natalidade=0.70 -> 70%


def test_benchmarks_usa_default_quando_campo_omitido(client_logado):
    """Sem campos opcionais o sistema usa defaults regionais razoáveis."""
    r = _classifica(client_logado, {
        'valores': [300, 280, 200, 80, 100, 40, 150, 10, 600, 15],
    })
    assert r.status_code == 200
    body = r.get_json()
    ind_bench = body['indicadores_benchmark']
    # Defaults atuais (média Rondônia)
    assert ind_bench['mortalidade'] == 5.0
    assert ind_bench['desmama'] == 72.0
    assert ind_bench['rend_carcaca'] == 52.0
    assert ind_bench['ganho_peso_arr'] == 0.55


def test_benchmark_mortalidade_alta_classifica_como_abaixo(client_logado):
    """Se o usuário informa mortalidade=10% (acima do limite 7),
    a faixa do benchmark de mortalidade deve ser 'abaixo'."""
    r = _classifica(client_logado, {
        'valores': [300, 280, 200, 80, 100, 40, 150, 10, 600, 15],
        'mortalidade_pct': 10.0,
    })
    assert r.status_code == 200
    body = r.get_json()
    bench = body['benchmarks']
    mort = next((b for b in bench if b['key'] == 'mortalidade'), None)
    assert mort is not None
    assert mort['valor'] == 10.0
    assert mort['faixa'] == 'abaixo'


def test_benchmark_desmama_excelente_quando_acima_de_80(client_logado):
    r = _classifica(client_logado, {
        'valores': [300, 280, 200, 80, 100, 40, 150, 10, 600, 15],
        'desmama_pct': 85.0,
    })
    body = r.get_json()
    bench = body['benchmarks']
    desm = next((b for b in bench if b['key'] == 'desmama'), None)
    assert desm is not None
    assert desm['valor'] == 85.0
    assert desm['faixa'] == 'excelente'


def test_benchmark_aceita_string_numerica(client_logado):
    """Front pode mandar números como string (typical form data)."""
    r = _classifica(client_logado, {
        'valores': [300, 280, 200, 80, 100, 40, 150, 10, 600, 15],
        'mortalidade_pct': '4.5',
        'desmama_pct': '78',
    })
    body = r.get_json()
    ind_bench = body['indicadores_benchmark']
    assert ind_bench['mortalidade'] == 4.5
    assert ind_bench['desmama'] == 78.0


def test_benchmark_ignora_string_invalida_e_usa_default(client_logado):
    r = _classifica(client_logado, {
        'valores': [300, 280, 200, 80, 100, 40, 150, 10, 600, 15],
        'mortalidade_pct': 'abc',
    })
    body = r.get_json()
    ind_bench = body['indicadores_benchmark']
    # default 5.0 quando a string não puder ser convertida
    assert ind_bench['mortalidade'] == 5.0
