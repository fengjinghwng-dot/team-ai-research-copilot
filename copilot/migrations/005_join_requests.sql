ALTER TABLE copilot.teams ADD COLUMN join_requests_enabled boolean NOT NULL DEFAULT false;
CREATE TABLE copilot.join_requests (
    id uuid PRIMARY KEY,
    team_id uuid NOT NULL REFERENCES copilot.teams(id),
    user_id uuid NOT NULL REFERENCES copilot.users(id),
    message text NOT NULL DEFAULT '' CHECK (length(message) <= 1000),
    status varchar(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','rejected','cancelled')),
    created_at timestamptz NOT NULL,
    reviewed_at timestamptz,
    reviewed_by uuid REFERENCES copilot.users(id)
);
CREATE UNIQUE INDEX join_requests_pending_unique ON copilot.join_requests(team_id,user_id) WHERE status='pending';
CREATE INDEX ix_copilot_join_requests_team_id ON copilot.join_requests(team_id);
CREATE INDEX ix_copilot_join_requests_user_id ON copilot.join_requests(user_id);
REVOKE ALL ON copilot.join_requests FROM PUBLIC;
