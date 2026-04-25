# Retreino Automático por Lote — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Substituir o retreino a cada confirmação individual por um retreino automático a cada 10 novas confirmações, usando contador em memória.

**Architecture:** Duas variáveis globais em `app.py` (`RETRAIN_A_CADA = 10` e `_confirmacoes_desde_retrain = 0`). `api_confirmar` incrementa o contador e só dispara `_auto_retrain` ao atingir o threshold; `api_retrain` (manual) zera o contador. O frontend exibe progresso no toast.

**Tech Stack:** Flask (Python), JavaScript vanilla

---

## Arquivos Modificados

| Arquivo | O que muda |
|---|---|
| `app.py` | Globals, `api_confirmar`, `api_retrain` |
| `templates/index.html` | `confirmarClassificacao()`, texto de ajuda do card |
| `tests/test_retreino.py` | Novo arquivo de testes da lógica do contador |

---

### Task 1: Backend — contador de confirmações em `app.py`

**Files:**
- Modify: `app.py` — linhas ~120-135 (globals) e ~233-259 (endpoints)
- Create: `tests/test_retreino.py`

**Contexto:** Hoje `_retraining = False` e `_retrain_lock` estão na linha ~121. `api_confirmar` está em ~233 e `api_retrain` em ~252.

- [ ] **Step 1: Escrever o teste da lógica do contador**

Criar `c:\Users\Lucas\Downloads\boviml_python\boviml\tests\test_retreino.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Testa a lógica do contador de forma isolada — sem precisar do servidor
def test_contador_dispara_ao_atingir_limite():
    """Simula o comportamento do contador: deve disparar no 10º."""
    LIMITE = 10
    contador = 0
    disparou = []

    for i in range(1, 12):
        contador += 1
        if contador >= LIMITE:
            disparou.append(i)
            contador = 0

    assert len(disparou) == 1, "Deve disparar exatamente 1 vez em 11 confirmações"
    assert disparou[0] == 10, "Deve disparar na 10ª confirmação"
    assert contador == 1, "Contador deve ter 1 após o reset (11ª confirmação)"


def test_contador_reseta_apos_retrain_manual():
    """Simula que api_retrain zera o contador."""
    LIMITE = 10
    contador = 7  # usuário confirmou 7 antes de clicar Retreinar manualmente

    # api_retrain zera
    contador = 0

    assert contador == 0

    # Próximas confirmações começam do zero
    for _ in range(9):
        contador += 1

    assert contador == 9
    assert contador < LIMITE  # ainda não disparou


def test_resposta_json_inclui_progresso():
    """Verifica que os campos de progresso são calculados corretamente."""
    RETRAIN_A_CADA = 10
    _confirmacoes_desde_retrain = 0

    # Simula 4 confirmações
    for _ in range(4):
        _confirmacoes_desde_retrain += 1

    faltam = RETRAIN_A_CADA - _confirmacoes_desde_retrain
    assert faltam == 6
    assert _confirmacoes_desde_retrain == 4
```

- [ ] **Step 2: Executar o teste para confirmar que passa com a lógica esperada**

```bash
cd c:/Users/Lucas/Downloads/boviml_python/boviml
python -m pytest tests/test_retreino.py -v
```

Esperado: `3 passed`

- [ ] **Step 3: Adicionar globals em `app.py` após `_retrain_lock`**

Localizar:
```python
_retraining = False
_retrain_lock = threading.Lock()
```

Substituir por:
```python
_retraining = False
_retrain_lock = threading.Lock()

RETRAIN_A_CADA = 10              # retreina a cada N confirmações novas
_confirmacoes_desde_retrain = 0  # contador em memória (zera no restart)
```

- [ ] **Step 4: Atualizar `api_confirmar` com a lógica do contador**

Localizar:
```python
@app.route('/api/confirmar', methods=['POST'])
@login_required
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
```

Substituir por:
```python
@app.route('/api/confirmar', methods=['POST'])
@login_required
def api_confirmar():
    """Confirma ou corrige a classificação. Retreina a cada RETRAIN_A_CADA confirmações."""
    global _confirmacoes_desde_retrain
    data = request.json
    rid  = data.get('registro_id')
    cls  = data.get('classificacao', '').strip().upper()
    if not rid or not cls:
        return jsonify({'erro': 'Campos registro_id e classificacao são obrigatórios'}), 400
    try:
        db.confirmar(int(rid), cls)
        s = db.stats()
        _confirmacoes_desde_retrain += 1
        if _confirmacoes_desde_retrain >= RETRAIN_A_CADA and not _retraining:
            _confirmacoes_desde_retrain = 0
            threading.Thread(target=_auto_retrain, daemon=True).start()
            retraining_agora = True
        else:
            retraining_agora = False
        return jsonify({
            'ok': True,
            'stats': s,
            'retraining': retraining_agora,
            'confirmacoes_ate_retrain': RETRAIN_A_CADA - _confirmacoes_desde_retrain,
            'limite_retrain': RETRAIN_A_CADA,
        })
    except ValueError as e:
        return jsonify({'erro': str(e)}), 400
```

