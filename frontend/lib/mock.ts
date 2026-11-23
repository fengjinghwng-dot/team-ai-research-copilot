import type {
  Annotation, Claim, DailyDigest, Idea, IdeaStatus, Me, Paper, PaperDetail,
  ProfileInput, Role, TeamConfigInput, UUID,
} from './contracts/types';
import { ApiError } from './contracts/api';

const MOCK_ROLE_KEY = 'copilot_mock_role';

export function isMockEnabled(): boolean {
  return process.env.NEXT_PUBLIC_USE_MOCK === 'true';
}

export function getMockRole(): Role {
  if (typeof window === 'undefined') return 'admin';
  try {
    const val = localStorage.getItem(MOCK_ROLE_KEY);
    return val === 'member' ? 'member' : 'admin';
  } catch {
    return 'admin';
  }
}

export function setMockRole(role: Role): void {
  if (typeof window === 'undefined') return;
  try {
    localStorage.setItem(MOCK_ROLE_KEY, role);
  } catch {
    // ignore
  }
}

// 仅用于本地演示模式，不包含任何真实团队或个人 UUID/邮箱
const DEMO_TEAM_ID = 'demo-team-0001';
const DEMO_USER_ADMIN = 'demo-user-admin';
const DEMO_USER_MEMBER = 'demo-user-member';
const DEMO_PAPER_1 = 'demo-paper-fedsubmuon';
const DEMO_PAPER_2 = 'demo-paper-phantom';
const DEMO_PAPER_3 = 'demo-paper-metaonly';

const demoPapers: Record<UUID, Paper> = {
  [DEMO_PAPER_1]: {
    id: DEMO_PAPER_1,
    arxiv_id: '2609.06073',
    arxiv_version: '2609.06073v2',
    doi: null,
    s2_id: null,
    title: 'FedSubMuon: Communication-Efficient Federated LLM Fine-Tuning via Structured Subspace Muon',
    normalized_title: 'fedsubmuon communication efficient federated llm fine tuning via structured subspace muon',
    abstract: 'We propose FedSubMuon, a communication-efficient federated Muon fine-tuning method that optimizes compact coefficient matrices within shared structured subspaces.',
    authors: ['Demo Author A', 'Demo Author B'],
    categories: ['cs.LG', 'cs.DC'],
    first_submitted_at: '2026-09-05T00:00:00Z',
    updated_at: '2026-09-12T00:00:00Z',
    first_date_verified: true,
    source_url: 'https://arxiv.org/abs/2609.06073',
    code_urls: [],
    discovered_at: '2026-11-23T06:00:00Z',
  },
  [DEMO_PAPER_2]: {
    id: DEMO_PAPER_2,
    arxiv_id: '2611.08971',
    arxiv_version: '2611.08971v1',
    doi: null,
    s2_id: null,
    title: 'Measuring Social Reasoning in Multi-Agent LLM Decision-Making',
    normalized_title: 'measuring social reasoning in multi agent llm decision making',
    abstract: 'We introduce PHANTOM-Bench separating isolated private judgments and public decisions after ambiguous social signals.',
    authors: ['Demo Author C'],
    categories: ['cs.AI', 'cs.MA'],
    first_submitted_at: '2026-11-06T00:00:00Z',
    updated_at: '2026-11-06T00:00:00Z',
    first_date_verified: true,
    source_url: 'https://arxiv.org/abs/2611.08971',
    code_urls: [],
    discovered_at: '2026-11-23T06:00:00Z',
  },
  [DEMO_PAPER_3]: {
    id: DEMO_PAPER_3,
    arxiv_id: '2609.33207',
    arxiv_version: '2609.33207v1',
    doi: null,
    s2_id: null,
    title: 'MorphAtt: A Neuromorphic Accelerator for Efficient Multi-Head Attention Processing in Spiking Vision Transformers',
    normalized_title: 'morphatt a neuromorphic accelerator for efficient multi head attention processing',
    abstract: 'We propose MorphAtt, a digital accelerator expediting SViT inference using SpikeQKV, SpikeAtten, and RepConv modules.',
    authors: ['Demo Author D'],
    categories: ['cs.AR', 'cs.NE'],
    first_submitted_at: '2026-09-27T00:00:00Z',
    updated_at: '2026-09-27T00:00:00Z',
    first_date_verified: true,
    source_url: 'https://arxiv.org/abs/2609.33207',
    code_urls: [],
    discovered_at: '2026-11-23T06:00:00Z',
  },
};

