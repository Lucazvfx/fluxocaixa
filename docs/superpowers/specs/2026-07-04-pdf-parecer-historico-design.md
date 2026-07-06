# PDF do parecer + histórico por fazenda

**Data:** 2026-07-04
**Escopo:** (1) vincular a análise a uma fazenda cadastrada (pré-requisito —
hoje o frontend nunca envia `fazenda_id`, então nenhum parecer é persistido);
(2) exportar o parecer em PDF; (3) tela de histórico de pareceres por fazenda.
**Fora de escopo:** histórico de *composição do rebanho* (`historico_fazenda`,
tabela `registros`) — só o histórico de **pareceres**. Multiempresa. Edição/
exclusão de pareceres salvos.

## Contexto e motivação

O backend já tem tudo para persistir e listar pareceres (`db.salvar_parecer`,
`db.listar_pareceres`, endpoint que já monta o parecer em `/api/classificar`).
Mas **nunca é usado de fato**: os campos de fazenda no formulário são texto
livre (`f_faz`/`f_mun`/`f_prop`), usados também pelos fluxos de importação de
PDF/planilha (auto-preenchem esses campos com o que foi extraído) — e nenhum
deles nunca envia `fazenda_id`. Sem isso, a tela de histórico não teria o que
mostrar. Este spec fecha esse ciclo: vincular → persistir → exibir → exportar.

## Componentes

### 1. Seletor de "Cliente cadastrado" (aditivo, não substitui os campos livres)

Novo grupo no card "Dados" da aba de entrada, ao lado dos campos existentes
(que continuam como estão, para não quebrar PDF/planilha):

```html
<div class="field">
  <label>Cliente cadastrado (opcional)</label>
  <select id="f_fazenda_id" onchange="onFazendaSelecionada()">
    <option value="">— análise avulsa (não salva histórico) —</option>
  </select>
</div>
<button class="btn-sm" onclick="novaFazendaPrompt()">+ Nova fazenda</button>
```

- Ao carregar a página, `GET /api/fazendas` (já existe) popula o `<select>`
  com `<option value="{id}">{nome} — {municipio}</option>`.
- `novaFazendaPrompt()`: prompts simples (nome, proprietário, município,
  estado) → `POST /api/fazendas` (já existe) → repopula o select e seleciona
  a nova.
- `onFazendaSelecionada()`: por conveniência, preenche a partir do objeto
  devolvido por `/api/fazendas` (campos `nome`, `proprietario`, `municipio`):
  `f_faz ← nome`, `f_mun ← municipio`, `f_prop ← proprietario` (o texto livre
  continua editável depois — é só um atalho, não uma trava).
- `classificar()`: body ganha `fazenda_id: +document.getElementById('f_fazenda_id').value || null`.
  Se vazio, comportamento idêntico ao atual (parecer gerado, não persistido —
  `app.py` já tem essa checagem: `if fazenda_id and data.get('credito_valor')`).

### 2. Geração de PDF — `services/parecer_pdf.py` (puro, testável)

```python
def gerar_pdf_parecer(parecer: dict) -> bytes
```

- Biblioteca: **reportlab** (nova dependência em `requirements.txt`). Sem
  dependência de sistema (diferente de weasyprint/cairo) — funciona igual em
  todos os alvos de deploy já configurados (Dockerfile, Procfile, render.yaml)
  sem pacotes extra no container.
- Layout **documento profissional** (fundo branco, tipografia de negócio —
  não o tema escuro do dashboard; é para anexar num processo de crédito):
  1. Cabeçalho: "Parecer de Crédito — Análise Técnico-Financeira", fazenda/
     proprietário/município (de `parecer['identificacao']`), data de emissão.
  2. Composição do rebanho (`parecer['composicao']`): total e valores.
  3. Indicadores técnicos vs benchmark (`parecer['indicadores']`): tabela.
  4. Consistência do rebanho declarado (`parecer['consistencia']`): score e
     flags (ícone/cor por severidade).
  5. Situação financeira (`parecer['financeiro']`): breakeven.
  6. **Conclusão** (`parecer['conclusao']`) em destaque: caixa colorida por
     `recomendacao` (aprovar=verde, ressalva=âmbar, negar=vermelho — mesmas
     cores do card na UI), DSCR, parcela mensal, justificativa. Se
     `recomendacao` for `None` (sem crédito solicitado), mostra texto neutro
     "Sem solicitação de crédito informada".
- Função pura: recebe o dict, devolve `bytes`. Sem I/O, sem Flask, sem DB —
  testável isoladamente.

### 3. Endpoint `POST /api/parecer/pdf`

```python
@app.route('/api/parecer/pdf', methods=['POST'])
@login_required
def api_parecer_pdf():
    parecer = request.json.get('parecer')
    if not parecer:
        return jsonify({'erro': 'parecer é obrigatório'}), 400
    pdf_bytes = gerar_pdf_parecer(parecer)
    return send_file(io.BytesIO(pdf_bytes), mimetype='application/pdf',
                     as_attachment=True, download_name='parecer_credito.pdf')
```

