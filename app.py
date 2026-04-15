"""
BoviML — Servidor Flask
"""
from flask import Flask, request, jsonify, render_template, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import os, re, tempfile, subprocess, threading
from ml_engine import (
    treinar_modelo, classificar, calcular_indicadores,
    simular_cenario, retrain_com_dados, carregar_modelo, CENARIOS
)
import database as db

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'boviml-dev-secret-2026')

# ── Flask-Login ──────────────────────────────────────────────────────────────
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Faça login para acessar o sistema.'

class User(UserMixin):
    def __init__(self, data: dict):
        self.id    = data['id']
        self.email = data['email']
        self.nome  = data['nome']
        self.plano = data.get('plano', 'free')

@login_manager.user_loader
def load_user(user_id):
    u = db.buscar_usuario_id(int(user_id))
    return User(u) if u else None

# ── Startup: carrega modelo do disco ou treina do zero ──────────────────────
_saved = carregar_modelo()
if _saved:
    stats = _saved
    print(f"✅ Modelo carregado do disco | Acurácia: {stats['accuracy_mean']*100:.1f}% | Amostras: {stats['n_samples']}")
else:
    print("🧠 Treinando modelo ML (primeira execução)...")
    stats = treinar_modelo()
    print(f"✅ Modelo treinado | Acurácia CV: {stats['accuracy_mean']*100:.1f}% ± {stats['accuracy_std']*100:.1f}% | Amostras: {stats['n_samples']}")

db.init_db()
print("🗃️  Banco SQLite inicializado.")

# ── Auto-retreino em background ──────────────────────────────────────────────
_retraining = False
_retrain_lock = threading.Lock()


def _auto_retrain():
    global stats, _retraining
    with _retrain_lock:
        _retraining = True
        try:
            X_extra, y_extra = db.exportar_treino()
            stats = retrain_com_dados(X_extra, y_extra)
            print(f"[ML] Auto-retreino concluído | Acurácia: {stats['accuracy_mean']*100:.1f}% | {stats['n_confirmados']} confirmados")
        except Exception as e:
            print(f"[ML] Erro no auto-retreino: {e}")
        finally:
            _retraining = False


# ── Auth routes ─────────────────────────────────────────────────────────────
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    erro = None
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        senha = request.form.get('senha', '')
        u = db.verificar_senha(email, senha)
        if u:
            login_user(User(u), remember=True)
            return redirect(url_for('index'))
        erro = 'E-mail ou senha incorretos.'
    return render_template('login.html', erro=erro)


@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    erro = None
    if request.method == 'POST':
        nome  = request.form.get('nome', '').strip()
        email = request.form.get('email', '').strip()
        senha = request.form.get('senha', '')
        if not nome or not email or len(senha) < 6:
            erro = 'Preencha todos os campos. Senha mínima: 6 caracteres.'
        elif db.buscar_usuario_email(email):
            erro = 'E-mail já cadastrado.'
        else:
            uid = db.criar_usuario(email, nome, senha)
            u   = db.buscar_usuario_id(uid)
            login_user(User(u), remember=True)
            return redirect(url_for('index'))
    return render_template('cadastro.html', erro=erro)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# ── Fazendas ─────────────────────────────────────────────────────────────────
@app.route('/api/fazendas', methods=['GET'])
@login_required
def api_listar_fazendas():
    return jsonify({'fazendas': db.listar_fazendas(current_user.id)})


@app.route('/api/fazendas', methods=['POST'])
@login_required
def api_criar_fazenda():
    data = request.json
    nome = (data.get('nome') or '').strip()
    if not nome:
        return jsonify({'erro': 'Nome obrigatório'}), 400
    fid = db.criar_fazenda(
        user_id=current_user.id,
        nome=nome,
        proprietario=data.get('proprietario', ''),
        municipio=data.get('municipio', ''),
        estado=data.get('estado', ''),
    )
    return jsonify({'ok': True, 'id': fid})


@app.route('/api/fazendas/<int:fid>/historico', methods=['GET'])
@login_required
def api_historico_fazenda(fid):
    f = db.buscar_fazenda(fid, current_user.id)
    if not f:
        return jsonify({'erro': 'Fazenda não encontrada'}), 404
    hist = db.historico_fazenda(fid, current_user.id)
    return jsonify({'fazenda': dict(f), 'historico': hist})


