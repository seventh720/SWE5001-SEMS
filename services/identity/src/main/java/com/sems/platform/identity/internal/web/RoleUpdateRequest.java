package com.sems.platform.identity.internal.web;

import com.sems.platform.identity.Role;
import jakarta.validation.constraints.NotEmpty;
import java.util.Set;

public record RoleUpdateRequest(@NotEmpty Set<@jakarta.validation.constraints.NotNull Role> roles) {
}