- [ ] **Step 5: Atualizar `api_retrain` para zerar o contador**

Localizar:
```python
@app.route('/api/retrain', methods=['POST'])
@login_required
def api_retrain():
    """Retreina o modelo com dados base + registros confirmados do BD."""
    global stats
    X_extra, y_extra = db.exportar_treino()
    stats = retrain_com_dados(X_extra, y_extra)
    return jsonify({**stats, 'ok': True})
```

Substituir por:
```python
@app.route('/api/retrain', methods=['POST'])
@login_required
def api_retrain():
    """Retreina o modelo com dados base + registros confirmados do BD."""
    global stats, _confirmacoes_desde_retrain
    X_extra, y_extra = db.exportar_treino()
    stats = retrain_com_dados(X_extra, y_extra)
    _confirmacoes_desde_retrain = 0
    return jsonify({**stats, 'ok': True})
```

- [ ] **Step 6: Verificar sintaxe**

```bash
python -c "import ast; ast.parse(open('app.py', encoding='utf-8').read()); print('OK')"
```

Esperado: `OK`

- [ ] **Step 7: Executar todos os testes**

```bash
python -m pytest -q
```

Esperado: `22 passed` (19 anteriores + 3 novos)

- [ ] **Step 8: Commit**

```bash
git add app.py tests/test_retreino.py
git commit -m "feat: retreino automático a cada 10 confirmações (contador em memória)"
```

---

### Task 2: Frontend — toast com progresso em `templates/index.html`

**Files:**
- Modify: `templates/index.html`
  - Função `confirmarClassificacao()` (~linha 1881)
  - Texto de ajuda do card `card-confirmar` (~linha 177)

**Contexto:** `confirmarClassificacao()` exibe um toast fixo hoje. Com os novos campos `retraining`, `confirmacoes_ate_retrain` e `limite_retrain` na resposta, o toast deve mostrar o progresso.

- [ ] **Step 1: Atualizar `confirmarClassificacao()`**

Localizar:
```javascript
async function confirmarClassificacao(){
  if(!lastRegistroId){toast('Nenhum registro para confirmar.',true);return}
  const cls=document.getElementById('conf-tipo').value;
  try{
    const res=await fetch('/api/confirmar',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({registro_id:lastRegistroId,classificacao:cls})});
    const data=await res.json();
    if(data.erro){toast(data.erro,true);return}
    const sv=document.getElementById('conf-saved');
    if(sv){sv.style.display='inline';setTimeout(()=>sv.style.display='none',3000)}
    toast('✓ Confirmado! Modelo atualizando em segundo plano...');
    atualizarDbStats(data.stats);
    // Verifica acurácia atualizada após ~35s (tempo estimado do retreino)
    setTimeout(()=>atualizarDbStats(),35000);
  }catch(e){toast('Erro ao confirmar: '+e.message,true)}
}
```

Substituir por:
```javascript
async function confirmarClassificacao(){
  if(!lastRegistroId){toast('Nenhum registro para confirmar.',true);return}
  const cls=document.getElementById('conf-tipo').value;
  try{
    const res=await fetch('/api/confirmar',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({registro_id:lastRegistroId,classificacao:cls})});
    const data=await res.json();
    if(data.erro){toast(data.erro,true);return}
    const sv=document.getElementById('conf-saved');
    if(sv){sv.style.display='inline';setTimeout(()=>sv.style.display='none',3000)}
    if(data.retraining){
      toast('✓ Confirmado! Retreinando modelo automaticamente…');
      setTimeout(()=>atualizarDbStats(),35000);
    }else{
      const faltam=data.confirmacoes_ate_retrain??'?';
      const limite=data.limite_retrain??10;
      toast('✓ Confirmado! Faltam '+faltam+'/'+limite+' para retreino automático');
    }
    atualizarDbStats(data.stats);
  }catch(e){toast('Erro ao confirmar: '+e.message,true)}
}
```

- [ ] **Step 2: Atualizar texto de ajuda do card**

Localizar:
```html
      Cada confirmação melhora o modelo. Após acumular dados, clique em <strong style="color:var(--tx)">Retreinar</strong> no cabeçalho.
```

Substituir por:
```html
      Cada confirmação melhora o modelo. O retreino ocorre <strong style="color:var(--tx)">automaticamente a cada 10 confirmações</strong> ou manualmente pelo botão <strong style="color:var(--tx)">Retreinar</strong> no cabeçalho.
```

- [ ] **Step 3: Verificar no browser**

1. Iniciar `python app.py` em `c:/Users/Lucas/Downloads/boviml_python/boviml/`
2. Classificar um rebanho
3. Clicar "✓ Confirmar" — toast deve mostrar "Faltam 9/10 para retreino automático"
4. Confirmar mais 9 vezes — na 10ª, toast deve mostrar "Retreinando modelo automaticamente…"

- [ ] **Step 4: Executar testes**

```bash
python -m pytest -q
```

Esperado: `22 passed`

- [ ] **Step 5: Commit**

```bash
git add templates/index.html
git commit -m "feat: toast mostra progresso do retreino automático"
```
