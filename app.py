"""
BoviML — Servidor Flask (CORRIGIDO)
"""
import logging
import os
import re
import io
import tempfile
import subprocess
import threading
from functools import wraps

from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, send_from_directory, send_file, session
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from apscheduler.schedulers.background import BackgroundScheduler

from ml_engine import (
    treinar_modelo, classificar, calcular_indicadores,
    simular_cenario, retrain_com_dados, carregar_modelo, CENARIOS,
    avaliar_benchmarks, extrair_indicadores_benchmark, calcular_breakeven_simples,
)
import database as db

# Importações do PDF parsers (evitamos sobrescrever com definições locais)
# Usaremos as funções locais para extrair texto e detectar origem, pois têm fallback.
# Mas importamos os parsers específicos.
from pdf_parsers import (
    parsear_idaron, parsear_indea, parsear_declaracao_idaron
)
# Tenta importar o parsear_generico se existir
try:
    from pdf_parsers import parsear_generico
except ImportError:
    parsear_generico = None

from scraper import obter_precos_arroba, obter_precos_agrobr_strict

from parsers.composicao_rebanho import ler_template
from services.consistencia_rebanho import analisar_consistencia, analisar_consistencia_historica
from services.benchmarks_nacionais import avaliar_nacional
from services.parecer_credito import montar_parecer
from services.parecer_pdf import gerar_pdf_parecer
from services.pesos_rebanho import arrobas_categorias
from services.custos_desembolso import custo_arroba_de_desembolso, COMPONENTES
from services.reconciliacao import reconciliar
from services.fluxo_caixa_gep import valor_rebanho_gep, calcular_fluxo_gep
from services.benchmarks_nacionais import avaliar_coe as _avaliar_coe

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'boviml-dev-secret-2026')  # Em produção, sempre defina via env

# ── Controle de acesso: administradores ───────────────────────────────────────
# Defina ADMIN_EMAILS no Railway (ex.: "voce@email.com"). Só admins acessam
# /admin, onde criam as contas dos usuários. O cadastro público fica desativado.
import secrets as _secrets
from functools import wraps

_ADMIN_EMAILS = {
    e.strip().lower()
    for e in os.environ.get('ADMIN_EMAILS', '').split(',')
    if e.strip()
}


def is_admin(email: str) -> bool:
    """True se o e-mail é de um administrador."""
    return (email or '').strip().lower() in _ADMIN_EMAILS


def gerar_senha(n: int = 10) -> str:
    """Gera uma senha aleatória legível (sem caracteres ambíguos)."""
    alfabeto = 'abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789'
    return ''.join(_secrets.choice(alfabeto) for _ in range(n))


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login'))
        if not is_admin(getattr(current_user, 'email', '')):
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return wrapper


def _resolver_empresa_ativa():
    """Empresa ativa da sessão; escolhe a primeira se ausente/inválida.
    Devolve None se o usuário não pertence a nenhuma empresa."""
    empresas = db.empresas_do_usuario(current_user.id)
    if not empresas:
        return None
    ativa = session.get('empresa_ativa_id')
    if ativa and any(e['id'] == ativa for e in empresas):
        return ativa
    nova_ativa = empresas[0]['id']
    session['empresa_ativa_id'] = nova_ativa
    return nova_ativa


def _empresa_ativa_ou_400():
    """Para endpoints JSON: devolve (empresa_id, None) ou (None, response_erro)."""
    eid = _resolver_empresa_ativa()
    if eid is None:
        return None, (jsonify({'erro': 'Usuário sem empresa vinculada'}), 400)
    return eid, None


def garantir_admins():
    """Provisiona as contas admin no start (resolve o ovo-e-galinha do acesso).

    Para cada e-mail em ADMIN_EMAILS: se não existir conta, cria uma com a
    senha de ADMIN_SENHA_INICIAL (ou uma gerada, logada uma vez). Se a conta já
    existir e ADMIN_RESET_SENHA estiver ligado, redefine a senha para
    ADMIN_SENHA_INICIAL — lever de recuperação quando você esquece a senha.
    """
    senha_inicial = os.environ.get('ADMIN_SENHA_INICIAL', '').strip()
    resetar = os.environ.get('ADMIN_RESET_SENHA', '').strip().lower() in (
        '1', 'true', 'yes', 'sim')
    for email in _ADMIN_EMAILS:
        existente = db.buscar_usuario_email(email)
        if existente is None:
            senha = senha_inicial or gerar_senha()
            db.criar_usuario(email, email.split('@')[0], senha)
            origem = 'ADMIN_SENHA_INICIAL' if senha_inicial else senha
            logger.warning(f"[ADMIN] Conta criada para {email} | senha: {origem}")
        elif resetar and senha_inicial:
            db.resetar_senha(email, senha_inicial)
            logger.warning(f"[ADMIN] Senha redefinida para {email} (ADMIN_RESET_SENHA).")

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
    logger.info(f"✅ Modelo carregado do disco | Acurácia: {stats['accuracy_mean']*100:.1f}% | Amostras: {stats['n_samples']}")
else:
    logger.info("🧠 Treinando modelo ML (primeira execução)...")
    stats = treinar_modelo()
    logger.info(f"✅ Modelo treinado | Acurácia CV: {stats['accuracy_mean']*100:.1f}% ± {stats['accuracy_std']*100:.1f}% | Amostras: {stats['n_samples']}")

db.init_db()
logger.info("🗃️  Banco SQLite inicializado.")
garantir_admins()

# ── Estado de re-treino com proteção de concorrência ──────────────────────
_retraining = False
_retrain_lock = threading.Lock()

# ── Automação: Cotações Diárias (Scraper) ────────────────────────────────────
def rotina_diaria_cotacoes():
    """Função executada em background para atualizar preços da arroba."""
    logger.info("📈 [Scraper] A iniciar a busca automática de cotações...")
    try:
        precos = obter_precos_arroba()
        if precos.get('boi', 0) > 0 or precos.get('vaca', 0) > 0:
            db.guardar_cotacao_diaria(precos)
            logger.info("✅ [Scraper] Cotações atualizadas no banco de dados.")
        else:
            logger.warning("⚠️ [Scraper] Cotações retornaram zero, não salvas.")
    except Exception as e:
        logger.error(f"❌ [Scraper] Erro na rotina: {e}", exc_info=True)

# Configura e inicia o agendador de tarefas
scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(rotina_diaria_cotacoes, 'cron', hour=8, minute=0)  # Roda todo dia às 08h00
scheduler.start()

