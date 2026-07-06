import database as db
from app import app
from tests.test_parecer_pdf import PARECER_COMPLETO


def _login_client():
    db.init_db()
    email = 'pdfendpoint@example.com'
    u = db.buscar_usuario_email(email)
    if not u:
        db.criar_usuario(email, 'PDF Endpoint', 'senha123')
        u = db.buscar_usuario_email(email)
    client = app.test_client()
    with client.session_transaction() as s:
        s['_user_id'] = str(u['id'])
    return client


def test_parecer_pdf_devolve_pdf():
    client = _login_client()
    r = client.post('/api/parecer/pdf', json={'parecer': PARECER_COMPLETO})
    assert r.status_code == 200
    assert r.mimetype == 'application/pdf'
    assert r.data.startswith(b'%PDF')


def test_parecer_pdf_sem_parecer_retorna_400():
    client = _login_client()
    r = client.post('/api/parecer/pdf', json={})
    assert r.status_code == 400
