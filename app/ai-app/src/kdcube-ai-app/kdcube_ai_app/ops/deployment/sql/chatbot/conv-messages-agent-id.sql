-- SPDX-License-Identifier: MIT
-- Copyright (c) 2026 Elena Viter
--
-- conv_messages.agent_id (one-time, idempotent migration). Adds the optional
-- owning-agent column to a previously-deployed project schema. Replace <SCHEMA>
-- with the project schema (e.g. kdcube_<tenant>_<project>) before applying,
-- mirroring deploy-kdcube-proj-schema.sql.
--
-- Runs BEFORE the schema provision (deploy-kdcube-proj-schema.sql). `CREATE TABLE
-- IF NOT EXISTS` never retrofits a column onto an existing table, so an
-- already-deployed conv_messages needs this explicit ALTER. The provision's
-- CREATE TABLE carries agent_id for fresh schemas; this migration carries it for
-- existing ones.
--
-- Additive and nullable: existing rows get NULL (== single / unspecified agent;
-- the column reflects what the runtime passes, NULL only when no agent_id is
-- given). Both guards (ALTER TABLE IF EXISTS / ADD COLUMN IF NOT EXISTS) make the
-- file a clean no-op on a fresh schema (table absent) and on a re-run.
--
-- TEMPORARY: remove this file (and its entry in apply_project_migrations) once
-- every environment has the agent_id column.

ALTER TABLE IF EXISTS <SCHEMA>.conv_messages
  ADD COLUMN IF NOT EXISTS agent_id TEXT NULL;
