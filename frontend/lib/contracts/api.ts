import type {
  Annotation, Claim, DailyDigest, Idea, IdeaStatus, Me, Paper, PaperDetail,
  ProfileInput, Role, TeamConfigInput, UUID,
} from './types';

export class ApiError extends Error {
  constructor(public status: number, public detail: unknown) {
    super(typeof detail === 'string' ? detail : `API error ${status}`);
  }
}

/** Pass a token getter, not a captured token, so Supabase refreshes are respected. */
export function createCopilotClient(baseUrl: string, getAccessToken: () => Promise<string | null>) {
  async function request<T>(path: string, init: RequestInit = {}, text = false): Promise<T> {
    const token = await getAccessToken();
    if (!token) throw new ApiError(401, '请先登录');
    const response = await fetch(`${baseUrl.replace(/\/$/, '')}${path}`, {
      ...init, headers: {
        ...(init.body ? {'Content-Type': 'application/json'} : {}),
        Authorization: `Bearer ${token}`, ...init.headers,
      },
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({detail: response.statusText}));
      throw new ApiError(response.status, body.detail);
    }
    return (text ? await response.text() : await response.json()) as T;
  }
  const teamPath = (team: UUID) => `/v1/teams/${encodeURIComponent(team)}`;
  const paperPath = (team: UUID, paper: UUID) => `${teamPath(team)}/papers/${encodeURIComponent(paper)}`;
  const body = (method: string, value: unknown): RequestInit => ({method, body: JSON.stringify(value)});
  return {
    me: () => request<Me>('/v1/me'),
    daily: (team: UUID, day?: string) => request<DailyDigest>(`${teamPath(team)}/daily${day ? `?day=${encodeURIComponent(day)}` : ''}`),
    papers: (team: UUID, q = '', limit = 20, offset = 0) => request<{
      items: Paper[]; total: number; limit: number; offset: number;
    }>(`${teamPath(team)}/papers?${new URLSearchParams({q, limit: String(limit), offset: String(offset)})}`),
    detail: (team: UUID, paper: UUID) => request<PaperDetail>(paperPath(team, paper)),
    search: (team: UUID, q: string) => request<{items: {paper: Paper; analysis_id: UUID; summary: string}[]}>(
      `${teamPath(team)}/search?q=${encodeURIComponent(q)}`, {method: 'POST'}),
    annotate: (team: UUID, paper: UUID, input: {body: string; parent_id?: UUID; anchor?: string}) =>
      request<Annotation>(`${paperPath(team, paper)}/annotations`, body('POST', input)),
    claim: (team: UUID, paper: UUID, meeting_date: string) => request<Claim>(
      `${paperPath(team, paper)}/claims`, body('POST', {meeting_date})),
    unclaim: (team: UUID, id: UUID) => request<{ok: boolean}>(`${teamPath(team)}/claims/${id}`, {method: 'DELETE'}),
    vote: (team: UUID, paper: UUID, value: -1 | 0 | 1) => request<{ok: boolean}>(
      `${paperPath(team, paper)}/vote`, body('PUT', {value})),
    ideas: (team: UUID, status?: IdeaStatus) => request<{items: Idea[]}>(
      `${teamPath(team)}/ideas${status ? `?status=${status}` : ''}`),
    addIdea: (team: UUID, input: {paper_id: UUID; title: string; hypothesis: string;
      experiment: string; annotation_id?: UUID}) => request<Idea>(`${teamPath(team)}/ideas`, body('POST', input)),
    updateIdea: (team: UUID, id: UUID, status: IdeaStatus, assignee_id: UUID | null) => request<Idea>(
      `${teamPath(team)}/ideas/${id}`, body('PATCH', {status, assignee_id})),
    config: (team: UUID) => request<{
      team: {id: UUID; name: string; daily_token_budget: number};
      topics: (TeamConfigInput['topics'][number] & {id: UUID; team_id: UUID})[];
      interests: Record<string, number>; role: Role; exploration_ratio: number;
    }>(`${teamPath(team)}/config`),
    setConfig: (team: UUID, input: TeamConfigInput) => request<{ok: boolean}>(
      `${teamPath(team)}/config`, body('PUT', input)),
    setProfile: (team: UUID, input: ProfileInput) => request<{ok: boolean}>(
      `${teamPath(team)}/profile`, body('PATCH', input)),
    members: (team: UUID) => request<{items: {id: UUID; display_name: string; role: Role}[]}>(
      `${teamPath(team)}/members`),
    addMember: (team: UUID, user_id: UUID, role: Role) => request<{ok: boolean}>(
      `${teamPath(team)}/members`, body('PUT', {user_id, role})),
    readingList: (team: UUID, week?: string) => request<string>(
      `${teamPath(team)}/reading-list${week ? `?week=${encodeURIComponent(week)}` : ''}`, {}, true),
    weekly: (team: UUID) => request<{items: {team_id: UUID; week: string; payload: {
      reading_list_markdown: string; state: string; hypotheses_verified: false;
      trends: {bottleneck: string; paper_ids: UUID[]; hypothesis: string; experiment: string;
        metric: string; falsification: string}[];
    }}[]}>(`${teamPath(team)}/weekly`),
    usage: (team: UUID) => request<{items: {scope: string; day: string; used: number; reserved: number}[];
      team_limit: number; llm_enabled: boolean}>(`${teamPath(team)}/admin/usage`),
    jobs: (team: UUID) => request<{items: {id: UUID; kind: string; state: string;
      stats: Record<string, unknown>; started_at: string; finished_at: string | null}[]}>(
      `${teamPath(team)}/admin/jobs`),
  };
}
