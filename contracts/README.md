# API contracts（待实现）

分别维护 identity.openapi.yaml、event-catalog.openapi.yaml、admission.openapi.yaml；本次尚未创建可执行业务契约。

公开 API 统一 /api/v1；内部 API 使用 /internal/v1 并禁止 gateway 对外路由。写入完整 DTO、JWT 权限、资源所有权、分页、Problem JSON 和 400/401/403/404/409/503 响应。接口契约合并后才迁移对应 controller。

路径归属：auth/admin → Identity；events/organizer/events 的活动操作 → Catalog；bookings、tickets、ticket-types、check-ins、staff-assignments、admission-summary → Admission。特别注意嵌套 events/{id}/ticket-types 与 events/{id}/check-ins 属于 Admission，不能全部按 events 前缀路由到 Catalog。
