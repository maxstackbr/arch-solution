# Ledger Service

Bounded context: **Lançamentos**. Registra débitos/créditos do fluxo de caixa (append-only) e publica um evento `EntryCreated` para o [consolidation-service](../consolidation-service) — de forma assíncrona e best-effort, para nunca ficar indisponível por causa dele (ver [ADR 0005](../../docs/adr/0005-outbox-vs-publish-best-effort.md)).

Contratos completos em [`docs/03-api-contracts.md`](../../docs/03-api-contracts.md); ver o README raiz para subir tudo via Docker Compose.

## Rodar isoladamente (fora do Docker Compose)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
export DATABASE_URL="sqlite:///./ledger.db"
uvicorn app.main:app --reload --port 8001
```

Swagger UI em `http://localhost:8001/docs`. Todas as rotas de negócio exigem o header `X-API-Key` (default local: `local-dev-key-change-me`, ver [`.env.example`](../../.env.example)).

## Testes

```bash
pytest -v
```
