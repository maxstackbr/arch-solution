# Estratégia de Testes

Pirâmide leve, proporcional ao escopo do desafio: a prioridade foi testar **as decisões arquiteturais que sustentam os RNFs**, não perseguir cobertura alta de forma artificial.

## Os dois testes mais importantes do repositório

1. **`ledger-service/tests/unit/test_event_publisher_resilience.py`** — com o publisher mockado para lançar exceção (Redis fora do ar), garante que `POST /entries` continua retornando `201` e persistindo o lançamento. **Prova em código o RNF-1** — ver [ADR 0005](adr/0005-outbox-vs-publish-best-effort.md).
2. **`consolidation-service/tests/unit/test_idempotency.py`** — processa o mesmo `event_id` duas vezes e verifica que `daily_balances` não duplica o saldo. **Prova em código o [ADR 0006](adr/0006-consumidor-idempotente.md)**, necessário porque a entrega é at-least-once.

## Cobertura por serviço

| | `ledger-service` | `consolidation-service` |
|---|---|---|
| **Unit** | Regras de domínio (`amount > 0`, `type` válido, imutabilidade) e resiliência do publisher | Lógica de agregação (`total_credits`/`total_debits`/`balance`) e idempotência |
| **Integration** | `TestClient` sobre `POST`/`GET /entries`, validação `422`, `401` sem `X-API-Key`, correlação por `request_id` | `GET /consolidated/{date}` com dado seed, cache-aside, e consumo de evento via `fakeredis` atualizando `daily_balances` ponta a ponta |

**Isolamento**: o cliente de cache é substituído por `fakeredis` em todos os testes, e o ledger aponta o broker para uma porta sem nada escutando. Sem isso, um `docker compose up` rodando na máquina faria os testes conversarem com o Redis real — o cache sobreviveria entre testes, e o teste de "broker indisponível" deixaria de testar o que promete.

**Trade-off assumido**: SQLite é mais rápido e não exige infraestrutura no CI, mas não reproduz 100% do Postgres (tipos, locks, `UPSERT`). A alternativa de maior fidelidade seria [testcontainers](https://testcontainers.com/) — deixada como evolução ([`08-future-work.md`](08-future-work.md)) por custar tempo e dependências sem mudar a decisão arquitetural que o desafio pede para validar.

## Fora da suíte automatizada

Dependem do `docker compose` de pé, por isso não entram no `pytest`:

- **`scripts/smoke_test.py`** — `POST` no Ledger e polling no Consolidation até o valor bater. Valida o fluxo assíncrono real (dois processos, broker real), incluindo a janela de consistência eventual.
- **`scripts/load_test.py`** — ~50 req/s sustentados contra `GET /consolidated/{date}`, medindo a taxa de perda. Valida o SLO de RNF-2 (≤5%) na prática, em vez de alegá-lo em documento.

## Como rodar

```bash
# dentro de cada services/<nome>-service/
pip install -r requirements.txt -r requirements-dev.txt
pytest -v
```
