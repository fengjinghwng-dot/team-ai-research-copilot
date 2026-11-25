# 个人方向日报

在「个人设置」保存方向关键词、每日篇数（1–50）和顶会/最新论文比例。
日报页可修改这些偏好并点击「立即生成日报」，当前偏好同时保存到当前团队的个人设置。
已配置偏好的成员，下一轮定时日报也使用这些参数；原有未配置成员保持现有团队推荐方式。

## 选文与来源
- 方向支持 1–12 个中英文关键词，每个最多 80 字，按任一关键词匹配标题/摘要；常见中文 AI 术语扩展为英文别名，其余方向建议使用英文或缩写。
- 最新论文：最近 72 小时首次提交且经 arXiv 元数据确认的论文。
- 候选不足时，可从近 90 天的匹配结果补位，页面标记为「往期论文」，不计入最新论文数。
- 顶会论文：最近五个年份（含当年）的 NeurIPS、ICML、ICLR、ACL、EMNLP、NAACL、
  CVPR、ICCV、ECCV、AAAI、IJCAI、KDD、SIGIR、WWW 主会论文。
  使用 Semantic Scholar 的会议字段及年份。候选不足或限流时查询 OpenAlex 的会议论文元数据，保留来源；不根据标题猜测录用，不将
  workshop、Findings、companion 或 arXiv 记录升级成主会论文。
- 顶会与最新可能重叠，顶会优先归类，一篇只计一次。目标篇数四舍五入到整数。
- 单类不足会用另一类可用论文补齐，并展示实际比例；总量不足则展示实际篇数和提示。
- 公共源限流/失败时可复用团队已有符合条件的候选，并明确显示来源警告。没有候选时保留本人已有日报。
- 日报上方可以按标题、摘要或会议筛选已生成的清单。论文详情可用 OpenAlex 查询该论文记录中的作者机构。
- 按关键词本地选文后，最多对 SHORTLIST_SIZE 篇请求中立解读；其余保留摘要及已有报告。
  原有共享缓存、证据校验、团队/全局预算仍生效。预算不足不伪造 AI 解读。

## 持久队列与权限
POST /v1/teams/{team_id}/daily/generate 返回 202 和持久任务。
FastAPI 的后台 worker 用 PostgreSQL advisory lock 串行消费，跨副本避免重复执行；
服务重启后继续处理尚未开始的任务。已经开始的任务会标记中断，保留已保存的选文和报告。重复点击返回本人当前任务。
页面先显示保存的选文，解读在后台生成并使用现有报告缓存。任务结束时刷新清单。
普通 GET 日报不抓取外部来源、不调用模型。手动生成不发送群消息或邮件。
团队公共版次与其他成员的日报不会被手动生成修改。偏好、任务及日报按团队和账号隔离。

接口：
- GET /v1/teams/{team_id}/daily/preferences：本人偏好及来源范围。
- PUT /v1/teams/{team_id}/daily/preferences：保存本人偏好。
- POST /v1/teams/{team_id}/daily/generate：保存偏好并排队生成。
- GET /v1/teams/{team_id}/daily/generation：本人最近任务。
- GET /v1/teams/{team_id}/daily/generation/{job_id}：本人指定任务。

## 部署
新增不可变迁移 007_personal_daily.sql。现有 Dockerfile.web 启动流程会先执行迁移；
独立 API/Worker 部署需先执行 copilot migrate。必须继续使用 PostgreSQL + pgvector
及支持 advisory lock 的 direct/session 连接。现有生产 Secrets 不需要改变。
本功能的真实 PostgreSQL、前端及隔离测试状态以 mqh 分支对应 CI 为准；
测试不代表真实模型科学质量或第三方来源可用性已经通过生产验收。
