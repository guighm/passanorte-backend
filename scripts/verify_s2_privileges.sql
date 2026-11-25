-- Run as the local deployment administrator after S2 migrations.
DO $$
DECLARE
    domains text[] := ARRAY['auth','catalog','gamification','benefits','insights','notifications','chatbot'];
    domain text;
    other_domain text;
    runtime text;
    readable regclass;
    immutable regclass;
BEGIN
    FOREACH domain IN ARRAY domains LOOP
        runtime := domain || '_runtime';
        readable := format('%I.outbox', domain)::regclass;
        IF NOT has_schema_privilege(runtime, domain, 'USAGE')
           OR has_schema_privilege(runtime, domain, 'CREATE')
           OR has_database_privilege(runtime, current_database(), 'CREATE')
           OR has_database_privilege(runtime, current_database(), 'TEMP')
           OR has_schema_privilege(runtime, 'public', 'CREATE')
           OR pg_has_role(runtime, domain || '_owner', 'MEMBER')
           OR NOT has_table_privilege(runtime, readable, 'SELECT')
           OR NOT has_table_privilege(runtime, readable, 'INSERT')
           OR NOT has_table_privilege(runtime, readable, 'UPDATE')
           OR NOT has_table_privilege(runtime, readable, 'DELETE')
           OR has_table_privilege(runtime, format('%I.alembic_version', domain), 'SELECT') THEN
            RAISE EXCEPTION 'Incorrect own-domain grants for %', runtime;
        END IF;
        FOREACH other_domain IN ARRAY domains LOOP
            IF other_domain <> domain AND (
                has_schema_privilege(runtime, other_domain, 'USAGE')
                OR has_table_privilege(runtime, format('%I.outbox', other_domain), 'SELECT,INSERT,UPDATE,DELETE')
            ) THEN
                RAISE EXCEPTION 'Cross-domain grants: % on %', runtime, other_domain;
            END IF;
        END LOOP;
        FOREACH immutable IN ARRAY ARRAY[
            to_regclass(format('%I.audit_logs', domain)), to_regclass(format('%I.ledger', domain))
        ] LOOP
            IF immutable IS NOT NULL AND (
                NOT has_table_privilege(runtime, immutable, 'SELECT')
                OR NOT has_table_privilege(runtime, immutable, 'INSERT')
                OR has_table_privilege(runtime, immutable, 'UPDATE,DELETE,TRUNCATE')
            ) THEN
                RAISE EXCEPTION 'Incorrect append-only grants on %', immutable;
            END IF;
        END LOOP;
    END LOOP;
END $$;
