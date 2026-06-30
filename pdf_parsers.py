"""
Parsers de PDF de saldo de rebanho — IDARON-RO, INDEA-MT, DECLARAÇÃO IDARON e GENÉRICO.

Expõe:
  extrair_texto_pdf(path) -> str
  detectar_origem(text)   -> 'IDARON' | 'INDEA' | 'DECLARACAO_IDARON' | 'GENERICO'
  parsear_idaron(text, pdf_path=None) -> dict
  parsear_indea(text)                 -> dict
  parsear_declaracao_idaron(text)     -> dict
  parsear_generico(text)              -> dict
"""
import re
import subprocess

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
        pass

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
        m_qtd = re.search(r'(\d{1,6})\s*$', line.strip())  # captura 1 a 6 dígitos
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
# PARSER IDARON-RO — extração por tabela (formulário de anotações)
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

# ─────────────────────────────────────────────
# PARSER IDARON-RO — orquestrador
# ─────────────────────────────────────────────
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
# PARSER DECLARAÇÃO IDARON (emitida eletronicamente)
# ─────────────────────────────────────────────
def parsear_declaracao_idaron(text: str) -> dict:
    """
    Parser para a Declaração IDARON com tabela horizontal:
    0 A 6 MESES  7 A 12 MESES  ... TOTAL
    M F M F ... M F
    0 0 88 0 316 ... 404 13
    """
    animais = _animais_vazios()
    fazenda = municipio = proprietario = cpf = data_saldo = ''

    # Metadados
    m = re.search(r'FAZENDA\s+([A-ZÁÉÍÓÚÂÊÎÔÛÃÕÇ0-9\s\.\-]+)', text, re.I)
    if m:
        fazenda = m.group(1).strip()[:60]
    else:
        m = re.search(r'endereço:\s*([^.\n]+)', text, re.I)
        if m:
            fazenda = m.group(1).strip()[:60]

    m = re.search(r'município\s+de\s+([A-ZÁÉÍÓÚÂÊÎÔÛÃÕÇ\s\-]+?)(?:\s*\-|\n)', text, re.I)
    if m:
        municipio = m.group(1).strip()

    m = re.search(r'CPF[:\s]*(\d{11})\s+([A-ZÁÉÍÓÚÂÊÎÔÛÃÕÇ\s]+?)(?:\n|$)', text, re.I)
    if m:
        cpf = m.group(1)
        proprietario = m.group(2).strip()

    m = re.search(r'Emitido em:\s*(\d{2}/\d{2}/\d{4})', text)
    if m:
        data_saldo = m.group(1)

    # Extração dos 10 números da tabela
    # Padrão: captura 10 números após a sequência "M F M F M F M F M F"
    padrao = r'M\s+F\s+M\s+F\s+M\s+F\s+M\s+F\s+M\s+F\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)'
    match = re.search(padrao, text)
    if match:
        valores = [int(g) for g in match.groups()]
        # Ordem: f00_M, f00_F, f05_M, f05_F, f13_M, f13_F, f25_M, f25_F, fac_M, fac_F
        animais['f00_M'] = valores[0]
        animais['f00_F'] = valores[1]
        animais['f05_M'] = valores[2]
        animais['f05_F'] = valores[3]
        animais['f13_M'] = valores[4]
        animais['f13_F'] = valores[5]
        animais['f25_M'] = valores[6]
        animais['f25_F'] = valores[7]
        animais['fac_M'] = valores[8]
        animais['fac_F'] = valores[9]

    # Fallback: captura uma sequência de 12 números (10 valores + 2 totais)
    if sum(animais.values()) == 0:
        bloco = re.search(r'(\d+\s+\d+\s+\d+\s+\d+\s+\d+\s+\d+\s+\d+\s+\d+\s+\d+\s+\d+\s+\d+\s+\d+)', text)
        if bloco:
            nums = list(map(int, bloco.group(1).split()))
            if len(nums) == 12:
                animais['f00_M'] = nums[0]
                animais['f00_F'] = nums[1]
                animais['f05_M'] = nums[2]
                animais['f05_F'] = nums[3]
                animais['f13_M'] = nums[4]
                animais['f13_F'] = nums[5]
                animais['f25_M'] = nums[6]
                animais['f25_F'] = nums[7]
                animais['fac_M'] = nums[8]
                animais['fac_F'] = nums[9]

    valores_lista = _para_valores(animais)
    return {
        'fazenda': fazenda,
        'municipio': municipio,
        'proprietario': proprietario,
        'cpf': cpf,
        'ie': '',
        'data_saldo': data_saldo,
        'total': sum(valores_lista),
        'animais': animais,
        'valores': valores_lista,
    }

