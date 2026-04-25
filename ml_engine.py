"""
Fluxo de caixa — Motor de Machine Learning
Classifica tipo de exploração bovina e simula cenários financeiros.
Versão melhorada com dataset CSV grande, ensemble estável e parâmetros atualizados para Rondônia 2026.
"""
import os
import csv as _csv
import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, VotingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import cross_val_score, RepeatedStratifiedKFold, cross_val_predict
from sklearn.metrics import classification_report, confusion_matrix
import joblib
import warnings
warnings.filterwarnings('ignore')

# ==================================================================
# CONSTANTES GLOBAIS
# ==================================================================
_MODEL_PATH = os.path.join(os.path.dirname(__file__), 'gestao_model.pkl')
_CSV_PATH = os.path.join(os.path.dirname(__file__), 'dataset_sintetico_bovino.csv')
TIPOS = ['CRIA', 'RECRIA', 'ENGORDA', 'CICLO_COMPLETO']

# ==================================================================
# 1. CARREGAMENTO DO DATASET (apenas CSV)
# ==================================================================
def _carregar_dataset_csv(path: str = _CSV_PATH):
    """Carrega dataset CSV e retorna (X_list, y_list)."""
    X, y = [], []
    if not os.path.exists(path):
        return X, y
    with open(path, newline='', encoding='utf-8') as f:
        reader = _csv.DictReader(f)
        for row in reader:
            try:
                v = [
                    float(row['f00F']), float(row['f00M']),
                    float(row['f05F']), float(row['f05M']),
                    float(row['f13F']), float(row['f13M']),
                    float(row['f25F']), float(row['f25M']),
                    float(row['facF']), float(row['facM']),
                ]
                label = int(row['rotulo'])
                if label not in (0, 1, 2, 3):
                    continue
                X.append(v)
                y.append(label)
            except (KeyError, ValueError):
                continue
    return X, y

# ==================================================================
# 2. FEATURE ENGINEERING (mantido igual)
# ==================================================================
def extrair_features(
    v: list,
    taxa_natalidade: float = 0.75,
    bois_vendidos: float = None,
    bezerros_vendidos: float = None,
) -> np.ndarray:
    v = np.array(v, dtype=float)
    total = v.sum() or 1.0

    norm = v / total

    femeas_024  = v[0] + v[2] + v[4]
    machos_024  = v[1] + v[3] + v[5]
    matrizes    = v[6] + v[8]
    bois        = v[7] + v[9]
    bois_25_36  = v[7]
    bezerros_0_24 = femeas_024 + machos_024

    p_femeas_024 = femeas_024 / total
    p_machos_024 = machos_024 / total
    p_matrizes   = matrizes   / total
    p_bois       = bois       / total

    bezerros_f = v[0] / total
    bezerros_m = v[1] / total
    bezerros   = (v[0] + v[1]) / total
    recria_f   = v[4] / total
    recria_m   = v[5] / total
    recria     = (v[4] + v[5]) / total

    ratio_boi_mat = bois / max(matrizes, 1)
    ratio_mat_boi = matrizes / max(bois, 1)
    ratio_mac_fem = machos_024 / max(femeas_024, 1)
    ratio_fem_mat = femeas_024 / max(matrizes, 1)

    ciclo_score = float(
        (bezerros > 0.05) and
        (recria_f > 0.03) and
        (p_matrizes > 0.05) and
        (p_machos_024 > 0.05)
    )

    has_matrizes   = 1.0 if p_matrizes   > 0.08 else 0.0
    has_bois_adult = 1.0 if p_bois       > 0.10 else 0.0
    has_mac_recria = 1.0 if recria_m     > 0.12 else 0.0
    big_bezerros   = 1.0 if bezerros     > 0.20 else 0.0
    engorda_sig    = 1.0 if (p_bois > 0.20 and p_matrizes < 0.15) else 0.0
    cria_sig       = 1.0 if (p_matrizes > 0.20 and bezerros > 0.15) else 0.0

    # Features de fluxo
    _bois_v = bois_vendidos if bois_vendidos is not None else float(bois_25_36)
    _bez_v  = bezerros_vendidos if bezerros_vendidos is not None else (bezerros_0_24 * 0.3)

    producao_esperada      = matrizes * taxa_natalidade
    eficiencia_reprodutiva = min(bezerros_0_24 / max(producao_esperada, 1), 3.0)
    taxa_transicao         = min(bois_25_36 / max(bezerros_0_24, 1), 3.0)
    intensidade_engorda    = _bois_v / total
    intensidade_cria       = _bez_v  / total

    features = np.concatenate([
        norm,
        [p_femeas_024, p_machos_024, p_matrizes, p_bois],
        [bezerros_f, bezerros_m, bezerros, recria_f, recria_m, recria],
        [min(p_matrizes*5, 2.0), min(p_bois*5, 2.0),
         min(p_machos_024*5, 2.0), min(bezerros*5, 2.0),
         min(ratio_boi_mat, 3.0), min(ratio_mat_boi/5, 2.0),
         min(ratio_mac_fem, 3.0), min(ratio_fem_mat, 3.0)],
        [has_matrizes, has_bois_adult, has_mac_recria,
         big_bezerros, engorda_sig, cria_sig, ciclo_score],
        [producao_esperada / max(total, 1),
         eficiencia_reprodutiva,
         taxa_transicao,
         intensidade_engorda,
         intensidade_cria],
    ])
    return features

