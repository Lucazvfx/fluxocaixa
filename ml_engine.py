"""
Fluxo de caixa — Motor de Machine Learning
Classifica tipo de exploração bovina usando scikit-learn, XGBoost e redes neurais.
Lógica de simulação baseada no modelo de ciclo completo documentado.
"""
import os
import csv as _csv
import numpy as np
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, VotingClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.model_selection import cross_val_score, StratifiedKFold, cross_val_predict, GridSearchCV
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from xgboost import XGBClassifier
import joblib
import warnings
warnings.filterwarnings('ignore')

_MODEL_PATH = os.path.join(os.path.dirname(__file__), 'boviml_model.pkl')

def salvar_modelo(stats_dict: dict):
    """Persiste o pipeline treinado e as métricas em disco."""
    try:
        joblib.dump({'pipeline': _pipeline, 'stats': stats_dict}, _MODEL_PATH)
    except Exception as e:
        print(f'[ML] Aviso: não foi possível salvar o modelo: {e}')

def carregar_modelo() -> dict | None:
    """
    Tenta carregar o modelo salvo em disco.
    Retorna as métricas salvas ou None se não existir / incompatível.
    """
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

_CSV_PATH = os.path.join(os.path.dirname(__file__), 'dataset_sintetico_bovino.csv')

def _carregar_dataset_csv(path: str = _CSV_PATH):
    """Carrega dataset CSV e retorna (X_list, y_list). Ignora linhas inválidas."""
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

TIPOS = ['CRIA', 'RECRIA', 'ENGORDA', 'CICLO_COMPLETO']

# ─────────────────────────────────────────────
# DADOS DE TREINAMENTO (sintéticos)
# v = [f00F, f00M, f05F, f05M, f13F, f13M, f25F, f25M, facF, facM]
# CRIA=0  RECRIA=1  ENGORDA=2  CICLO_COMPLETO=3
# ─────────────────────────────────────────────
TRAIN_X = [
    # CRIA: muitas matrizes adultas, bezerros, poucos machos recria/engorda
    [300,280,200,80,100,40,150,10,600,15],
    [250,230,180,70,80,30,120,8,550,12],
    [400,380,280,100,120,50,200,12,800,20],
    [150,140,100,40,60,20,80,5,350,8],
    [500,480,350,120,150,60,250,15,1000,25],
    [600,580,420,140,180,70,300,18,1200,30],
    [80,75,60,22,35,12,50,3,220,5],
    [450,430,310,110,140,55,230,14,900,22],
    [120,115,85,30,45,16,70,4,300,7],
    [700,670,490,160,210,80,350,22,1400,35],
    [200,195,140,50,70,25,100,6,450,11],
    [350,340,240,85,100,38,160,10,700,17],
    [90,88,65,24,40,14,55,3,250,6],
    [1000,960,700,230,300,110,500,30,2000,50],
    [60,58,45,16,25,9,35,2,170,4],
    # RECRIA: concentração em machos 13-24m, poucas matrizes adultas
    [50,45,80,70,400,600,100,80,80,20],
    [30,28,60,55,350,550,80,70,60,15],
    [70,65,100,90,500,700,120,100,100,25],
    [20,18,40,38,250,400,60,55,40,10],
    [90,85,120,110,600,800,150,120,120,30],
    [15,14,30,28,160,650,45,80,30,40],
    [25,22,45,40,300,900,70,100,50,12],
    [60,55,90,85,550,750,110,95,90,22],
    [10,9,20,18,180,480,40,60,25,8],
    [40,36,65,60,420,620,95,85,75,18],
    [5,4,12,10,100,350,25,40,15,5],
    [80,75,110,100,700,950,160,140,130,32],
    [35,32,55,50,380,580,85,75,65,16],
    [100,95,140,130,800,1100,180,160,150,38],
    [45,42,70,65,480,700,110,95,85,20],
    # ENGORDA: machos adultos 25m+ dominam, poucas femeas
    [10,8,20,18,50,80,20,120,10,400],
    [5,4,10,8,30,60,10,90,5,300],
    [15,12,25,22,60,100,25,150,12,500],
    [8,6,15,12,40,70,15,110,8,350],
    [3,2,8,6,20,45,8,70,4,220],
    [20,18,30,28,70,120,30,180,15,600],
    [12,10,18,16,55,90,20,130,10,430],
    [6,5,12,10,35,65,12,100,6,280],
    [25,22,35,32,80,140,35,200,18,700],
    [18,16,28,25,65,110,28,160,14,560],
    [2,1,5,4,15,35,6,55,3,180],
    [30,28,45,40,100,170,40,240,22,800],
    [9,8,16,14,48,82,18,120,9,390],
    [50,45,70,65,160,280,60,400,35,1200],
    [7,6,13,11,42,72,16,105,8,320],
    # CICLO COMPLETO: todas faixas representadas, matrizes + recria + adultos
    [300,280,400,200,900,1200,250,80,600,40],
    [250,230,350,180,800,1100,220,70,550,35],
    [400,380,500,250,1000,1400,300,100,700,45],
    [200,180,300,150,700,1000,200,65,500,32],
    [150,140,250,120,600,900,180,55,400,28],
    [500,480,600,300,1200,1600,350,120,800,50],
    [350,330,450,220,950,1300,280,90,650,42],
    [180,160,280,140,650,950,210,60,450,30],
    [100,90,180,90,450,700,150,45,320,20],
    [600,570,720,360,1400,1900,420,140,950,60],
    [280,260,380,190,850,1150,260,85,620,40],
    [120,110,200,100,500,750,160,50,380,24],
    [420,400,540,270,1050,1450,320,105,750,48],
    [80,75,140,70,380,560,120,38,290,18],
    [700,665,840,420,1600,2200,480,160,1100,70],
]

