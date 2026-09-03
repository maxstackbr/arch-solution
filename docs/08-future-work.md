# Evoluções Futuras

O que ficou fora do escopo por decisão explícita de foco, não por esquecimento — e o que seria priorizado primeiro.

## Prioridade alta

| Item | Por quê |
|---|---|
| **Transactional Outbox** no Ledger, no lugar do publish best-effort | Elimina a janela de perda de evento se o broker cair no instante da publicação — [ADR 0005](adr/0005-outbox-vs-publish-best-effort.md) |
| **Broker real (SQS/SNS)** no lugar do Redis Streams, validado antes via LocalStack | Reduz risco de surpresa na integração com a arquitetura alvo — [ADR 0004](adr/0004-broker-local-vs-aws.md) |
| **`Idempotency-Key` no cliente** em `POST /entries` | Protege contra duplicação por retry do *cliente*, que é problema diferente da idempotência do consumidor — [`05-security.md`](05-security.md) |
| **Endpoint de reconciliação** (`POST /admin/recalculate?date=...`) | Recalcula um dia do zero a partir do Ledger, para corrigir divergência detectada em auditoria sem depender do reprocessamento incremental |

## Prioridade média

| Item | Por quê |
|---|---|
| **Tracing distribuído** (OpenTelemetry + X-Ray/Tempo) | Hoje a correlação entre serviços é por `entry_id`/`event_id` em log estruturado — [`04-observability.md`](04-observability.md) |
| **CloudWatch Alarms → plantão** | Sobre `event_publish_failures_total` e `consolidation_requests_rejected_total` |
| **Multi-tenant** | O enunciado descreve "um comerciante"; múltiplos exigiriam `merchant_id` em todo o modelo, nos contratos e no particionamento |
| **Contract testing** (ex.: Pact) sobre o schema do `EntryCreated` | Detecta quebra de contrato entre os dois serviços antes de produção |
| **CI** (GitHub Actions) | Lint + testes a cada push/PR |

## Fora de escopo, deliberadamente

- **Arquitetura de migração de legado** — o enunciado não descreve sistema legado algum; desenhar uma migração fictícia acrescentaria complexidade sem sinal real de capacidade analítica.
- **Postgres real via testcontainers** nos testes de integração, no lugar do SQLite — trade-off discutido em [`07-testing-strategy.md`](07-testing-strategy.md).
- **Réplicas de leitura do RDS** — só se justificariam muito acima dos 50 req/s do enunciado; cache + read model já resolvem essa escala.
