import database as db


def test_cotacao_round_trip_com_bezerro_bezerra():
    db.init_db()
    db.guardar_cotacao_diaria({
        'boi': 330.0, 'vaca': 308.0, 'boi_china': 340.0,
        'bezerro': 3000.0, 'bezerra': 2700.0,
    })
    c = db.obter_cotacoes_atuais()
    assert c['boi'] == 330.0
    assert c['vaca'] == 308.0
    assert c['bezerro'] == 3000.0
    assert c['bezerra'] == 2700.0
