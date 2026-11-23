CREATE EXTENSION IF NOT EXISTS vector;
SET search_path TO copilot, extensions, public;


CREATE TABLE copilot.budget_usage (
	scope VARCHAR(64) NOT NULL, 
	day DATE NOT NULL, 
	used BIGINT NOT NULL, 
	reserved BIGINT NOT NULL, 
	PRIMARY KEY (scope, day)
)

;


CREATE TABLE copilot.deliveries (
	key VARCHAR(250) NOT NULL, 
	state VARCHAR(20) NOT NULL, 
	error TEXT, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (key)
)

;


CREATE TABLE copilot.fetch_cache (
	key VARCHAR(64) NOT NULL, 
	body BYTEA NOT NULL, 
	content_type VARCHAR(200) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (key)
)

;


CREATE TABLE copilot.papers (
	id UUID NOT NULL, 
	arxiv_id VARCHAR(100), 
	arxiv_version VARCHAR(120), 
	doi VARCHAR(300), 
	s2_id VARCHAR(100), 
	title TEXT NOT NULL, 
	normalized_title TEXT NOT NULL, 
	abstract TEXT NOT NULL, 
	authors JSONB NOT NULL, 
	categories JSONB NOT NULL, 
	first_submitted_at TIMESTAMP WITH TIME ZONE, 
	updated_at TIMESTAMP WITH TIME ZONE, 
	first_date_verified BOOLEAN NOT NULL, 
	source_url TEXT NOT NULL, 
	code_urls JSONB NOT NULL, 
	discovered_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (arxiv_id), 
	UNIQUE (doi), 
	UNIQUE (s2_id)
)

;


CREATE TABLE copilot.teams (
	id UUID NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	daily_token_budget INTEGER NOT NULL, 
	PRIMARY KEY (id)
)

;


CREATE TABLE copilot.users (
	id UUID NOT NULL, 
	email VARCHAR(320) NOT NULL, 
	display_name VARCHAR(100) NOT NULL, 
	email_opt_in BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (email)
)

;


CREATE TABLE copilot.annotations (
	id UUID NOT NULL, 
	team_id UUID NOT NULL, 
	paper_id UUID NOT NULL, 
	user_id UUID NOT NULL, 
	parent_id UUID, 
	anchor VARCHAR(200), 
	body TEXT NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(team_id) REFERENCES copilot.teams (id), 
	FOREIGN KEY(paper_id) REFERENCES copilot.papers (id), 
	FOREIGN KEY(user_id) REFERENCES copilot.users (id), 
	FOREIGN KEY(parent_id) REFERENCES copilot.annotations (id)
)

;


CREATE TABLE copilot.claims (
	id UUID NOT NULL, 
	team_id UUID NOT NULL, 
	paper_id UUID NOT NULL, 
	user_id UUID NOT NULL, 
	meeting_date DATE NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (team_id, paper_id, meeting_date), 
	FOREIGN KEY(team_id) REFERENCES copilot.teams (id), 
	FOREIGN KEY(paper_id) REFERENCES copilot.papers (id), 
	FOREIGN KEY(user_id) REFERENCES copilot.users (id)
)

;


CREATE TABLE copilot.digests (
	team_id UUID NOT NULL, 
	user_id UUID NOT NULL, 
	day DATE NOT NULL, 
	payload JSONB NOT NULL, 
	PRIMARY KEY (team_id, user_id, day), 
	FOREIGN KEY(team_id) REFERENCES copilot.teams (id), 
	FOREIGN KEY(user_id) REFERENCES copilot.users (id)
)

;


CREATE TABLE copilot.documents (
	cache_key VARCHAR(64) NOT NULL, 
	paper_id UUID NOT NULL, 
	kind VARCHAR(20) NOT NULL, 
	sections JSONB NOT NULL, 
	truncated BOOLEAN NOT NULL, 
	PRIMARY KEY (cache_key), 
	FOREIGN KEY(paper_id) REFERENCES copilot.papers (id)
)

;


CREATE TABLE copilot.job_runs (
	id UUID NOT NULL, 
	kind VARCHAR(30) NOT NULL, 
	team_id UUID, 
	state VARCHAR(20) NOT NULL, 
	stats JSONB NOT NULL, 
	started_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	finished_at TIMESTAMP WITH TIME ZONE, 
	PRIMARY KEY (id), 
	FOREIGN KEY(team_id) REFERENCES copilot.teams (id)
)

;


