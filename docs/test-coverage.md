# 测试覆盖与适用范围

测试入口以 [CI workflow](../.github/workflows/ci.yml) 为准，最新结果见 [GitHub Actions](https://github.com/seventh720/SWE5001-SEMS/actions/workflows/ci.yml)。长期实测材料按日期和版本保存在[证据目录](evidence/README.md)。本文说明各类检查覆盖什么，不累计逐次 PR 的测试数。

## 自动检查

| 类型 | 覆盖范围 | 不能据此证明 |
| --- | --- | --- |
| Java 单元/组件 | 角色、状态机、分页、请求校验、库存服务及 Catalog 只读重试边界 | 实际 PostgreSQL 锁、事务回滚、网络或云端容量 |
| Web 单元/组件 | 页面、表单、列表、授权路由、相机生命周期、通知及组合筛选 | 所有浏览器、手机摄像头和真实权限场景 |
| API / PostgreSQL | 服务协作、真实 SQL、schema 隔离、并发、幂等、取消、治理及故障恢复 | 受控扩容收益、十分钟稳态或主机级 HA |
| 部署配置 | image lock、release 允许列表、生产保护、调度/探针契约、监控配置及告警规则 | 实际 IAM、镜像拉取和集群运行 |
| 运行镜像 | 扫描过的同一批镜像启动、数据库初始化、API smoke 与库存审计 | 高负载或故障域级可靠性 |
| K3s / 生产只读 | 实际镜像、副本/节点、HTTPS、登录、内部接口拒绝、指标、日志及三服务追踪 | 生产故障注入或全部写业务的本轮复测 |

Catalog 客户端回归覆盖 502/503/504 后成功、最多两次尝试、404/409 不重试、只读 details POST 重试及 prepare-sales 写操作不重放。冷启动验收继续要求订票、同键重放和当前回执无失败，并验证全部 Catalog 停止后的有界 503 和恢复后的唯一订单。

## 业务与故障验收

[CI 操作](ci.md)列出脚本与执行环境。验收覆盖组织权限、发布/修订、公开/内部活动、通知、订单/票券、核销、取消、组织关闭、旧库迁移和中断恢复。并发库存以独立 SQL 结果核对，不能只检查 HTTP 状态。

[跨节点 K3s 记录](evidence/2026-10-24-k3s-regression/README.md)包含两个 Admission Pod 的正确性、Catalog Pod 故障和浏览器闭环；[生产数据迁移](evidence/2026-10-25-production-namespace/README.md)比较全部 27 张表、角色及凭据。历史脚本在独立测试库中执行；当前生产 `sems-prod` 拒绝原夹具/故障入口。

浏览器检查与设备实测分开记录。已有桌面、390px 移动布局、报名/二维码/取消/通知及用户确认的手机扫码结果；没有测量所有设备识别率。

## 覆盖率

前端使用 Vitest V8；后端使用 JaCoCo，按服务和有效报告加权统计。真实 API/数据库验收不计入单元覆盖率。CI 缺失报告显示 N/A，当前没有百分比门槛；测试、类型检查、构建和安全失败仍阻断相应任务。

历史百分比保留于[覆盖汇总](evidence/2026-10-19-coverage-review/summary.json)，不套用到当前版本。复现当前报告：

```bash
npm --prefix apps/web run test:coverage
npm --prefix apps/web run build
mvn verify
python3 scripts/ci/coverage.py frontend
python3 scripts/ci/coverage.py backend
```

## 待补验证

自动 OpenAPI 符合性、数据库/API 路径的独立覆盖采集、当前 K3s 容量与扩容收益、十分钟稳态、主机/数据库故障以及完整灾难恢复尚未完成。优先级见[工程待办](roadmap.md)。
