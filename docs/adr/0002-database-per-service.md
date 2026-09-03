# ADR 0002 — Banco de dados independente por serviço (Database per Service)

## Status
Aceito

## Contexto
Mesmo com comunicação assíncrona ([ADR 0001](0001-event-driven-vs-sincrono.md)), os dois serviços ainda poderiam compartilhar o mesmo banco de dados (cada um com suas próprias tabelas, mas na mesma instância/processo do banco). Isso é mais simples de operar, mas precisa ser avaliado contra RNF-1.

## Decisão
Cada serviço possui seu próprio schema/banco lógico, sem nenhuma tabela, view ou conexão compartilhada entre eles: `ledger_db` (Lançamentos) e `consolidation_db` (Consolidado). O único ponto de contato entre os dois contextos é o evento publicado no broker (ver [ADR 0001](0001-event-driven-vs-sincrono.md)).

Localmente (escopo simplificado do desafio), os dois bancos lógicos rodam na **mesma instância** do Postgres, criados via [`infra/local/init-db.sql`](../../infra/local/init-db.sql) — isolamento lógico, não físico. Isso é uma simplificação operacional para não exigir dois containers de Postgres no `docker-compose` local; a arquitetura alvo em produção usa duas instâncias RDS separadas (ver [`02-target-architecture.md`](../02-target-architecture.md)).

## Alternativas consideradas

**A. Banco compartilhado com view/materialized view alimentando o consolidado a partir das tabelas do Lançamentos.**
Rejeitada. Mesmo em processos de aplicação separados, uma query de agregação pesada do relatório (ex.: `SUM` sobre lançamentos do dia, sob 50 req/s) competiria por locks, I/O e conexões do connection pool com as escritas do Lançamentos no mesmo banco físico. Sob carga, isso é exatamente o cenário que RNF-1 proíbe: uma falha de capacidade do lado de leitura degradando o lado de escrita.

**B. Réplica de leitura (read replica) do banco do Lançamentos servindo o Consolidado diretamente.**
Rejeitada como solução principal, mas próxima da ideia certa. Uma réplica de leitura isola o *recurso físico* de I/O, mas o Consolidado ainda ficaria acoplado ao **schema interno** do Lançamentos (qualquer migração de schema no Lançamentos quebraria o Consolidado) e ainda precisaria fazer agregação on-the-fly a cada leitura, em vez de servir um dado pré-computado. O read model materializado (ver [ADR 0003](0003-read-model-materializado.md)) resolve os dois problemas ao mesmo tempo.

## Consequências

**Positivas**: autonomia total de schema entre os dois contextos (cada um evolui seu modelo de dados sem coordenar com o outro); nenhum recurso de banco compartilhado que uma sobrecarga de leitura do Consolidado possa usar para afetar o Lançamentos.

**Negativas (trade-offs aceitos)**: sem transações distribuídas entre os dois contextos — nunca existirá uma operação atômica que atualize Lançamentos e Consolidado ao mesmo tempo (é exatamente a consistência eventual descrita em RNF-3); no ambiente local, os dois bancos lógicos compartilham a mesma instância física de Postgres, o que não reproduz o isolamento de recursos completo da arquitetura alvo (aceito como simplificação, já que o objetivo do desafio é validar a decisão arquitetural, não a infraestrutura local).