TRAIN_Y = (
    [0]*15 +   # CRIA
    [1]*15 +   # RECRIA
    [2]*15 +   # ENGORDA
    [3]*15     # CICLO_COMPLETO
)

# ─────────────────────────────────────────────
# FEATURE ENGINEERING (mantido igual)
# ─────────────────────────────────────────────
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

    # ── Features derivadas de fluxo ──────────────────────────────────────
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
        # novas features de fluxo (5)
        [producao_esperada / max(total, 1),
         eficiencia_reprodutiva,
         taxa_transicao,
         intensidade_engorda,
         intensidade_cria],
    ])
    return features

# ─────────────────────────────────────────────
# COMPARAÇÃO DE MODELOS (NOVO)
# ─────────────────────────────────────────────
def comparar_modelos(X, y, cv_folds=5):
    """
    Compara diferentes algoritmos usando validação cruzada estratificada.
    Exibe F1-score (macro), matriz de confusão e relatório de classificação.
    Retorna o melhor pipeline (já treinado nos dados completos).
    """
    modelos = {
        'RandomForest': RandomForestClassifier(
            n_estimators=300, max_depth=12, min_samples_leaf=2,
            random_state=42, n_jobs=-1, class_weight='balanced'
        ),
        'GradientBoosting': GradientBoostingClassifier(
            n_estimators=200, learning_rate=0.05, max_depth=4,
            subsample=0.8, random_state=42
        ),
        'XGBoost': XGBClassifier(
            n_estimators=200, learning_rate=0.1, max_depth=5,
            random_state=42, eval_metric='mlogloss', use_label_encoder=False
        ),
        'MLP (Rede Neural)': MLPClassifier(
            hidden_layer_sizes=(100, 50), max_iter=500, random_state=42,
            early_stopping=True, validation_fraction=0.1
        ),
        'Ensemble (RF+GB)': VotingClassifier(
            estimators=[
                ('rf', RandomForestClassifier(n_estimators=300, max_depth=12, random_state=42)),
                ('gb', GradientBoostingClassifier(n_estimators=200, learning_rate=0.05, random_state=42))
            ], voting='soft'
        )
    }
    
    cv = StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=42)
    resultados = {}
    
    for nome, modelo_raw in modelos.items():
        # Cria pipeline com scaler (essencial para MLP e XGBoost, não prejudica árvores)
        pipeline = Pipeline([('scaler', StandardScaler()), ('model', modelo_raw)])
        
        scores_f1 = cross_val_score(pipeline, X, y, cv=cv, scoring='f1_macro')
        print(f"\n{'='*50}")
        print(f"📊 {nome}")
        print(f"F1-macro médio: {scores_f1.mean():.4f} (+/- {scores_f1.std():.4f})")
        
        y_pred = cross_val_predict(pipeline, X, y, cv=cv)
        print("\nMatriz de confusão (total dos folds):")
        print(confusion_matrix(y, y_pred))
        print("\nRelatório de classificação (média macro):")
        print(classification_report(y, y_pred, target_names=TIPOS))
        
        # Treina modelo final em todos os dados
        pipeline.fit(X, y)
        resultados[nome] = {
            'pipeline': pipeline,
            'f1_mean': scores_f1.mean(),
            'f1_std': scores_f1.std()
        }
    
    melhor_nome = max(resultados, key=lambda k: resultados[k]['f1_mean'])
    print(f"\n🏆 Melhor modelo: {melhor_nome} (F1={resultados[melhor_nome]['f1_mean']:.4f})")
    return resultados[melhor_nome]['pipeline']