# ==================================================================
# 3. MODELO BASE (ensemble fixo e estável)
# ==================================================================
def _build_model():
    """Cria pipeline com ensemble RandomForest + GradientBoosting."""
    rf = RandomForestClassifier(
        n_estimators=300, max_depth=12, min_samples_leaf=2,
        random_state=42, n_jobs=-1, class_weight='balanced'
    )
    gb = GradientBoostingClassifier(
        n_estimators=200, learning_rate=0.05, max_depth=4,
        subsample=0.8, random_state=42
    )
    ensemble = VotingClassifier(
        estimators=[('rf', rf), ('gb', gb)], voting='soft'
    )
    return Pipeline([('scaler', StandardScaler()), ('model', ensemble)])

# ==================================================================
# 4. TREINAMENTO E PERSISTÊNCIA
# ==================================================================
_pipeline = None

def treinar_modelo():
    """Treina o ensemble com o dataset CSV grande e salva no disco."""
    global _pipeline
    X_csv, y_csv = _carregar_dataset_csv()
    if not X_csv:
        raise RuntimeError("Dataset CSV não encontrado. Execute dataset.py primeiro.")
    
    # Aplica feature engineering
    X = np.array([extrair_features(v) for v in X_csv])
    y = np.array(y_csv)
    
    print(f"Treinando com {len(X)} amostras e {X.shape[1]} features.")
    
    # Validação cruzada repetida para avaliar estabilidade
    cv = RepeatedStratifiedKFold(n_splits=5, n_repeats=3, random_state=42)
    pipeline = _build_model()
    scores_f1 = cross_val_score(pipeline, X, y, cv=cv, scoring='f1_macro')
    print(f"F1-macro médio: {scores_f1.mean():.4f} (+/- {scores_f1.std():.4f})")
    
    # Treina modelo final
    _pipeline = pipeline
    _pipeline.fit(X, y)
    
    # Métricas finais
    y_pred = _pipeline.predict(X)
    print("\nRelatório final (todos os dados):")
    print(classification_report(y, y_pred, target_names=TIPOS))
    
    cv_acc = cross_val_score(_pipeline, X, y, cv=5, scoring='accuracy')
    cv_f1 = cross_val_score(_pipeline, X, y, cv=5, scoring='f1_macro')
    result = {
        'accuracy_mean': round(float(cv_acc.mean()), 4),
        'accuracy_std': round(float(cv_acc.std()), 4),
        'f1_macro_mean': round(float(cv_f1.mean()), 4),
        'f1_macro_std': round(float(cv_f1.std()), 4),
        'n_samples': len(X),
        'n_features': X.shape[1],
        'n_csv': len(X_csv),
    }
    salvar_modelo(result)
    return result