# ── App principal ─────────────────────────────────────────────────────────────
@app.route('/')
@login_required
def index():
    fazendas = db.listar_fazendas(current_user.id)
    return render_template('index.html', model_stats=stats, cenarios=CENARIOS,
                           usuario=current_user, fazendas=fazendas)


@app.route('/api/classificar', methods=['POST'])
@login_required
def api_classificar():
    data = request.json
    v = data.get('valores', [])
    if len(v) != 10 or sum(v) < 10:
        return jsonify({'erro': 'Envie 10 valores (fêmeas e machos por faixa) com total >= 10'}), 400

    kwargs = {}
    if 'taxa_natalidade' in data:
        kwargs['taxa_natalidade'] = float(data['taxa_natalidade'])
    if 'bois_vendidos' in data:
        kwargs['bois_vendidos'] = float(data['bois_vendidos'])
    if 'bezerros_vendidos' in data:
        kwargs['bezerros_vendidos'] = float(data['bezerros_vendidos'])

    result = classificar(v, **kwargs)
    ind    = calcular_indicadores(v)

    # Salvar automaticamente no BD para futuros retreinamentos
    fazenda   = data.get('fazenda', '')
    municipio = data.get('municipio', '')
    nat_pct   = float(data.get('taxa_natalidade', 0.75)) * 100
    registro_id = db.salvar(
        valores=v,
        class_ml=result['classificacao'],
        confianca=result['confianca'],
        fazenda=fazenda,
        municipio=municipio,
        nat_pct=nat_pct,
    )

    return jsonify({**result, 'indicadores': ind, 'valores': v, 'registro_id': registro_id})


@app.route('/api/confirmar', methods=['POST'])
def api_confirmar():
    """Confirma ou corrige a classificação e dispara auto-retreino em background."""
    data = request.json
    rid  = data.get('registro_id')
    cls  = data.get('classificacao', '').strip().upper()
    if not rid or not cls:
        return jsonify({'erro': 'Campos registro_id e classificacao são obrigatórios'}), 400
    try:
        db.confirmar(int(rid), cls)
        s = db.stats()
        # Dispara retreino em background se não houver um em andamento
        if not _retraining:
            threading.Thread(target=_auto_retrain, daemon=True).start()
        return jsonify({'ok': True, 'stats': s, 'retraining': True})
    except ValueError as e:
        return jsonify({'erro': str(e)}), 400


@app.route('/api/retrain', methods=['POST'])
def api_retrain():
    """Retreina o modelo com dados base + registros confirmados do BD."""
    global stats
    X_extra, y_extra = db.exportar_treino()
    stats = retrain_com_dados(X_extra, y_extra)
    return jsonify({**stats, 'ok': True})


@app.route('/api/historico', methods=['GET'])
def api_historico():
    limit = min(int(request.args.get('limit', 60)), 200)
    return jsonify({'registros': db.listar(limit), 'stats': db.stats()})


@app.route('/api/db-stats', methods=['GET'])
def api_db_stats():
    s = db.stats()
    s['accuracy'] = stats.get('accuracy_mean', 0)
    s['retraining'] = _retraining
    return jsonify(s)


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
        tmp_path = tmp.name
        f.save(tmp_path)
    # Arquivo fechado antes de processar (necessário no Windows)
    try:
        text  = extrair_texto_pdf(tmp_path)
        orig  = detectar_origem(text)
        if orig == 'IDARON':
            dados = parsear_idaron(text, pdf_path=tmp_path)
        elif orig == 'INDEA':
            dados = parsear_indea(text)
        else:
            # Tenta IDARON com tabela, depois INDEA, depois genérico
            dados = parsear_idaron(text, pdf_path=tmp_path)
            if dados['total'] == 0:
                dados = parsear_indea(text)
        dados['origem'] = orig
        return jsonify(dados)
    except Exception as e:
        return jsonify({'erro': str(e)}), 500
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


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
            or 'FORMULÁRIO DE ANOTAÇÕES' in up
            or 'FORMULARIO DE ANOTACOES' in up
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
# PARSER IDARON-RO — extração por tabela (formulário de anotações)
# ─────────────────────────────────────────────
# Padrões de faixa etária usados em ambos os parsers
_FAIXA_PATS = [
    (r'0\s*[AÀ]\s*0?6\s*(M[EÊ]S)?|ATÉ\s*6|ATE\s*6',           'f00'),
    (r'0?7\s*[AÀ]\s*12\s*(M[EÊ]S)?',                            'f05'),
    (r'0\s*[AÀ]\s*12\s*(M[EÊ]S)?|ATÉ\s*12|ATE\s*12',           'f00_12'),
    (r'13\s*[AÀ]\s*24\s*(M[EÊ]S)?',                             'f13'),
    (r'25\s*[AÀ]\s*36\s*(M[EÊ]S)?',                             'f25'),
    (r'ACIMA|MAIOR\s*DE?\s*36|>\s*36',                          'fac'),
]


