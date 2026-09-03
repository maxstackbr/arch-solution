# ADR 0003 — Read model materializado para o saldo consolidado

## Status
Aceito

## Contexto
RNF-2 exige que o Consolidado sirva 50 req/s de leitura com no máximo 5% de perda. A forma como o dado é armazenado no lado do Consolidado determina se isso é trivial ou difícil de sustentar.

## Decisão
O consumidor de eventos do Consolidado mantém uma tabela `daily_balances` já agregada (uma linha por dia: `date` como chave primária, `total_credits`, `total_debits`, `entry_count`, `last_updated_at`; `balance` e `status` não são colunas — são derivados na leitura, para não existir duas fontes da verdade para o mesmo número), atualizada incrementalmente a cada evento `EntryCreated` recebido (`UPDATE ... SET total_credits = total_credits + evento.amount WHERE date = evento.occurred_date`, com upsert se o dia ainda não existir). O endpoint `GET /consolidated/{date}` faz apenas um `SELECT` por chave primária — nenhuma agregação acontece no caminho de leitura.

## Alternativas consideradas

**A. Agregação on-the-fly a cada leitura** (`SELECT SUM(...) FROM entries WHERE date = ...` direto sobre os lançamentos brutos).
Rejeitada como estratégia principal. Isso exigiria o Consolidado ter acesso aos lançamentos brutos (violando [ADR 0002](0002-database-per-service.md)) e, mais importante, transformaria cada requisição de leitura em uma agregação potencialmente cara — exatamente o oposto do que RNF-2 pede. O custo computacional é pago uma vez por evento (na escrita incremental), não uma vez por requisição de leitura.

**B. Reprocessar tudo do zero a cada evento** (recalcular o dia inteiro somando todos os lançamentos daquele dia a cada novo evento).
Rejeitada. Funciona, mas descarta o benefício de uma atualização incremental O(1) por evento; sob um volume maior de lançamentos no mesmo dia, o custo de processamento do consumidor cresceria linearmente sem necessidade. É mantida como opção de *reconciliação* (recalcular do zero) para uso ocasional, não como caminho principal — ver `POST /admin/recalculate` mencionado em [`08-future-work.md`](../08-future-work.md).

## Consequências

**Positivas**: leitura do relatório é barata e previsível independentemente de quantos lançamentos existem no dia; o custo de agregação é amortizado ao longo do dia (um `UPDATE` pequeno por evento) em vez de concentrado no momento da leitura, que é justamente quando a carga é maior (pico de 50 req/s).

**Negativas (trade-offs aceitos)**: a atualização incremental precisa ser idempotente (um evento reprocessado não pode somar o valor duas vezes) — tratado em [ADR 0006](0006-consumidor-idempotente.md); existe uma pequena janela de defasagem entre o lançamento ser criado e o `daily_balances` refletir esse valor (consistência eventual, já assumida em RNF-3).
