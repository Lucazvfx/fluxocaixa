# Design: Retreino Automático por Lote de Confirmações

**Data:** 2026-04-24  
**Status:** Aprovado

## Contexto

Hoje `api_confirmar` dispara `_auto_retrain` em background a **cada confirmação individual**. Se o usuário confirmar 10 classificações seguidas, o modelo retreina 10 vezes — desnecessário e custoso. O objetivo é acumular N confirmações e retreinar uma única vez.

## Objetivo

Retreinar o modelo automaticamente apenas quando acumular 10 novas confirmações desde o último retreino, usando um contador em memória simples.

## Arquitetura

### Backend — `app.py`

**Duas novas variáveis globais** (logo após `_retraining`):
```python
RETRAIN_A_CADA = 10          # altere aqui para mudar o threshold
_confirmacoes_desde_retrain = 0
```

**Lógica atualizada em `api_confirmar`**:
- Após `db.confirmar(rid, cls)` bem-sucedido, incrementar `_confirmacoes_desde_retrain`
- Se `_confirmacoes_desde_retrain >= RETRAIN_A_CADA` e não há retreino em curso: disparar `_auto_retrain`, zerar o contador, retornar `retraining: true`
- Caso contrário: retornar `retraining: false`, incluir `confirmacoes_ate_retrain` e `limite_retrain` no JSON

**`api_retrain` (botão manual)** — zera `_confirmacoes_desde_retrain` após disparar o retreino, para não contar duplo.

**Resposta JSON de `api_confirmar`** (campo novo):
```json
{
  "ok": true,
  "stats": { ... },
  "retraining": false,
  "confirmacoes_ate_retrain": 7,
  "limite_retrain": 10
}
```

### Frontend — `templates/index.html`

**Função `confirmarClassificacao()`** já recebe o JSON. Toast atualizado:
- Retreino disparado → `"✓ Confirmado! Retreinando modelo (10/10)…"`
- Acumulando → `"✓ Confirmado! 7/10 para próximo retreino automático"`

## O Que Não Muda

- `_auto_retrain()` — sem alteração
- `api_retrain` (botão manual) — continua funcionando; apenas zera o contador
- DB, ML engine, `database.py` — sem alteração
- Formato do `.pkl` — sem alteração

## Comportamento no Restart do Servidor

O contador zera. Isso é aceitável: o DB preserva todos os confirmados e o próximo retreino (após 10 novas confirmações) usará tudo. Nenhum dado é perdido.
