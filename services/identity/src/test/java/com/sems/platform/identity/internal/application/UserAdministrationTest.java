package com.sems.platform.identity.internal.application;

import com.sems.platform.identity.Role;
import com.sems.platform.identity.internal.domain.UserAccount;
import com.sems.platform.identity.internal.persistence.UserAccountRepository;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.server.ResponseStatusException;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

class UserAdministrationTest {
    @Test void refusesLastActiveAdminButAllowsDemotionWithAnotherAdmin() {
        var users=mock(UserAccountRepository.class);
        var jdbc=mock(JdbcTemplate.class);
        var account=UserAccount.bootstrapAdmin("admin","admin@example.com","hash");
        UUID id=UUID.randomUUID();
        when(users.findById(id)).thenReturn(Optional.of(account));
        when(jdbc.queryForObject(anyString(),eq(Long.class))).thenReturn(1L,2L);
        var service=new UserAdministrationService(users,jdbc);
        assertEquals(409,assertThrows(ResponseStatusException.class,()->service.replaceRoles(id,Set.of(Role.ATTENDEE))).getStatusCode().value());
        assertTrue(account.getRoles().contains(Role.ADMIN));
        service.replaceRoles(id,Set.of(Role.ATTENDEE));
        assertFalse(account.getRoles().contains(Role.ADMIN));
    }
}
