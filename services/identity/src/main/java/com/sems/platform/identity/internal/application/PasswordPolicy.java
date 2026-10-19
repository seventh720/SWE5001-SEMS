package com.sems.platform.identity.internal.application;

import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

public final class PasswordPolicy {
    public static final String PATTERN = "[!-~]{8,16}";
    public static final String MESSAGE = "Password must contain 8–16 characters using English letters, numbers or symbols. Spaces are not allowed.";

    private PasswordPolicy() {}

    public static void validate(String password) {
        if (password == null || !password.matches(PATTERN)) {
            throw new ResponseStatusException(HttpStatus.BAD_REQUEST, MESSAGE);
        }
    }
}
