# SEMS Web Application

React + TypeScript client for account registration, login, administrator role assignment and organizer draft management, ticket setup, publication and public discovery. Business permissions are enforced by the services.

Run `npm ci`, `npm test`, and `npm run build`. Build output is required before the Compose web image is built. For development, `npm run dev` proxies `/api` to the gateway on port 8080.

Role changes require a fresh login. Draft times use the browser timezone and are submitted as ISO 8601 UTC timestamps. Free ticket configuration and publication are available. Booking, cancellation and check-in remain pending.