# ─────────────────────────────────────────────
# PARSER GENÉRICO (fallback robusto)
# ─────────────────────────────────────────────
_FAIXA_PATS_GENERICO = [
    (re.compile(r'\b(?:0?0\s*[aà\-]\s*0?6|at[ée]\s*0?6)(?:\s*m[eê]s(?:es)?)?\b', re.I), 'f00'),
    (re.compile(r'\b0?7\s*[aà\-]\s*12(?:\s*m[eê]s(?:es)?)?\b', re.I),               'f05'),
    (re.compile(r'\b0?0\s*[aà\-]\s*0?4(?:\s*m[eê]s(?:es)?)?\b', re.I),               'f00'),
    (re.compile(r'\b0?5\s*[aà\-]\s*12(?:\s*m[eê]s(?:es)?)?\b', re.I),                'f05'),
    (re.compile(r'\b(?:0?0\s*[aà\-]\s*12|at[ée]\s*12)(?:\s*m[eê]s(?:es)?)?\b', re.I), 'f00_12'),
    (re.compile(r'\b13\s*[aà\-]\s*24(?:\s*m[eê]s(?:es)?)?\b', re.I),                 'f13'),
    (re.compile(r'\b25\s*[aà\-]\s*36(?:\s*m[eê]s(?:es)?)?\b', re.I),                 'f25'),
    (re.compile(r'(?:\b(?:acima(?:\s*de)?|maior\s*(?:que|de))|>)\s*36\b', re.I),     'fac'),
]

def _faixa_generica(texto: str):
    for pat, faixa in _FAIXA_PATS_GENERICO:
        if pat.search(texto):
            return faixa
    return None

_CATEGORIAS_ZOOTECNICAS = [
    (re.compile(r'\bbezerr([ao])s?\b', re.I),       'f00',  None),
    (re.compile(r'\bgarrot([ao])s?\b', re.I),       'f13',  None),
    (re.compile(r'\bnovilh([ao])s?\b', re.I),       'f25',  None),
    (re.compile(r'\bvacas?\b',         re.I),       'fac',  'F'),
    (re.compile(r'\b(?:touros?|boi(?:s)?)\b', re.I), 'fac', 'M'),
]

def _categoria_zootecnica(up: str):
    """
    Retorna (faixa, sexo) para uma linha com nome de categoria zootécnica.
    sexo pode ser 'F', 'M' ou 'AMBOS'.

    Regras de inferência pela terminação da palavra:
      - "...A"  (novilha)   -> F (singular feminino)
      - "...AS" (novilhas)  -> F (plural feminino, inequívoco)
      - "...O"  (novilho)   -> M (singular masculino)
      - "...OS" (novilhos)  -> AMBOS — em português "novilhos"/"bezerros" no
        plural é comumente usado tanto como "só machos" quanto como termo
        genérico do rebanho jovem sem distinção de sexo. Sem uma coluna
        explícita de Fêmea/Macho, a leitura mais segura é dividir 50/50
        (mesma lógica já usada para faixas etárias mistas).
    """
    for pat, faixa, sexo_fixo in _CATEGORIAS_ZOOTECNICAS:
        m = pat.search(up)
        if not m:
            continue
        sexo = sexo_fixo
        if sexo is None and m.groups():
            letra = m.group(1).upper()
            plural = m.group(0).upper().endswith('S')
            if letra == 'A':
                sexo = 'F'                  # "...a" ou "...as" -> sempre feminino
            else:
                sexo = 'AMBOS' if plural else 'M'   # "...os" ambíguo; "...o" -> masculino
        return faixa, sexo
    return None, None

def parsear_generico(text: str) -> dict:
    animais = _animais_vazios()
    fazenda = municipio = proprietario = cpf = data_saldo = ''

    for pat in [
        r'(?:NOME\s+DA\s+)?(?:PROPRIEDADE|FAZENDA|ESTABELECIMENTO)[:\s]+(.+)',
    ]:
        m = re.search(pat, text, re.I)
        if m:
            fazenda = m.group(1).strip().splitlines()[0][:60]
            break

    m = re.search(r'MUNIC[IÍ]PIO[:\s]+([A-ZÁÉÍÓÚÂÊÎÔÛÃÕÇ\s\-/]+?)(?:\s{2,}|\n|$)', text, re.I)
    if m:
        municipio = m.group(1).strip()[:60]

    m = re.search(r'\b(\d{3}\.?\d{3}\.?\d{3}[\-\.]?\d{2}|\d{11})\b', text)
    if m:
        cpf = re.sub(r'[^\d]', '', m.group(1))

    m = re.search(r'\b(\d{2}/\d{2}/\d{4})\b', text)
    if m:
        data_saldo = m.group(1)

    for line in text.split('\n'):
        bruto = line.strip()
        if not bruto:
            continue
        m_qtd = re.search(r'(\d{1,6})\s*$', bruto)
        if not m_qtd:
            continue
        qtd = int(m_qtd.group(1))
        if qtd <= 0 or qtd > 500_000:
            continue

        up = bruto.upper()
        sexo = _sexo_da_linha(up)

        faixa = _faixa_generica(up)
        if not faixa or not sexo:
            cat_faixa, cat_sexo = _categoria_zootecnica(up)
            if not faixa:
                faixa = cat_faixa
            if not sexo:
                sexo = cat_sexo

        if not faixa or not sexo:
            continue

        if sexo == 'AMBOS':
            metade = qtd // 2
            _adicionar(animais, faixa, 'F', metade)
            _adicionar(animais, faixa, 'M', qtd - metade)
        else:
            _adicionar(animais, faixa, sexo, qtd)

    valores = _para_valores(animais)
    return {
        'fazenda': fazenda, 'municipio': municipio,
        'proprietario': proprietario, 'cpf': cpf, 'ie': '',
        'data_saldo': data_saldo, 'total': sum(valores),
        'animais': animais, 'valores': valores,
    }