# ─────────────────────────────────────────────
# TREINAMENTO PRINCIPAL (MODIFICADO)
# ─────────────────────────────────────────────
_pipeline = None

def treinar_modelo(otimizar_hiperparams=True):
    """
    Treina o modelo usando comparação entre vários algoritmos.
    Opcionalmente realiza hyperparameter tuning no melhor modelo.
    Retorna estatísticas de desempenho.
    """
    global _pipeline
    
    # Carrega dados
    X_csv, y_csv = _carregar_dataset_csv()
    X_all = [extrair_features(v) for v in TRAIN_X] + [extrair_features(v) for v in X_csv]
    y_all = list(TRAIN_Y) + y_csv
    X = np.array(X_all)
    y = np.array(y_all)
    
    # 1. Compara modelos base
    melhor_pipeline = comparar_modelos(X, y, cv_folds=5)
    
    # 2. Hyperparameter tuning (se for XGBoost e solicitado)
    if otimizar_hiperparams and isinstance(melhor_pipeline.named_steps['model'], XGBClassifier):
        print("\n🔍 Otimizando hiperparâmetros do XGBoost com GridSearchCV...")
        param_grid = {
            'model__n_estimators': [100, 200, 300],
            'model__max_depth': [3, 5, 7],
            'model__learning_rate': [0.01, 0.05, 0.1],
            'model__subsample': [0.8, 1.0]
        }
        grid = GridSearchCV(
            melhor_pipeline, param_grid, cv=5, scoring='f1_macro', n_jobs=-1, verbose=1
        )
        grid.fit(X, y)
        melhor_pipeline = grid.best_estimator_
        print(f"✅ Melhores parâmetros: {grid.best_params_}")
        print(f"Melhor F1-macro (CV): {grid.best_score_:.4f}")
    elif otimizar_hiperparams and isinstance(melhor_pipeline.named_steps['model'], MLPClassifier):
        print("\n🔍 Otimizando hiperparâmetros da MLP...")
        param_grid = {
            'model__hidden_layer_sizes': [(50,), (100,), (100, 50)],
            'model__alpha': [0.0001, 0.001, 0.01],
            'model__learning_rate_init': [0.001, 0.01]
        }
        grid = GridSearchCV(
            melhor_pipeline, param_grid, cv=5, scoring='f1_macro', n_jobs=-1, verbose=1
        )
        grid.fit(X, y)
        melhor_pipeline = grid.best_estimator_
        print(f"✅ Melhores parâmetros: {grid.best_params_}")
        print(f"Melhor F1-macro (CV): {grid.best_score_:.4f}")
    
    _pipeline = melhor_pipeline
    
    # Avaliação final no dataset completo
    y_pred = _pipeline.predict(X)
    print("\n📈 Relatório final (todos os dados):")
    print(classification_report(y, y_pred, target_names=TIPOS))
    
    # Métricas para salvar
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


