# Development records

The current increment implements identity, role management, event drafts and a React client. Three services own separate PostgreSQL schemas and credentials. Admission now owns free ticket configuration, quota checks and sales activation. Catalog publication is durable and retry-safe. Booking and check-in remain pending.

Changes must record their associated commits, affected files, design rationale, contributors and validation results. Acceptance evidence must correspond to the tested version. Retain applicable attribution and license notices when incorporating third-party code.
