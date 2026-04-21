import requests
import json

def test_classify():
    url = "http://localhost:5050/api/classificar"
    # Simulando um rebanho de ciclo completo (10 categorias)
    body = {
        "valores": [300, 280, 400, 200, 900, 1200, 250, 80, 600, 40],
        "fazenda": "Teste Automático",
        "municipio": "Sinop - MT",
        "proprietario": "Lucas"
    }
    try:
        # Precisamos estar logados? O endpoint /api/classificar geralmente exige login.
        # Vamos tentar sem login primeiro, se falhar, tentamos logar.
        print(f"Testando {url}...")
        res = requests.post(url, json=body)
        print(f"Status: {res.status_code}")
        print(f"Response: {res.text[:500]}...")
    except Exception as e:
        print(f"Erro: {e}")

if __name__ == "__main__":
    test_classify()