# ─────────────────────────────────────────────
# MODELO ORIGINAL (para retreinamento com dados confirmados)
# ─────────────────────────────────────────────
def _build_model():
    """Modelo ensemble original (usado por retrain_com_dados para compatibilidade)."""
    rf = RandomForestClassifier(
        n_estimators=300, max_depth=12,
        min_samples_leaf=2, random_state=42, n_jobs=-1,
        class_weight='balanced',
    )
    gb = GradientBoostingClassifier(
        n_estimators=200, learning_rate=0.05,
        max_depth=4, subsample=0.8, random_state=42
    )
    ensemble = VotingClassifier(
        estimators=[('rf', rf), ('gb', gb)], voting='soft'
    )
    return Pipeline([('scaler', StandardScaler()), ('model', ensemble)])


def retrain_com_dados(X_extra: list, y_extra: list) -> dict:
    """
    Retreina o ensemble original combinando os dados de treino originais com
    registros confirmados pelo usuário armazenados no BD SQLite.
    Quanto mais confirmações, mais preciso o modelo fica para o rebanho local.
    """
    global _pipeline
    X_csv, y_csv = _carregar_dataset_csv()
    X_base = [extrair_features(v) for v in TRAIN_X] + [extrair_features(v) for v in X_csv]
    y_base = list(TRAIN_Y) + y_csv

    if X_extra:
        X_all = np.array(X_base + [extrair_features(v) for v in X_extra])
        y_all = np.array(y_base + list(y_extra))
    else:
        X_all = np.array(X_base)
        y_all = np.array(y_base)

    _pipeline = _build_model()
    _pipeline.fit(X_all, y_all)

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


# ─────────────────────────────────────────────
# CLASSIFICAÇÃO (mantida exatamente igual)
# ─────────────────────────────────────────────
def classificar(
    v: list,
    taxa_natalidade: float = 0.75,
    bois_vendidos: float = None,
    bezerros_vendidos: float = None,
) -> dict:
    if _pipeline is None:
        raise RuntimeError("Modelo nao treinado.")

    va            = np.array(v, dtype=float)
    total         = va.sum() or 1.0
    matrizes      = va[6] + va[8]
    bois_25_36    = va[7]
    bezerros_0_24 = va[0] + va[1] + va[2] + va[3] + va[4] + va[5]

    _bois_v = bois_vendidos  if bois_vendidos  is not None else float(bois_25_36)
    _bez_v  = bezerros_vendidos if bezerros_vendidos is not None else (bezerros_0_24 * 0.3)

    producao_esperada   = matrizes * taxa_natalidade
    intensidade_engorda = _bois_v / total
    intensidade_cria    = _bez_v  / total

    # Regra híbrida CICLO_COMPLETO
    p_matrizes_h   = matrizes / total
    p_mac_13_24_h  = float(va[5]) / total
    p_bois_h       = bois_25_36 / total
    p_bez_h        = bezerros_0_24 / total

    indice_ciclo = (
        int(p_matrizes_h  > 0.15) +
        int(p_mac_13_24_h > 0.10) +
        int(p_bois_h      > 0.01) +
        int(p_bez_h       > 0.10)
    )

    feat  = extrair_features(v, taxa_natalidade, _bois_v, _bez_v).reshape(1, -1)
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
        ml_idx  = int(probs.argmax())
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
        ml_idx    = int(probs.argmax())
        tipo      = TIPOS[ml_idx]
        confianca = round(float(probs[ml_idx]) * 100, 1)
        explicacao.append("Classificação via modelo ML (após otimização)")
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
        'tipo':          tipo,
        'confianca':     confianca,
        'probabilidades': prob_dict,
        'explicacao':    explicacao,
    }


