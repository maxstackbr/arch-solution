# ADR 0004 — Redis Streams localmente como substituto simplificado do broker AWS

## Status
Aceito

## Contexto
O desafio pede uma implementação simplificada, rodável localmente via `docker-compose`, mas a arquitetura alvo em AWS deve usar serviços gerenciados apropriados (ver [`02-target-architecture.md`](../02-target-architecture.md)). É preciso escolher uma peça de mensageria para o ambiente local que seja barata de operar (um único container) mas que preserve a semântica relevante (persistência, entrega at-least-once, consumer groups) — para que a decisão local não fique divorciada da decisão de produção.

## Decisão
Localmente, o broker é o **Redis Streams** (`XADD`/`XREADGROUP`), rodando no mesmo container Redis já usado como cache pelo Consolidado (ver trade-off de acoplamento abaixo). Na arquitetura alvo AWS, o broker é **Amazon SQS** (fila) alimentada por um **SNS topic** (ou EventBridge, caso mais de um consumidor futuro precise do mesmo evento) — ver detalhamento em [`02-target-architecture.md`](../02-target-architecture.md).

Redis Streams foi escolhido para o ambiente local (em vez de subir Kafka, RabbitMQ, ou um emulador de SQS como LocalStack/ElasticMQ) porque:
- É um único binário/container, sem necessidade de Zookeeper, cluster ou configuração de exchanges/filas.
- Suporta consumer groups com `XACK`, ou seja, reproduz a semântica at-least-once que o consumidor precisa tratar (idempotência) de forma realista — diferente de uma fila in-memory ingênua, que esconderia esse problema.
- O time já precisa de Redis para o cache do lado de leitura ([ADR 0007](0007-cache-e-load-shedding.md)), então reaproveitá-lo reduz a quantidade de infraestrutura local sem introduzir uma tecnologia nova só para o desafio.

## Alternativas consideradas

**A. LocalStack (emulando SQS/SNS reais).**
Rejeitada para o escopo simplificado. Daria maior fidelidade à arquitetura alvo, mas adiciona complexidade de configuração (containers extras, emulação de IAM/credenciais) desproporcional ao que o desafio pede ("implementação simplificada"). Fica registrada como evolução natural em [`08-future-work.md`](../08-future-work.md) para quem quiser validar a integração real com SQS antes de ir para produção.

**B. RabbitMQ ou Kafka locais.**
Rejeitados pelo mesmo motivo: overhead operacional (múltiplos containers, configuração de tópicos/exchanges) não justificado pelo volume e escopo do desafio. Kafka em particular seria um exagero de engenharia para um sistema de 2 serviços com 50 req/s.

## Consequências

**Positivas**: ambiente local sobe com `docker-compose up` sem componentes extras; o comportamento at-least-once é realista o suficiente para validar a idempotência do consumidor de verdade (não é um mock que sempre entrega uma vez só).

**Negativas (trade-off aceito e documentado)**: usar a mesma instância Redis como cache e como broker acopla dois componentes que, na arquitetura alvo, têm perfis de falha diferentes — perder o cache é apenas degradação de performance (a leitura volta a bater no banco), perder o broker é perda de eventos em trânsito. Essa simplificação é aceitável **apenas no ambiente local**; a arquitetura alvo mantém ElastiCache (cache) e SQS/SNS (broker) como serviços gerenciados independentes, com blast radius separado.
