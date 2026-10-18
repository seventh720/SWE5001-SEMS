package com.sems.platform.identity.internal.application;

import com.sems.platform.identity.Role;
import com.sems.platform.identity.config.BootstrapAdminProperties;
import com.sems.platform.identity.internal.domain.UserAccount;
import com.sems.platform.identity.internal.persistence.UserAccountRepository;
import java.util.Optional;
import java.util.Set;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.security.crypto.password.PasswordEncoder;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class BootstrapAdminInitializerTest {
    private final UserAccountRepository users = mock(UserAccountRepository.class);
    private final PasswordEncoder encoder = mock(PasswordEncoder.class);
    private final BootstrapAdminProperties properties = new BootstrapAdminProperties("admin", "admin@example.com", "test-password");

    @Test void restartDoesNotRestoreRevokedAdministratorRole() {
        var existing = UserAccount.bootstrapAdmin("admin", properties.email(), "old-hash");
        existing.replaceRoles(Set.of(Role.ATTENDEE));
        when(users.findByEmail(properties.email())).thenReturn(Optional.of(existing));
        new BootstrapAdminInitializer(properties, users, encoder).run(null);
        assertEquals(Set.of(Role.ATTENDEE), existing.getRoles());
        verify(users, never()).save(any());
        verifyNoInteractions(encoder);
    }

    @Test void freshInstallationStillCreatesAdministrator() {
        when(users.findByEmail(properties.email())).thenReturn(Optional.empty());
        when(encoder.encode(properties.password())).thenReturn("hash");
        new BootstrapAdminInitializer(properties, users, encoder).run(null);
        var account = ArgumentCaptor.forClass(UserAccount.class);
        verify(users).save(account.capture());
        assertTrue(account.getValue().getRoles().contains(Role.ADMIN));
    }
}
