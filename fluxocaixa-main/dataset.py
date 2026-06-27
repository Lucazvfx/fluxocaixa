import numpy as np
import pandas as pd
from collections import defaultdict

# ------------------------------------------------------------
# Parâmetros globais (ajuste conforme necessidade)
# ------------------------------------------------------------
np.random.seed(42)  # reprodutibilidade

def gerar_total_aleatorio():
    """Gera um número total de cabeças entre 50 e 5000, com distribuição log-normal"""
    return int(np.random.lognormal(mean=6, sigma=1.2))  # média ~400, max ~5000

def garantir_total(v, total_desejado):
    """Ajusta o vetor para somar exatamente total_desejado (redistribui proporcionalmente)"""
    soma_atual = sum(v)
    if soma_atual == 0:
        return v
    fator = total_desejado / soma_atual
    v_ajustado = [int(round(x * fator)) for x in v]
    # corrige pequenos desvios arredondando o maior componente
    diff = total_desejado - sum(v_ajustado)
    if diff != 0:
        idx_max = np.argmax(v_ajustado)
        v_ajustado[idx_max] += diff
    return v_ajustado

# ------------------------------------------------------------
# Geradores por classe
# ------------------------------------------------------------

def gerar_cria():
    """
    Características:
    - Alta proporção de matrizes (f25F + facF) > 20% do total
    - Alta proporção de bezerros (f00F+f00M) > 15% do total
    - Baixa proporção de bois (f25M+facM) < 10%
    - Predomínio de fêmeas sobre machos na cria
    """
    total = gerar_total_aleatorio()
    
    # Matrizes: entre 20% e 45%
    p_mat = np.random.uniform(0.20, 0.45)
    matrizes = int(total * p_mat)
    # distribuição entre f25F (25-36m) e facF (>36m) - maioria adulta
    f25F = int(matrizes * np.random.uniform(0.2, 0.5))
    facF = matrizes - f25F
    
    # Bezerros (0-6 meses): entre 15% e 35% do total
    p_bez = np.random.uniform(0.15, 0.35)
    bezerros = int(total * p_bez)
    # divisão 50/50 entre machos e fêmeas
    f00F = bezerros // 2 + np.random.randint(-3, 4)
    f00M = bezerros - f00F
    
    # Bezerros 7-12 meses (f05F, f05M): entre 5% e 15%
    p_bez7_12 = np.random.uniform(0.05, 0.15)
    bezerros7_12 = int(total * p_bez7_12)
    f05F = bezerros7_12 // 2 + np.random.randint(-2, 3)
    f05M = bezerros7_12 - f05F
    
    # Recria 13-24m (f13F, f13M): entre 5% e 15%
    p_rec = np.random.uniform(0.05, 0.15)
    recria = int(total * p_rec)
    f13F = recria // 2 + np.random.randint(-2, 3)
    f13M = recria - f13F
    
    # Bois adultos (f25M, facM): muito baixo, entre 1% e 8%
    p_bois = np.random.uniform(0.01, 0.08)
    bois = int(total * p_bois)
    f25M = bois // 2 + np.random.randint(-1, 2)
    facM = bois - f25M
    
    v = [f00F, f00M, f05F, f05M, f13F, f13M, f25F, f25M, facF, facM]
    # Ajuste fino para garantir total exato (devido a arredondamentos)
    v = garantir_total(v, total)
    return v

def gerar_recria():
    """
    Características:
    - Concentração em machos 13-24 meses (recria)
    - Baixa proporção de matrizes (< 10%)
    - Bezerros também baixos (< 10%)
    - Bois adultos ainda não predominam
    """
    total = gerar_total_aleatorio()
    
    # Machos em recria (f13M) dominam: entre 30% e 60%
    p_mac_rec = np.random.uniform(0.30, 0.60)
    f13M = int(total * p_mac_rec)
    # Fêmeas em recria (f13F) acompanham em menor número: 10% a 30%
    p_fem_rec = np.random.uniform(0.10, 0.30)
    f13F = int(total * p_fem_rec)
    
    # Bezerros (0-12 meses) baixos: < 10%
    p_bez = np.random.uniform(0.02, 0.10)
    bezerros = int(total * p_bez)
    f00F = bezerros // 2 + np.random.randint(-2, 3)
    f00M = bezerros - f00F
    
    # Bezerros 7-12 meses (f05)
    p_bez7 = np.random.uniform(0.02, 0.08)
    bez7 = int(total * p_bez7)
    f05F = bez7 // 2
    f05M = bez7 - f05F
    
    # Matrizes muito baixas: < 8%
    p_mat = np.random.uniform(0.02, 0.08)
    matrizes = int(total * p_mat)
    f25F = int(matrizes * 0.4)
    facF = matrizes - f25F
    
    # Bois adultos ainda poucos: < 15%
    p_bois = np.random.uniform(0.05, 0.15)
    bois = int(total * p_bois)
    f25M = bois // 2
    facM = bois - f25M
    
    v = [f00F, f00M, f05F, f05M, f13F, f13M, f25F, f25M, facF, facM]
    v = garantir_total(v, total)
    return v

