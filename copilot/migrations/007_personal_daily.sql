ALTER TABLE copilot.memberships ADD COLUMN daily_preferences JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE copilot.papers ADD COLUMN venue VARCHAR(200);
ALTER TABLE copilot.papers ADD COLUMN publication_year INTEGER;
ALTER TABLE copilot.papers ADD COLUMN venue_source TEXT;

CREATE TABLE copilot.personal_daily_jobs (
    id UUID PRIMARY KEY,
    team_id UUID NOT NULL,
    user_id UUID NOT NULL,
    day DATE NOT NULL,
    preferences JSONB NOT NULL,
    state VARCHAR(20) NOT NULL,
    stats JSONB NOT NULL,
    error TEXT,
    created_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ,
    FOREIGN KEY (team_id, user_id) REFERENCES copilot.memberships(team_id, user_id) ON DELETE CASCADE,
    CHECK (state IN ('queued', 'running', 'succeeded', 'degraded', 'failed'))
);
CREATE UNIQUE INDEX personal_daily_jobs_active_unique ON copilot.personal_daily_jobs(team_id, user_id)
    WHERE state IN ('queued', 'running');
CREATE INDEX personal_daily_jobs_queue ON copilot.personal_daily_jobs(created_at)
    WHERE state IN ('queued', 'running');
