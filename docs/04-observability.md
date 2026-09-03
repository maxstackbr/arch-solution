# Observabilidade e Monitoramento

## O que existe em código (escopo simplificado)

### Logging estruturado
Ambos os serviços logam em JSON (campo por campo, não strings formatadas), incluindo um identificador de correlação injetado automaticamente em **todo** registro emitido durante uma unidade de trabalho (um `contextvars.ContextVar` lido por um `logging.Filter`, em vez de repassado manualmente a cada chamada):

- **Ledger**: um middleware gera um `request_id` por requisição (ou reaproveita o `X-Request-ID` do cliente) e o devolve no mesmo header. O log `entry_created` carrega esse `request_id` e o `entry_id` persistido.
- **Consolidation Worker**: o `event_id` vira o identificador daquele processamento; `event_applied` e `event_duplicate_skipped` carregam `event_id` e `entry_id`.

Como `entry_id` aparece nos dois serviços, dá para seguir um lançamento de ponta a ponta filtrando por ele — proxy simplificado de correlação, sem exigir tracing distribuído completo. Dois testes cobrem essa promessa: `test_entry_created_is_logged_with_entry_id_and_request_id` e `test_applied_event_is_logged_with_event_id_and_entry_id`.

### Métricas (Prometheus, via `prometheus_client`)

| Serviço | Métrica | Prova/serve para |
|---|---|---|
| Ledger | `http_requests_total{route,status}` | tráfego e taxa de erro geral |
| Ledger | `http_request_duration_seconds{route}` | latência |
| Ledger | `event_publish_failures_total` | **prova RNF-1**: quantas publicações falharam sem afetar a resposta HTTP |
| Consolidation | `http_requests_total{route,status}` | tráfego e taxa de erro geral |
| Consolidation | `consolidation_requests_rejected_total` | **prova RNF-2**: taxa de rejeição por load shedding (deve ficar ≤ 5% do tráfego sob pico) |
| Consolidation | `event_processed_total` / `event_duplicate_total` | throughput do consumidor e taxa de deduplicação (prova ADR 0006 funcionando) |
| Consolidation | `cache_hit_total` / `cache_miss_total` | efetividade do cache (ADR 0007) |

Expostas em `GET /metrics` (formato texto Prometheus) nos dois serviços. Requisições sem rota casada entram como `route="<unmatched>"` (o path cru daria uma série nova por URL, e no Consolidado uma por data consultada), e `/health`/`/metrics` não são contabilizados — inflariam o denominador do próprio cálculo de perda de RNF-2.

### Health checks
`GET /health` em cada serviço, verificando as dependências que de fato importam para aquele serviço estar operacional (banco nos dois; cache no Consolidation, de forma não bloqueante — ver [`03-api-contracts.md`](03-api-contracts.md)). Importante: o `/health` do Ledger **não** verifica o broker — um broker fora do ar não torna o Ledger "não saudável", coerente com RNF-1.

### Stack local
`docker-compose` inclui `prometheus` (scrape dos dois `/metrics`) e `grafana` com um dashboard mínimo pré-provisionado (`infra/monitoring/dashboard.json`) mostrando: taxa de requisições, taxa de erro, `event_publish_failures_total` e `consolidation_requests_rejected_total` lado a lado — as duas métricas que "provam" os dois RNFs do desafio.

## O que fica só na arquitetura alvo (não implementado no desafio)

- **Tracing distribuído completo** (AWS X-Ray ou OpenTelemetry + Grafana Tempo/Jaeger): propagação de trace-id via header entre API Gateway → ECS → SQS → Worker, com spans e visualização de latência ponta a ponta. Cortado do escopo simplificado porque o correlation-id manual em log já demonstra a decisão de design sem exigir instrumentação OTel completa nos dois serviços.
- **CloudWatch Alarms → SNS → Slack/PagerDuty**: alarmes automáticos sobre as métricas acima (ex.: `event_publish_failures_total` crescendo, `consolidation_requests_rejected_total` > 5% em janela de 5 min) disparando notificação para o time de plantão.
- **Dashboards de SLO** com error budget (ex.: 99.9% de disponibilidade do Ledger, orçamento de indisponibilidade mensal).
- **Log centralizado** (CloudWatch Logs Insights ou OpenSearch) com retenção e busca — localmente os logs ficam no stdout dos containers (`docker-compose logs`).