const demoDetails: Record<UUID, PaperDetail> = {
  [DEMO_PAPER_1]: {
    paper: demoPapers[DEMO_PAPER_1],
    analyses: [
      {
        id: 'demo-analysis-1',
        paper_id: DEMO_PAPER_1,
        cache_key: 'demo-v1',
        tier: 'deep',
        model: 'demo-reasoning-model',
        prompt_version: 'v1',
        embedding_model: 'text-embedding-3-small',
        created_at: '2026-11-23T06:10:00Z',
        report: {
          summary: '在共享结构化子空间中优化紧凑系数矩阵，兼顾 Muon 矩阵几何与极低联邦通信开销。',
          innovation: '避免将 Muon 直接套在 LoRA 因子上破坏矩阵几何，通过投影梯度自适应追踪子空间基。',
          methods: [
            { statement: '客户端仅上传紧凑系数矩阵而非整层更新。', evidence: { anchor: 'S3.1', quote: 'reducing the client upload to compact coefficient matrices.' } },
          ],
          paper_facts: [
            { statement: '在 Dolly-15K 上，最接近通信基线在 Llama-1B 上需多消耗 5.5 倍通信量。', evidence: { anchor: 'S4.2', quote: 'the closest communication baseline requires 5.5 times more total communication on Llama-1B.' } },
          ],
          critical_gaps: [
            { kind: 'inference', statement: '在 Qwen-4B 上通信优势收敛至 1.4 倍，更大规模模型下的投影开销尚待验证。', evidence: { anchor: 'S4.2', quote: '1.4 times more total communication on Qwen-4B' } },
          ],
          testable_hypotheses: [
            {
              statement: '按层奇异值谱动态分配子空间秩并加入本地残差误差反馈可扩大 4B+ 模型压缩红利。',
              evidence: { anchor: 'S4.2', quote: '5.5 times and 1.4 times more total communication' },
              rationale: '不同 Transformer 层的有效梯度秩差异显著，固定秩会造成高层冗余或底层截断。',
              experiment: '在 Qwen-4B + Non-IID Dolly-15K 上对比固定秩与层级自适应秩 + 误差反馈。',
              metric: '同等通信预算下的验证集困惑度与收敛轮次',
              falsification: '若高异构客户端下误差累积导致发散或增益低于 5%，则假设不成立。',
            },
          ],
          reviewer_view: '问题切入精准、方法优雅，建议重点核查极端 Non-IID 场景下的收敛稳定性。',
          source: {
            kind: 'html',
            truncated: false,
            requested_tier: 'deep',
            evidence_checked: true,
            paper_version: '2609.06073v1', // 故意设为 v1 演示“旧版本报告”提示
            paper_updated_at: '2026-09-05T00:00:00Z',
          },
        },
      },
    ],
    annotations: [
      {
        id: 'demo-ann-1',
        team_id: DEMO_TEAM_ID,
        paper_id: DEMO_PAPER_1,
        user_id: DEMO_USER_ADMIN,
        parent_id: null,
        anchor: 'S4.2',
        body: '这篇和我们本周关注的分布式微调通信瓶颈非常贴合，组会可以重点拆一下它的子空间更新公式。',
        created_at: '2026-11-23T07:00:00Z',
      },
    ],
    claims: [
      {
        id: 'demo-claim-1',
        team_id: DEMO_TEAM_ID,
        paper_id: DEMO_PAPER_1,
        user_id: DEMO_USER_MEMBER,
        meeting_date: '2026-11-27',
        created_at: '2026-11-23T07:05:00Z',
      },
    ],
    vote_total: 3,
    my_vote: 1,
  },
  [DEMO_PAPER_2]: {
    paper: demoPapers[DEMO_PAPER_2],
    analyses: [
      {
        id: 'demo-analysis-2',
        paper_id: DEMO_PAPER_2,
        cache_key: 'demo-v2',
        tier: 'medium',
        model: 'demo-fast-model',
        prompt_version: 'v1',
        embedding_model: null,
        created_at: '2026-11-23T06:12:00Z',
        report: {
          summary: '提出 PHANTOM-Bench，量化多智能体在模糊社交信号下的集体理性失效。',
          innovation: '分离独立私有判断与公开社交决策，验证透明化公开私有记录的无标签修复效应。',
          methods: [
            { statement: '对照独立私有判断、模糊公共信号决策与透明化恢复条件。', evidence: { anchor: 'page=2', quote: 'separates isolated private judgments, public decisions after ambiguous social signals' } },
          ],
          paper_facts: [
            { statement: '模糊公共信号可使公开准确率最高下降 47.8 个百分点。', evidence: { anchor: 'page=1', quote: 'Public accuracy drops by as much as 47.8 percentage points' } },
          ],
          critical_gaps: [
            { kind: 'paper_stated', statement: '公开私有判断的修复幅度在不同模型间差异明显。', evidence: { anchor: 'page=1', quote: 'although recovery varies across models' } },
          ],
          testable_hypotheses: [],
          reviewer_view: '基准设计清晰，但未提供训练期根治从众偏置的通用算法。',
          source: {
            kind: 'pdf',
            truncated: true,
            requested_tier: 'medium',
            evidence_checked: true,
            paper_version: '2611.08971v1',
            paper_updated_at: '2026-11-06T00:00:00Z',
          },
        },
      },
    ],
    annotations: [],
    claims: [],
    vote_total: 2,
    my_vote: 0,
  },
  [DEMO_PAPER_3]: {
    paper: demoPapers[DEMO_PAPER_3],
    analyses: [], // 演示 metadata_only / 尚无 AI 解读
    annotations: [],
    claims: [],
    vote_total: 0,
    my_vote: 0,
  },
};