def _faixa_de_celula(cell_up: str):
    """Retorna o código de faixa se a célula contiver um marcador de faixa etária."""
    for pat, faixa in _FAIXA_PATS:
        if re.search(pat, cell_up):
            return faixa
    return None


def _adicionar(animais: dict, faixa: str, sexo: str, qtd: int):
    if faixa == 'f00_12':
        metade = qtd // 2
        animais[f'f00_{sexo}'] += metade
        animais[f'f05_{sexo}'] += qtd - metade
    else:
        animais[f'{faixa}_{sexo}'] += qtd


def _parsear_tabela_bovinos(table) -> dict:
    """
    Interpreta uma tabela pdfplumber buscando cabeçalhos de faixa etária/sexo.
    Suporta layouts onde F/M são sub-colunas abaixo das faixas etárias,
    ou onde faixas e sexo estão na mesma célula.
    """
    animais = _animais_vazios()
    if not table or len(table) < 2:
        return animais

    # Normaliza: None → ''
    rows = [[str(c or '').upper().strip() for c in row] for row in table]

    # ── Passo 1: mapear colunas com faixas etárias ────────────────────────
    faixa_col = {}   # col_idx → faixa
    for row in rows:
        for c_idx, cell in enumerate(row):
            f = _faixa_de_celula(cell)
            if f and c_idx not in faixa_col:
                faixa_col[c_idx] = f

    if not faixa_col:
        return animais  # sem cabeçalhos reconhecíveis

    # ── Passo 2: mapear colunas com sexo ──────────────────────────────────
    sexo_col = {}    # col_idx → sexo
    for row in rows:
        for c_idx, cell in enumerate(row):
            if cell in ('F', 'FÊMEA', 'FEMEA') or re.match(r'^F[EÊ]MEA$', cell):
                sexo_col[c_idx] = 'F'
            elif cell in ('M', 'MACHO') or re.match(r'^MACHO$', cell):
                sexo_col[c_idx] = 'M'

    # ── Passo 3: construir mapa final col_idx → (faixa, sexo) ─────────────
    col_map = {}

    if sexo_col:
        for c_idx, sexo in sexo_col.items():
            # Coluna de sexo mais próxima de uma coluna de faixa (dist ≤ 4)
            candidatos = {fc: f for fc, f in faixa_col.items()
                          if abs(fc - c_idx) <= 4}
            if candidatos:
                nearest = min(candidatos, key=lambda x: abs(x - c_idx))
                col_map[c_idx] = (candidatos[nearest], sexo)
    else:
        # Sem marcadores F/M explícitos — assume alternância F, M para cada faixa
        sorted_f = sorted(faixa_col.items())
        for i, (c_idx, faixa) in enumerate(sorted_f):
            col_map[c_idx] = (faixa, 'F' if i % 2 == 0 else 'M')

    # ── Passo 4: extrair números das linhas de dados ───────────────────────
    for row in rows:
        for c_idx, cell in enumerate(row):
            if c_idx not in col_map:
                continue
            if not re.match(r'^\d+$', cell):
                continue
            qtd = int(cell)
            if qtd <= 0 or qtd > 500_000:
                continue
            faixa, sexo = col_map[c_idx]
            _adicionar(animais, faixa, sexo, qtd)

    return animais


