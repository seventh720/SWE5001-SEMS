package com.sems.platform.identity;

import java.time.Instant;
import java.util.Set;
import java.util.UUID;

public record UserView(
        UUID id,
        String username,
        String email,
        UserStatus status,
        Set<Role> roles,
        Instant createdAt) {
}
