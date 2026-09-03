# ADR 0007 — Cache com TTL diferenciado e load shedding controlado no Consolidado

## Status
Aceito

## Contexto
RNF-2 exige que o Consolidado sustente 50 req/s de leitura com no máximo 5% de perda. O read model materializado ([ADR 0003](0003-read-model-materializado.md)) já torna cada leitura barata (um `SELECT` por chave primária), mas sob pico ainda é preciso proteger o serviço de degradar de forma descontrolada (todas as requisições lentas/travando) em vez de degradar de forma previsível e mensurável.

## Decisão

**1. Cache com TTL diferenciado por natureza do dado.** O saldo de dias passados é imutável (nenhum evento novo vai alterá-lo) — cacheado sem expiração (ou TTL longo, invalidado só se uma reconciliação manual rodar). O saldo do dia corrente muda a cada novo lançamento — cacheado com TTL curto (poucos segundos), suficiente para absorver rajadas de leitura sem servir um dado antigo por muito tempo. Estratégia cache-aside: o `GET /consolidated/{date}` primeiro consulta o Redis; em cache miss, consulta o Postgres e popula o cache.

**2. Load shedding por limite de concorrência.** O serviço limita quantas requisições processa simultaneamente (semáforo/bounded queue configurável via `CONSOLIDATION_MAX_CONCURRENCY`). Acima do limite, novas requisições recebem `503 Service Unavailable` com header `Retry-After` **imediatamente**, em vez de enfileirar indefinidamente até todo mundo dar timeout. Cada rejeição incrementa `consolidation_requests_rejected_total` — a métrica que prova (ou refuta) o SLO de ≤5% de perda em produção.

## Alternativas consideradas

**A. Sem limite de concorrência, confiando apenas em auto scaling horizontal para absorver o pico.**
Rejeitada como única linha de defesa. Auto scaling (ECS Fargate na arquitetura alvo) tem latência de minutos para provisionar novas tasks — um pico de tráfego pode saturar o serviço muito antes do scaling reagir. Load shedding é a defesa de curtíssimo prazo (milissegundos) que protege o serviço enquanto o scaling não reage; os dois mecanismos são complementares, não substitutos.

**B. Deixar a fila de requisições crescer sem limite (comportamento padrão de muitos servidores HTTP sob carga).**
Rejeitada. Sem um limite explícito, todas as requisições em voo competem pelos mesmos recursos (conexões de banco, threads/event loop), e a tendência é que *todas* fiquem lentas o suficiente para estourar o timeout do cliente — uma forma de perda pior (100% de degradação percebida) do que rejeitar rapidamente uma fração das requisições com um 503 explícito e imediato.

## Consequências

**Positivas**: o comportamento sob sobrecarga é previsível e mensurável (uma métrica dedicada), em vez de um colapso genérico; o cache reduz drasticamente a carga no Postgres para o caso mais comum (consultar o saldo do dia atual repetidamente).

**Negativas (trade-off aceito)**: requisições acima do limite de concorrência são recusadas mesmo que o serviço tivesse capacidade de atendê-las com uma latência um pouco maior — é uma escolha deliberada de "falhar rápido e de forma controlada" em vez de "tentar atender todo mundo, mais devagar". Reaproveitar a mesma instância Redis para cache e broker localmente é discutido em [ADR 0004](0004-broker-local-vs-aws.md).