def _parse_idaron_tabelas(pdf_path: str) -> dict:
    """
    Tenta extrair bovinos via extração de tabelas pdfplumber.
    Funciona bem para o formulário IDARON estruturado em grade.
    """
    try:
        import pdfplumber
        animais = _animais_vazios()

        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                for settings in [
                    {'vertical_strategy': 'lines', 'horizontal_strategy': 'lines'},
                    {'vertical_strategy': 'lines_strict', 'horizontal_strategy': 'lines_strict'},
                    {'vertical_strategy': 'text', 'horizontal_strategy': 'text',
                     'min_words_vertical': 3, 'min_words_horizontal': 1},
                ]:
                    try:
                        tables = page.extract_tables(settings)
                    except Exception:
                        continue
                    for tbl in (tables or []):
                        result = _parsear_tabela_bovinos(tbl)
                        if sum(result.values()) > 0:
                            for k, v in result.items():
                                if v > 0:
                                    animais[k] = max(animais[k], v)
                    if sum(animais.values()) > 0:
                        break   # encontrou na primeira estratégia que funcionou

        return animais
    except Exception:
        return _animais_vazios()


def _parse_idaron_words(pdf_path: str) -> dict:
    """
    Fallback: usa posições X das palavras para mapear colunas.
    Útil quando pdfplumber não detecta bordas de tabela.
    """
    try:
        import pdfplumber
        animais = _animais_vazios()

        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                words = page.extract_words(x_tolerance=5, y_tolerance=5)
                if not words:
                    continue

                # Agrupa palavras por linha (y0 próximo)
                linhas: dict[float, list] = {}
                for w in words:
                    y = round(w['top'] / 4) * 4   # quantiza em 4pt
                    linhas.setdefault(y, []).append(w)

                # 1ª passagem: mapear colunas de faixa por x
                faixa_x: dict[float, str] = {}   # x_mid → faixa
                for y, ws in linhas.items():
                    texto = ' '.join(w['text'].upper() for w in ws)
                    f = _faixa_de_celula(texto)
                    if f:
                        x_mid = sum((w['x0'] + w['x1']) / 2 for w in ws) / len(ws)
                        faixa_x[x_mid] = f

                if not faixa_x:
                    continue

                # 2ª passagem: mapear colunas de sexo
                col_map: dict[float, tuple] = {}   # x_mid → (faixa, sexo)
                for y, ws in linhas.items():
                    for w in ws:
                        t = w['text'].upper()
                        if t in ('F', 'FÊMEA', 'FEMEA', 'M', 'MACHO'):
                            sexo = 'F' if t in ('F', 'FÊMEA', 'FEMEA') else 'M'
                            x_mid = (w['x0'] + w['x1']) / 2
                            nearest = min(faixa_x, key=lambda x: abs(x - x_mid))
                            if abs(nearest - x_mid) < 60:
                                col_map[x_mid] = (faixa_x[nearest], sexo)

                if not col_map:
                    # Sem marcadores F/M — alternância
                    for i, (xf, faixa) in enumerate(sorted(faixa_x.items())):
                        col_map[xf] = (faixa, 'F' if i % 2 == 0 else 'M')

                # 3ª passagem: extrair números
                for y, ws in linhas.items():
                    for w in ws:
                        if not re.match(r'^\d+$', w['text']):
                            continue
                        qtd = int(w['text'])
                        if qtd <= 0 or qtd > 500_000:
                            continue
                        x_mid = (w['x0'] + w['x1']) / 2
                        nearest = min(col_map, key=lambda x: abs(x - x_mid))
                        if abs(nearest - x_mid) < 40:
                            faixa, sexo = col_map[nearest]
                            _adicionar(animais, faixa, sexo, qtd)

        return animais
    except Exception:
        return _animais_vazios()