let demoIdeas: Idea[] = [
  {
    id: 'demo-idea-1',
    team_id: DEMO_TEAM_ID,
    paper_id: DEMO_PAPER_1,
    user_id: DEMO_USER_ADMIN,
    annotation_id: 'demo-ann-1',
    title: '层级自适应子空间秩分配 + 本地残差误差补偿',
    hypothesis: '按 Transformer 层梯度奇异值谱动态分配秩可缓解 4B+ 模型上的通信压缩收益衰减。',
    experiment: '在 Qwen-4B + Non-IID Dolly-15K 上以 FedSubMuon-GT 为基线对比收敛曲线。',
    status: 'evaluating',
    assignee_id: DEMO_USER_ADMIN,
    created_at: '2026-11-23T07:30:00Z',
  },
];

let demoConfig = {
  team: { id: DEMO_TEAM_ID, name: 'AI Research Lab (演示团队)', daily_token_budget: 250000 },
  topics: [
    { id: 't1', team_id: DEMO_TEAM_ID, label: 'Distributed & Federated AI', keywords: ['federated', 'distributed', 'communication'], weight: 0.35 },
    { id: 't2', team_id: DEMO_TEAM_ID, label: 'LLM & Multi-Agent', keywords: ['multi-agent', 'reasoning', 'llm'], weight: 0.35 },
    { id: 't3', team_id: DEMO_TEAM_ID, label: 'Trustworthy AI', keywords: ['hallucination', 'reliable', 'safety'], weight: 0.30 },
  ],
  interests: { 'Distributed & Federated AI': 0.4, 'LLM & Multi-Agent': 0.35, 'Trustworthy AI': 0.25 } as Record<string, number>,
  exploration_ratio: 0.2,
};

