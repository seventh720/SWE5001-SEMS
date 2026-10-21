package com.sems.platform.catalog;

import java.time.Instant;
import java.util.UUID;

/** Read projection: do not hydrate publication state or registration JSON for receipts. */
public record EventDetails(UUID id, String title, String location, Instant startsAt,
                           Instant endsAt, String status) {}