Recebe o **mesmo JSON** que `/api/classificar` já devolve em `data.parecer`,
ou o que fica salvo em `pareceres.parecer` (histórico) — um único endpoint
serve os dois casos de uso (baixar na hora / baixar depois).

### 4. Endpoint `GET /api/fazendas/<int:fid>/pareceres`

Wrapper fino sobre `db.listar_pareceres`, no mesmo padrão do já existente
`/api/fazendas/<int:fid>/historico`:

```python
@app.route('/api/fazendas/<int:fid>/pareceres', methods=['GET'])
@login_required
def api_fazenda_pareceres(fid):
    itens = db.listar_pareceres(fazenda_id=fid, user_id=current_user.id)
    return jsonify({'pareceres': itens})
```

`db.listar_pareceres` já devolve `solicitacao`/`parecer` como JSON **texto**
(campo `TEXT` no banco) — o endpoint devolve como veio; o frontend faz
`JSON.parse` antes de repassar ao endpoint de PDF.

### 5. Nova aba "Histórico" (`templates/index.html`)

Segue o padrão de abas existente (`.tab-btn` / `.panel`, como "Reconciliação"
— sempre visível, não gated por classificação):

```html
<button class="tab-btn" onclick="showTab('historico',this)">Histórico</button>
...
<div class="panel" id="panel-historico">
  <div class="field"><label>Fazenda</label>
    <select id="hist-fazenda-id" onchange="carregarHistoricoPareceres()"></select>
  </div>
  <div id="hist-lista"></div>
</div>
```

- `carregarHistoricoPareceres()`: lê o `<select>` (populado do mesmo
  `/api/fazendas`), busca `/api/fazendas/<id>/pareceres`, renderiza uma lista:
  data, badge colorido de recomendação, DSCR, valor do crédito solicitado, e
  botão **"Baixar PDF"** (POST `/api/parecer/pdf` com o `parecer` daquele item,
  dispara download via blob).
- No card "Parecer de Crédito" (renderizado após classificar), o mesmo botão
  "Baixar PDF" aparece quando `data.parecer.conclusao.recomendacao` existe —
  usa o `data.parecer` que já está em memória, sem round-trip ao banco.

## Fluxo de dados

```
Aba Entrada: seleciona/cria fazenda → fazenda_id
        │  POST /api/classificar {..., fazenda_id}
        ▼
monta parecer (já existe) → salva se fazenda_id + credito_valor (já existe)
        │
        ├─ resposta inclui parecer → botão "Baixar PDF" no card do resultado
        │        │  POST /api/parecer/pdf {parecer}
        │        ▼
        │   services/parecer_pdf.gerar_pdf_parecer → PDF (download)
        │
        └─ Aba Histórico: seleciona fazenda
                 │  GET /api/fazendas/<id>/pareceres
                 ▼
           lista pareceres salvos → "Baixar PDF" por item (mesmo endpoint)
```

## Tratamento de erros / bordas

- Sem fazenda selecionada: análise funciona normalmente, só não persiste
  (comportamento já existente, inalterado).
- `POST /api/parecer/pdf` sem `parecer` no body → 400.
- Parecer sem conclusão de crédito (nunca pediu crédito): PDF gera normalmente,
  seção de conclusão mostra texto neutro em vez da caixa colorida.
- Fazenda sem pareceres salvos: aba Histórico mostra "Nenhum parecer salvo
  ainda para esta fazenda."

## Testes

`tests/test_parecer_pdf.py`:
- `gerar_pdf_parecer(parecer_completo)` devolve `bytes` que começam com
  `b'%PDF'`.
- Com `conclusao.recomendacao is None` (sem crédito): não lança exceção.
- Com `consistencia` tendo `flags` vazias: não lança exceção.

`tests/test_parecer_pdf_endpoint.py`:
- `POST /api/parecer/pdf` com parecer válido → 200, `content-type` PDF, bytes
  começam com `%PDF`.
- Sem `parecer` no body → 400.

`tests/test_fazenda_pareceres_endpoint.py`:
- Salva 2 pareceres via `db.salvar_parecer`, `GET /api/fazendas/<id>/pareceres`
  devolve os 2, mais recente primeiro.

## Critérios de sucesso

- Selecionar/criar fazenda e enviar `fazenda_id` faz o parecer ser realmente
  persistido (hoje isso nunca acontece).
- PDF do parecer sai profissional (fundo claro, seções na ordem do parecer,
  conclusão em destaque), gerado sem dependência de sistema no deploy.
- Aba Histórico lista pareceres salvos por fazenda com download de PDF.
- Nenhum fluxo existente (PDF/planilha import, análise avulsa) quebra.
