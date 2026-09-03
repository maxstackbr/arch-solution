# Segurança para Consumo/Integração de Serviços

## O que existe em código (escopo simplificado)

| Controle | Como |
|---|---|
| **Autenticação de API** | `X-API-Key` em todas as rotas de negócio, validado contra `API_KEY` ([`.env.example`](../.env.example)); chave ausente ou inválida dá `401`. `/health` e `/metrics` ficam fora, para health checks sem credencial |
| **Validação de entrada** | Schemas Pydantic antes do domínio (tipos, `amount > 0`, `type` no enum) — entrada malformada morre com `422` antes de qualquer efeito colateral |
| **CORS restritivo** | Default é lista **vazia** — nada cross-origin passa, o correto para uma API sem cliente de navegador. Liberar é opt-in via `CORS_ORIGINS`, nunca o `*` que sobra de setup de desenvolvimento |
| **Segredos fora do código** | Credenciais e `API_KEY` vêm de variáveis de ambiente (`.env`, git-ignorado); [`.env.example`](../.env.example) documenta as chaves sem valores reais |
| **Sem superfície de escrita no Consolidado** | Não há endpoint público de escrita ([`03`](03-api-contracts.md)): `daily_balances` só muda por evento interno, o que elimina a classe de ataque "forjar um saldo pela API" |
| **Lançamentos imutáveis** | Sem `PUT`/`DELETE` no Ledger — qualquer correção é um novo lançamento de estorno, auditável |

## O que fica só na arquitetura alvo (AWS)

| Controle | O quê |
|---|---|
| **Autenticação robusta** | API Gateway + Cognito (OAuth2) para clientes externos; IAM roles (SigV4) ou mTLS entre serviços na VPC, no lugar de API Key estática compartilhada |
| **Rede** | RDS e ElastiCache em subnets privadas, sem IP público, alcançáveis só pelos security groups das tasks ECS correspondentes |
| **WAF** | Na borda (API Gateway/CloudFront), com regras OWASP e rate limiting por IP |
| **Secrets Manager** | Credenciais com rotação automática, no lugar de variáveis de ambiente estáticas |
| **Criptografia** | Em trânsito (TLS em todas as bordas, incluindo ECS↔RDS/ElastiCache) e em repouso (RDS/ElastiCache/SQS) |
| **Least privilege** | Uma IAM role por task: o Ledger não tem permissão de ler a fila do Consolidado, o Worker não escreve no banco do Ledger |
| **Auditoria** | CloudTrail sobre as chamadas de API AWS — quem alterou o quê na infraestrutura |
| **`Idempotency-Key` do cliente** | Header opcional em `POST /entries`, para reenvio seguro após timeout de rede — resolve duplicação por retry do *cliente*, que a idempotência do consumidor não cobre |
