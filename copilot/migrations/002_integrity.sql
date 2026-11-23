ALTER TABLE copilot.memberships ADD CONSTRAINT memberships_role_check
    CHECK (role IN ('admin', 'member'));
ALTER TABLE copilot.votes ADD CONSTRAINT votes_value_check CHECK (value IN (-1, 0, 1));
ALTER TABLE copilot.ideas ADD CONSTRAINT ideas_status_check
    CHECK (status IN ('backlog', 'evaluating', 'planned', 'experimenting', 'archived'));
ALTER TABLE copilot.teams ADD CONSTRAINT teams_budget_check CHECK (daily_token_budget > 0);
ALTER TABLE copilot.team_topics ADD CONSTRAINT topics_weight_check CHECK (weight > 0 AND weight <= 1);
ALTER TABLE copilot.budget_usage ADD CONSTRAINT budget_nonnegative_check CHECK (used >= 0 AND reserved >= 0);

-- Business tables are API-only. Supabase anon/authenticated must not access the private schema.
REVOKE ALL ON SCHEMA copilot FROM PUBLIC;
DO $$
DECLARE role_name text;
BEGIN
    FOREACH role_name IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
            EXECUTE format('REVOKE ALL ON SCHEMA copilot FROM %I', role_name);
            EXECUTE format('REVOKE ALL ON ALL TABLES IN SCHEMA copilot FROM %I', role_name);
        END IF;
    END LOOP;
END $$;
