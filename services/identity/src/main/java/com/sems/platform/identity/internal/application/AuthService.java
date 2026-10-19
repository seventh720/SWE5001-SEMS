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
        PasswordPolicy.validate(rawPassword);
        String normalizedUsername = UsernamePolicy.normalize(username);
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

    public record UsernameAvailability(String username, boolean available) {}

    @Transactional(readOnly = true)
    public UsernameAvailability usernameAvailability(String subject, String requested) {
        String name = UsernamePolicy.normalize(requested);
        UserAccount user = users.findById(java.util.UUID.fromString(subject)).orElseThrow(InvalidCredentialsException::new);
        return new UsernameAvailability(name, name.equals(user.getUsername()) || !users.existsByUsername(name));
    }

    @Transactional
    public UserView rename(String subject, String requested) {
        String name = UsernamePolicy.normalize(requested);
        UserAccount user = users.findById(java.util.UUID.fromString(subject)).orElseThrow(InvalidCredentialsException::new);
        if (!user.isActive()) throw new InvalidCredentialsException();
        if (name.equals(user.getUsername())) return user.toView();
        if (users.existsByUsername(name)) throw new DuplicateUserException("Username is already registered");
        user.rename(name);
        try { return users.saveAndFlush(user).toView(); }
        catch (org.springframework.dao.DataIntegrityViolationException e) {
            throw new DuplicateUserException("Username is already registered");
        }
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