def retrain_com_dados(X_extra: list, y_extra: list) -> dict:
    """
    Retreina o ensemble combinando o CSV original + dados confirmados.
    Mantém a mesma arquitetura do pipeline.
    """
    global _pipeline
    X_csv, y_csv = _carregar_dataset_csv()
    X_base = [extrair_features(v) for v in X_csv]
    y_base = list(y_csv)
    
    if X_extra:
        X_all = np.array(X_base + [extrair_features(v) for v in X_extra])
        y_all = np.array(y_base + list(y_extra))
    else:
        X_all = np.array(X_base)
        y_all = np.array(y_base)
    
    # Se não existe pipeline, cria um novo
    if _pipeline is None:
        _pipeline = _build_model()
    _pipeline.fit(X_all, y_all)
    
    # Estatísticas
    n_classes = len(set(y_all))
    cv = min(5, max(2, len(X_all) // max(n_classes, 1)))
    scores = cross_val_score(_pipeline, X_all, y_all, cv=cv, scoring='accuracy')
    result = {
        'accuracy_mean': round(float(scores.mean()), 4),
        'accuracy_std':  round(float(scores.std()),  4),
        'n_samples':     int(len(X_all)),
        'n_features':    int(X_all.shape[1]),
        'n_confirmados': int(len(X_extra)),
        'n_csv':         len(X_csv),
    }
    salvar_modelo(result)
    return result

def salvar_modelo(stats_dict: dict):
    try:
        joblib.dump({'pipeline': _pipeline, 'stats': stats_dict}, _MODEL_PATH)
    except Exception as e:
        print(f'[ML] Aviso: não foi possível salvar o modelo: {e}')

def carregar_modelo() -> dict | None:
    if not os.path.exists(_MODEL_PATH):
        return None
    try:
        data = joblib.load(_MODEL_PATH)
        global _pipeline
        _pipeline = data['pipeline']
        return data['stats']
    except Exception as e:
        print(f'[ML] Modelo em disco incompatível, retreinando: {e}')
        return None

# ==================================================================
# 5. CLASSIFICAÇÃO (com regras híbridas corrigidas)
# ==================================================================
def classificar(
    v: list,
    taxa_natalidade: float = 0.75,
    bois_vendidos: float = None,
    bezerros_vendidos: float = None,
) -> dict:
    if _pipeline is None:
        raise RuntimeError("Modelo não treinado.")

    va = np.array(v, dtype=float)
    total = va.sum() or 1.0
    matrizes = va[6] + va[8]
    bois_25_36 = va[7]
    bezerros_0_24 = va[0] + va[1] + va[2] + va[3] + va[4] + va[5]

    _bois_v = bois_vendidos if bois_vendidos is not None else float(bois_25_36)
    _bez_v = bezerros_vendidos if bezerros_vendidos is not None else (bezerros_0_24 * 0.3)

    producao_esperada = matrizes * taxa_natalidade
    intensidade_engorda = _bois_v / total
    intensidade_cria = _bez_v / total

    # Regra híbrida para ciclo completo (índice 0-4)
    p_matrizes_h = matrizes / total
    p_mac_13_24_h = (va[3] + va[5]) / total   # machos 5-13m + 13-25m (corrigido)
    p_bois_h = (va[7] + va[9]) / total        # todos bois adultos (corrigido)
    p_bez_h = bezerros_0_24 / total

    indice_ciclo = (
        int(p_matrizes_h > 0.15) +
        int(p_mac_13_24_h > 0.10) +
        int(p_bois_h > 0.01) +
        int(p_bez_h > 0.10)
    )

    feat = extrair_features(v, taxa_natalidade, _bois_v, _bez_v).reshape(1, -1)
    probs = _pipeline.predict_proba(feat)[0]
    prob_dict = {TIPOS[i]: round(float(p) * 100, 1) for i, p in enumerate(probs)}

    explicacao = []

    if indice_ciclo >= 4:
        tipo = 'CICLO_COMPLETO'
        confianca = max(prob_dict.get('CICLO_COMPLETO', 0.0), 85.0)
        explicacao.append(f"Regra híbrida ativada: indice_ciclo={indice_ciclo}/4 → ciclo_completo")
        explicacao.append(
            f"p_matrizes={p_matrizes_h:.2%}, p_mac_13_24={p_mac_13_24_h:.2%}, "
            f"p_bois={p_bois_h:.2%}, p_bez={p_bez_h:.2%}"
        )
    elif intensidade_engorda < 0.1:
        ml_idx = int(probs.argmax())
        ml_tipo = TIPOS[ml_idx]
        if ml_tipo == 'ENGORDA':
            tipo = 'CRIA' if probs[0] >= probs[1] else 'RECRIA'
            explicacao.append(
                f"Regra híbrida: intensidade_engorda={intensidade_engorda:.3f} < 0.1 → ENGORDA descartada"
            )
            explicacao.append(f"ML sugeria ENGORDA; substituído por {tipo}")
        else:
            tipo = ml_tipo
            explicacao.append(
                f"Regra híbrida: intensidade_engorda={intensidade_engorda:.3f} < 0.1 → priorizando cria/recria"
            )
            explicacao.append(f"ML confirmou: {tipo}")
        confianca = round(float(probs[TIPOS.index(tipo)]) * 100, 1)
    else:
        ml_idx = int(probs.argmax())
        tipo = TIPOS[ml_idx]
        confianca = round(float(probs[ml_idx]) * 100, 1)
        explicacao.append("Classificação via modelo ML (ensemble RF+GB)")
        explicacao.append(f"Confiança do modelo: {confianca}%")

    explicacao.append(
        f"Variáveis chave — matrizes={matrizes:.0f}, bois_25_36={bois_25_36:.0f}, "
        f"bezerros_0_24={bezerros_0_24:.0f}"
    )
    explicacao.append(
        f"intensidade_engorda={intensidade_engorda:.3f}, "
        f"intensidade_cria={intensidade_cria:.3f}, indice_ciclo={indice_ciclo}"
    )

    return {
        'classificacao': tipo,
        'tipo': tipo,
        'confianca': confianca,
        'probabilidades': prob_dict,
        'explicacao': explicacao,
    }

# ==================================================================
# 6. INDICADORES ZOOTÉCNICOS
# ==================================================================
def calcular_indicadores(v: list) -> dict:
    v = np.array(v, dtype=float)
    total      = v.sum() or 1
    femeas_024 = v[0]+v[2]+v[4]
    machos_024 = v[1]+v[3]+v[5]
    matrizes   = v[6]+v[8]
    bois       = v[7]+v[9]
    tot_fem    = femeas_024 + matrizes
    tot_mac    = machos_024 + bois
    cria       = v[0]+v[1]+v[2]+v[3]
    recria     = v[4]+v[5]

    return {
        'total':           int(total),
        'total_femeas':    int(tot_fem),
        'total_machos':    int(tot_mac),
        'femeas_024':      int(femeas_024),
        'machos_024':      int(machos_024),
        'matrizes':        int(matrizes),
        'bois':            int(bois),
        'fem_adultas':     int(matrizes),
        'mac_adultos':     int(bois),
        'cria':            int(cria),
        'recria':          int(recria),
        'adultos':         int(matrizes+bois),
        'pct_cria':        round(cria/total*100, 1),
        'pct_recria':      round(recria/total*100, 1),
        'pct_adultos':     round((matrizes+bois)/total*100, 1),
        'pct_matrizes':    round(matrizes/total*100, 1),
        'pct_mac_adultos': round(bois/total*100, 1),
        'ratio_fm':        round(tot_fem/max(tot_mac, 1), 2),
        'bezerros_est':    int(matrizes * 0.75),
    }

# ==================================================================
# 7. SIMULAÇÕES FINANCEIRAS (PARÂMETROS ATUALIZADOS)
# ==================================================================
def calcular_ano(
    matrizes, femeas_024, machos_024, bois,
    nat_pct, desc_mat_pct, prop_boi, renov_boi_pct,
    venda_bez_pct, mort_pct, preco_arroba, custo_cab_ano,
    peso_boi: float = 20.0, peso_vaca: float = 17.0, peso_bezerra: float = 8.0,
) -> dict:
    bezerros = matrizes * nat_pct
    bois_nec   = max(round(matrizes / max(prop_boi, 1)), 1)
    bois_exc   = max(bois - bois_nec, 0)
    renovacao       = round(bois_nec * renov_boi_pct)
    machos_024_vend = max(machos_024 - renovacao, 0)
    bois_vendidos   = bois_exc + renovacao
    desc_mat = round(matrizes * desc_mat_pct)
    bez_vend  = round(femeas_024 * venda_bez_pct)
    fem_repor = femeas_024 - bez_vend
    aumento  = fem_repor - desc_mat
    vendidos = bois_vendidos + desc_mat + bez_vend + machos_024_vend
    total_atual = matrizes + femeas_024 + machos_024 + bois
    mortes      = round(total_atual * mort_pct)
    mat_prox       = max(matrizes + aumento - round(mortes * 0.5), 0)
    bois_prox      = max(bois_nec, 1)
    femeas_024_prx = round(bezerros * 0.5)
    machos_024_prx = round(bezerros * 0.5)
    total_prox     = mat_prox + femeas_024_prx + machos_024_prx + bois_prox
    receita   = (
        bois_vendidos                * peso_boi      +
        desc_mat                     * peso_vaca     +
        (bez_vend + machos_024_vend) * peso_bezerra
    ) * preco_arroba
    custo_tot = total_prox * custo_cab_ano
    resultado = receita - custo_tot
    return {
        'bezerros_produzidos': int(bezerros),
        'bois_necessarios':    bois_nec,
        'bois_excedentes':     int(bois_exc),
        'renovacao_bois':      renovacao,
        'bois_vendidos':       int(bois_vendidos),
        'descarte_matrizes':   desc_mat,
        'bezerras_vendidas':   bez_vend,
        'machos_024_vendidos': int(machos_024_vend),
        'total_vendido':       int(vendidos),
        'aumento_matrizes':    int(aumento),
        'mortes':              mortes,
        'matrizes_prox':       int(mat_prox),
        'bois_prox':           bois_prox,
        'femeas_024_prox':     int(femeas_024_prx),
        'machos_024_prox':     int(machos_024_prx),
        'total_prox':          int(total_prox),
        'receita':             round(receita, 2),
        'custo':               round(custo_tot, 2),
        'resultado':           round(resultado, 2),
    }

# ==================================================================
# 8. CENÁRIOS ECONÔMICOS (definido ANTES das simulações)
# ==================================================================
CENARIOS = {
    'otimista': {
        'nome': 'Otimista — Melhoria Tecnológica',
        'desc': 'IATF, suplementação, genética melhorada. Alta produtividade.',
        'emoji': '🚀',
        'mods': {'nat': 1.08, 'mort': 0.70, 'desc': 0.90, 'preco': 1.05}
    },
    'crescimento': {
        'nome': 'Crescimento Gradual',
        'desc': 'Expansão sustentável com reinvestimento de resultados.',
        'emoji': '📈',
        'mods': {'nat': 1.03, 'mort': 0.90, 'desc': 0.95, 'preco': 1.02}
    },
    'especulativo': {
        'nome': 'Especulativo — Alta Venda',
        'desc': 'Maximiza venda aproveitando preço favorável.',
        'emoji': '💰',
        'mods': {'nat': 1.00, 'mort': 1.00, 'desc': 1.20, 'preco': 1.10}
    },
    'conservador': {
        'nome': 'Conservador — Manutenção',
        'desc': 'Estabilidade mínima em cenário de baixa de preços.',
        'emoji': '🛡️',
        'mods': {'nat': 0.95, 'mort': 1.10, 'desc': 0.80, 'preco': 0.95}
    },
}

def _montar_resultado(cenario, sc, anos_proj, total_ini, ciclo):
    return {
        'cenario': cenario,
        'nome': sc['nome'],
        'emoji': sc['emoji'],
        'ciclo': ciclo,
        'anos': anos_proj,
        'acumulado': {
            'receita':   round(sum(a['receita']   for a in anos_proj), 2),
            'custo':     round(sum(a['custo']     for a in anos_proj), 2),
            'resultado': round(sum(a['resultado'] for a in anos_proj), 2),
        },
        'delta_rebanho': anos_proj[-1]['total'] - int(total_ini),
    }

def _simular_cria(
    v, cenario, nat_pct, mort_pct, desmama_pct, venda_bez_pct,
    preco_bezerro, custo_cab_ano, anos,
):
    va  = np.array(v, dtype=float)
    sc  = CENARIOS.get(cenario, CENARIOS['crescimento'])
    m   = sc['mods']

    nat      = min((nat_pct / 100) * m['nat'], 0.95)
    mort     = (mort_pct / 100) * m['mort']
    desmama  = (desmama_pct / 100)
    venda_bz = (venda_bez_pct / 100)
    preco_bz = preco_bezerro * m['preco']

    matrizes    = float(va[6] + va[8])
    fem_recria  = float(va[0] + va[2] + va[4])
    total_ini   = float(va.sum())

    anos_proj = []
    for yr in range(1, anos + 1):
        nascidos      = matrizes * nat
        desmamados    = nascidos * desmama * (1 - mort)
        vez_vendidos  = desmamados * venda_bz
        machos_vend   = vez_vendidos * 0.5
        femeas_vend   = vez_vendidos * 0.5
        bezerras_ret  = (desmamados - vez_vendidos) * 0.5

        descarte_mat  = round(matrizes * 0.15)
        matrizes_prox = max(matrizes + bezerras_ret - descarte_mat, matrizes * 0.7)
        total_prox    = int(matrizes_prox + bezerras_ret)
        mortes        = round((matrizes + fem_recria) * mort)

        receita  = vez_vendidos * preco_bz
        custo    = (matrizes + fem_recria) * custo_cab_ano
        resultado = receita - custo

        anos_proj.append({
            'ano': yr,
            'total': total_prox,
            'matrizes': int(matrizes_prox),
            'bezerros': int(nascidos),
            'vendidos': int(vez_vendidos),
            'bois_vendidos': int(machos_vend),
            'matrizes_descartadas': descarte_mat,
            'bezerras_vendidas': int(femeas_vend),
            'machos_vendidos': int(machos_vend),
            'aumento_matrizes': int(bezerras_ret - descarte_mat),
            'receita': round(receita, 2),
            'custo': round(custo, 2),
            'resultado': round(resultado, 2),
        })
        matrizes   = matrizes_prox
        fem_recria = bezerras_ret

    result = _montar_resultado(cenario, sc, anos_proj, total_ini, 'CRIA')
    ano1 = anos_proj[0]
    units = float(max(ano1['vendidos'], 1))
    result.update({
        'preco_breakeven':         round(ano1['custo'] / units, 2),
        'preco_breakeven_unidade': 'R$/cabeça',
        'preco_usado':             preco_bz,
        'slider_units':            units,
        'slider_custo_ano1':       ano1['custo'],
        'margem_atual_pct':        round(ano1['resultado'] / max(ano1['custo'], 1) * 100, 1),
        'margem_atual_rs':         round(ano1['resultado'], 2),
    })
    return result

def _simular_recria(
    v, cenario, mort_pct, preco_arroba, peso_entrada_arr, peso_saida_arr,
    meses_recria, custo_cab_mes, anos,
):
    va  = np.array(v, dtype=float)
    sc  = CENARIOS.get(cenario, CENARIOS['crescimento'])
    m   = sc['mods']

    mort  = (mort_pct / 100) * m['mort']
    preco = preco_arroba * m['preco']

    # Animais em recria = machos 5–25 meses (corrigido)
    animais   = float(va[3] + va[5])
    total_ini = float(va.sum())

    anos_proj = []
    for yr in range(1, anos + 1):
        mortes       = animais * mort
        animais_sai  = animais - mortes
        ganho_arr    = peso_saida_arr - peso_entrada_arr

        receita   = animais_sai * peso_saida_arr * preco
        custo     = animais * meses_recria * custo_cab_mes
        resultado = receita - custo

        # Crescimento simplificado (limitado a 5% ao ano)
        animais_prox = animais * (1 + min(0.05, 0.04 * m['nat']))

        anos_proj.append({
            'ano': yr,
            'total': int(animais_prox),
            'matrizes': 0,
            'bezerros': 0,
            'vendidos': int(animais_sai),
            'bois_vendidos': int(animais_sai),
            'matrizes_descartadas': 0,
            'bezerras_vendidas': 0,
            'machos_vendidos': int(animais_sai),
            'aumento_matrizes': 0,
            'ganho_arrobas_por_animal': round(ganho_arr, 2),
            'receita': round(receita, 2),
            'custo': round(custo, 2),
            'resultado': round(resultado, 2),
        })
        animais = animais_prox

    result = _montar_resultado(cenario, sc, anos_proj, total_ini, 'RECRIA')
    ano1 = anos_proj[0]
    units = float(max(ano1['vendidos'], 1)) * peso_saida_arr
    result.update({
        'preco_breakeven':         round(ano1['custo'] / max(units, 1), 2),
        'preco_breakeven_unidade': 'R$/arroba',
        'preco_usado':             preco,
        'slider_units':            round(units, 2),
        'slider_custo_ano1':       ano1['custo'],
        'margem_atual_pct':        round(ano1['resultado'] / max(ano1['custo'], 1) * 100, 1),
        'margem_atual_rs':         round(ano1['resultado'], 2),
    })
    return result

def _simular_engorda(
    v, cenario, mort_pct, preco_arroba, peso_entrada_kg, peso_saida_kg,
    rendimento_carcaca, custo_cab_dia, dias_engorda, anos,
):
    va  = np.array(v, dtype=float)
    sc  = CENARIOS.get(cenario, CENARIOS['crescimento'])
    m   = sc['mods']

    mort  = (mort_pct / 100) * m['mort']
    preco = preco_arroba * m['preco']
    rend  = rendimento_carcaca / 100

    # Bois em engorda = machos adultos (25m+)
    bois      = float(va[7] + va[9])
    total_ini = float(va.sum())
    lotes_ano = max(1, int(365 / max(dias_engorda, 30)))

    anos_proj = []
    for yr in range(1, anos + 1):
        bois_no_ano   = bois * lotes_ano
        mortes        = bois_no_ano * mort
        bois_abatidos = bois_no_ano - mortes

        arrobas_por_boi = (peso_saida_kg * rend) / 15.0
        receita   = bois_abatidos * arrobas_por_boi * preco
        custo     = bois_no_ano * dias_engorda * custo_cab_dia
        resultado = receita - custo

        bois_prox = bois * (1 + min(0.05, 0.04 * m['nat']))

        anos_proj.append({
            'ano': yr,
            'total': int(bois_prox),
            'matrizes': 0,
            'bezerros': 0,
            'vendidos': int(bois_abatidos),
            'bois_vendidos': int(bois_abatidos),
            'matrizes_descartadas': 0,
            'bezerras_vendidas': 0,
            'machos_vendidos': int(bois_abatidos),
            'aumento_matrizes': 0,
            'arrobas_por_boi': round(arrobas_por_boi, 2),
            'lotes_por_ano': lotes_ano,
            'ganho_peso_kg': round(peso_saida_kg - peso_entrada_kg, 1),
            'receita': round(receita, 2),
            'custo': round(custo, 2),
            'resultado': round(resultado, 2),
        })
        bois = bois_prox

    result = _montar_resultado(cenario, sc, anos_proj, total_ini, 'ENGORDA')
    ano1 = anos_proj[0]
    arrobas_por_boi_be = (peso_saida_kg * rend) / 15.0
    units = float(max(ano1['vendidos'], 1)) * arrobas_por_boi_be
    result.update({
        'preco_breakeven':         round(ano1['custo'] / max(units, 1), 2),
        'preco_breakeven_unidade': 'R$/arroba',
        'preco_usado':             preco,
        'slider_units':            round(units, 2),
        'slider_custo_ano1':       ano1['custo'],
        'margem_atual_pct':        round(ano1['resultado'] / max(ano1['custo'], 1) * 100, 1),
        'margem_atual_rs':         round(ano1['resultado'], 2),
    })
    return result

def simular_cenario(
    v: list,
    cenario:        str   = 'crescimento',
    nat_pct:        float = 65.0,      # atualizado
    mort_pct:       float = 4.0,       # atualizado
    desc_pct:       float = 30.0,
    preco_arroba:   float = 340.0,     # atualizado
    custo_cab_ano:  float = 950.0,     # atualizado
    peso_arroba:    float = 16.0,
    prop_boi:       float = 30.0,
    renov_boi_pct:  float = 20.0,
    venda_bez_pct:  float = 30.0,
    anos:           int   = 5,
    ciclo:              str   = 'CICLO_COMPLETO',
    preco_bezerro:      float = 2960.0,   # atualizado
    desmama_pct:        float = 75.0,     # atualizado
    peso_entrada_arr:   float = 13.33,    # 200 kg
    peso_saida_arr:     float = 20.0,     # 300 kg
    meses_recria:       int   = 12,
    custo_cab_mes:      float = 67.0,     # atualizado
    peso_entrada_kg:    float = 450.0,
    peso_saida_kg:      float = 540.0,    # atualizado
    rendimento_carcaca: float = 52.0,
    custo_cab_dia:      float = 13.76,    # atualizado
    dias_engorda:       int   = 90,
    peso_boi:           float = 20.0,
    peso_vaca:          float = 17.0,
) -> dict:
    if ciclo == 'CRIA':
        return _simular_cria(
            v, cenario, nat_pct, mort_pct, desmama_pct, venda_bez_pct,
            preco_bezerro, custo_cab_ano, anos,
        )
    if ciclo == 'RECRIA':
        return _simular_recria(
            v, cenario, mort_pct, preco_arroba, peso_entrada_arr, peso_saida_arr,
            meses_recria, custo_cab_mes, anos,
        )
    if ciclo == 'ENGORDA':
        return _simular_engorda(
            v, cenario, mort_pct, preco_arroba, peso_entrada_kg, peso_saida_kg,
            rendimento_carcaca, custo_cab_dia, dias_engorda, anos,
        )

    # CICLO_COMPLETO
    va  = np.array(v, dtype=float)
    sc  = CENARIOS.get(cenario, CENARIOS['crescimento'])
    m   = sc['mods']

    nat  = min((nat_pct  / 100) * m['nat'],  0.95)
    mort = (mort_pct / 100) * m['mort']
    desc = min((desc_pct / 100) * m['desc'], 0.99)

    femeas_024 = float(va[0]+va[2]+va[4])
    machos_024 = float(va[1]+va[3]+va[5])
    matrizes   = float(va[6]+va[8])
    bois       = float(va[7]+va[9])
    total_ini  = float(va.sum())

    anos_proj = []
    for yr in range(1, anos + 1):
        r = calcular_ano(
            matrizes=matrizes, femeas_024=femeas_024,
            machos_024=machos_024, bois=bois,
            nat_pct=nat, desc_mat_pct=desc,
            prop_boi=prop_boi, renov_boi_pct=renov_boi_pct/100,
            venda_bez_pct=venda_bez_pct/100,
            mort_pct=mort,
            preco_arroba=preco_arroba * m['preco'],
            custo_cab_ano=custo_cab_ano,
            peso_boi=peso_boi,
            peso_vaca=peso_vaca,
            peso_bezerra=peso_arroba,
        )
        anos_proj.append({
            'ano':      yr,
            'total':    r['total_prox'],
            'matrizes': r['matrizes_prox'],
            'bezerros': r['bezerros_produzidos'],
            'vendidos': r['total_vendido'],
            'bois_vendidos':        r['bois_vendidos'],
            'matrizes_descartadas': r['descarte_matrizes'],
            'bezerras_vendidas':    r['bezerras_vendidas'],
            'machos_vendidos':      r['machos_024_vendidos'],
            'aumento_matrizes':     r['aumento_matrizes'],
            'receita':   r['receita'],
            'custo':     r['custo'],
            'resultado': r['resultado'],
        })
        matrizes   = float(r['matrizes_prox'])
        bois       = float(r['bois_prox'])
        femeas_024 = float(r['femeas_024_prox'])
        machos_024 = float(r['machos_024_prox'])

    result = _montar_resultado(cenario, sc, anos_proj, total_ini, 'CICLO_COMPLETO')
    ano1 = anos_proj[0]
    preco_adj = preco_arroba * m['preco']
    bv = float(ano1.get('bois_vendidos', 0))
    dv = float(ano1.get('matrizes_descartadas', 0))
    ov = float(max(ano1['vendidos'] - bv - dv, 0))
    peso_medio = (bv * peso_boi + dv * peso_vaca + ov * peso_arroba) / max(ano1['vendidos'], 1)
    units = float(max(ano1['vendidos'], 1)) * peso_medio
    result.update({
        'preco_breakeven':         round(ano1['custo'] / max(units, 1), 2),
        'preco_breakeven_unidade': 'R$/arroba',
        'preco_usado':             preco_adj,
        'slider_units':            round(units, 2),
        'slider_custo_ano1':       ano1['custo'],
        'margem_atual_pct':        round(ano1['resultado'] / max(ano1['custo'], 1) * 100, 1),
        'margem_atual_rs':         round(ano1['resultado'], 2),
    })
    return result

# ==================================================================
# 9. BENCHMARKS REGIONAIS (RONDÔNIA 2026)
# ==================================================================
BENCHMARKS_RO = {
    'natalidade': {
        'label': 'Taxa de Natalidade',
        'unidade': '%',
        'faixas': {'abaixo': 55.0, 'medio': 65.0, 'bom': 75.0},
        'inverso': False,
        'ciclos': ['CRIA', 'CICLO_COMPLETO'],
    },
    'mortalidade': {
        'label': 'Mortalidade Geral',
        'unidade': '%',
        'faixas': {'abaixo': 7.0, 'medio': 5.0, 'bom': 3.0},
        'inverso': True,
        'ciclos': ['CRIA', 'RECRIA', 'ENGORDA', 'CICLO_COMPLETO'],
    },
    'desmama': {
        'label': 'Taxa de Desmama',
        'unidade': '%',
        'faixas': {'abaixo': 65.0, 'medio': 72.0, 'bom': 80.0},
        'inverso': False,
        'ciclos': ['CRIA', 'CICLO_COMPLETO'],
    },
    'relacao_fm': {
        'label': 'Relação Fêmeas/Macho Adulto',
        'unidade': ':1',
        'faixas': {'abaixo': 1.8, 'medio': 2.2, 'bom': 2.8},
        'inverso': False,
        'ciclos': ['CRIA', 'CICLO_COMPLETO'],
    },
    'pct_matrizes': {
        'label': '% Matrizes no Rebanho',
        'unidade': '%',
        'faixas': {'abaixo': 28.0, 'medio': 35.0, 'bom': 42.0},
        'inverso': False,
        'ciclos': ['CRIA', 'CICLO_COMPLETO'],
    },
    'ganho_peso_arr': {
        'label': 'Ganho de Peso (kg/dia)',
        'unidade': 'kg/dia',
        'faixas': {'abaixo': 0.4, 'medio': 0.55, 'bom': 0.7},
        'inverso': False,
        'ciclos': ['RECRIA'],
    },
    'rend_carcaca': {
        'label': 'Rendimento de Carcaça',
        'unidade': '%',
        'faixas': {'abaixo': 50.0, 'medio': 52.0, 'bom': 54.0},
        'inverso': False,
        'ciclos': ['ENGORDA', 'CICLO_COMPLETO'],
    },
}

def _classificar_faixa(valor: float, faixas: dict, inverso: bool = False) -> tuple:
    t_a, t_m, t_b = faixas['abaixo'], faixas['medio'], faixas['bom']
    if not inverso:
        if valor >= t_b:
            return 'excelente', None, 0.0
        elif valor >= t_m:
            return 'bom', 'excelente', round(t_b - valor, 2)
        elif valor >= t_a:
            return 'medio', 'bom', round(t_m - valor, 2)
        else:
            return 'abaixo', 'medio', round(t_a - valor, 2)
    else:
        if valor <= t_b:
            return 'excelente', None, 0.0
        elif valor <= t_m:
            return 'bom', 'excelente', round(valor - t_b, 2)
        elif valor <= t_a:
            return 'medio', 'bom', round(valor - t_m, 2)
        else:
            return 'abaixo', 'medio', round(valor - t_a, 2)

def avaliar_benchmarks(ciclo: str, indicadores: dict) -> list:
    resultado = []
    for key, cfg in BENCHMARKS_RO.items():
        if ciclo not in cfg['ciclos']:
            continue
        valor = indicadores.get(key)
        if valor is None:
            continue
        faixa, proximo, falta = _classificar_faixa(
            float(valor), cfg['faixas'], cfg.get('inverso', False)
        )
        resultado.append({
            'key': key,
            'label': cfg['label'],
            'valor': round(float(valor), 2),
            'unidade': cfg['unidade'],
            'faixa': faixa,
            'proximo_nivel': proximo,
            'falta': falta,
        })
    return resultado

def calcular_breakeven_simples(v: list, ciclo: str) -> dict:
    """Estimativa rápida do breakeven usando parâmetros atualizados para Rondônia."""
    va = np.array(v, dtype=float)
    custo_cab_ano = 950.0

    if ciclo == 'CRIA':
        matrizes  = float(va[6] + va[8])
        total     = float(va.sum()) or 1.0
        custo     = total * custo_cab_ano
        bezerros  = matrizes * 0.65 * 0.75 * 0.60   # nat 65%, desmama 75%, venda 60%
        if bezerros <= 0:
            return {}
        return {'preco_breakeven': round(custo / bezerros, 2), 'unidade': 'R$/cabeça'}

    if ciclo == 'RECRIA':
        # 12 meses * R$67 / 20 arrobas
        be = round((12 * 67.0) / 20.0, 2)
        return {'preco_breakeven': be, 'unidade': 'R$/arroba'}

    if ciclo == 'ENGORDA':
        arrobas = (540.0 * 0.52) / 15.0   # 18.72 @
        be = round((90 * 13.76) / arrobas, 2)
        return {'preco_breakeven': be, 'unidade': 'R$/arroba'}

    # CICLO_COMPLETO
    total   = float(va.sum()) or 1.0
    custo   = total * custo_cab_ano
    units   = total * 0.30 * 18.0   # 30% do rebanho produz 18 arrobas em média
    return {'preco_breakeven': round(custo / max(units, 1), 2), 'unidade': 'R$/arroba'}