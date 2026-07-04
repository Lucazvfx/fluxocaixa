from app import app


def test_precos_live_inclui_bezerro_e_bezerra():
    client = app.test_client()
    r = client.get('/api/precos/live')
    assert r.status_code == 200
    data = r.get_json()
    assert data['ok'] is True
    p = data['precos']
    assert 'bezerro' in p and p['bezerro'] > 0
    assert 'bezerra' in p and p['bezerra'] > 0
    # bezerra ≈ bezerro × 0,90 quando derivada
    assert p['bezerra'] <= p['bezerro']
