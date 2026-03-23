-- age_schema.sql — PostgreSQL AGE Schema für XOS Context-Verwaltung.
--
-- Einmalig ausführen nach dem Cluster-Setup:
--   psql -h localhost -U postgres -d xium -f age_schema.sql
--
-- Oder via kubectl:
--   kubectl exec -n xos-dev statefulset/postgresql -- \
--     sh -c "PGPASSWORD=xium-dev-2026 psql -U postgres -d xium" < age_schema.sql

-- AGE Extension aktivieren
CREATE EXTENSION IF NOT EXISTS age;
LOAD 'age';
SET search_path = ag_catalog, "$user", public;

-- Graph anlegen (idempotent)
SELECT create_graph('xos_graph')
WHERE NOT EXISTS (
    SELECT 1 FROM ag_graph WHERE name = 'xos_graph'
);

-- Tabelle für XML-Inhalte der Contexts
-- AGE verwaltet die Beziehungen, PostgreSQL speichert den Inhalt
CREATE TABLE IF NOT EXISTS public.xos_contexts (
    name        varchar(200) PRIMARY KEY,
    xml_content text         NOT NULL,
    updated_at  timestamptz  DEFAULT now() NOT NULL
);

-- Index für schnellen Lookup nach Name
CREATE INDEX IF NOT EXISTS xos_contexts_name_idx ON public.xos_contexts (name);