# Opcional: Roda uma vez assim que o servidor liga para garantir que a tabela não fica vazia
rotina_diaria_cotacoes()

# ── Auto-retreino em background ──────────────────────────────────────────────
def _auto_retrain():
    """Executa o re-treino em background com proteção de concorrência."""
    global stats, _retraining
    with _retrain_lock:
        if _retraining:
            logger.info("⚠️ Re-treino já em andamento, ignorando nova solicitação.")
            return
        _retraining = True

    try:
        logger.info("🔄 Iniciando auto-retreino em background...")
        X_extra, y_extra = db.exportar_treino()
        new_stats = retrain_com_dados(X_extra, y_extra)
        with _retrain_lock:
            stats = new_stats
        logger.info(f"✅ Auto-retreino concluído | Acurácia: {stats['accuracy_mean']*100:.1f}% | {stats.get('n_confirmados', 0)} confirmados")
    except Exception as e:
        logger.error(f"❌ Erro no auto-retreino: {e}", exc_info=True)
    finally:
        with _retrain_lock:
            _retraining = False

def is_retraining() -> bool:
    """Retorna True se um re-treino estiver em andamento (thread-safe)."""
    with _retrain_lock:
        return _retraining

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

@app.route('/esqueci-senha')
def esqueci_senha():
    return render_template('esqueci_senha.html')

@app.route('/privacidade')
def privacidade():
    return render_template('privacidade.html')

@app.route('/termos')
def termos():
    return render_template('termos.html')

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    # Cadastro público desativado: apenas administradores criam contas em /admin.
    return render_template(
        'login.html',
        erro='O cadastro é feito pelo administrador. Solicite seu acesso.'
    ), 403


# ── Administração de usuários ─────────────────────────────────────────────────
@app.route('/admin')
@admin_required
def admin():
    return render_template(
        'admin.html',
        usuarios=db.listar_usuarios(),
        usuario=current_user,
        nova_conta=None,
        empresas=db._exec('SELECT * FROM empresas ORDER BY nome', fetch='all') or [],
        membros=db._exec('''SELECT m.empresa_id, m.user_id, e.nome as empresa_nome,
                            u.email as user_email FROM empresa_membros m
                            JOIN empresas e ON e.id=m.empresa_id
                            JOIN usuarios u ON u.id=m.user_id ORDER BY e.nome''', fetch='all') or [],
    )

@app.route('/admin/empresas/criar', methods=['POST'])
@admin_required
def admin_criar_empresa():
    nome = (request.form.get('nome') or '').strip()
    if nome:
        db._exec(f"INSERT INTO empresas (nome) VALUES ({db._PH})", (nome,), commit=True)
    return redirect(url_for('admin'))

@app.route('/admin/empresas/vincular', methods=['POST'])
@admin_required
def admin_vincular_empresa():
    user_id = request.form.get('user_id')
    empresa_id = request.form.get('empresa_id')
    if user_id and empresa_id and not db.usuario_pertence_a_empresa(int(user_id), int(empresa_id)):
        db._exec(f"INSERT INTO empresa_membros (empresa_id, user_id) VALUES ({db._PH},{db._PH})",
                 (int(empresa_id), int(user_id)), commit=True)
    return redirect(url_for('admin'))

@app.route('/admin/empresas/desvincular', methods=['POST'])
@admin_required
def admin_desvincular_empresa():
    user_id = request.form.get('user_id')
    empresa_id = request.form.get('empresa_id')
    if user_id and empresa_id:
        db._exec(f"DELETE FROM empresa_membros WHERE user_id={db._PH} AND empresa_id={db._PH}",
                 (int(user_id), int(empresa_id)), commit=True)
    return redirect(url_for('admin'))


@app.route('/admin/criar', methods=['POST'])
@admin_required
def admin_criar():
    nome  = request.form.get('nome', '').strip()
    email = request.form.get('email', '').strip().lower()
    erro = None
    nova_conta = None
    if not nome or not email:
        erro = 'Preencha nome e e-mail.'
    elif db.buscar_usuario_email(email):
        erro = 'E-mail já cadastrado.'
    else:
        senha = gerar_senha()
        db.criar_usuario(email, nome, senha)
        nova_conta = {'nome': nome, 'email': email, 'senha': senha}
    return render_template(
        'admin.html',
        usuarios=db.listar_usuarios(),
        usuario=current_user,
        nova_conta=nova_conta,
        erro=erro,
        empresas=db._exec('SELECT * FROM empresas ORDER BY nome', fetch='all') or [],
        membros=db._exec('''SELECT m.empresa_id, m.user_id, e.nome as empresa_nome,
                            u.email as user_email FROM empresa_membros m
                            JOIN empresas e ON e.id=m.empresa_id
                            JOIN usuarios u ON u.id=m.user_id ORDER BY e.nome''', fetch='all') or [],
    )