# ─────────────────────────────────────────────
# INDICADORES (mantido igual)
# ─────────────────────────────────────────────
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


# ─────────────────────────────────────────────
# CÁLCULO ANUAL E SIMULAÇÃO (mantidos iguais)
# ─────────────────────────────────────────────
def calcular_ano(
    matrizes, femeas_024, machos_024, bois,
    nat_pct, desc_mat_pct, prop_boi, renov_boi_pct,
    venda_bez_pct, mort_pct, preco_arroba, custo_cab_ano, peso_arroba,
) -> dict:
    # (código original inalterado)
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
    receita   = vendidos * peso_arroba * preco_arroba
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


# ─────────────────────────────────────────────
# SIMULAÇÕES ESPECÍFICAS POR CICLO
# ─────────────────────────────────────────────

def _simular_cria(
    v, cenario, nat_pct, mort_pct, desmama_pct, venda_bez_pct,
    preco_bezerro, custo_cab_ano, anos,
):
    """
    CRIA: receita vem da venda de bezerros desmamados por cabeça.
    Não usa preço de arroba — o produto final é o bezerro.
    """
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

    return _montar_resultado(cenario, sc, anos_proj, total_ini, 'CRIA')


def _simular_recria(
    v, cenario, mort_pct, preco_arroba, peso_entrada_arr, peso_saida_arr,
    meses_recria, custo_cab_mes, anos,
):
    """
    RECRIA: compra garrotes/novilhos leves e vende mais pesados.
    Receita = animais vendidos × arrobas na saída × preço arroba novilho.
    """
    va  = np.array(v, dtype=float)
    sc  = CENARIOS.get(cenario, CENARIOS['crescimento'])
    m   = sc['mods']

    mort  = (mort_pct / 100) * m['mort']
    preco = preco_arroba * m['preco']

    # Animais em recria = machos 05-24 meses
    animais   = float(va[1] + va[3] + va[5])
    total_ini = float(va.sum())

    anos_proj = []
    for yr in range(1, anos + 1):
        mortes       = animais * mort
        animais_sai  = animais - mortes
        ganho_arr    = peso_saida_arr - peso_entrada_arr

        receita   = animais_sai * peso_saida_arr * preco
        custo     = animais * meses_recria * custo_cab_mes
        resultado = receita - custo

        # Capacidade cresce levemente a cada ano
        animais_prox = animais * (1 + 0.04 * m['nat'])

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

    return _montar_resultado(cenario, sc, anos_proj, total_ini, 'RECRIA')


def _simular_engorda(
    v, cenario, mort_pct, preco_arroba, peso_entrada_kg, peso_saida_kg,
    rendimento_carcaca, custo_cab_dia, dias_engorda, anos,
):
    """
    ENGORDA: vende boi gordo por arroba de carcaça.
    Receita = bois abatidos × (peso_saida × rendimento / 15) × preço arroba boi gordo.
    """
    va  = np.array(v, dtype=float)
    sc  = CENARIOS.get(cenario, CENARIOS['crescimento'])
    m   = sc['mods']

    mort  = (mort_pct / 100) * m['mort']
    preco = preco_arroba * m['preco']
    rend  = rendimento_carcaca / 100

    # Bois em engorda = machos adultos (25m+)
    bois      = float(va[7] + va[9])
    total_ini = float(va.sum())

    # Lotes por ano: quantas rodadas cabem em 365 dias
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

        bois_prox = bois * (1 + 0.04 * m['nat'])

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

    return _montar_resultado(cenario, sc, anos_proj, total_ini, 'ENGORDA')


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


