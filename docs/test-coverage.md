# 测试覆盖与适用范围

测试入口以 [CI workflow](../.github/workflows/ci.yml) 为准，结果见 [GitHub Actions](https://github.com/seventh720/SWE5001-SEMS/actions/workflows/ci.yml)。测量结果和版本见[验证摘要](evidence/README.md)，完整实测材料保存在本地离线证据包。

## 自动检查

| 类型 | 覆盖范围 | 不能据此证明 |
| --- | --- | --- |
| Java 单元/组件 | 角色、状态机、分页、请求校验、库存服务及 Catalog 只读重试边界 | 实际 PostgreSQL 锁、事务回滚、网络或云端容量 |
| Web 单元/组件 | 页面、表单、列表、授权路由、相机生命周期、通知及组合筛选 | 所有浏览器、手机摄像头和真实权限场景 |
| API / PostgreSQL | 服务协作、真实 SQL、schema 隔离、并发、幂等、取消、治理及故障恢复 | 受控扩容收益、十分钟稳态或主机级 HA |
| 部署配置 | image lock、release 允许列表、生产保护、调度/探针契约、监控配置及告警规则 | 实际 IAM、镜像拉取和集群运行 |
| 运行镜像 | 扫描过的同一批镜像启动、数据库初始化、API smoke 与库存审计 | 高负载或故障域级可靠性 |
| K3s / 生产只读 | 实际镜像、副本/节点、HTTPS、登录、内部接口拒绝、指标、日志及三服务追踪 | 生产故障注入或全部写业务的本轮复测 |

Catalog 客户端回归覆盖 502/503/504 后成功、最多两次尝试、404/409 不重试、只读 details POST 重试及 prepare-sales 写操作不重放。冷启动验收核对订票、同键重放和回执，验证全部 Catalog 停止后的有界 503 和恢复后的唯一订单。

## 业务与故障验收

[CI 操作](ci.md)列出脚本与执行环境。验收覆盖组织权限、发布/修订、公开/内部活动、通知、订单/票券、核销、取消、组织关闭、旧库迁移和中断恢复。并发库存以独立 SQL 结果核对，不能只检查 HTTP 状态。

历史跨节点 K3s 验证覆盖两个 Admission Pod 的正确性、Catalog Pod 故障和浏览器闭环；生产数据迁移比较全部 27 张表、角色及凭据。结果摘要与离线记录位置见[验证索引](evidence/README.md)。历史脚本在独立测试库中执行；当前生产 `sems-prod` 拒绝原夹具/故障入口。

浏览器检查与设备实测分开记录。已有桌面、390px 移动布局、报名/二维码/取消/通知及用户确认的手机扫码结果；没有测量所有设备识别率。

## 覆盖率

前端使用 Vitest V8；后端使用 JaCoCo，按服务和有效报告加权统计。真实 API/数据库验收不计入单元覆盖率。CI 缺失报告显示 N/A，当前没有百分比门槛；测试、类型检查、构建和安全失败仍阻断相应任务。

已记录的测试数量与覆盖率分子、分母见[验证摘要](evidence/README.md)，不套用到后续版本。复现当前报告：

```bash
npm --prefix apps/web run test:coverage
npm --prefix apps/web run build
mvn verify
python3 scripts/ci/coverage.py frontend
python3 scripts/ci/coverage.py backend
```

## 验证边界

单元覆盖率不包含真实 API/数据库路径，自动 OpenAPI 符合性校验未接入。主机或数据库故障、完整灾难恢复及跨设备扫码成功率不在已测范围。K3s 的[十分钟混合稳态与扩容对照](evidence/2026-11-06-cloud-validation/README.md)每个条件仅一次样本，Admission 100 VU 双副本未执行。
