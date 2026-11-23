/** Contract for the implemented API. IDs are UUID strings and timestamps are ISO 8601 UTC. */
export type UUID = string;
export type Role = 'admin' | 'member';
export interface Evidence { anchor: string; quote: string }
export interface Fact { statement: string; evidence: Evidence }
export interface Gap extends Fact { kind: 'paper_stated' | 'inference' }
export interface Hypothesis extends Fact {
  rationale: string; experiment: string; metric: string; falsification: string;
}
export interface PaperReport {
  summary: string; innovation: string; methods: Fact[]; paper_facts: Fact[];
  critical_gaps: Gap[]; testable_hypotheses: Hypothesis[]; reviewer_view: string;
  source: { kind: 'abstract' | 'html' | 'latex' | 'pdf'; truncated: boolean;
    requested_tier: 'deep' | 'medium'; evidence_checked: boolean;
    paper_version: string | null; paper_updated_at: string };
}
export interface Paper {
  personal_state?: PaperState;
  id: UUID; arxiv_id: string | null; arxiv_version: string | null;
  doi: string | null; s2_id: string | null; title: string; normalized_title: string;
  abstract: string; authors: string[]; categories: string[];
  first_submitted_at: string | null; updated_at: string | null; first_date_verified: boolean;
  source_url: string; code_urls: string[]; discovered_at: string;
}
export interface Analysis {
  id: UUID; paper_id: UUID; cache_key: string; tier: 'deep' | 'medium'; model: string;
  prompt_version: string; report: PaperReport; embedding_model: string | null; created_at: string;
}
export interface Annotation {
  id: UUID; team_id: UUID; paper_id: UUID; user_id: UUID;
  parent_id: UUID | null; anchor: string | null; body: string; created_at: string;
}
export interface Claim {
  id: UUID; team_id: UUID; paper_id: UUID; user_id: UUID; meeting_date: string; created_at: string;
}
export type IdeaStatus = 'backlog' | 'evaluating' | 'planned' | 'experimenting' | 'archived';
export interface Idea {
  id: UUID; team_id: UUID; paper_id: UUID; user_id: UUID; annotation_id: UUID | null;
  title: string; hypothesis: string; experiment: string; status: IdeaStatus;
  assignee_id: UUID | null; created_at: string;
}
export interface FeedItem {
  paper_id: UUID; title: string; abstract: string; source_url: string; arxiv_id: string | null;
  first_submitted_at: string | null; quality: number; reason: string;
  votes: number; claims: number; score: number; team_match: number; personal_match: number;
  is_exploration: boolean; analysis_state: 'ready' | 'metadata_only';
  summary?: string; innovation?: string; analysis_tier?: 'deep' | 'medium';
  analysis_stale?: boolean;
}
export interface DailyDigest {
  day: string; team_must_read: FeedItem[];
  personal: { items: FeedItem[]; exploration_target: number; exploration_actual: number };
  persisted: boolean; generated_at?: string; llm_enabled?: boolean; message?: string;
}
export interface TeamConfigInput {
  topics: {label: string; keywords: string[]; weight: number}[];
  daily_token_budget: number;
}
export interface ProfileInput {
  display_name: string; interests: Record<string, number>; email_opt_in: boolean;
}
export interface Me {
  id: UUID; email: string; display_name: string; email_opt_in: boolean;
  memberships: {team_id: UUID; user_id: UUID; role: Role; interests: Record<string, number>}[];
}
export interface PaperDetail {
  personal_state?: PaperState;
  paper: Paper; analyses: Analysis[]; annotations: Annotation[]; claims: Claim[];
  vote_total: number; my_vote: -1 | 0 | 1;
}

export interface PaperState { saved: boolean; is_read: boolean; note: string; updated_at: string | null }
export interface Invitation {
  id: UUID; team_id: UUID; email: string; invited_by: UUID; expires_at: string; created_at: string;
  accepted_at: string | null; accepted_by: UUID | null; revoked_at: string | null;
  state: 'pending' | 'accepted' | 'expired' | 'revoked';
}
export interface Usage {
  items: {scope: string; day: string; used: number; reserved: number}[];
  team_limit: number; llm_enabled: boolean; provider: string; daily_budget_cny: string | null;
  global_token_limit: number; global_tokens_remaining: number; cost_basis: string;
  spending: {day: string; input_tokens: number; output_tokens: number; estimated_cny_upper: string;
    calls: number; unpriced_calls: number}[];
}
export interface Integrations {
  analysis_enabled: boolean; analysis_provider: string; analysis_key_configured: boolean;
  semantic_search_available: boolean; email_digest_provider: string; group_delivery_provider: string;
  workspace_url: string; daily_budget_cny: string; weekly_topic_fallback: boolean;
}
