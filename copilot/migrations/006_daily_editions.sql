CREATE TABLE copilot.daily_editions (
    team_id uuid NOT NULL REFERENCES copilot.teams(id),
    day date NOT NULL,
    payload jsonb NOT NULL,
    PRIMARY KEY (team_id, day)
);
REVOKE ALL ON copilot.daily_editions FROM PUBLIC;
