# Design: Mesclagem de Múltiplos PDFs

**Data:** 2026-04-24  
**Status:** Aprovado

## Contexto

O app BovIML lê PDFs do IDARON/INDEA para extrair contagens de animais por faixa etária/sexo. Atualmente aceita um único PDF por vez. Produtores com múltiplos documentos da mesma fazenda precisam somar os dados manualmente.

## Objetivo

Permitir upload de múltiplos PDFs simultaneamente, com os contadores de animais somados automaticamente, em ambos os painéis da interface.

## Arquitetura

### Backend

**Novo endpoint:** `POST /api/ler-pdfs` (plural)

- Aceita `multipart/form-data` com campo `pdf` contendo N arquivos
- Para cada arquivo: salva em `tempfile`, extrai texto, detecta origem (IDARON/INDEA), chama o parser correto
- Acumula `valores[0..9]` somando todos os arquivos
- Metadados (fazenda, município, proprietário, IE, data_saldo) vêm do primeiro PDF que tiver esses campos preenchidos
- Retorna o mesmo formato JSON do endpoint singular, mais campo `pdfs_processados: N`
- O endpoint singular `/api/ler-pdf` permanece inalterado (sem quebra)

**Tratamento de erros:** Se um PDF falhar, continua os demais e inclui lista `erros: []` no retorno.

### Frontend — Painel "Ler PDF" (panel-pdf)

- `<input type="file" accept=".pdf" multiple>` nos dois elementos de seleção (upzone e botão)
- Texto da upzone: "Carregue os PDFs" / "Arraste ou clique"
- `lerPDF()` envia para `/api/ler-pdfs` com todos os arquivos selecionados
- Preview mostra: "N PDFs · X animais total" e nome da fazenda do primeiro PDF
- Botão "Classificar com ML" recebe os valores somados (sem mudança)

### Frontend — Botão "Ler PDF" no painel Inserir Dados

- `<input type="file" accept=".pdf" multiple>` no input oculto
- `lerPDFInserir()` envia para `/api/ler-pdfs`
- Toast: "N PDFs carregados: Fazenda X (Y animais)"
- Preenchimento dos campos com valores somados (sem mudança na lógica de atribuição)

## Fluxo de Dados

```
[N arquivos .pdf] 
  → POST /api/ler-pdfs
  → para cada pdf: extrair_texto → detectar_origem → parsear_*
  → somar valores[0..9]
  → metadados do primeiro pdf com dados
  → { valores, total, fazenda, municipio, proprietario, pdfs_processados }
  → frontend: mesmo tratamento do endpoint singular
```

## O Que Não Muda

- Formato de resposta JSON (retrocompatível)
- Endpoint `/api/ler-pdf` singular
- Lógica de classificação ML
- Parsers IDARON/INDEA
- Visual da tabela de preview e botão de classificar
