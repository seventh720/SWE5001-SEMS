package com.sems.platform.identity.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "sems.bootstrap.admin")
public record BootstrapAdminProperties(String username, String email, String password) {

    public boolean enabled() {
        return email != null && !email.isBlank() && password != null && !password.isBlank();
    }
}
