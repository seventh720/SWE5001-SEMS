# EC2 K3s 可观测性接入验证 — 2026-10-25

在现有两台 `t3.medium` 上安装独立 `observability` namespace；未创建新的 AWS 计算、托管监控或存储服务。所有监控镜像及 Java Agent 使用不可变摘要。业务继续使用原有镜像及数据，各服务两个副本。完整操作和限制见[运维指南](../../observability.md)。

[现场验证](verification.json)记录：

- 五个应用均 2/2；三个 Java 服务六个 Pod 均有 JVM/HTTP 指标。
- 17 个采集目标全部 up，包括两个节点、cAdvisor、API server、Pod 状态、PostgreSQL 和四条正式 HTTPS readiness。
- Grafana 面板及 Prometheus/Loki/Tempo/外部 Alertmanager 数据源可用；全部面板 PromQL 可执行。另通过原生 `/api/ds/query` 验证连接池返回三个服务的数据帧。
- 真实公开 GET 查询的同一 Trace ID 有 11 个 spans，验证 `admission → event-catalog → identity` 的跨服务 parent 关系；存储前移除 SQL 文本和 URL query。请求未创建或修改业务数据。
- 三个服务的应用日志已进入 Loki；gateway/web/PostgreSQL 使用每节点日志采集器，仅采集接入后新产生的日志。
- `ObservabilitySmokeTest` 合成 gauge 实际触发 Prometheus → Alertmanager → Telegram，再将 gauge 清零；Telegram firing 和 resolved 均投递，失败计数为零。没有停止应用、删 Pod 或注入数据库故障。最终没有 firing 运维告警。
- 监控数据库角色默认只读、非超级用户，不能使用 identity/catalog/admission 业务 schema。各次安装/采集接入均确认 PostgreSQL Pod/PVC UID 不变。

离线检查包括七项真实组件配置/规则验证（Prometheus 配置、告警样例、Alertmanager、两个 Collector、Loki、Tempo）、十项 K3s release 测试、三项生产数据保护测试、Python 语法及文档链接检查。告警样例覆盖保持时间、持续 5xx 触发、404 和低流量不误报；新增 release 测试确认应用 CD 保留 Agent 摘要和 Collector 地址。

验证中修正了三个实际问题：Grafana 13 的插件缓存默认位于只读根文件系统，现改到已有 Grafana PVC；JDBC 池实际指标为 `db_client_connections_usage`，已据实修正；本机工作区包含空格，SSH known-hosts 选项已正确引用，互斥锁获取/释放也已实测。Grafana 完整加载数据源后内存高于初始预算，最终设置 512Mi 容器上限及 192MiB Go 软目标。

资源快照只反映当前小流量和验证过程，不能作为容量成绩。监控后端是单实例、同集群本地磁盘，根盘与业务共享；日志/追踪保留期不是严格磁盘配额。整体主机或控制平面故障可能同时影响监控和通知。未新增 HPA/节点自动扩容、外部独立探测或数据库高可用。

Telegram Token、Chat ID、Grafana 密码、数据库监控密码、Deployment 原模板和访问日志保存在忽略的私有目录或 Kubernetes Secret，不进入本记录。

## 固定 HTTPS 与过渡域名退休

用户配置 DNS 后，已启用 <https://grafana.seventh720.com>，复用现有 Traefik/Let's Encrypt 和 Grafana 账号。仅 Traefik 可从 kube-system 进入 Grafana，其他监控后端保持 ClusterIP。Grafana 自身 metrics 端点也要求认证。

[公网验证](public-https-verification.json)通过：可信 TLS、HTTP → HTTPS、匿名面板/数据源/metrics 拦截、错误登录拒绝、现有账号登录、Secure/HttpOnly/SameSite 会话和已登录实时数据。未公开登录凭据或会话值。

旧 Lightsail 过渡代理已改为直连 K3s IP，使用正式域名校验 TLS 证书与 Host，不再依赖 `sems-test.seventh720.com`。Caddy 配置备份、验证、reload 及共享项目配置/容器未变化见[代理记录](alias-proxy-verification.json)；旧 IP 过渡请求、正式站点和 SWE5006 均返回 200。

仅删除过渡 Ingress `sems-test/sems`，保留正式 `sems-public`、生产 namespace、PostgreSQL Pod 和 PVC；Cloudflare 的 `sems-test` A 记录可由维护者删除。新 CD render 排除 Ingress，11 项 release 测试通过，并继续接受历史 release 的旧 Ingress 记录用于回退兼容。PR 合并后新规则才成为后续 main 发布的默认行为。

固定域名及过渡别名退休后的[内部只读复核](after-public-verification.json)也已通过。日志 label 验收显式查询 48 小时保留期，避免 Loki 默认一小时回看窗口将安静服务的已有日志漏掉；不要求服务为验证额外输出业务日志。