const demoMembers = [
  { id: DEMO_USER_ADMIN, display_name: '演示管理员', role: 'admin' as Role },
  { id: DEMO_USER_MEMBER, display_name: '演示队员 A', role: 'member' as Role },
];

export function createMockCopilotClient() {
  const currentUserId = () => (getMockRole() === 'admin' ? DEMO_USER_ADMIN : DEMO_USER_MEMBER);
  return {
    me: async (): Promise<Me> => ({
      id: currentUserId(),
      email: getMockRole() === 'admin' ? 'demo-admin@example.local' : 'demo-member@example.local',
      display_name: getMockRole() === 'admin' ? '演示管理员' : '演示队员 A',
      email_opt_in: true,
      memberships: [
        { team_id: DEMO_TEAM_ID, user_id: currentUserId(), role: getMockRole(), interests: demoConfig.interests },
      ],
    }),
    daily: async (_team: UUID, day?: string): Promise<DailyDigest> => {
      const targetDay = day || new Date().toISOString().slice(0, 10);
      if (targetDay === '2026-01-01') {
        return { day: targetDay, team_must_read: [], personal: { items: [], exploration_target: 0.2, exploration_actual: 0 }, persisted: false, message: '该日期日报尚未生成' };
      }
      return {
        day: targetDay,
        persisted: true,
        generated_at: new Date().toISOString(),
        llm_enabled: true,
        team_must_read: [
          {
            paper_id: DEMO_PAPER_1,
            title: demoPapers[DEMO_PAPER_1].title,
            abstract: demoPapers[DEMO_PAPER_1].abstract,
            source_url: demoPapers[DEMO_PAPER_1].source_url,
            arxiv_id: demoPapers[DEMO_PAPER_1].arxiv_id,
            first_submitted_at: demoPapers[DEMO_PAPER_1].first_submitted_at,
            quality: 9.1,
            reason: '高度契合团队分布式微调主线，通信压缩比达 5.5x',
            votes: demoDetails[DEMO_PAPER_1].vote_total,
            claims: demoDetails[DEMO_PAPER_1].claims.length,
            score: 9.2,
            team_match: 0.95,
            personal_match: 0.92,
            is_exploration: false,
            analysis_state: 'ready',
            summary: demoDetails[DEMO_PAPER_1].analyses[0].report.summary,
            innovation: demoDetails[DEMO_PAPER_1].analyses[0].report.innovation,
            analysis_tier: 'deep',
            analysis_stale: true,
          },
        ],
        personal: {
          exploration_target: 0.2,
          exploration_actual: 1,
          items: [
            {
              paper_id: DEMO_PAPER_2,
              title: demoPapers[DEMO_PAPER_2].title,
              abstract: demoPapers[DEMO_PAPER_2].abstract,
              source_url: demoPapers[DEMO_PAPER_2].source_url,
              arxiv_id: demoPapers[DEMO_PAPER_2].arxiv_id,
              first_submitted_at: demoPapers[DEMO_PAPER_2].first_submitted_at,
              quality: 8.8,
              reason: '多智能体与可信 AI 交叉，揭示从众导致的准确率暴跌',
              votes: demoDetails[DEMO_PAPER_2].vote_total,
              claims: demoDetails[DEMO_PAPER_2].claims.length,
              score: 8.7,
              team_match: 0.85,
              personal_match: 0.89,
              is_exploration: false,
              analysis_state: 'ready',
              summary: demoDetails[DEMO_PAPER_2].analyses[0].report.summary,
              analysis_tier: 'medium',
              analysis_stale: false,
            },
            {
              paper_id: DEMO_PAPER_3,
              title: demoPapers[DEMO_PAPER_3].title,
              abstract: demoPapers[DEMO_PAPER_3].abstract,
              source_url: demoPapers[DEMO_PAPER_3].source_url,
              arxiv_id: demoPapers[DEMO_PAPER_3].arxiv_id,
              first_submitted_at: demoPapers[DEMO_PAPER_3].first_submitted_at,
              quality: 7.9,
              reason: '跨方向神经形态硬件探索位（当前仅元数据入库）',
              votes: 0,
              claims: 0,
              score: 7.6,
              team_match: 0.4,
              personal_match: 0.5,
              is_exploration: true,
              analysis_state: 'metadata_only',
            },
          ],
        },
      };
    },
    papers: async (_team: UUID, q = '', limit = 20, offset = 0) => {
      const all = Object.values(demoPapers).filter(
        (p) => !q || p.title.toLowerCase().includes(q.toLowerCase()) || p.abstract.toLowerCase().includes(q.toLowerCase())
      );
      return { items: all.slice(offset, offset + limit), total: all.length, limit, offset };
    },
    detail: async (_team: UUID, paper: UUID): Promise<PaperDetail> => {
      const d = demoDetails[paper];
      if (!d) throw new ApiError(404, '当前团队不存在该论文');
      return structuredClone(d);
    },
    search: async (_team: UUID, q: string) => {
      if (q.toLowerCase().includes('503')) {
        throw new ApiError(503, '语义检索暂不可用（演示 503 降级）');
      }
      return {
        items: [
          {
            paper: demoPapers[DEMO_PAPER_1],
            analysis_id: 'demo-analysis-1',
            summary: demoDetails[DEMO_PAPER_1].analyses[0].report.summary,
          },
        ],
      };
    },
    annotate: async (_team: UUID, paper: UUID, input: { body: string; parent_id?: UUID; anchor?: string }): Promise<Annotation> => {
      const ann: Annotation = {
        id: `demo-ann-${Date.now()}`,
        team_id: DEMO_TEAM_ID,
        paper_id: paper,
        user_id: currentUserId(),
        parent_id: input.parent_id ?? null,
        anchor: input.anchor ?? null,
        body: input.body,
        created_at: new Date().toISOString(),
      };
      demoDetails[paper]?.annotations.push(ann);
      return ann;
    },
    claim: async (_team: UUID, paper: UUID, meeting_date: string): Promise<Claim> => {
      const detail = demoDetails[paper];
      if (!detail) throw new ApiError(404, '论文不存在');
      const existing = detail.claims.find((c) => c.meeting_date === meeting_date);
      if (existing) {
        if (existing.user_id === currentUserId()) return existing;
        throw new ApiError(409, '该组会日期已被其他成员认领');
      }
      const claim: Claim = {
        id: `demo-claim-${Date.now()}`,
        team_id: DEMO_TEAM_ID,
        paper_id: paper,
        user_id: currentUserId(),
        meeting_date,
        created_at: new Date().toISOString(),
      };
      detail.claims.push(claim);
      return claim;
    },
    unclaim: async (_team: UUID, id: UUID) => {
      Object.values(demoDetails).forEach((d) => {
        d.claims = d.claims.filter((c) => c.id !== id);
      });
      return { ok: true };
    },
    vote: async (_team: UUID, paper: UUID, value: -1 | 0 | 1) => {
      const d = demoDetails[paper];
      if (d) {
        d.vote_total = d.vote_total - d.my_vote + value;
        d.my_vote = value;
      }
      return { ok: true };
    },
    ideas: async (_team: UUID, status?: IdeaStatus) => ({
      items: status ? demoIdeas.filter((i) => i.status === status) : demoIdeas,
    }),
    addIdea: async (_team: UUID, input: { paper_id: UUID; title: string; hypothesis: string; experiment: string; annotation_id?: UUID }): Promise<Idea> => {
      const idea: Idea = {
        id: `demo-idea-${Date.now()}`,
        team_id: DEMO_TEAM_ID,
        paper_id: input.paper_id,
        user_id: currentUserId(),
        annotation_id: input.annotation_id ?? null,
        title: input.title,
        hypothesis: input.hypothesis,
        experiment: input.experiment,
        status: 'backlog',
        assignee_id: currentUserId(),
        created_at: new Date().toISOString(),
      };
      demoIdeas = [idea, ...demoIdeas];
      return idea;
    },
    updateIdea: async (_team: UUID, id: UUID, status: IdeaStatus, assignee_id: UUID | null): Promise<Idea> => {
      const found = demoIdeas.find((i) => i.id === id);
      if (!found) throw new ApiError(404, 'Idea 不存在');
      found.status = status;
      found.assignee_id = assignee_id;
      return { ...found };
    },
    config: async (_team: UUID) => ({
      ...demoConfig,
      role: getMockRole(),
    }),
    setConfig: async (_team: UUID, input: TeamConfigInput) => {
      if (getMockRole() !== 'admin') throw new ApiError(403, '需要管理员权限');
      demoConfig.team.daily_token_budget = input.daily_token_budget;
      demoConfig.topics = input.topics.map((t, idx) => ({ ...t, id: `t-${idx}`, team_id: DEMO_TEAM_ID }));
      return { ok: true };
    },
    setProfile: async (_team: UUID, input: ProfileInput) => {
      demoConfig.interests = input.interests;
      return { ok: true };
    },
    members: async (_team: UUID) => ({ items: demoMembers }),
    addMember: async (_team: UUID, user_id: UUID, role: Role) => {
      if (getMockRole() !== 'admin') throw new ApiError(403, '需要管理员权限');
      const existing = demoMembers.find((m) => m.id === user_id);
      if (existing) existing.role = role;
      else demoMembers.push({ id: user_id, display_name: user_id.slice(0, 8), role });
      return { ok: true };
    },
    readingList: async () => `# 本周组会阅读清单（演示）\n\n- **FedSubMuon** (2609.06073) — 认领人：演示队员 A\n- **PHANTOM-Bench** (2611.08971) — 待认领\n`,
    weekly: async () => ({
      items: [
        {
          team_id: DEMO_TEAM_ID,
          week: '2026-W47',
          payload: {
            reading_list_markdown: '# 2026-W47 周会材料',
            state: 'ready',
            hypotheses_verified: false as const,
            trends: [
              {
                bottleneck: '联邦大模型微调在 4B+ 规模下子空间压缩收益衰减',
                paper_ids: [DEMO_PAPER_1],
                hypothesis: '结合层级奇异值谱动态分配子空间秩与本地误差反馈可维持高压缩比',
                experiment: '在 Qwen-4B + Non-IID Dolly-15K 上对比固定秩与自适应秩',
                metric: '同等通信预算下验证困惑度',
                falsification: '高异构场景下若残差反馈引起发散则推翻',
              },
            ],
          },
        },
      ],
    }),
    usage: async () => {
      if (getMockRole() !== 'admin') throw new ApiError(403, '需要管理员权限');
      return {
        items: [{ scope: 'team', day: new Date().toISOString().slice(0, 10), used: 68400, reserved: 12000 }],
        team_limit: demoConfig.team.daily_token_budget,
        llm_enabled: true,
      };
    },
    jobs: async () => {
      if (getMockRole() !== 'admin') throw new ApiError(403, '需要管理员权限');
      return {
        items: [
          {
            id: 'demo-job-1',
            kind: 'daily_digest',
            state: 'succeeded',
            stats: { discovered: 142, selected: 15, deep_analyzed: 4 },
            started_at: '2026-11-23T06:00:00Z',
            finished_at: '2026-11-23T06:08:12Z',
          },
        ],
      };
    },
  };
}
