# ADR 0001：服务边界与一致性

状态：采用 proposal 边界。当前已实现 Identity、Catalog 草稿、三服务认证与独立 schema、发布及自动恢复、免费预订、独立出票和参与者取消订单；整场活动取消协议与工作人员核销仍待实现。

Identity 拥有用户和角色；Catalog 拥有活动、owner、发布状态；Admission 拥有销售状态、票种、库存、订单、票券、staff assignment、签到。共享物理 PostgreSQL 时仍隔离 schema/凭据，撤销公共建表权限，每服务独立迁移。跨服务仅存 ID/必要快照，禁止共享 JPA 或 repository。

## 跨服务协议

Catalog 持久化操作 ID、目标版本、步骤及错误；恢复任务从 pending 操作继续。内部 HTTP 须认证，不能只依赖内网。Admission 持久化命令 ID、指纹和结果，同键同参数返回既有结果，异参数409。版本单调，取消终态拒绝迟到激活。

发布：DRAFT→PUBLISHING（不可见）→Admission activate-sales（含 owner/容量/时间/版本）→Catalog PUBLISHED。预订先查询 Catalog 是否 PUBLISHED，网络失败返回503；所以激活成功但 Catalog 未发布时不能售票。

取消：Catalog 先保存 CANCEL_PENDING 并拒绝新的 eligibility 请求，调用 Admission close-sales。Admission 锁本地 sales 记录，关闭销售、取消有效订单和未核销票、条件释放库存；完成后 Catalog CANCELLED。已核销记录保留历史。超时保持 pending，同操作ID恢复，不重新发布。

远程检查不是锁：预订完成 HTTP 校验后，在本地事务锁 sales 并再次检查销售状态/时间。取消获取相同锁；已在途预订如果先提交，由取消事务随后撤销。售票关闭提交之后不能新增有效订单。不得持数据库锁发远程请求。

首版仅草稿允许变更时间、容量及票种配置。已发布活动编辑不在首版范围；后续需要时另设计版本化协调。

## Admission 事务规则

- 同用户/request key唯一；同请求返回原订单，异载荷409。跨实例用数据库锁和唯一约束，不用JVM锁。
- 总配额不超过容量，可售库存非负；金额平台计算，核心仅免费票。
- 确认订单和 quantity 张唯一、不可预测的票凭证同事务生成；取消至多释放一次。
- 个人取消须未开始且无任何已签到票，与签到用一致锁顺序串行化。
- 签到验证 staff assignment、活动关联及有效票，条件更新 VALID→CHECKED_IN，成功最多一次。
- Organizer校验owner；ADMIN不默认绕过owner；Attendee仅访问本人订单。

不引入消息中间件或分布式事务。网关不暴露/internal，内部调用另做认证。共享数据库和热点锁吞吐上限通过实验报告。

## 当前票种与发布实现

Admission 保存免费票种、配额、销售窗口和销售状态。开始票种配置时先通过 Catalog 的认证内部 API 固定活动时间和容量；只允许继续修改其他草稿字段。这一限制避免容量/时间编辑与跨服务配额配置竞态。首次开始配置即固定，即使票种输入随后被拒绝。发布后本轮不允许编辑。

Catalog 的 `PUBLISHING`、操作ID、原始请求版本、票种版本持久化在事件记录中。Admission 在同一事件数据库锁内检查快照、票种版本并激活；同操作同参数重放无副作用。明确409退回DRAFT并保存错误；超时/网络故障保持PUBLISHING，由每5秒执行的恢复任务重试。重启不会丢失待处理操作。网络调用在数据库事务外执行。

两个内部调用方向使用分别生成的服务令牌，网关不暴露内部路径。当前开发环境为HTTP；云部署需内部传输保护与密钥管理。预订事务已实现，同请求键先取数据库 advisory lock，再锁 sales 行；取消也先锁 sales 行，重复取消不释放更多库存。两个 Admission 副本的本地验收已覆盖 100 请求争 10 个名额与数据库结果检查，不代表已完成云端性能实验。详见 [预订设计](../booking-increment.md)。