# ─────────────────────────────────────────────
# BENCHMARKS — Médias Regionais Rondônia
# ─────────────────────────────────────────────
BENCHMARKS_RO = {
    'natalidade': {
        'label': 'Taxa de Natalidade',
        'unidade': '%',
        'faixas': {'abaixo': 65.0, 'medio': 78.0, 'bom': 88.0},
        'inverso': False,
        'ciclos': ['CRIA', 'CICLO_COMPLETO'],
    },
    'mortalidade': {
        'label': 'Mortalidade Geral',
        'unidade': '%',
        'faixas': {'abaixo': 5.0, 'medio': 3.0, 'bom': 1.5},
        'inverso': True,
        'ciclos': ['CRIA', 'RECRIA', 'ENGORDA', 'CICLO_COMPLETO'],
    },
    'desmama': {
        'label': 'Taxa de Desmama',
        'unidade': '%',
        'faixas': {'abaixo': 70.0, 'medio': 82.0, 'bom': 90.0},
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
        'label': 'Ganho de Peso (@/mês)',
        'unidade': '@/mês',
        'faixas': {'abaixo': 0.5, 'medio': 0.7, 'bom': 0.9},
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
    """Retorna (faixa, proximo_nivel, falta) comparando valor com thresholds regionais."""
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
    """Avalia indicadores do rebanho contra benchmarks regionais de Rondônia."""
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
    """Estimativa rápida do breakeven usando parâmetros padrão RO. Não precisa de simulação completa."""
    va = np.array(v, dtype=float)
    custo_cab_ano = 850.0

    if ciclo == 'CRIA':
        matrizes  = float(va[6] + va[8])
        total     = float(va.sum()) or 1.0
        custo     = total * custo_cab_ano
        bezerros  = matrizes * 0.75 * 0.80 * 0.60
        if bezerros <= 0:
            return {}
        return {'preco_breakeven': round(custo / bezerros, 2), 'unidade': 'R$/cabeça'}

    if ciclo == 'RECRIA':
        be = round((12 * 80.0) / 14.0, 2)
        return {'preco_breakeven': be, 'unidade': 'R$/arroba'}

    if ciclo == 'ENGORDA':
        arrobas = (520.0 * 0.52) / 15.0
        be = round((90 * 12.0) / arrobas, 2)
        return {'preco_breakeven': be, 'unidade': 'R$/arroba'}

    # CICLO_COMPLETO
    total   = float(va.sum()) or 1.0
    custo   = total * custo_cab_ano
    units   = total * 0.30 * 16.0
    return {'preco_breakeven': round(custo / max(units, 1), 2), 'unidade': 'R$/arroba'}


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


def simular_cenario(
    v: list,
    cenario:        str   = 'crescimento',
    nat_pct:        float = 75.0,
    mort_pct:       float = 3.0,
    desc_pct:       float = 30.0,
    preco_arroba:   float = 320.0,
    custo_cab_ano:  float = 850.0,
    peso_arroba:    float = 16.0,
    prop_boi:       float = 30.0,
    renov_boi_pct:  float = 20.0,
    venda_bez_pct:  float = 30.0,
    anos:           int   = 5,
    # Parâmetros por ciclo
    ciclo:              str   = 'CICLO_COMPLETO',
    preco_bezerro:      float = 1800.0,
    desmama_pct:        float = 80.0,
    peso_entrada_arr:   float = 8.0,
    peso_saida_arr:     float = 14.0,
    meses_recria:       int   = 12,
    custo_cab_mes:      float = 80.0,
    peso_entrada_kg:    float = 300.0,
    peso_saida_kg:      float = 520.0,
    rendimento_carcaca: float = 52.0,
    custo_cab_dia:      float = 12.0,
    dias_engorda:       int   = 90,
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

    # CICLO_COMPLETO — lógica original
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
            peso_arroba=peso_arroba,
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

    return _montar_resultado(cenario, sc, anos_proj, total_ini, 'CICLO_COMPLETO')