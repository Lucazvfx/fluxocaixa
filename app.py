"""
BoviML — Servidor Flask
"""
from flask import Flask, request, jsonify, render_template
import os, re, tempfile, subprocess
from ml_engine import (
    treinar_modelo, classificar, calcular_indicadores,
    simular_cenario, CENARIOS
)

app = Flask(__name__)

print("🧠 Treinando modelo ML...")
stats = treinar_modelo()
print(f"✅ Modelo treinado | Acurácia CV: {stats['accuracy_mean']*100:.1f}% ± {stats['accuracy_std']*100:.1f}% | Features: {stats['n_features']} | Amostras: {stats['n_samples']}")


@app.route('/')
def index():
    return render_template('index.html', model_stats=stats, cenarios=CENARIOS)


@app.route('/api/classificar', methods=['POST'])
def api_classificar():
    data = request.json
    v = data.get('valores', [])
    if len(v) != 10 or sum(v) < 10:
        return jsonify({'erro': 'Envie 10 valores (fêmeas e machos por faixa) com total >= 10'}), 400

    # Variáveis de fluxo opcionais
    kwargs = {}
    if 'taxa_natalidade' in data:
        kwargs['taxa_natalidade'] = float(data['taxa_natalidade'])
    if 'bois_vendidos' in data:
        kwargs['bois_vendidos'] = float(data['bois_vendidos'])
    if 'bezerros_vendidos' in data:
        kwargs['bezerros_vendidos'] = float(data['bezerros_vendidos'])

    result = classificar(v, **kwargs)
    ind    = calcular_indicadores(v)
    return jsonify({**result, 'indicadores': ind, 'valores': v})


@app.route('/api/cenario', methods=['POST'])
def api_cenario():
    data    = request.json
    v       = data.get('valores', [])
    cenario = data.get('cenario', 'crescimento')
    params  = {
        'nat_pct':       float(data.get('nat',      75)),
        'mort_pct':      float(data.get('mort',      3)),
        'desc_pct':      float(data.get('desc',     30)),
        'preco_arroba':  float(data.get('preco',   320)),
        'custo_cab_ano': float(data.get('custo',   850)),
        'peso_arroba':   float(data.get('peso',     16)),
        'prop_boi':      float(data.get('propboi',  30)),
        'renov_boi_pct': float(data.get('renovboi', 20)),
        'venda_bez_pct': float(data.get('vendbez',  30)),
    }
    if len(v) != 10:
        return jsonify({'erro': 'Valores inválidos'}), 400
    result = simular_cenario(v, cenario, **params)
    return jsonify(result)


@app.route('/api/cenarios', methods=['GET'])
def api_cenarios():
    return jsonify({k: {'nome': v['nome'], 'desc': v['desc'], 'emoji': v['emoji']}
                    for k, v in CENARIOS.items()})


@app.route('/api/ler-pdf', methods=['POST'])
def api_ler_pdf():
    if 'pdf' not in request.files:
        return jsonify({'erro': 'Nenhum arquivo enviado'}), 400
    f = request.files['pdf']
    if not f.filename.lower().endswith('.pdf'):
        return jsonify({'erro': 'Apenas arquivos PDF são aceitos'}), 400
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
        f.save(tmp.name)
        try:
            text  = extrair_texto_pdf(tmp.name)
            orig  = detectar_origem(text)
            dados = parsear_idaron(text) if orig == 'IDARON' else parsear_indea(text)
            dados['origem'] = orig
            return jsonify(dados)
        except Exception as e:
            return jsonify({'erro': str(e)}), 500
        finally:
            os.unlink(tmp.name)


@app.route('/api/modelo-info', methods=['GET'])
def api_modelo_info():
    return jsonify(stats)


