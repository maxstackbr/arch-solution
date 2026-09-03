# Estimativa de Custos — Infraestrutura AWS

> Estimativa de ordem de grandeza (metodologia AWS Pricing Calculator, região `us-east-1`, preços sob demanda de 2025/2026), não uma cotação formal. Objetivo: dar ao negócio uma noção de custo mensal da arquitetura alvo descrita em [`02-target-architecture.md`](02-target-architecture.md) e evidenciar as principais alavancas de otimização — não uma proposta comercial.

## Premissas de volume assumidas

- Pico de 50 req/s em `GET /consolidated` só em janelas curtas; média sustentada de ~5 req/s no mês (~13M requisições).
- Escrita uma ordem de grandeza abaixo da leitura — irrelevante para o dimensionamento nesta escala.
- 1 task de baseline por serviço; o auto scaling de pico é elástico e cresce com o uso real.

## Tabela de custos

| Componente | Especificação | Custo mensal estimado (USD) |
|---|---|---:|
| ECS Fargate — Ledger API | 0,5 vCPU / 1 GB, 1 task, 24×7 | ~$18 |
| ECS Fargate — Consolidation API | 0,5 vCPU / 1 GB, 1 task, 24×7 | ~$18 |
| ECS Fargate — Consolidation Worker | 0,5 vCPU / 1 GB, 1 task, **Fargate Spot** | ~$5 |
| RDS PostgreSQL — `ledger_db` | db.t4g.micro, **Multi-AZ**, 20 GB gp3 | ~$49 |
| RDS PostgreSQL — `consolidation_db` | db.t4g.micro, Single-AZ, 20 GB gp3 | ~$14 |
| ElastiCache Redis | cache.t4g.micro, 1 nó | ~$12 |
| SNS + SQS (+ DLQ) | baixo volume, dentro/próximo do free tier | ~$1 |
| API Gateway (HTTP API) + NLB (VPC Link) | ~13M req/mês | ~$29 |
| NAT Gateway | 1 AZ, egress mínimo | ~$35 |
| CloudWatch (logs, métricas, alarmes) | retenção 30 dias | ~$12 |
| Secrets Manager | 4 segredos (credenciais DB ×2, API key, Redis) | ~$1,6 |
| AWS WAF | regras básicas (rate limiting, managed rules) | ~$6 |
| **Total estimado** | | **≈ $200/mês** |

## Por que o RDS do Ledger custa mais que o do Consolidation

`ledger_db` é Multi-AZ porque é a fonte da verdade financeira — RNF-1 justifica o custo do failover automático. `consolidation_db` é read model reconstruível: se perdido, basta reprocessar a fila dentro da retenção. Single-AZ ali é escolha de custo-benefício, não omissão.

## Maiores alavancas de otimização (em ordem de impacto)

**NAT Gateway (~$35/mês)** é o item proporcionalmente mais caro para o tráfego que gera. Substituí-lo por VPC Endpoints (Gateway para S3, Interface para ECR/CloudWatch/Secrets Manager) elimina o egress via NAT para tráfego que nunca sai da AWS — corta o item quase inteiro se não houver dependência externa real.

| Alavanca | Efeito | Ressalva |
|---|---|---|
| **Fargate Spot** | Já aplicado ao Worker (tolera interrupção, pois o consumo é idempotente — ADR 0006) | Estender à Consolidation API só em ambientes não críticos; não em produção, que serve tráfego síncrono |
| **Aurora Serverless v2** no `consolidation_db` | Escala com a carga de leitura, sem pagar capacidade ociosa | Vale reavaliar só se o tráfego real for mais espaçado (picos concentrados, vales longos) que o estimado aqui |
| **Savings Plans / RIs** na capacidade baseline (Fargate + RDS) | Desconto sobre o custo fixo | Só depois de conhecer o padrão real em produção — antes disso, trava capacidade contra um dimensionamento incerto |
| **Free Tier** | Boa parte de RDS/Fargate/CloudWatch dos primeiros 12 meses, se a conta for nova | Não computado na tabela por ser temporário |
