package com.sems.platform.identity.internal.domain;

import com.sems.platform.identity.Role;
import com.sems.platform.identity.UserStatus;
import com.sems.platform.identity.UserView;
import jakarta.persistence.CollectionTable;
import jakarta.persistence.Column;
import jakarta.persistence.ElementCollection;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.PrePersist;
import jakarta.persistence.PreUpdate;
import jakarta.persistence.Table;
import jakarta.persistence.Version;
import java.time.Instant;
import java.util.Collections;
import java.util.EnumSet;
import java.util.Set;
import java.util.UUID;

@Entity
@Table(name = "users")
public class UserAccount {

    @Id
    private UUID id;

    @Column(nullable = false, unique = true, length = 50)
    private String username;

    @Column(nullable = false, unique = true, length = 255)
    private String email;

    @Column(name = "password_hash", nullable = false, length = 255)
    private String passwordHash;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 20)
    private UserStatus status;

    @ElementCollection(fetch = FetchType.EAGER)
    @CollectionTable(name = "user_roles", joinColumns = @JoinColumn(name = "user_id"))
    @Column(name = "role_code", nullable = false, length = 30)
    @Enumerated(EnumType.STRING)
    private Set<Role> roles = EnumSet.noneOf(Role.class);

    @Version
    @Column(nullable = false)
    private long version;

    @Column(name = "created_at", nullable = false, updatable = false)
    private Instant createdAt;

    @Column(name = "updated_at", nullable = false)
    private Instant updatedAt;

    protected UserAccount() {
    }

    private UserAccount(
            String username,
            String email,
            String passwordHash,
            Set<Role> roles) {
        this.id = UUID.randomUUID();
        this.username = username;
        this.email = email;
        this.passwordHash = passwordHash;
        this.status = UserStatus.ACTIVE;
        this.roles = EnumSet.copyOf(roles);
    }

    public static UserAccount register(String username, String email, String passwordHash) {
        return new UserAccount(username, email, passwordHash, EnumSet.of(Role.ATTENDEE));
    }

    public static UserAccount bootstrapAdmin(String username, String email, String passwordHash) {
        return new UserAccount(username, email, passwordHash, EnumSet.of(Role.ADMIN));
    }

    public void replaceRoles(Set<Role> updatedRoles) {
        if (updatedRoles == null || updatedRoles.isEmpty()) {
            throw new IllegalArgumentException("A user must have at least one role");
        }
        this.roles = EnumSet.copyOf(updatedRoles);
    }

    public void addRole(Role role) {
        this.roles.add(role);
    }

    public boolean isActive() {
        return status == UserStatus.ACTIVE;
    }

    public UUID getId() {
        return id;
    }

    public void rename(String username) { this.username = username; }

    public String getUsername() {
        return username;
    }

    public String getEmail() {
        return email;
    }

    public String getPasswordHash() {
        return passwordHash;
    }

    public UserStatus getStatus() {
        return status;
    }

    public Set<Role> getRoles() {
        return Collections.unmodifiableSet(roles);
    }

    public UserView toView() {
        return new UserView(id, username, email, status, Set.copyOf(roles), createdAt);
    }

    @PrePersist
    void onCreate() {
        Instant now = Instant.now();
        createdAt = now;
        updatedAt = now;
    }

    @PreUpdate
    void onUpdate() {
        updatedAt = Instant.now();
    }
}