# ─────────────────────────────────────────────
# EXTRAÇÃO DE TEXTO
# ─────────────────────────────────────────────
def extrair_texto_pdf(path: str) -> str:
    try:
        result = subprocess.run(
            ['pdftotext', '-layout', path, '-'],
            capture_output=True, text=True
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
    except FileNotFoundError:
        pass  # pdftotext não instalado — usa pdfplumber

    try:
        import pdfplumber
        text = ''
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text += (page.extract_text() or '') + '\n'
        return text
    except Exception as e:
        raise RuntimeError(f'Não foi possível extrair texto do PDF: {e}')


# ─────────────────────────────────────────────
# DETECÇÃO DE ORIGEM
# ─────────────────────────────────────────────
def detectar_origem(text: str) -> str:
    up = text.upper()
    if ('IDARON' in up
            or 'AGÊNCIA DE DEFESA SANITÁRIA AGROSILVOPASTORIL' in up
            or 'AGENCIA DE DEFESA SANITARIA AGROSILVOPASTORIL' in up
            or ('RONDÔNIA' in up and ('SALDO' in up or 'REBANHO' in up or 'GTA' in up))):
        return 'IDARON'
    if ('INDEA' in up
            or 'INSTITUTO DE DEFESA AGROPECUÁRIA' in up
            or 'INSTITUTO DE DEFESA AGROPECUARIA' in up
            or 'SALDO ATUAL DA EXPLORAÇÃO' in up
            or 'SALDO ATUAL DA EXPLORACAO' in up):
        return 'INDEA'
    return 'GENERICO'


# ─────────────────────────────────────────────
# HELPERS COMUNS
# ─────────────────────────────────────────────
def _animais_vazios() -> dict:
    return {
        'f00_F': 0, 'f00_M': 0, 'f05_F': 0, 'f05_M': 0,
        'f13_F': 0, 'f13_M': 0, 'f25_F': 0, 'f25_M': 0,
        'fac_F': 0, 'fac_M': 0,
    }


def _para_valores(animais: dict) -> list:
    return [
        animais['f00_F'], animais['f00_M'],
        animais['f05_F'], animais['f05_M'],
        animais['f13_F'], animais['f13_M'],
        animais['f25_F'], animais['f25_M'],
        animais['fac_F'], animais['fac_M'],
    ]


def _sexo_da_linha(up: str):
    if 'FEMEA' in up or 'FÊMEA' in up:
        return 'F'
    if 'MACHO' in up:
        return 'M'
    return None


# ─────────────────────────────────────────────
# PARSER INDEA-MT
# ─────────────────────────────────────────────
def parsear_indea(text: str) -> dict:
    animais = _animais_vazios()
    fazenda = municipio = proprietario = cpf = data_saldo = ''

    m = re.search(r'PROPRIEDADE[:\s]+[\d\-]+\s*[-–]\s*(.+)', text)
    if m:
        fazenda = m.group(1).strip()[:60]

    m = re.search(r'MUNIC[IÍ]PIO[:\s]+([A-ZÁÉÍÓÚÂÊÎÔÛÃÕÇ\s\-]+?)(?:\s{3,}|SIT\.)', text, re.I)
    if m:
        municipio = m.group(1).strip()

    m = re.search(r'(\d{11})\s+([A-ZÁÉÍÓÚÂÊÎÔÛÃÕÇ\s]+?)(?:\s{3,}|\n)', text, re.I)
    if m:
        cpf, proprietario = m.group(1), m.group(2).strip()

    m = re.search(r'(\d{2}/\d{2}/\d{4})', text)
    if m:
        data_saldo = m.group(1)

    for line in text.split('\n'):
        up = line.upper()
        if 'BOVINO' not in up:
            continue
        m_qtd = re.search(r'(\d{2,6})\s*$', line.strip())
        if not m_qtd:
            continue
        qtd = int(m_qtd.group(1))
        if qtd <= 0 or qtd > 500_000:
            continue
        sexo = _sexo_da_linha(up)
        if not sexo:
            continue
        if   '00 A 04' in up or '0 A 04' in up or '0 A 4' in up: faixa = 'f00'
        elif '05 A 12' in up or '5 A 12' in up:                   faixa = 'f05'
        elif '13 A 24' in up:                                      faixa = 'f13'
        elif '25 A 36' in up:                                      faixa = 'f25'
        elif 'ACIMA'   in up:                                      faixa = 'fac'
        else:
            continue
        animais[f'{faixa}_{sexo}'] = qtd

    valores = _para_valores(animais)
    return {
        'fazenda': fazenda, 'municipio': municipio,
        'proprietario': proprietario, 'cpf': cpf,
        'data_saldo': data_saldo, 'total': sum(valores),
        'animais': animais, 'valores': valores,
    }


# ─────────────────────────────────────────────
# PARSER IDARON-RO
# Suporta:
#  • Faixas numéricas (0-12, 0-6, 7-12, 13-24, 25-36, acima)
#  • Categorias zootécnicas (bezerra/o, garrota/e, novilha/o, vaca, touro/boi)
#  • IE (Inscrição Estadual RO) no lugar do código de exploração
# Quando a faixa 0-12 vem combinada, divide 50/50 entre f00 e f05.
# ─────────────────────────────────────────────
def parsear_idaron(text: str) -> dict:
    animais = _animais_vazios()
    fazenda = municipio = proprietario = cpf = data_saldo = ie = ''

    # IE (Inscrição Estadual)
    m = re.search(r'\bI\.?E\.?\b[:\s]+([A-Z0-9\.\-\/]+)', text, re.I)
    if m:
        ie = m.group(1).strip()

    # Nome da propriedade — padrões do mais específico ao mais genérico
    for pat in [
        r'NOME\s+DA\s+PROPRIEDADE[:\s]+(.+)',
        r'ESTABELECIMENTO[:\s]+(.+)',
        r'(?m)^\s*PROPRIEDADE\s*:\s*(.+)',   # PROPRIEDADE: no início da linha
        r'FAZENDA[:\s]+([A-ZÁÉÍÓÚÂÊÎÔÛÃÕÇ0-9\s\.\-]+)',
    ]:
        m = re.search(pat, text, re.I)
        if m:
            fazenda = m.group(1).strip()[:60]
            break

    # Município — termina em /RO ou antes de espaços/newline
    m = re.search(
        r'MUNIC[IÍ]PIO[:\s]+([A-ZÁÉÍÓÚÂÊÎÔÛÃÕÇ\s\-]+?(?:/\s*RO)?)(?:\s{2,}|\n|$)',
        text, re.I
    )
    if m:
        municipio = m.group(1).strip()

    # CPF — com ou sem pontuação, seguido do nome
    m = re.search(
        r'(?:CPF|PRODUTOR)[:\s/]*'
        r'(\d{3}\.?\d{3}\.?\d{3}[\-\.]?\d{2})'
        r'[:\s/]*([A-ZÁÉÍÓÚÂÊÎÔÛÃÕÇ][A-ZÁÉÍÓÚÂÊÎÔÛÃÕÇ\s]+?)(?:\s{2,}|\n)',
        text, re.I
    )
    if not m:
        # INDEA-style: 11 dígitos seguidos do nome
        m = re.search(r'(\d{11})\s+([A-ZÁÉÍÓÚÂÊÎÔÛÃÕÇ\s]+?)(?:\s{3,}|\n)', text, re.I)
    if m:
        cpf = re.sub(r'[^\d]', '', m.group(1))
        proprietario = m.group(2).strip()

    m = re.search(r'(\d{2}/\d{2}/\d{4})', text)
    if m:
        data_saldo = m.group(1)

    # ── Animais por faixa etária numérica ────────────────────────────────
    for line in text.split('\n'):
        up = line.upper()
        if 'BOVINO' not in up:
            continue
        m_qtd = re.search(r'(\d{2,6})\s*$', line.strip())
        if not m_qtd:
            continue
        qtd = int(m_qtd.group(1))
        if qtd <= 0 or qtd > 500_000:
            continue
        sexo = _sexo_da_linha(up)
        if not sexo:
            continue

        # 0-12 combinado (IDARON): distribui 50 % f00 + 50 % f05
        if re.search(r'0\s*A\s*12', up) or 'ATÉ 12' in up or 'ATE 12' in up:
            metade = qtd // 2
            animais[f'f00_{sexo}'] += metade
            animais[f'f05_{sexo}'] += qtd - metade
        # 0-6 meses (algumas versões IDARON)
        elif re.search(r'0\s*A\s*0?6', up) or re.search(r'ATÉ\s*6', up, re.I):
            animais[f'f00_{sexo}'] += qtd
        # 7-12 meses
        elif re.search(r'0?7\s*A\s*12', up):
            animais[f'f05_{sexo}'] += qtd
        # Faixas padrão compartilhadas com INDEA
        elif re.search(r'0?0\s*A\s*0?4', up):
            animais[f'f00_{sexo}'] = qtd
        elif re.search(r'0?5\s*A\s*12', up):
            animais[f'f05_{sexo}'] = qtd
        elif '13 A 24' in up:
            animais[f'f13_{sexo}'] = qtd
        elif '25 A 36' in up:
            animais[f'f25_{sexo}'] = qtd
        elif 'ACIMA' in up:
            animais[f'fac_{sexo}'] = qtd

    # ── Animais por categoria zootécnica (sem faixa numérica) ────────────
    # Usado quando o documento lista BEZERRA, NOVILHA, VACA, etc.
    _categorias = [
        (['BEZERRA', 'BEZERRO'],       'f05', None),   # 0-12 → f05
        (['GARROTA', 'GARROTE'],       'f13', None),   # 13-24
        (['NOVILHA', 'NOVILHO'],       'f25', None),   # 25-36
        (['VACA'],                     'fac', 'F'),
        (['TOURO', 'BOI', 'BOIS'],     'fac', 'M'),
    ]
    for line in text.split('\n'):
        up = line.upper()
        if 'BOVINO' not in up:
            continue
        m_qtd = re.search(r'(\d{2,6})\s*$', line.strip())
        if not m_qtd:
            continue
        qtd = int(m_qtd.group(1))
        if qtd <= 0 or qtd > 500_000:
            continue
        for palavras, faixa, sexo_fixo in _categorias:
            if any(p in up for p in palavras):
                sexo = sexo_fixo or _sexo_da_linha(up)
                if sexo:
                    # Só sobrescreve se ainda zero (faixa numérica tem prioridade)
                    if animais[f'{faixa}_{sexo}'] == 0:
                        animais[f'{faixa}_{sexo}'] = qtd
                break

    valores = _para_valores(animais)
    return {
        'fazenda': fazenda, 'municipio': municipio,
        'proprietario': proprietario, 'cpf': cpf, 'ie': ie,
        'data_saldo': data_saldo, 'total': sum(valores),
        'animais': animais, 'valores': valores,
    }


if __name__ == '__main__':
    print("Fluxo de caixa rodando em http://localhost:5050")
    app.run(debug=True, port=5050)
