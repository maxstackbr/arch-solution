-- Cria os dois bancos lógicos, um por bounded context (ADR 0002).
-- Executado automaticamente pela imagem oficial do Postgres na primeira inicialização do volume.
CREATE DATABASE ledger_db;
CREATE DATABASE consolidation_db;
