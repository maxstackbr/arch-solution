# Consolidation Service

Bounded context: **Consolidado Diário**. Mantém um read model materializado (`daily_balances`) atualizado de forma assíncrona a partir dos eventos `EntryCreated` publicados pelo [ledger-service](../ledger-service), e serve o relatório de saldo consolidado. Sem endpoints de escrita públicos — o único jeito de alterar o saldo é via evento consumido internamente (ver [ADR 0003](../../docs/adr/0003-read-model-materializado.md)).

Este serviço roda como **dois processos** a partir da mesma imagem: a API (`app.main:app`, serve `GET /consolidated/...`) e o Worker (`worker.py`, consome a fila e atualiza o read model) — ver [`docs/02-target-architecture.md`](../../docs/02-target-architecture.md) sobre por que eles escalam separadamente.

Contratos completos em [`docs/03-api-contracts.md`](../../docs/03-api-contracts.md); ver o README raiz para subir tudo via Docker Compose.

## Rodar isoladamente (fora do Docker Compose)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
export DATABASE_URL="sqlite:///./consolidation.db"

# API:
uvicorn app.main:app --reload --port 8002

# Worker (em outro terminal, precisa de um Redis real rodando em localhost:6379):
python worker.py
```

Swagger UI em `http://localhost:8002/docs`. Todas as rotas de negócio exigem o header `X-API-Key`.

## Testes

```bash
pytest -v
```
