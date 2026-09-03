# Requisitos Funcionais e Não Funcionais (Refinados)

> **[Enunciado]** vem literalmente do desafio. **[Refinamento]** é premissa assumida e documentada explicitamente — a tradução em métrica mensurável que o próprio desafio pede, não fato dado.

## Requisitos Funcionais

### RF-1 — Registro de lançamentos **[Enunciado]**
O sistema deve permitir registrar lançamentos de débito e crédito no fluxo de caixa do comerciante.

- **[Refinamento]** Todo lançamento tem: valor (positivo, decimal com 2 casas), tipo (`CREDIT`/`DEBIT`), descrição, data/hora de ocorrência.
- **[Refinamento]** Lançamentos são imutáveis após criados (sem edição/remoção) — correções são feitas via novo lançamento de estorno. Justificativa: rastreabilidade/auditoria contábil, requisito implícito em qualquer domínio de "fluxo de caixa".

### RF-2 — Consulta de lançamentos **[Refinamento]**
O comerciante deve poder consultar o histórico de lançamentos (não está explícito no enunciado, mas é indispensável para qualquer conferência/auditoria do que foi lançado — sem isso, o serviço de lançamentos seria "write-only", o que não é um sistema utilizável).

### RF-3 — Consolidado diário **[Enunciado]**
O sistema deve disponibilizar um relatório de saldo diário consolidado (total de créditos, total de débitos, saldo do dia).

- **[Refinamento]** O relatório deve indicar se o dia está `CONSOLIDATED` (nenhum lançamento pendente de processamento conhecido) ou `PARTIAL` (pode haver lançamentos recentes ainda em trânsito, dado que a consolidação é assíncrona) — isso comunica honestamente ao cliente da API o nível de consistência do dado que ele está lendo, em vez de esconder a consistência eventual.

## Requisitos Não Funcionais

O parágrafo de RNF do enunciado ("*O serviço de controle de lançamento não deve ficar indisponível se o sistema de consolidado diário cair. Em dias de pico, o serviço de consolidado diário recebe 50 requisições por segundo, com no máximo 5% de perda de requisições.*") descreve, na prática, **dois requisitos de natureza diferente**. Separá-los é a base de todo o desenho de solução deste projeto.

### RNF-1 — Isolamento de falha (disponibilidade) **[Enunciado]**
O serviço de Lançamentos **não deve ficar indisponível se o serviço de Consolidado Diário cair**.

- **[Refinamento]** Métrica: disponibilidade do Lançamentos não pode ter nenhuma dependência *hard* (síncrona e bloqueante) do Consolidado. Alvo de disponibilidade proposto: 99.9% para o Lançamentos, medido independentemente do estado do Consolidado.
- **Consequência arquitetural**: comunicação assíncrona entre os dois serviços (nunca uma chamada síncrona de Lançamentos para Consolidado no caminho crítico de escrita) + bancos de dados independentes (sem recurso compartilhado que possa ser saturado pelo outro serviço). Ver [ADR 0001](adr/0001-event-driven-vs-sincrono.md) e [ADR 0002](adr/0002-database-per-service.md).

### RNF-2 — Capacidade de leitura do Consolidado **[Enunciado]**
Em dias de pico, o Consolidado recebe **50 requisições/segundo**, com **no máximo 5% de perda de requisições**.

- **[Refinamento]** Interpretação assumida: o enunciado chama o Consolidado de "relatório", então 50 req/s é lido como tráfego de **leitura** (`GET /consolidated/...`), não como volume de eventos na fila — o texto original admite as duas leituras. A decisão arquitetural não depende de resolver essa ambiguidade: mesmo na leitura conservadora (50 eventos/s de escrita), read model pré-computado + fila durável comportam a carga sem mudança.
- **[Refinamento]** "Perda" = 5xx, timeout ou rejeição explícita por sobrecarga (503). Meta: ≤ 5% sob 50 req/s sustentados.
- **[Refinamento]** Latência-alvo (não mencionada no enunciado, adicionada para tornar o requisito testável): p95 < 300ms para `GET /consolidated/{date}` sob carga de pico.
- **Consequência arquitetural**: read model pré-computado (a agregação já foi feita de forma assíncrona, então o `GET` é uma leitura barata), cache para o dia corrente, e *load shedding* controlado (rejeitar rápido com 503 acima de um limite de concorrência, em vez de degradar todos os clientes com timeouts lentos e imprevisíveis). Ver [ADR 0007](adr/0007-cache-e-load-shedding.md).

### RNF-3 — Consistência **[Refinamento]**
Dado RNF-1 e RNF-2, o sistema opera com **consistência eventual**: um lançamento recém-criado leva segundos até refletir no consolidado. Aceitável porque o consolidado é relatório analítico, não saldo transacional que autoriza operação em tempo real. O `status` (`PARTIAL`/`CONSOLIDATED`) e o `last_updated_at` tornam essa defasagem visível ao consumidor, em vez de escondida.

### RNF-4 — Segurança **[Diferencial escolhido]**
Chamadas às APIs devem ser autenticadas (API Key no escopo deste desafio; OAuth2/mTLS na arquitetura alvo) e a entrada deve ser validada antes de qualquer persistência. Ver [`05-security.md`](05-security.md).

### RNF-5 — Observabilidade **[Diferencial escolhido]**
Ambos os serviços devem expor `/health` e métricas mínimas que tornem RNF-1 e RNF-2 verificáveis em produção (não apenas alegadas em documento) — especificamente, uma métrica de falha de publicação de evento (prova de RNF-1) e uma métrica de requisições rejeitadas por sobrecarga (prova de RNF-2). Ver [`04-observability.md`](04-observability.md).

## Fora de escopo (explicitamente)

- Autenticação de usuário final / multi-tenant (o enunciado fala de "um comerciante"; multi-comerciante é evolução futura, ver [`08-future-work.md`](08-future-work.md)).
- Edição/estorno automatizado de lançamentos (o estorno é modelado como um novo lançamento manual, não como uma operação de sistema).
- Migração de legado (diferencial descartado para este desafio, por não haver sistema legado descrito no enunciado).