# ─────────────────────────────────────────────
# PARSER IDARON-RO — texto linha a linha (fallback)
# ─────────────────────────────────────────────
def _parse_idaron_linhas(text: str) -> dict:
    """Parser texto-linha original — fallback para documentos GTA/saldo IDARON."""
    animais = _animais_vazios()

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

        if re.search(r'0\s*A\s*12', up) or 'ATÉ 12' in up or 'ATE 12' in up:
            metade = qtd // 2
            animais[f'f00_{sexo}'] += metade
            animais[f'f05_{sexo}'] += qtd - metade
        elif re.search(r'0\s*A\s*0?6', up) or re.search(r'ATÉ\s*6', up, re.I):
            animais[f'f00_{sexo}'] += qtd
        elif re.search(r'0?7\s*A\s*12', up):
            animais[f'f05_{sexo}'] += qtd
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

    # Categorias zootécnicas (bezerra, novilha, vaca, touro…)
    _categorias = [
        (['BEZERRA', 'BEZERRO'],   'f05', None),
        (['GARROTA', 'GARROTE'],   'f13', None),
        (['NOVILHA', 'NOVILHO'],   'f25', None),
        (['VACA'],                 'fac', 'F'),
        (['TOURO', 'BOI', 'BOIS'], 'fac', 'M'),
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
                if sexo and animais[f'{faixa}_{sexo}'] == 0:
                    animais[f'{faixa}_{sexo}'] = qtd
                break

    return animais


# ─────────────────────────────────────────────
# PARSER IDARON-RO — orquestrador
# ─────────────────────────────────────────────
def parsear_idaron(text: str, pdf_path: str = None) -> dict:
    """
    Suporta dois layouts IDARON:
      1. Formulário de Anotações (grade de células) → extração por tabela/palavras
      2. GTA / Saldo de Exploração (texto linha a linha) → parser regex
    """
    fazenda = municipio = proprietario = cpf = data_saldo = ie = ''

    # IE (Inscrição Estadual)
    m = re.search(r'\bI\.?E\.?\b[:\s]+([A-Z0-9\.\-\/]+)', text, re.I)
    if m:
        ie = m.group(1).strip()

    # Nome da propriedade
    for pat in [
        r'NOME\s+DA\s+PROPRIEDADE[:\s]+(.+)',
        r'PROPRIEDADE[:\s]+(.+)',
        r'ESTABELECIMENTO[:\s]+(.+)',
        r'FAZENDA[:\s]+([A-ZÁÉÍÓÚÂÊÎÔÛÃÕÇ0-9\s\.\-]+)',
    ]:
        m = re.search(pat, text, re.I)
        if m:
            fazenda = m.group(1).strip()[:60]
            break

    # Município
    m = re.search(
        r'MUNIC[IÍ]PIO[:\s]+([A-ZÁÉÍÓÚÂÊÎÔÛÃÕÇ\s\-]+?(?:/\s*RO)?)(?:\s{2,}|\n|$)',
        text, re.I
    )
    if m:
        municipio = m.group(1).strip()

    # CPF / Proprietário
    m = re.search(
        r'(?:CPF|PRODUTOR)[:\s/]*'
        r'(\d{3}\.?\d{3}\.?\d{3}[\-\.]?\d{2})'
        r'[:\s/]*([A-ZÁÉÍÓÚÂÊÎÔÛÃÕÇ][A-ZÁÉÍÓÚÂÊÎÔÛÃÕÇ\s]+?)(?:\s{2,}|\n)',
        text, re.I
    )
    if not m:
        m = re.search(r'(\d{11})\s+([A-ZÁÉÍÓÚÂÊÎÔÛÃÕÇ\s]+?)(?:\s{3,}|\n)', text, re.I)
    if m:
        cpf = re.sub(r'[^\d]', '', m.group(1))
        proprietario = m.group(2).strip()

    m = re.search(r'(\d{2}/\d{2}/\d{4})', text)
    if m:
        data_saldo = m.group(1)

    # ── Extração de animais (3 estratégias em cascata) ────────────────────
    animais = _animais_vazios()

    if pdf_path:
        # 1. Tabela (melhor para formulário de anotações em grade)
        animais = _parse_idaron_tabelas(pdf_path)

    if pdf_path and sum(animais.values()) == 0:
        # 2. Posição de palavras (fallback para PDFs sem bordas de célula)
        animais = _parse_idaron_words(pdf_path)

    if sum(animais.values()) == 0:
        # 3. Texto linha a linha (GTA, saldo de exploração, etc.)
        animais = _parse_idaron_linhas(text)

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
