package com.sems.platform.identity.internal.application;

import com.sems.platform.identity.UserView;
import com.sems.platform.identity.internal.domain.UserAccount;
import com.sems.platform.identity.internal.persistence.UserAccountRepository;
import java.util.Locale;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class AuthService {

    private final UserAccountRepository users;
    private final PasswordEncoder passwordEncoder;
    private final TokenService tokenService;

    public AuthService(
            UserAccountRepository users,
            PasswordEncoder passwordEncoder,
            TokenService tokenService) {
        this.users = users;
        this.passwordEncoder = passwordEncoder;
        this.tokenService = tokenService;
    }

    @Transactional
    public UserView register(String username, String email, String rawPassword) {
        if (rawPassword.getBytes(java.nio.charset.StandardCharsets.UTF_8).length > 72) {
            throw new org.springframework.web.server.ResponseStatusException(org.springframework.http.HttpStatus.BAD_REQUEST, "Password must be at most 72 UTF-8 bytes");
        }
        String normalizedUsername = normalizeUsername(username);
        String normalizedEmail = normalizeEmail(email);
        if (users.existsByUsername(normalizedUsername)) {
            throw new DuplicateUserException("Username is already registered");
        }
        if (users.existsByEmail(normalizedEmail)) {
            throw new DuplicateUserException("Email is already registered");
        }

        UserAccount user = UserAccount.register(
                normalizedUsername,
                normalizedEmail,
                passwordEncoder.encode(rawPassword));
        try {
            return users.saveAndFlush(user).toView();
        } catch (org.springframework.dao.DataIntegrityViolationException exception) {
            // A competing registration may pass the existence checks before either insert commits.
            for (Throwable cause = exception; cause != null; cause = cause.getCause()) {
                if (cause instanceof org.hibernate.exception.ConstraintViolationException constraint) {
                    if ("uk_users_username".equals(constraint.getConstraintName())) {
                        throw new DuplicateUserException("Username is already registered");
                    }
                    if ("uk_users_email".equals(constraint.getConstraintName())) {
                        throw new DuplicateUserException("Email is already registered");
                    }
                }
            }
            throw exception;
        }
    }

    @Transactional(readOnly = true)
    public LoginResult login(String email, String rawPassword) {
        UserAccount user = users.findByEmail(normalizeEmail(email))
                .orElseThrow(InvalidCredentialsException::new);
        if (!user.isActive() || !passwordEncoder.matches(rawPassword, user.getPasswordHash())) {
            throw new InvalidCredentialsException();
        }

        TokenService.IssuedToken token = tokenService.issue(user);
        return new LoginResult(token.value(), token.expiresInSeconds(), user.toView());
    }

    @Transactional(readOnly = true)
    public UserView currentUser(String subject) {
        try {
            return users.findById(java.util.UUID.fromString(subject))
                    .orElseThrow(() -> new UserNotFoundException(java.util.UUID.fromString(subject)))
                    .toView();
        } catch (IllegalArgumentException exception) {
            throw new InvalidCredentialsException();
        }
    }

    private String normalizeUsername(String username) {
        return username.strip().toLowerCase(Locale.ROOT);
    }

    private String normalizeEmail(String email) {
        return email.strip().toLowerCase(Locale.ROOT);
    }

    public record LoginResult(
            String accessToken,
            long expiresInSeconds,
            UserView user) {
    }
}
