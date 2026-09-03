# ADR 0005 — Publicação best-effort do evento (com outbox transacional como recomendação de produção)

## Status
Aceito para o escopo do desafio, com ressalva explícita para produção.

## Contexto
Depois que o Lançamentos persiste um lançamento, ele precisa publicar o evento `EntryCreated` no broker. Escrever no banco e publicar no broker são duas operações contra dois sistemas diferentes — não existe uma transação atômica nativa que cubra as duas (o clássico "dual write problem"). Além disso, RNF-1 exige que uma falha do broker **nunca** impeça o `POST /entries` de retornar sucesso.

## Decisão
Para o escopo simplificado deste desafio: a publicação do evento acontece **imediatamente após o commit** da transação do lançamento, dentro de um bloco que **nunca propaga exceção** para a camada HTTP. Se `redis.xadd(...)` falhar (Redis fora do ar, timeout, etc.), o handler apenas registra um log de erro e incrementa a métrica `event_publish_failures_total` — a resposta ao cliente continua sendo `201 Created`, porque o lançamento já foi persistido com sucesso e essa é a única garantia que RNF-1 exige.

```python
# services/ledger-service/app/infra/event_publisher.py — esboço da regra
try:
    publisher.publish(entry_created_event)
except Exception:
    logger.exception("event_publish_failed", entry_id=entry.id)
    metrics.event_publish_failures_total.inc()
    # NUNCA re-raise aqui — ver ADR 0005
```

O teste automatizado mais importante do repositório (`tests/unit/test_event_publisher_resilience.py`, no ledger-service) prova exatamente essa regra: com o publisher mockado para lançar exceção, o `POST /entries` continua retornando 201.

## Trade-off assumido e recomendação para produção

Publicação best-effort tem uma falha de fato: **se o Redis estiver indisponível no exato instante do `XADD`, aquele evento é perdido para sempre** — não há retry automático, não há reconciliação. Isso é aceitável no escopo do desafio (o objetivo é demonstrar a decisão e o teste de resiliência, não um sistema de produção), mas seria inaceitável em produção, onde perda silenciosa de um lançamento no relatório consolidado é um bug financeiro real.

**Recomendação de produção — Transactional Outbox Pattern**: gravar o evento em uma tabela `outbox_events` **na mesma transação de banco** que persiste o lançamento (atomicidade garantida pelo próprio banco). Um processo separado (relay/publisher, ex.: Debezium via CDC ou um worker que faz polling da tabela) lê a `outbox_events` e publica no broker de forma assíncrona, com retry até confirmar, removendo (ou marcando como enviado) somente após sucesso. Isso garante que o evento **nunca se perde**, mesmo que o broker fique indisponível por horas — ele será publicado assim que voltar. O trade-off do outbox é operacional: mais uma tabela, mais um processo (o relay) para manter e monitorar, e latência de publicação ligeiramente maior (depende do intervalo de polling do relay). Ver desenho completo em [`02-target-architecture.md`](../02-target-architecture.md).

## Consequências

**Positivas**: implementação simples, sem infraestrutura extra; prova de forma direta e testável que RNF-1 é satisfeito mesmo sob falha do broker.

**Negativas (aceitas para o escopo do desafio, não para produção)**: possibilidade real de perda de evento em caso de falha exatamente no momento da publicação. Mitigação futura documentada (outbox pattern) em vez de ignorada.