CREATE TABLE copilot.llm_calls (
	id UUID NOT NULL, 
	team_id UUID NOT NULL, 
	day DATE NOT NULL, 
	model VARCHAR(120) NOT NULL, 
	purpose VARCHAR(30) NOT NULL, 
	reserved INTEGER NOT NULL, 
	actual INTEGER, 
	state VARCHAR(20) NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(team_id) REFERENCES copilot.teams (id)
)

;


CREATE TABLE copilot.memberships (
	team_id UUID NOT NULL, 
	user_id UUID NOT NULL, 
	role VARCHAR(20) NOT NULL, 
	interests JSONB NOT NULL, 
	PRIMARY KEY (team_id, user_id), 
	FOREIGN KEY(team_id) REFERENCES copilot.teams (id), 
	FOREIGN KEY(user_id) REFERENCES copilot.users (id)
)

;


CREATE TABLE copilot.paper_analyses (
	id UUID NOT NULL, 
	cache_key VARCHAR(64) NOT NULL, 
	paper_id UUID NOT NULL, 
	tier VARCHAR(20) NOT NULL, 
	model VARCHAR(120) NOT NULL, 
	prompt_version VARCHAR(64) NOT NULL, 
	report JSONB NOT NULL, 
	embedding VECTOR(1536), 
	embedding_model VARCHAR(120), 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (cache_key), 
	FOREIGN KEY(paper_id) REFERENCES copilot.papers (id)
)

;


CREATE TABLE copilot.team_papers (
	team_id UUID NOT NULL, 
	paper_id UUID NOT NULL, 
	discovered_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	relevance JSONB NOT NULL, 
	score FLOAT NOT NULL, 
	reason TEXT NOT NULL, 
	PRIMARY KEY (team_id, paper_id), 
	FOREIGN KEY(team_id) REFERENCES copilot.teams (id), 
	FOREIGN KEY(paper_id) REFERENCES copilot.papers (id)
)

;


CREATE TABLE copilot.team_topics (
	id UUID NOT NULL, 
	team_id UUID NOT NULL, 
	label VARCHAR(100) NOT NULL, 
	keywords JSONB NOT NULL, 
	weight FLOAT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(team_id) REFERENCES copilot.teams (id)
)

;


CREATE TABLE copilot.votes (
	team_id UUID NOT NULL, 
	paper_id UUID NOT NULL, 
	user_id UUID NOT NULL, 
	value INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (team_id, paper_id, user_id), 
	FOREIGN KEY(team_id) REFERENCES copilot.teams (id), 
	FOREIGN KEY(paper_id) REFERENCES copilot.papers (id), 
	FOREIGN KEY(user_id) REFERENCES copilot.users (id)
)

;


CREATE TABLE copilot.weekly_reports (
	team_id UUID NOT NULL, 
	week DATE NOT NULL, 
	payload JSONB NOT NULL, 
	PRIMARY KEY (team_id, week), 
	FOREIGN KEY(team_id) REFERENCES copilot.teams (id)
)

;


CREATE TABLE copilot.ideas (
	id UUID NOT NULL, 
	team_id UUID NOT NULL, 
	paper_id UUID NOT NULL, 
	user_id UUID NOT NULL, 
	annotation_id UUID, 
	title VARCHAR(200) NOT NULL, 
	hypothesis TEXT NOT NULL, 
	experiment TEXT NOT NULL, 
	status VARCHAR(30) NOT NULL, 
	assignee_id UUID, 
	created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(team_id) REFERENCES copilot.teams (id), 
	FOREIGN KEY(paper_id) REFERENCES copilot.papers (id), 
	FOREIGN KEY(user_id) REFERENCES copilot.users (id), 
	FOREIGN KEY(annotation_id) REFERENCES copilot.annotations (id), 
	FOREIGN KEY(assignee_id) REFERENCES copilot.users (id)
)

;

CREATE INDEX ix_copilot_papers_first_submitted_at ON copilot.papers (first_submitted_at);
CREATE INDEX ix_copilot_papers_normalized_title ON copilot.papers (normalized_title);
CREATE INDEX ix_copilot_annotations_team_id ON copilot.annotations (team_id);
CREATE INDEX ix_copilot_annotations_paper_id ON copilot.annotations (paper_id);
CREATE INDEX ix_copilot_documents_paper_id ON copilot.documents (paper_id);
CREATE INDEX ix_copilot_paper_analyses_paper_id ON copilot.paper_analyses (paper_id);
CREATE INDEX analyses_embedding_hnsw ON copilot.paper_analyses USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ix_copilot_team_papers_discovered_at ON copilot.team_papers (discovered_at);
CREATE INDEX ix_copilot_team_topics_team_id ON copilot.team_topics (team_id);
CREATE INDEX ix_copilot_ideas_team_id ON copilot.ideas (team_id);
