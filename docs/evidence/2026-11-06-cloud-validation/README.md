# 现有云资源验证（2026-11-06 开始）

在明确授权的维护窗口内，复用现有两台 EC2/K3s 节点和应用 Pod，没有新增云实例、节点、磁盘或第二套应用。测试数据写入现有 PostgreSQL 内的临时逻辑数据库，原业务库 `sems` 保留。结果按实际执行范围记录，不代表 proposal 或正式报告已全部完成。

## 版本与环境

- 应用：`5e9081a9f5421fa5bdbd965d750641f3666dd5f3`。[main CI/CD](https://github.com/seventh720/SWE5001-SEMS/actions/runs/42192164894)的八项报告归档已核对 SHA-256 和 ZIP CRC，后端 92 项测试通过；摘要见 [main-ci-artifacts.json](main-ci-artifacts.json)。镜像扫描中的 PostgreSQL 发布镜像与运行中的原数据库镜像分别记录，未借测试升级数据库。
- 两节点均为 `t3.medium`，各 2 vCPU / 4 GiB。控制平面、监控、数据库和应用共置；PostgreSQL 为原有单 Pod/PVC，版本 17.11，限额 1 CPU / 768 MiB。后端每副本限额 1 CPU / 768 MiB，请求 250m / 512 MiB。
- 数据集：1000 个不同账号、100 个已发布活动，每活动 1000000 票额；每轮从同一快照恢复，并刷新本轮活跃账号的 JWT。测试账号、JWT、维护令牌、数据库备份和原始日志不提交。
- 负载发生器：本机 Docker 中的 k6 1.3.0，限额 2 CPU / 1 GiB，经公网 HTTPS 访问。原始响应计数与 summary、网关测量计数逐轮对账；逐 Pod 流量、节点位置、资源及 SQL 库存结果一并保留。
- 性能脚本版本为 `ef7c6c9b3fc37a55dd2b25a317bb40650be25292`；后续故障验证脚本版本为 `2083b0fae6721ae0e61b4e8c3dc5e9619c329576`。各阶段实际源文件 SHA-256 分别保留，后续脚本修正不追溯改变前一阶段的结论。

## 十分钟混合稳态

100 VU，60 秒爬升、600 秒稳态，思考时间 1 秒。目录、详情、本人资料、订单读取持续执行，每五次迭代订票、取回执并取消，写入没有次数上限；三个后端均为双副本。

稳态 **178959 次 HTTP 请求，0 意外错误**，总体 p95 约 338 ms，最慢操作为订票，p95 约 525 ms。十个分钟窗口都有成功订票，原始计数与 summary 完全一致。网关服务端门禁及库存审计通过。六个业务副本均有实际成功业务流量；[逐副本记录](mixed-replica-traffic.json)来自运行中采集，包含预热与部分稳态，不是全程精确流量比例。

[计时与持续写入复核](mixed-measurement-validation.json)、[完整样本](performance/mixed-100vu-600s.json)。这些结果支持本环境下的 100 VU 十分钟混合目标，不说明最大容量。

## 1/2 副本对照

每轮预热 60 秒、测量 600 秒，固定闭环 VU，思考时间 0.1 秒。仅改变被测服务副本数，其余后端固定一个，gateway/web 保持两个。Catalog 为 80% 目录 / 20% 详情；Admission 为分散活动的订票加回执。下表吞吐均只计算测量窗口，每个条件仅一次样本。

| 场景 | VU | 单副本 | 双副本 | 本轮成功吞吐变化 |
| --- | ---: | ---: | ---: | ---: |
| Catalog，HTTP/s | 25 | 181.95 | 186.17 | +2.3% |
| Catalog，HTTP/s | 50 | 290.10 | 340.63 | +17.4% |
| Catalog，HTTP/s | 100 | 235.78 | 357.68 | +51.7% |
| Admission，订单/s | 25 | 104.23 | 110.30 | +5.8% |
| Admission，订单/s | 50 | 71.02 | 133.85 | +88.5% |
| Admission，订单/s | 100 | 66.72，严格门禁失败 | 未执行 | 无完整对照 |

五组完整对照均通过客户端、网关、库存及逐副本接流量检查。Admission 50 VU 订票 p95 从 579 ms 降至 333 ms；Catalog 100 VU 目录 p95 从 589 ms 降至 484 ms。全部分操作 p95、实际请求数、Pod 位置、CPU/内存采样及比较值见 [comparisons.json](comparisons.json) 和 [performance/](performance/)。

单副本高 VU 的吞吐低于较低 VU 样本，已如实保留。Catalog 100 VU、Admission 50/100 VU 的单副本平均 CPU 均接近 1 核限额，说明 CPU 配额是需要继续调查的因素；未采集完整 JVM/GC 和连接池等待剖析，不能据此断定唯一瓶颈。

## 保留的失败与未执行项

Admission 100 VU 单副本稳态 80064 次请求全部返回 200，订票 / 回执 p95 约 1765 / 1094 ms，SQL 库存一致。但预热开始后出现 **16 次内部 Catalog 504**，时间均为 `2026-11-06T15:25:56Z`，被已有只读重试掩盖。因此整轮严格服务端门禁失败，脚本停止性能矩阵并恢复原站点，100 VU 双副本未执行。见[失败分析](booking-100vu-failure.json)及[失败样本](performance/booking-r1-vu100-600s.json)。

共执行 3 个短时预检、12 个正式性能样本；正式样本 11 个通过、1 个失败，原计划的第 13 个正式样本未执行。没有调低阈值或删除失败记录。此次未测热点分布、三次交错重复、HPA、整台节点故障、数据库切换及平台复用配置耗时。

## 并发库存与单 Pod 故障

在新维护窗口中复用相同的私有种子快照，每次故障前重新恢复临时库，独立执行下列检查。源码和本地验证摘要见 [recovery-summary.json](recovery-summary.json)：36 项离线检查通过，k6 语法检查通过，Docker/本机时钟在整秒精度内一致。

100 个不同账号经同步屏障同时竞争 10 个名额，**10 单成功、90 个正确售罄响应**，两个 Admission 副本均处理请求。SQL 为 `quota = reserved = confirmed = tickets = 10`，没有超售。见 [contested-inventory.json](contested-inventory.json)。

两个故障试验分别在目标服务双副本、25 VU 和额外三个订票/同键重放/回执工作线程下，强制删除其中一个 Pod。故障前确认两个目标副本均接到业务流量，并保存当时所有已提交订单 ID；故障后核对该快照、所有客户端成功订票 ID/幂等键和 SQL 库存。

| 指标 | Catalog 故障 | Admission 故障 |
| --- | ---: | ---: |
| 测量窗口请求 | 21705 | 16847 |
| 客户端意外错误 | 0 | 3（约 0.018%） |
| 首个业务达标 30 秒窗口起点，距故障 | 0 秒 | 0 秒 |
| 订票/重放/回执探针达标窗口起点 | 0 秒 | 0 秒 |
| 首次观察到替换 Pod Ready | 72.23 秒 | 61.25 秒 |
| 已确认探针订单 / 丢失 | 850 / 0 | 549 / 0 |
| 已确认后台负载订单 / 丢失 | 0（后台只读） | 8598 / 0 |
| 故障前已提交订单快照 / 丢失 | 139 / 0 | 1083 / 0 |
| 重复探针订单、回执不一致 | 0 | 0 |
| 网关请求覆盖与 SQL 库存审计 | 通过 | 通过 |

“达标窗口”要求连续 30 秒内意外错误率 <1%、每操作 p95 <3 秒，起点在故障后 60 秒以内；起点为 0 秒允许少量瞬态错误，不代表所有请求均成功。Pod Ready 另按约五秒轮询记录，属于首次检测到的时间上界，不能替代业务恢复时间。Admission 的三个错误及 Catalog 的两次上游 502/网关重试均保留；故障试验按恢复与数据留存判定，不要求性能实验的零服务端错误门禁。各订单计数组之间可能重叠，不相加。

完整记录见 [Catalog](event-catalog-recovery.json) 和 [Admission](admission-recovery.json)。仅测试单 Pod 删除，没有演练主机、控制平面、网络分区或数据库故障。

## 数据隔离与恢复

维护入口检查见 [maintenance-access.json](maintenance-access.json)；运行中实际数据库连接与原库指纹核对见 [midway-isolation.json](midway-isolation.json)。性能阶段结束后，独立检查五个 Deployment 原 spec、两个 ConfigMap 原数据、六个后端实际数据库 URL、跨节点双副本、原 PostgreSQL Pod/PVC 及重启次数，均与测试前相符；原业务库 27 表指纹一致，临时库已移除，恢复计时器已停止。首页、四个健康检查和目录 API 返回 200，公网内部路径返回 404。见 [performance-restoration.json](performance-restoration.json)。

全部故障验证结束后，于 `2026-11-07 00:09 SGT` 再次独立完成同样检查，均通过；原业务库 27 表仍与维护前一致，原 PostgreSQL Pod/PVC 和重启次数保持不变。两次维护创建的临时库均已移除，远端恢复计时器均已停止，发布锁已释放。见 [final-restoration.json](final-restoration.json) 和 [清理复核](cleanup-verification.json)。持续轮询未发现监控组件新增重启、替换或未就绪，最终 13 个监控 Pod 的身份、重启次数和就绪状态均符合维护前基线，采样范围见 [observability-watch-summary.json](observability-watch-summary.json)。

时间戳使用 UTC；本地时区为 Asia/Singapore。每个条件只有一个顺序样本，没有统计显著性或线性扩容结论。固定闭环负载、节点共置、CPU 配额、Pod 位置及维护访问日志都是本轮实验条件。