def gerar_engorda():
    """
    Características:
    - Alta concentração de machos adultos (f25M + facM) > 40%
    - Pouquíssimas matrizes e bezerros (< 5% cada)
    - Foco em terminação
    """
    total = gerar_total_aleatorio()
    
    # Bois adultos: entre 40% e 80%
    p_bois = np.random.uniform(0.40, 0.80)
    bois = int(total * p_bois)
    # maioria em facM (terminação), menos em f25M
    facM = int(bois * np.random.uniform(0.6, 0.9))
    f25M = bois - facM
    
    # Matrizes: muito baixo, < 5%
    p_mat = np.random.uniform(0.01, 0.05)
    matrizes = int(total * p_mat)
    f25F = matrizes // 2
    facF = matrizes - f25F
    
    # Bezerros: muito baixo, < 5%
    p_bez = np.random.uniform(0.01, 0.05)
    bezerros = int(total * p_bez)
    f00F = bezerros // 2
    f00M = bezerros - f00F
    
    # Bezerros 7-12m: baixo
    p_bez7 = np.random.uniform(0.01, 0.04)
    bez7 = int(total * p_bez7)
    f05F = bez7 // 2
    f05M = bez7 - f05F
    
    # Recria 13-24m: baixo a médio (alguns entrantes)
    p_rec = np.random.uniform(0.05, 0.15)
    rec = int(total * p_rec)
    f13F = rec // 2
    f13M = rec - f13F
    
    v = [f00F, f00M, f05F, f05M, f13F, f13M, f25F, f25M, facF, facM]
    v = garantir_total(v, total)
    return v

def gerar_ciclo_completo():
    """
    Características:
    - Distribuição equilibrada entre todas as faixas
    - Matrizes entre 10% e 25%
    - Bezerros (0-12m) entre 10% e 25%
    - Recria (13-24m) entre 10% e 25%
    - Bois adultos entre 10% e 25%
    - Proporção de machos e fêmeas balanceada em cada faixa
    """
    total = gerar_total_aleatorio()
    
    # Matrizes: 10-25%
    p_mat = np.random.uniform(0.10, 0.25)
    matrizes = int(total * p_mat)
    f25F = int(matrizes * np.random.uniform(0.3, 0.6))
    facF = matrizes - f25F
    
    # Bois: 10-25%
    p_bois = np.random.uniform(0.10, 0.25)
    bois = int(total * p_bois)
    f25M = int(bois * np.random.uniform(0.4, 0.6))
    facM = bois - f25M
    
    # Bezerros 0-6m: 10-20%
    p_bez = np.random.uniform(0.10, 0.20)
    bez = int(total * p_bez)
    f00F = bez // 2 + np.random.randint(-3, 4)
    f00M = bez - f00F
    
    # Bezerros 7-12m: 5-15%
    p_bez7 = np.random.uniform(0.05, 0.15)
    bez7 = int(total * p_bez7)
    f05F = bez7 // 2
    f05M = bez7 - f05F
    
    # Recria 13-24m: 10-20%
    p_rec = np.random.uniform(0.10, 0.20)
    rec = int(total * p_rec)
    f13F = rec // 2
    f13M = rec - f13F
    
    v = [f00F, f00M, f05F, f05M, f13F, f13M, f25F, f25M, facF, facM]
    v = garantir_total(v, total)
    return v

# ------------------------------------------------------------
# Geração do dataset completo
# ------------------------------------------------------------
def gerar_dataset_sintetico(n_por_classe=500):
    """
    Gera n_por_classe exemplos para cada uma das 4 classes.
    Retorna DataFrame com colunas f00F ... facM e 'rotulo'.
    """
    dados = []
    geradores = {
        0: gerar_cria,
        1: gerar_recria,
        2: gerar_engorda,
        3: gerar_ciclo_completo
    }
    for rotulo, gerador in geradores.items():
        for _ in range(n_por_classe):
            v = gerador()
            # validação simples: total deve ser positivo e cada categoria >=0
            if sum(v) > 0 and all(x >= 0 for x in v):
                dados.append(v + [rotulo])
    colunas = ['f00F', 'f00M', 'f05F', 'f05M', 'f13F', 'f13M', 'f25F', 'f25M', 'facF', 'facM', 'rotulo']
    df = pd.DataFrame(dados, columns=colunas)
    return df

# ------------------------------------------------------------
# Exemplo de uso
# ------------------------------------------------------------
if __name__ == "__main__":
    df = gerar_dataset_sintetico(n_por_classe=1000)  # gera 4000 exemplos
    print(df.head())
    print(f"\nDistribuição das classes:\n{df['rotulo'].value_counts()}")
    # Salvar para uso futuro
    df.to_csv('dataset_sintetico_bovino.csv', index=False)
    print("\nArquivo 'dataset_sintetico_bovino.csv' salvo.")