# ADR 0006 — Consumidor idempotente no Consolidado

## Status
Aceito

## Contexto
Redis Streams com consumer groups (e igualmente SQS na arquitetura alvo) entrega mensagens com garantia **at-least-once**: se o consumidor cair depois de processar uma mensagem mas antes de confirmar (`XACK`/delete da mensagem), a mensagem será entregue novamente. Sem tratamento, isso faz o Consolidado somar o mesmo lançamento duas vezes no `daily_balances`, corrompendo o saldo — um bug silencioso e grave em um sistema financeiro.

## Decisão
O consolidation-service mantém uma tabela `processed_events (event_id UUID PRIMARY KEY, processed_at TIMESTAMP)`. Ao processar uma mensagem, o consumidor executa, na **mesma transação** que atualiza `daily_balances`:

1. `INSERT INTO processed_events (event_id) VALUES (:event_id)`
2. Se o insert violar a constraint `UNIQUE`/`PRIMARY KEY` (evento já processado), a transação é abortada, o `UPDATE` em `daily_balances` não é aplicado, e a mensagem é confirmada (`XACK`) normalmente — reprocessar um evento já visto não é um erro, é o comportamento esperado de at-least-once.
3. Se o insert for bem-sucedido, o `UPDATE`/`UPSERT` em `daily_balances` é aplicado na mesma transação, e só então a mensagem é confirmada.

## Alternativas consideradas

**A. Deduplicação no broker** (ex.: SQS FIFO com `MessageDeduplicationId`).
Rejeitada como solução única. Reduz a *probabilidade* de duplicata, mas não elimina o caso onde o consumidor processa a mensagem, falha antes do ACK, e o broker reentrega — a garantia de deduplicação do broker cobre a entrega, não o processamento. A idempotência precisa estar no consumidor de qualquer forma; deduplicação no broker é uma otimização complementar, não um substituto.

**B. Ignorar o problema, assumindo que duplicatas são raras.**
Rejeitada. "At-least-once" não é um caso extremo raro, é a garantia padrão desse tipo de infraestrutura sob crash/restart do consumidor — vai acontecer em operação normal, especialmente durante deploys (o worker é reiniciado no meio de um lote). Ignorar isso teria significado assumir uma característica ("exactly-once") que a infraestrutura escolhida não oferece.

## Consequências

**Positivas**: `daily_balances` fica correto independentemente de quantas vezes um evento seja reentregue; o teste `test_idempotency.py` prova isso processando o mesmo `event_id` duas vezes e verificando que o saldo não duplica.

**Negativas (custo aceito)**: uma tabela extra e uma query adicional por evento processado — custo desprezível na escala do desafio (~dezenas de eventos/segundo). Em produção, essa tabela deve ter uma política de retenção/purga (eventos processados há mais de N dias podem ser removidos) para não crescer indefinidamente — ver [`08-future-work.md`](../08-future-work.md).
