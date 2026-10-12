package com.sems.platform.identity.internal.web;

import com.sems.platform.identity.UserView;

public record AuthResponse(
        String accessToken,
        String tokenType,
        long expiresIn,
        UserView user) {
}
