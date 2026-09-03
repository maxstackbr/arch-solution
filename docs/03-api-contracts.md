# Contratos de API

Ambos os serviços expõem OpenAPI/Swagger automático do FastAPI em `/docs` (Swagger UI) e `/openapi.json`. Este documento resume os contratos estáveis; o Swagger é a fonte viva de verdade quando os serviços estão rodando.

Todas as rotas de negócio exigem o header `X-API-Key` (ver [`05-security.md`](05-security.md)). `/health` e `/metrics` são exceções (não exigem autenticação, para permitir health checks de infraestrutura).

Toda resposta inclui `X-Request-ID` (gerado, ou ecoado se o cliente enviar o seu) — o mesmo valor do campo `request_id` nos logs ([`04-observability.md`](04-observability.md)).

## Ledger Service (`http://localhost:8001`)

### `POST /entries`
Cria um lançamento (débito ou crédito). Operação de escrita única — não há update/delete (ver [`00-domain-mapping.md`](00-domain-mapping.md)).

> **Valores monetários trafegam como string JSON** (`"150.00"`, não `150.00`): um número JSON seria lido como float pela maioria dos clientes, reintroduzindo erro de arredondamento binário no único dado que não pode tê-lo. Na entrada, string e número são aceitos.

```json
// Request
{
  "amount": "150.00",
  "type": "CREDIT",
  "description": "Venda balcão",
  "occurred_at": "2026-08-31T14:32:00Z"
}
```
`occurred_at` é opcional (default: momento do recebimento da requisição). `amount` deve ser > 0. `type` deve ser `"CREDIT"` ou `"DEBIT"`.

```json
// 201 Created
{
  "id": "b3f1c2b0-...",
  "amount": "150.00",
  "type": "CREDIT",
  "description": "Venda balcão",
  "occurred_at": "2026-08-31T14:32:00Z",
  "created_at": "2026-08-31T14:32:00.412Z"
}
```
`422 Unprocessable Entity` em caso de validação (amount ≤ 0, type inválido, description vazia).

### `GET /entries`
Lista lançamentos, paginado. Query params opcionais: `date` (`YYYY-MM-DD`), `page` (default 1), `page_size` (default 50, máx 200).

```json
// 200 OK
{ "items": [ { "id": "...", "amount": "150.00", "type": "CREDIT", "...": "..." } ],
  "page": 1, "page_size": 50, "total": 1 }
```

### `GET /entries/{id}`
Detalhe de um lançamento. `404` se não existir.

### `GET /health`
`200 { "status": "ok", "database": "ok" }` ou `503` se a conexão com o banco falhar. Não depende do broker (publicação é best-effort e não é um pré-requisito de saúde do serviço — ADR 0005).

### `GET /metrics`
Formato Prometheus (`text/plain`). Ver métricas detalhadas em [`04-observability.md`](04-observability.md).

---

## Consolidation Service (`http://localhost:8002`)

Sem endpoints de escrita expostos publicamente — reforça por design que é um read model derivado (ver [ADR 0003](adr/0003-read-model-materializado.md)).

### `GET /consolidated/{date}`
`date` no formato `YYYY-MM-DD`.

```json
// 200 OK
{
  "date": "2026-08-31",
  "total_credits": "500.00",
  "total_debits": "120.00",
  "balance": "380.00",
  "entry_count": 12,
  "status": "PARTIAL",
  "last_updated_at": "2026-08-31T14:32:05.120Z"
}
```
`status: "PARTIAL"` indica que o dia ainda pode receber novos lançamentos (é o dia corrente); `"CONSOLIDATED"` indica um dia já encerrado. Se o dia não tiver nenhum lançamento processado ainda, retorna `200` com todos os totais zerados (não `404` — o dia "existe", apenas está vazio; simplifica o cliente, que não precisa tratar 404 como caso especial de "zero movimentação").

`503 Service Unavailable` (com header `Retry-After`) quando o limite de concorrência é atingido — ver [ADR 0007](adr/0007-cache-e-load-shedding.md). Esta é a resposta que a métrica `consolidation_requests_rejected_total` contabiliza.

### `GET /consolidated?from=2026-08-01&to=2026-08-31`
Lista os saldos diários no intervalo (mesma estrutura de item de `/consolidated/{date}`, em uma lista).

### `GET /health`
`200 { "status": "ok", "database": "ok", "cache": "ok" }` — degrada para `"cache": "degraded"` (ainda `200`) se o Redis estiver fora, já que o serviço consegue operar (mais lento) direto no Postgres.

### `GET /metrics`
Formato Prometheus. Inclui `consolidation_requests_rejected_total`, `event_processed_total`, `event_duplicate_total`.

---

## Evento interno (não é uma API pública — contrato entre os dois bounded contexts)

**Stream**: `ledger.entry.created` (Redis Streams local · SNS/SQS na arquitetura alvo)

```json
{
  "event_id": "b7e0...-uuid",
  "event_type": "EntryCreated",
  "entry_id": "b3f1c2b0-...",
  "amount": "150.00",
  "type": "CREDIT",
  "occurred_at": "2026-08-31T14:32:00Z",
  "occurred_date": "2026-08-31",
  "published_at": "2026-08-31T14:32:00.415Z"
}
```
`event_id` é a chave de idempotência usada pelo consumidor (ADR 0006). `occurred_date` já vem derivado de `occurred_at` para que o consumidor não precise repetir essa lógica.
