# Marca própria da consultoria no PDF do parecer

**Data:** 2026-07-06
**Subprojeto:** #2 de N rumo a "preparar para vender a outras consultorias"
(decompostos: #1 empresa/equipe multiempresa, #2 marca própria — este spec,
#3 cobrança/assinatura, #4 onboarding self-service, #5 painel admin de
clientes, #6 LGPD/jurídico). Cada um terá seu próprio ciclo spec→plano→
implementação.
**Escopo:** o PDF do parecer de crédito passa a exibir o nome e o logo da
consultoria que gerou a análise, configurável pelo próprio usuário.
**Fora de escopo:** conceito de "empresa"/equipe compartilhada (subprojeto
#1) — a marca fica amarrada ao **usuário atual** (fronteira de isolamento
já existente), não a uma entidade nova. Marca no dashboard/UI do app (só o
PDF exportado, que é o documento entregue ao cliente da consultoria).

## Contexto e motivação

Para vender a outras consultorias, o parecer que sai do sistema precisa levar
a identidade de quem o emitiu, não "Fluxo de Caixa feito por Lucas". Hoje o
PDF (`services/parecer_pdf.py`, entregue nesta mesma sessão) tem cabeçalho
genérico fixo.

**Decisão de escopo:** amarrar a marca ao usuário (`usuarios`), não criar uma
tabela `empresa` agora — isso adiantaria o trabalho do subprojeto #1 antes de
ele ser desenhado. Quando #1 existir, promover esses dois campos de usuário
para empresa é uma migração simples, não um retrabalho.

**Armazenamento do logo:** base64 **no banco** (coluna `TEXT`), não arquivo em
disco — os alvos de deploy (Railway/Render) têm sistema de arquivos efêmero;
um logo salvo em disco sumiria no próximo deploy/restart. Um logo é pequeno
o bastante para não pesar como blob de banco.

## Componentes

### 1. Schema (`database.py`)

```python
_add_column_safe('usuarios', 'nome_consultoria', "TEXT DEFAULT ''")
_add_column_safe('usuarios', 'logo_base64', "TEXT DEFAULT ''")
```

Seguindo o padrão já usado para `security_question`/`security_answer_hash`
(retrocompatível SQLite/Postgres, sem migração manual).

### 2. Persistência (`database.py`)

```python
def atualizar_perfil_consultoria(user_id: int, nome_consultoria: str, logo_base64: str):
    ph = _PH
    _exec(f'UPDATE usuarios SET nome_consultoria={ph}, logo_base64={ph} WHERE id={ph}',
          (nome_consultoria.strip()[:120], logo_base64, user_id), commit=True)
```

`db.buscar_usuario_id(user_id)` já faz `SELECT *`, então os dois campos novos
já vêm de graça — nenhuma outra função precisa mudar.

### 3. Endpoint (`app.py`)

```python
@app.route('/api/perfil-consultoria', methods=['GET', 'POST'])
@login_required
def api_perfil_consultoria():
    if request.method == 'POST':
        data = request.json or {}
        db.atualizar_perfil_consultoria(
            current_user.id,
            data.get('nome_consultoria', ''),
            data.get('logo_base64', ''))
        return jsonify({'ok': True})
    u = db.buscar_usuario_id(current_user.id)
    return jsonify({
        'nome_consultoria': u.get('nome_consultoria', '') if u else '',
        'logo_base64': u.get('logo_base64', '') if u else '',
    })
```

### 4. PDF (`services/parecer_pdf.py`)

`gerar_pdf_parecer(parecer: dict, branding: dict | None = None) -> bytes`.

- `branding = {'nome_consultoria': str, 'logo_base64': str}` (ambos opcionais
  dentro do dict).
- Se `branding['nome_consultoria']` estiver preenchido, o cabeçalho passa a
  ser `"{nome_consultoria} — Parecer de Crédito"` em vez do genérico atual;
  se vazio/`branding is None`, mantém `"Parecer de Crédito — Análise
  Técnico-Financeira"` (comportamento atual, retrocompatível).
- Se `branding['logo_base64']` estiver preenchido, decodifica
  (`base64.b64decode`) para um `io.BytesIO` e insere como `Image` do
  reportlab no topo da primeira página (largura máxima ~4cm, mantém
  proporção). Falha silenciosa (base64 inválido/corrompido) → PDF segue sem
  logo, não quebra a geração.

### 5. Ligação no endpoint de PDF (`app.py`)

Em `api_parecer_pdf`, antes de chamar `gerar_pdf_parecer`:

```python
u = db.buscar_usuario_id(current_user.id)
branding = {'nome_consultoria': u.get('nome_consultoria', ''),
            'logo_base64': u.get('logo_base64', '')} if u else None
pdf_bytes = gerar_pdf_parecer(parecer, branding=branding)
```

### 6. UI (`templates/index.html`)

- Botão **"⚙ Marca"** no `<header>`, ao lado do botão "Sair", abrindo um
  modal simples (`position:fixed`, overlay, seguindo a linguagem visual dos
  `.card` existentes — não há modal reutilizável no código hoje, este é o
  primeiro):
  - Campo texto: nome da consultoria.
  - Input de arquivo (logo): lido no navegador via `FileReader` →
    `readAsDataURL` → extrai só a parte base64 (após a vírgula do data URI).
  - Preview do logo carregado.
  - Botão "Salvar" → `POST /api/perfil-consultoria`.
- Ao abrir o modal, `GET /api/perfil-consultoria` pré-popula os campos com o
  que já estiver salvo.
- Sem nenhuma configuração feita: PDF sai igual a hoje (genérico) — nada
  quebra, nada é obrigatório.

## Fluxo de dados

```
Header: botão "⚙ Marca" → modal
  GET /api/perfil-consultoria → pré-popula nome + preview do logo
  (usuário edita, escolhe logo) → POST /api/perfil-consultoria → salva em usuarios

Botão "Baixar PDF" (já existente, card do resultado ou histórico)
  → POST /api/parecer/pdf {parecer}
      app.py busca branding do current_user
      → gerar_pdf_parecer(parecer, branding) → PDF com nome/logo da consultoria
```

## Tratamento de erros / bordas

- Sem marca configurada: PDF sai com o cabeçalho genérico atual (comportamento
  já existente, não regride).
- Logo corrompido/base64 inválido: PDF gera sem o logo (não lança exceção),
  loga o erro no servidor.
- `nome_consultoria` vazio mas logo preenchido: mostra só o logo, sem trocar
  o texto do título.
- Logo muito grande (ex.: usuário sobe uma foto de 8MB): sem limite de
  tamanho de arquivo nesta versão — aceitável para uso próprio/piloto; se
  virar problema real (banco inchando), tratar depois com limite de upload.

## Testes

`tests/test_parecer_pdf.py` (estender):
- `gerar_pdf_parecer(parecer, branding={'nome_consultoria': 'Consultoria X'})`
  devolve `bytes` começando com `%PDF` (não valida o conteúdo visual, só que
  não quebra e gera).
- `gerar_pdf_parecer(parecer, branding={'logo_base64': 'não-é-base64-válido'})`
  não lança exceção (fallback sem logo).
- `gerar_pdf_parecer(parecer, branding=None)` continua idêntico ao
  comportamento atual (regressão).

`tests/test_perfil_consultoria.py`:
- `db.atualizar_perfil_consultoria` + `db.buscar_usuario_id` fazem round-trip
  de `nome_consultoria`/`logo_base64`.
- `POST /api/perfil-consultoria` salva; `GET` subsequente devolve os mesmos
  valores.

## Critérios de sucesso

- Usuário configura nome/logo uma vez; todo PDF gerado depois carrega essa
  marca, sem precisar reconfigurar por análise.
- Sem configuração, nada muda (retrocompatível).
- Logo armazenado no banco (sobrevive a redeploy no Railway/Render).
- Campos prontos para virar "marca da empresa" quando o subprojeto #1
  (multiempresa) for desenhado, sem precisar refazer o PDF.