@app.route('/admin/remover/<int:uid>', methods=['POST'])
@admin_required
def admin_remover(uid):
    alvo = db.buscar_usuario_id(uid)
    if alvo and not is_admin(alvo['email']):
        db.remover_usuario(uid)
    return redirect(url_for('admin'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# ── Empresa ativa ────────────────────────────────────────────────────────────
@app.route('/api/empresa/ativa', methods=['GET'])
@login_required
def api_empresa_ativa_get():
    empresas = db.empresas_do_usuario(current_user.id)
    ativa_id = _resolver_empresa_ativa()
    return jsonify({'empresas': empresas, 'ativa_id': ativa_id})

@app.route('/api/empresa/ativa', methods=['POST'])
@login_required
def api_empresa_ativa_post():
    empresa_id = (request.json or {}).get('empresa_id')
    if not db.usuario_pertence_a_empresa(current_user.id, empresa_id):
        return jsonify({'erro': 'Você não pertence a essa empresa'}), 403
    session['empresa_ativa_id'] = empresa_id
    return jsonify({'ok': True})

# ── Fazendas ─────────────────────────────────────────────────────────────────
@app.route('/api/fazendas', methods=['GET'])
@login_required
def api_listar_fazendas():
    empresa_id, erro = _empresa_ativa_ou_400()
    if erro:
        return erro
    return jsonify({'fazendas': db.listar_fazendas(empresa_id)})

@app.route('/api/fazendas', methods=['POST'])
@login_required
def api_criar_fazenda():
    empresa_id, erro = _empresa_ativa_ou_400()
    if erro:
        return erro
    data = request.json
    nome = (data.get('nome') or '').strip()
    if not nome:
        return jsonify({'erro': 'Nome obrigatório'}), 400
    fid = db.criar_fazenda(
        nome=nome,
        proprietario=data.get('proprietario', ''),
        municipio=data.get('municipio', ''),
        estado=data.get('estado', ''),
        empresa_id=empresa_id,
        criado_por=current_user.id,
    )
    return jsonify({'ok': True, 'id': fid})

@app.route('/api/fazendas/<int:fid>/historico', methods=['GET'])
@login_required
def api_historico_fazenda(fid):
    empresa_id, erro = _empresa_ativa_ou_400()
    if erro:
        return erro
    f = db.buscar_fazenda(fid, empresa_id)
    if not f:
        return jsonify({'erro': 'Fazenda não encontrada'}), 404
    hist = db.historico_fazenda(fid)
    return jsonify({'fazenda': dict(f), 'historico': hist})

@app.route('/api/fazendas/<int:fid>/pareceres', methods=['GET'])
@login_required
def api_fazenda_pareceres(fid):
    empresa_id, erro = _empresa_ativa_ou_400()
    if erro:
        return erro
    if not db.buscar_fazenda(fid, empresa_id):
        return jsonify({'erro': 'Fazenda não encontrada'}), 404
    itens = db.listar_pareceres(fazenda_id=fid)
    return jsonify({'pareceres': itens})

@app.route('/api/empresa/perfil', methods=['GET', 'POST'])
@login_required
def api_empresa_perfil():
    empresa_id, erro = _empresa_ativa_ou_400()
    if erro:
        return erro
    if request.method == 'POST':
        data = request.json or {}
        db.atualizar_perfil_empresa(
            empresa_id, data.get('nome_consultoria', ''), data.get('logo_base64', ''))
        return jsonify({'ok': True})
    e = db.buscar_empresa(empresa_id)
    return jsonify({
        'nome_consultoria': (e.get('nome') or '') if e else '',
        'logo_base64': (e.get('logo_base64') or '') if e else '',
    })

@app.route('/api/parecer/pdf', methods=['POST'])
@login_required
def api_parecer_pdf():
    parecer = (request.json or {}).get('parecer')
    if not parecer:
        return jsonify({'erro': 'parecer é obrigatório'}), 400
    empresa_id = _resolver_empresa_ativa()
    e = db.buscar_empresa(empresa_id) if empresa_id else None
    branding = {'nome_consultoria': e.get('nome') or '',
                'logo_base64': e.get('logo_base64') or ''} if e else None
    pdf_bytes = gerar_pdf_parecer(parecer, branding=branding)
    return send_file(io.BytesIO(pdf_bytes), mimetype='application/pdf',
                     as_attachment=True, download_name='parecer_credito.pdf')

# ── App principal ─────────────────────────────────────────────────────────────
@app.route('/')
@login_required
def index():
    empresa_id = _resolver_empresa_ativa()
    fazendas = db.listar_fazendas(empresa_id) if empresa_id else []
    cotacoes_dia = db.obter_cotacoes_atuais()
    return render_template('index.html', model_stats=stats, cenarios=CENARIOS,
                           usuario=current_user, fazendas=fazendas, cotacoes=cotacoes_dia,
                           eh_admin=is_admin(current_user.email))

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

    # Indicadores comparáveis a benchmarks regionais (GEP Araguaia / Rondônia):
    # usa o que o usuário informou (mortalidade_pct, desmama_pct,
    # rend_carcaca_pct, ganho_peso_kg_dia, desfrute_pct) e completa o
    # resto com defaults regionais ou com o que já foi calculado do rebanho.
    ind_bench  = extrair_indicadores_benchmark(v, data)
    benchmarks = avaliar_benchmarks(result['tipo'], ind_bench)
    breakeven  = calcular_breakeven_simples(v, result['tipo'])

    # Painel de benchmarks NACIONAIS (multi-fonte + financeiro): confronta os
    # indicadores contra cada fonte institucional (Embrapa, Scot, CEPEA-USP,
    # ABCZ, ASBIA) e contra o desembolso de referência (Inttegra 2025).
    def _opt_float(x):
        try:
            return float(x) if x not in (None, '') else None
        except (TypeError, ValueError):
            return None
    painel_nacional = avaliar_nacional(result['tipo'], {
        'prenhez':    _opt_float(data.get('taxa_prenhez_pct')),
        'natalidade': ind_bench.get('natalidade'),
        'desfrute':   ind_bench.get('desfrute'),
        'desembolso': _opt_float(data.get('desembolso_cab_mes')),
    })

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

    # Consistência do rebanho declarado (diferencial de análise de crédito):
    # roda também no fluxo principal, não só na importação de PDF.
    consistencia = analisar_consistencia(v)

    # Consistência histórica: compara com a declaração anterior da mesma fazenda.
    fazenda_id_hist = data.get('fazenda_id')
    if fazenda_id_hist:
        hist = db.historico_fazenda(int(fazenda_id_hist), limit=1)
        if hist and hist[0].get('valores'):
            flags_hist = analisar_consistencia_historica(v, hist[0]['valores'])
            if flags_hist:
                consistencia['flags'] = flags_hist + consistencia['flags']
                erros_hist = sum(1 for f in flags_hist if f['severidade'] == 'erro')
                alertas_hist = sum(1 for f in flags_hist if f['severidade'] == 'alerta')
                consistencia['resumo']['erros'] += erros_hist
                consistencia['resumo']['alertas'] += alertas_hist
                penalidade = erros_hist * 25 + alertas_hist * 8
                consistencia['score_consistencia'] = max(0, consistencia['score_consistencia'] - penalidade)

    # Custo real por componentes (desembolso R$/cab/mês) → custo_arroba exato.
    # Se não vierem componentes, usa custo_arroba do campo único (default 95 R$/@·ano
    # equivalente a ~119 R$/cab/mês ÷ 15@ — CICLO_COMPLETO médio GEP safra 24/25).
    custo_arroba = float(data.get('custo_arroba', 95) or 95)
    custo_desembolso = None
    componentes = data.get('custo_componentes') or {}
    desembolso_cab_mes = sum(float(componentes.get(k, 0) or 0) for k, _ in COMPONENTES)
    if desembolso_cab_mes > 0:
        femeas_024 = float(v[0] + v[2] + v[4])
        machos_024 = float(v[1] + v[3] + v[5])
        matrizes   = float(v[6] + v[8])
        bois       = float(v[7] + v[9])
        arrobas_rebanho = arrobas_categorias(
            matrizes=matrizes, bois=bois, jovens_f=femeas_024, jovens_m=machos_024)
        total_cabecas = int(sum(v))
        custo_arroba = custo_arroba_de_desembolso(
            desembolso_cab_mes, arrobas_rebanho, total_cabecas)
        custo_desembolso = {
            'componentes': {k: float(componentes.get(k, 0) or 0) for k, _ in COMPONENTES},
            'desembolso_cab_mes': round(desembolso_cab_mes, 2),
            'custo_arroba': round(custo_arroba, 2),
            'peso_medio_arroba': round(arrobas_rebanho / max(total_cabecas, 1), 2),
        }

    # Preços por categoria (cotação do dia): request → banco → None (usa arroba).
    _cot = db.obter_cotacoes_atuais() or {}
    def _preco(chave):
        v_ = float(data.get(chave) or _cot.get(chave.replace('preco_', '')) or 0)
        return v_ if v_ > 0 else None
    preco_boi = _preco('preco_boi')
    preco_vaca = _preco('preco_vaca')
    preco_bezerra = _preco('preco_bezerra')
    preco_bezerro = _preco('preco_bezerro')

    # Geração de caixa recorrente: resultado do ano 1 no cenário conservador,
    # dentro do ciclo detectado (número mais conservador e recorrente).
    def _custo_fase(chave):
        v_ = float(data.get(chave) or 0)
        return v_ if v_ > 0 else None
    _cx = simular_cenario(
        v, 'conservador', ciclo=result['tipo'],
        preco_arroba=preco_boi or float(data.get('preco', 320)),
        custo_arroba=custo_arroba,
        custo_arroba_cria=_custo_fase('custo_arroba_cria'),
        custo_arroba_recria=_custo_fase('custo_arroba_recria'),
        custo_arroba_engorda=_custo_fase('custo_arroba_engorda'),
        preco_boi_arr=preco_boi, preco_vaca_arr=preco_vaca,
        preco_bezerra_cab=preco_bezerra, preco_bezerro_cab=preco_bezerro)
    geracao_caixa_anual = _cx['anos'][0]['resultado']

    # ── Fluxo de caixa completo — metodologia GEP Araguaia ──────────────────
    # Calcula variação de estoque do rebanho (ativo que valoriza ou deprecia).
    # Diferencial: nenhum sistema de crédito rural calcula isso automaticamente.
    _va = [float(x) for x in v]
    _preco_boi_ref = preco_boi or float(data.get('preco', 320))
    _val_ini = valor_rebanho_gep(
        matrizes = _va[6] + _va[8],   # f25F + facF
        bois     = _va[7] + _va[9],   # f25M + facM
        novilhas = _va[4],             # f13F  (9.33@ × pv)
        garrotes = _va[5],             # f13M  (10.67@ × pb)
        bezerras = _va[0] + _va[2],   # f00F + f05F (R$/cab)
        bezerros = _va[1] + _va[3],   # f00M + f05M (R$/cab)
        preco_boi        = _preco_boi_ref,
        preco_vaca       = preco_vaca,
        preco_bezerra_cab = preco_bezerra,
        preco_bezerro_cab = preco_bezerro,
    )
    _ano1 = _cx['anos'][0]
    _val_fim = valor_rebanho_gep(
        matrizes = float(_ano1['matrizes']),
        bois     = _ano1.get('bois_fim', _va[7] + _va[9]),
        jovens_f = float(_ano1.get('jovens_f_fim', 0)),
        jovens_m = float(_ano1.get('jovens_m_fim', 0)),
        preco_boi  = _preco_boi_ref,
        preco_vaca = preco_vaca,
    )
    # Reposição de reprodutores: touros renovados × preço por cabeça
    # Touro reprodutor ≈ 1.5× valor do boi comercial (benchmark mercado RO/MT)
    _matrizes_ini   = _va[6] + _va[8]
    _prop_boi       = float(data.get('propboi', 30))
    _renov_boi_pct  = float(data.get('renovboi', 20)) / 100
    _touros_nec     = max(_matrizes_ini / max(_prop_boi, 1), 0)
    _touros_renovados = _touros_nec * _renov_boi_pct
    _fator_touro    = float(data.get('fator_touro', 1.5))  # multiplier s/ boi comercial
    _peso_touro_arr = 20.53  # arrobas — mesmo do CATEGORIAS_GEP['boi']
    _preco_touro_cab = _preco_boi_ref * _peso_touro_arr * _fator_touro
    _reposicao_reprodutores = round(_touros_renovados * _preco_touro_cab, 2)

    # Serviço da dívida para o fluxo GEP (mesma base do DSCR do parecer)
    _servico_gep = 0.0
    if data.get('credito_valor') and data.get('prazo_meses') and data.get('juros_aa'):
        from services.parecer_credito import parcela_price
        _n = max(int(data.get('prazo_meses', 0)) - int(data.get('carencia_meses', 0) or 0), 0)
        _parcela = parcela_price(
            float(data.get('credito_valor', 0)),
            float(data.get('juros_aa', 0)),
            _n,
        )
        _servico_gep = 12 * (_parcela + float(data.get('dividas_mensais', 0) or 0))
    fluxo_gep = calcular_fluxo_gep(
        receita_caixa            = _ano1['receita'],
        custo_caixa              = _ano1['custo'],
        valor_rebanho_ini        = _val_ini['valor_total'],
        valor_rebanho_fim        = _val_fim['valor_total'],
        servico_divida_anual     = _servico_gep,
        reposicao_reprodutores   = _reposicao_reprodutores,
    )

    # COE (R$/@ vendida) = custo_operacional / arrobas_vendidas_estimadas
    # arrobas_vendidas_est = receita / preco_boi (aproximação: toda receita em @)
    if _preco_boi_ref > 0 and _ano1.get('receita', 0) > 0:
        _arrobas_vend_est = _ano1['receita'] / _preco_boi_ref
        _coe_calc = fluxo_gep['custo_operacional'] / _arrobas_vend_est
        fluxo_gep['coe_por_arroba'] = round(_coe_calc, 2)
        fluxo_gep['coe_benchmark']  = _avaliar_coe(result.get('tipo', 'CICLO_COMPLETO'), _coe_calc)
    else:
        fluxo_gep['coe_por_arroba'] = None
        fluxo_gep['coe_benchmark']  = None

    credito_inputs = {k: data.get(k) for k in
                      ('credito_valor', 'prazo_meses', 'juros_aa',
                       'carencia_meses', 'dividas_mensais')}

    # ── Sensibilidade de preço: −15% / base / +15% ───────────────────────────
    _servico_base = _servico_gep  # já calculado acima (mesma base do DSCR)
    sensibilidade = []
    for _label, _fator in (('queda_15pct', 0.85), ('base', 1.00), ('alta_15pct', 1.15)):
        _pb_s = _preco_boi_ref * _fator
        _cx_s = simular_cenario(
            v, 'conservador', ciclo=result['tipo'],
            preco_arroba=_pb_s,
            custo_arroba=custo_arroba,
            custo_arroba_cria=_custo_fase('custo_arroba_cria'),
            custo_arroba_recria=_custo_fase('custo_arroba_recria'),
            custo_arroba_engorda=_custo_fase('custo_arroba_engorda'),
            preco_boi_arr=_pb_s,
            preco_vaca_arr=(preco_vaca * _fator) if preco_vaca else None,
            preco_bezerra_cab=(preco_bezerra * _fator) if preco_bezerra else None,
            preco_bezerro_cab=(preco_bezerro * _fator) if preco_bezerro else None,
        )
        _gc_s = _cx_s['anos'][0]['resultado']
        _dscr_s = round(_gc_s / _servico_base, 2) if _servico_base > 0 else None
        sensibilidade.append({
            'cenario': _label,
            'variacao_pct': round((_fator - 1) * 100),
            'preco_boi': round(_pb_s, 2),
            'geracao_caixa': round(_gc_s, 2),
            'dscr': _dscr_s,
            'recomendacao': (
                'aprovar'  if _dscr_s and _dscr_s >= 1.30 else
                'ressalva' if _dscr_s and _dscr_s >= 1.00 else
                'negar'    if _dscr_s is not None else None
            ),
        })

    parecer = montar_parecer(
        identificacao={'fazenda': fazenda, 'municipio': municipio,
                       'proprietario': data.get('proprietario', '')},
        composicao={'total': int(sum(v)), 'valores': v},
        indicadores=ind, benchmarks=benchmarks,
        consistencia=consistencia, financeiro=breakeven,
        geracao_caixa_anual=geracao_caixa_anual,
        credito=credito_inputs,
        fluxo_gep=fluxo_gep,
        sensibilidade=sensibilidade)

    # Persiste no histórico da fazenda apenas quando há fazenda e solicitação.
    fazenda_id = data.get('fazenda_id')
    if fazenda_id and data.get('credito_valor'):
        empresa_id = _resolver_empresa_ativa()
        if empresa_id and db.buscar_fazenda(int(fazenda_id), empresa_id):
            db.salvar_parecer(current_user.id, int(fazenda_id),
                              solicitacao=credito_inputs, parecer=parecer)

    return jsonify({
        **result,
        'indicadores': ind,
        'indicadores_benchmark': ind_bench,
        'benchmarks': benchmarks,
        'benchmarks_nacionais': painel_nacional,
        'breakeven_simples': breakeven,
        'consistencia': consistencia,
        'parecer': parecer,
        'fluxo_gep': fluxo_gep,
        'sensibilidade': sensibilidade,
        'custo_desembolso': custo_desembolso,
        'valores': v,
        'registro_id': registro_id,
    })

@app.route('/api/confirmar', methods=['POST'])
@login_required
def api_confirmar():
    """Confirma ou corrige a classificação e dispara auto-retreino em background.
       Apenas o dono do registro pode confirmar (verifica pela fazenda).
    """
    data = request.json
    rid  = data.get('registro_id')
    cls  = data.get('classificacao', '').strip().upper()
    if not rid or not cls:
        return jsonify({'erro': 'Campos registro_id e classificacao são obrigatórios'}), 400

    # Buscar o registro e verificar se a fazenda pertence à empresa ativa.
    registro = db.buscar_registro_por_id(int(rid))
    if not registro:
        return jsonify({'erro': 'Registro não encontrado'}), 404
    fazenda_nome = registro['fazenda']
    empresa_id = _resolver_empresa_ativa()
    fazendas_do_user = db.listar_fazendas(empresa_id) if empresa_id else []
    if not any(f['nome'] == fazenda_nome for f in fazendas_do_user):
        return jsonify({'erro': 'Você não tem permissão para confirmar este registro'}), 403

    try:
        db.confirmar(int(rid), cls)
        s = db.stats()
        # Dispara retreino em background se não houver um em andamento
        if not is_retraining():
            threading.Thread(target=_auto_retrain, daemon=True).start()
        return jsonify({'ok': True, 'stats': s, 'retraining': True})
    except ValueError as e:
        return jsonify({'erro': str(e)}), 400

@app.route('/api/retrain', methods=['POST'])
@login_required
def api_retrain():
    """Dispara o re-treino do modelo em background (não bloqueia)."""
    if is_retraining():
        return jsonify({'ok': False, 'mensagem': 'Re-treino já em andamento'}), 409
    threading.Thread(target=_auto_retrain, daemon=True).start()
    return jsonify({'ok': True, 'mensagem': 'Re-treino iniciado em background'})

@app.route('/api/retrain/status', methods=['GET'])
@login_required
def api_retrain_status():
    """Retorna o status atual do re-treino."""
    return jsonify({'retraining': is_retraining(), 'stats': stats})

@app.route('/api/historico', methods=['GET'])
@login_required
def api_historico():
    """Retorna o histórico de classificações da empresa ativa (registros de suas fazendas)."""
    # Busca todas as fazendas da empresa ativa
    empresa_id = _resolver_empresa_ativa()
    fazendas = db.listar_fazendas(empresa_id) if empresa_id else []
    nomes_fazendas = [f['nome'] for f in fazendas]
    if not nomes_fazendas:
        return jsonify({'registros': [], 'stats': db.stats()})

    limit = min(int(request.args.get('limit', 60)), 200)
    rows = db.listar_registros_por_fazendas(nomes_fazendas, limit=limit)
    registros = []
    for row in rows:
        registros.append({
            'id': row['id'],
            'valores': row['valores'],
            'classificacao_ml': row.get('class_ml'),
            'confianca': row.get('confianca'),
            'classificacao_confirmada': row.get('class_conf'),
            'fazenda': row.get('fazenda'),
            'municipio': row.get('municipio'),
            'data_criacao': row.get('created_at'),
            'natalidade_pct': row.get('nat_pct'),
        })
    return jsonify({'registros': registros, 'stats': db.stats()})

@app.route('/api/db-stats', methods=['GET'])
@login_required
def api_db_stats():
    s = db.stats()
    s['accuracy'] = stats.get('accuracy_mean', 0)
    s['retraining'] = is_retraining()
    return jsonify(s)

@app.route('/api/precos/live', methods=['GET'])
def api_precos_live():
    """Cotação mais recente por categoria (boi/vaca R$/@, bezerro/bezerra R$/cab).

    Quando o banco ainda não tem cotação, devolve as referências editáveis
    (bezerro de referência + bezerra derivada) para a UI sempre ter algo.
    """
    from services.precos_diarios import BEZERRO_REF, bezerra_de
    try:
        c = db.obter_cotacoes_atuais() or {}
        tem = c.get('boi', 0) > 0 or c.get('vaca', 0) > 0
        bezerro = c.get('bezerro') or BEZERRO_REF
        return jsonify({
            'ok': True,
            'origem': 'banco' if tem else 'referência',
            'precos': {
                'boi': c.get('boi', 0),
                'vaca': c.get('vaca', 0),
                'boi_china': c.get('boi_china', 0),
                'bezerro': bezerro,
                'bezerra': c.get('bezerra') or bezerra_de(bezerro),
            }
        })
    except Exception as e:
        logger.error(f"Erro ao buscar cotações: {e}", exc_info=True)
        return jsonify({'erro': str(e)}), 500

@app.route('/api/cenario', methods=['POST'])
@login_required
def api_cenario():
    data = request.json
    v = data.get('valores', [])
    cenario = data.get('cenario', 'crescimento')
    # Valida se o cenário existe
    if cenario not in CENARIOS:
        return jsonify({'erro': f'Cenário "{cenario}" não encontrado'}), 400

    params = {
        'nat_pct':       float(data.get('nat', 75)),
        'mort_pct':      float(data.get('mort', 3)),
        'desc_pct':      float(data.get('desc', 30)),
        'preco_arroba':  float(data.get('preco', 320)),
        'custo_arroba':  float(data.get('custo', 57)),
        'peso_arroba':   float(data.get('peso', 16)),
        'prop_boi':      float(data.get('propboi', 30)),
        'renov_boi_pct': float(data.get('renovboi', 20)),
        'venda_bez_pct': float(data.get('vendbez', 30)),
    }
    for fase in ('custo_arroba_cria', 'custo_arroba_recria', 'custo_arroba_engorda'):
        v_ = float(data.get(fase) or 0)
        if v_ > 0:
            params[fase] = v_
    if len(v) != 10:
        return jsonify({'erro': 'Valores inválidos'}), 400
    result = simular_cenario(v, cenario, **params)
    return jsonify(result)

@app.route('/api/cenarios', methods=['GET'])
def api_cenarios():
    return jsonify({k: {'nome': v['nome'], 'desc': v['desc'], 'emoji': v['emoji']}
                    for k, v in CENARIOS.items()})

# ── Rota: Matemática Financeira da Arroba ──────────────────────────────────
@app.route('/api/estimativa-valor', methods=['POST'])
@login_required
def api_estimativa_valor():
    """Calcula o valor estimado de um animal baseado no peso, sexo e cotação do dia."""
    data = request.json
    peso_vivo = float(data.get('peso_vivo', 0))
    sexo = data.get('sexo', 'M').upper()

    if peso_vivo <= 0:
        return jsonify({"erro": "Peso vivo inválido."}), 400

    cotacoes = db.obter_cotacoes_atuais()
    preco_arroba = cotacoes.get('boi', 0.0) if sexo == 'M' else cotacoes.get('vaca', 0.0)

    if preco_arroba == 0.0:
        return jsonify({"erro": "Cotação indisponível no banco de dados."}), 503

    peso_carcaca_arrobas = peso_vivo / 30.0
    valor_estimado = peso_carcaca_arrobas * preco_arroba

    return jsonify({
        "sexo": sexo,
        "peso_vivo_kg": peso_vivo,
        "peso_estimado_arrobas": round(peso_carcaca_arrobas, 2),
        "cotacao_aplicada": preco_arroba,
        "valor_estimado_reais": round(valor_estimado, 2)
    })

# ── Leitura de PDF ──────────────────────────────────────────────────────────
def extrair_texto_pdf(path: str) -> str:
    """Extrai texto de um PDF usando pdftotext (preferencial) ou pdfplumber."""
    try:
        result = subprocess.run(
            ['pdftotext', '-layout', path, '-'],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass  # pdftotext não instalado ou timeout — usa pdfplumber

    try:
        import pdfplumber
        text = ''
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text += (page.extract_text() or '') + '\n'
        return text
    except Exception as e:
        raise RuntimeError(f'Não foi possível extrair texto do PDF: {e}')

def detectar_origem(text: str) -> str:
    """Detecta a origem do documento com base no texto."""
    up = text.upper()
    if 'DECLARAÇÃO Nº' in up and 'IDARON' in up:
        return 'DECLARACAO_IDARON'
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

@app.route('/api/ler-pdf', methods=['POST'])
@login_required
def api_ler_pdf():
    if 'pdf' not in request.files:
        return jsonify({'erro': 'Nenhum arquivo enviado'}), 400
    f = request.files['pdf']
    if not f.filename.lower().endswith('.pdf'):
        return jsonify({'erro': 'Apenas arquivos PDF são aceitos'}), 400

    # Usa NamedTemporaryFile com delete=True para garantir remoção automática
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=True) as tmp:
        f.save(tmp.name)
        tmp_path = tmp.name  # O arquivo será excluído ao sair do with
        try:
            text = extrair_texto_pdf(tmp_path)
            orig = detectar_origem(text)
            if orig == 'DECLARACAO_IDARON':
                dados = parsear_declaracao_idaron(text)
            elif orig == 'IDARON':
                dados = parsear_idaron(text, pdf_path=tmp_path)
            elif orig == 'INDEA':
                dados = parsear_indea(text)
            else:
                # Fallback: tenta IDARON, INDEA e genérico se disponível
                dados = parsear_idaron(text, pdf_path=tmp_path)
                if dados['total'] == 0:
                    dados = parsear_indea(text)
                if dados['total'] == 0 and parsear_generico is not None:
                    dados = parsear_generico(text)
            dados['origem'] = orig
            return jsonify(dados)
        except Exception as e:
            logger.error(f"Erro ao processar PDF: {e}", exc_info=True)
            return jsonify({'erro': str(e)}), 500

@app.route('/api/template/download', methods=['GET'])
@login_required
def api_template_download():
    """Baixa o template oficial de composição de rebanho para o produtor preencher."""
    return send_from_directory(
        os.path.join(app.static_folder, 'templates'),
        'modelo_composicao_rebanho.xlsx',
        as_attachment=True,
    )


@app.route('/api/ler-planilha', methods=['POST'])
@login_required
def api_ler_planilha():
    """Lê o template preenchido e já retorna a análise de consistência do rebanho."""
    if 'planilha' not in request.files:
        return jsonify({'erro': 'Nenhum arquivo enviado'}), 400
    f = request.files['planilha']
    if not f.filename.lower().endswith(('.xlsx', '.xlsm')):
        return jsonify({'erro': 'Apenas planilhas .xlsx são aceitas'}), 400

    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=True) as tmp:
        f.save(tmp.name)
        try:
            dados = ler_template(tmp.name)
            dados['consistencia'] = analisar_consistencia(dados['valores'])
            return jsonify(dados)
        except ValueError as e:
            return jsonify({'erro': str(e)}), 400
        except Exception as e:
            logger.error(f"Erro ao processar planilha: {e}", exc_info=True)
            return jsonify({'erro': str(e)}), 500


@app.route('/api/reconciliacao', methods=['POST'])
@login_required
def api_reconciliacao():
    """Cruza o rebanho declarado em Ficha Sanitária, IR e GTA.

    Detecta garantia superavaliada (rebanho de papel > rebanho físico).
    """
    data = request.get_json() or {}
    totais = {
        'ficha': data.get('ficha'),
        'ir': data.get('ir'),
        'gta': data.get('gta'),
    }
    try:
        return jsonify(reconciliar(totais))
    except ValueError as e:
        return jsonify({'erro': str(e)}), 400
    except Exception as e:
        logger.error(f"Erro na reconciliação: {e}", exc_info=True)
        return jsonify({'erro': str(e)}), 500


@app.route('/api/parse-text', methods=['POST'])
@login_required
def api_parse_text():
    """Reprocessa um texto extraído de PDF com o parser escolhido."""
    data = request.get_json() or {}
    text = data.get('text', '')
    if not text:
        return jsonify({'erro': 'Campo "text" é obrigatório.'}), 400
    origem = data.get('origem')
    try:
        orig = origem or detectar_origem(text)
        if orig == 'IDARON':
            dados = parsear_idaron(text)
        elif orig == 'INDEA':
            dados = parsear_indea(text)
        else:
            dados = parsear_idaron(text)
            if dados['total'] == 0:
                dados = parsear_indea(text)
            if dados['total'] == 0 and parsear_generico is not None:
                dados = parsear_generico(text)
        dados['origem'] = orig
        return jsonify(dados)
    except Exception as e:
        logger.error(f"Erro no parse-text: {e}", exc_info=True)
        return jsonify({'erro': str(e)}), 500

# ─────────────────────────────────────────────
# HELPERS COMUNS (para parsers locais)
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
# PARSER INDEA-MT (mantido localmente)
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
        m_qtd = re.search(r'(\d{1,6})\s*$', line.strip())
        if not m_qtd:
            continue
        qtd = int(m_qtd.group(1))
        if qtd <= 0 or qtd > 500_000:
            continue
        sexo = _sexo_da_linha(up)
        if not sexo:
            continue
        if   '00 A 04' in up or '0 A 04' in up or '0 A 4' in up: faixa = 'f00'
        elif '05 A 12' in up or '5 A 12' in up:                  faixa = 'f05'
        elif '13 A 24' in up:                                    faixa = 'f13'
        elif '25 A 36' in up:                                    faixa = 'f25'
        elif 'ACIMA'   in up:                                    faixa = 'fac'
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
# PARSER IDARON-RO (mantido localmente)
# ─────────────────────────────────────────────
_FAIXA_PATS = [
    (r'0\s*[AÀ]\s*0?6\s*(M[EÊ]S)?|ATÉ\s*6|ATE\s*6',           'f00'),
    (r'0?7\s*[AÀ]\s*12\s*(M[EÊ]S)?',                           'f05'),
    (r'0\s*[AÀ]\s*12\s*(M[EÊ]S)?|ATÉ\s*12|ATE\s*12',           'f00_12'),
    (r'13\s*[AÀ]\s*24\s*(M[EÊ]S)?',                            'f13'),
    (r'25\s*[AÀ]\s*36\s*(M[EÊ]S)?',                            'f25'),
    (r'ACIMA|MAIOR\s*DE?\s*36|>\s*36',                         'fac'),
]

def _faixa_de_celula(cell_up: str):
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
    animais = _animais_vazios()
    if not table or len(table) < 2:
        return animais

    rows = [[str(c or '').upper().strip() for c in row] for row in table]

    faixa_col = {}
    for row in rows:
        for c_idx, cell in enumerate(row):
            f = _faixa_de_celula(cell)
            if f and c_idx not in faixa_col:
                faixa_col[c_idx] = f

    if not faixa_col:
        return animais

    sexo_col = {}
    for row in rows:
        for c_idx, cell in enumerate(row):
            if cell in ('F', 'FÊMEA', 'FEMEA') or re.match(r'^F[EÊ]MEA$', cell):
                sexo_col[c_idx] = 'F'
            elif cell in ('M', 'MACHO') or re.match(r'^MACHO$', cell):
                sexo_col[c_idx] = 'M'

    col_map = {}
    if sexo_col:
        for c_idx, sexo in sexo_col.items():
            candidatos = {fc: f for fc, f in faixa_col.items() if abs(fc - c_idx) <= 4}
            if candidatos:
                nearest = min(candidatos, key=lambda x: abs(x - c_idx))
                col_map[c_idx] = (candidatos[nearest], sexo)
    else:
        sorted_f = sorted(faixa_col.items())
        for i, (c_idx, faixa) in enumerate(sorted_f):
            col_map[c_idx] = (faixa, 'F' if i % 2 == 0 else 'M')

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
                        break
        return animais
    except Exception:
        return _animais_vazios()

def _parse_idaron_words(pdf_path: str) -> dict:
    try:
        import pdfplumber
        animais = _animais_vazios()

        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                words = page.extract_words(x_tolerance=5, y_tolerance=5)
                if not words:
                    continue

                linhas: dict[float, list] = {}
                for w in words:
                    y = round(w['top'] / 4) * 4
                    linhas.setdefault(y, []).append(w)

                faixa_x: dict[float, str] = {}
                for y, ws in linhas.items():
                    texto = ' '.join(w['text'].upper() for w in ws)
                    f = _faixa_de_celula(texto)
                    if f:
                        x_mid = sum((w['x0'] + w['x1']) / 2 for w in ws) / len(ws)
                        faixa_x[x_mid] = f

                if not faixa_x:
                    continue

                col_map: dict[float, tuple] = {}
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
                    for i, (xf, faixa) in enumerate(sorted(faixa_x.items())):
                        col_map[xf] = (faixa, 'F' if i % 2 == 0 else 'M')

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

def _parse_idaron_linhas(text: str) -> dict:
    animais = _animais_vazios()

    for line in text.split('\n'):
        up = line.upper()
        if 'BOVINO' not in up:
            continue
        m_qtd = re.search(r'(\d{1,6})\s*$', line.strip())
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
        m_qtd = re.search(r'(\d{1,6})\s*$', line.strip())
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

def parsear_idaron(text: str, pdf_path: str = None) -> dict:
    fazenda = municipio = proprietario = cpf = data_saldo = ie = ''

    m = re.search(r'\bI\.?E\.?\b[:\s]+([A-Z0-9\.\-\/]+)', text, re.I)
    if m:
        ie = m.group(1).strip()

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

    m = re.search(
        r'MUNIC[IÍ]PIO[:\s]+([A-ZÁÉÍÓÚÂÊÎÔÛÃÕÇ\s\-]+?(?:/\s*RO)?)(?:\s{2,}|\n|$)',
        text, re.I
    )
    if m:
        municipio = m.group(1).strip()

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

    animais = _animais_vazios()

    if pdf_path:
        animais = _parse_idaron_tabelas(pdf_path)

    if pdf_path and sum(animais.values()) == 0:
        animais = _parse_idaron_words(pdf_path)

    if sum(animais.values()) == 0:
        animais = _parse_idaron_linhas(text)

    valores = _para_valores(animais)
    return {
        'fazenda': fazenda, 'municipio': municipio,
        'proprietario': proprietario, 'cpf': cpf, 'ie': ie,
        'data_saldo': data_saldo, 'total': sum(valores),
        'animais': animais, 'valores': valores,
    }

# ─────────────────────────────────────────────
# PARSER DECLARAÇÃO IDARON (mantido localmente)
# ─────────────────────────────────────────────
def parsear_declaracao_idaron(text: str) -> dict:
    """
    Parser para a Declaração IDARON (formulário eletrônico).
    """
    animais = _animais_vazios()
    fazenda = municipio = proprietario = cpf = data_saldo = ''

    # Extrai dados gerais
    m = re.search(r'DECLARAÇÃO Nº\s*(\d+)', text, re.I)
    if m:
        pass  # podemos ignorar o número

    m = re.search(r'PROPRIETÁRIO[:\s]+([A-ZÁÉÍÓÚÂÊÎÔÛÃÕÇ\s]+?)(?:\n|$)', text, re.I)
    if m:
        proprietario = m.group(1).strip()

    m = re.search(r'CPF[:\s]+(\d{3}\.?\d{3}\.?\d{3}[\-\.]?\d{2})', text, re.I)
    if m:
        cpf = re.sub(r'[^\d]', '', m.group(1))

    m = re.search(r'PROPRIEDADE[:\s]+([A-ZÁÉÍÓÚÂÊÎÔÛÃÕÇ0-9\s\.\-]+?)(?:\n|$)', text, re.I)
    if m:
        fazenda = m.group(1).strip()[:60]

    m = re.search(r'MUNICÍPIO[:\s]+([A-ZÁÉÍÓÚÂÊÎÔÛÃÕÇ\s\-]+?)(?:\n|$)', text, re.I)
    if m:
        municipio = m.group(1).strip()

    m = re.search(r'DATA[:\s]+(\d{2}/\d{2}/\d{4})', text, re.I)
    if m:
        data_saldo = m.group(1)

    # Tabela de bovinos
    # Procurar por linhas com "FÊMEA" ou "MACHO" e números
    lines = text.split('\n')
    for i, line in enumerate(lines):
        up = line.upper()
        if 'BOVINO' not in up:
            continue
        # Tenta encontrar padrões como "FÊMEA 0 A 12 10" ou "MACHO 13 A 24 5"
        m = re.search(r'(FÊMEA|MACHO|FEMEA)\s+(\d+)\s*(?:[AÀ]\s*(\d+))?\s+(\d+)', up)
        if m:
            sexo = 'F' if m.group(1).startswith('F') else 'M'
            ini = int(m.group(2))
            fim = int(m.group(3)) if m.group(3) else ini
            qtd = int(m.group(4))
            if qtd <= 0 or qtd > 500_000:
                continue
            # Determina faixa
            if fim <= 6:
                faixa = 'f00'
            elif fim <= 12:
                faixa = 'f05'
            elif fim <= 24:
                faixa = 'f13'
            elif fim <= 36:
                faixa = 'f25'
            else:
                faixa = 'fac'
            animais[f'{faixa}_{sexo}'] = qtd

    # Fallback: procura por padrões mais simples
    if sum(animais.values()) == 0:
        for line in lines:
            up = line.upper()
            if 'BOVINO' not in up:
                continue
            m = re.search(r'(\d+)\s*(?:[AÀ]\s*(\d+))?\s+(FÊMEA|MACHO|FEMEA)', up)
            if m:
                qtd = int(m.group(1))
                if qtd <= 0 or qtd > 500_000:
                    continue
                sexo = 'F' if m.group(3).startswith('F') else 'M'
                # Sem faixa, tentamos inferir por outras palavras
                if 'BEZERRO' in up or 'BEZERRA' in up:
                    faixa = 'f05'
                elif 'GARROTE' in up or 'GARROTA' in up:
                    faixa = 'f13'
                elif 'NOVILHO' in up or 'NOVILHA' in up:
                    faixa = 'f25'
                elif 'VACA' in up or 'TOURO' in up or 'BOI' in up:
                    faixa = 'fac'
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
# INÍCIO DA APLICAÇÃO
# ─────────────────────────────────────────────
if __name__ == '__main__':
    logger.info("🚀 BoviML iniciado em http://localhost:5050")
    app.run(debug=True, port=5050)