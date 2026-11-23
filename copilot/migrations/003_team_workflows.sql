CREATE TABLE copilot.invitations (
    id uuid PRIMARY KEY,
    team_id uuid NOT NULL REFERENCES copilot.teams(id),
    email varchar(320) NOT NULL CHECK (email = lower(trim(email))),
    invited_by uuid NOT NULL REFERENCES copilot.users(id),
    expires_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL,
    accepted_at timestamptz,
    accepted_by uuid REFERENCES copilot.users(id),
    revoked_at timestamptz,
    UNIQUE (team_id, email)
);
CREATE INDEX invitations_team_id_idx ON copilot.invitations(team_id);
CREATE TABLE copilot.paper_states (
    team_id uuid NOT NULL,
    user_id uuid NOT NULL REFERENCES copilot.users(id),
    paper_id uuid NOT NULL,
    saved boolean NOT NULL DEFAULT false,
    is_read boolean NOT NULL DEFAULT false,
    note text NOT NULL DEFAULT '' CHECK (length(note) <= 10000),
    updated_at timestamptz NOT NULL,
    PRIMARY KEY (team_id, user_id, paper_id),
    FOREIGN KEY (team_id, paper_id) REFERENCES copilot.team_papers(team_id, paper_id) ON DELETE CASCADE
);
REVOKE ALL ON copilot.invitations, copilot.paper_states FROM PUBLIC;
