# ADR 0001 — Comunicação assíncrona (orientada a eventos) entre Lançamentos e Consolidado

## Status
Aceito

## Contexto
RNF-1 exige que o serviço de Lançamentos não fique indisponível se o serviço de Consolidado cair. Isso restringe fortemente como os dois serviços podem se comunicar: qualquer forma de comunicação em que uma falha do Consolidado possa se propagar (direta ou indiretamente) para o caminho de escrita do Lançamentos viola o requisito.

## Decisão
O Lançamentos publica um evento de domínio (`EntryCreated`) em um broker de mensageria **após** persistir o lançamento com sucesso. O Consolidado consome esse evento de forma assíncrona e atualiza seu próprio read model. Não existe nenhuma chamada do Lançamentos para o Consolidado no caminho crítico do `POST /entries` — a publicação do evento é *fire-and-forget* (ver [ADR 0005](0005-outbox-vs-publish-best-effort.md) para o tratamento de falha dessa publicação).

## Alternativas consideradas

**A. Chamada síncrona REST (Lançamentos → Consolidado) com Circuit Breaker + Retry.**
Rejeitada. Circuit breaker evita que o *chamador* fique bloqueado esperando um serviço fora do ar, mas não resolve o problema de fundo: a atualização do consolidado ainda precisa acontecer eventualmente. Se o breaker abre, é necessário guardar a atualização pendente em algum lugar durável para retentar depois — ou seja, a aplicação acabaria implementando uma fila (pior: sem persistência real, sem consumer groups, sem replay) só para evitar usar um broker de mensageria de verdade. Circuit breaker é a ferramenta certa quando a chamada é opcional e existe um fallback aceitável; aqui a atualização do consolidado não é opcional.

**B. Polling** — o Consolidado consulta periodicamente o Lançamentos por novos registros.
Rejeitada. Acopla os dois serviços por uma API de "buscar novidades desde X" que precisa ser mantida, introduz latência mínima igual ao intervalo de polling, e desperdiça requisições em períodos sem novos lançamentos. Mensageria push-based com um broker durável é estritamente melhor para este caso de uso sem custo adicional relevante na escala do desafio.

## Consequências

**Positivas**: Lançamentos nunca depende da disponibilidade do Consolidado para responder a um `POST /entries`; o broker absorve picos e indisponibilidades temporárias do consumidor, entregando os eventos quando ele voltar.

**Negativas (trade-offs aceitos)**: o sistema passa a operar sob consistência eventual (ver RNF-3 em [`01-requirements.md`](../01-requirements.md)); é necessário lidar com entrega "at-least-once" do broker, o que exige um consumidor idempotente (ver [ADR 0006](0006-consumidor-idempotente.md)); a operação ganha mais uma peça de infraestrutura (o broker) para monitorar.
