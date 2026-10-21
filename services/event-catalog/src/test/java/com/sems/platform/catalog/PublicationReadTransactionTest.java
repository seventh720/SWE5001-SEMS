package com.sems.platform.catalog;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import java.sql.Connection;
import java.time.Instant;
import java.util.*;
import javax.sql.DataSource;
import org.junit.jupiter.api.*;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.context.annotation.*;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.annotation.EnableTransactionManagement;
import org.springframework.transaction.support.*;
import org.springframework.web.server.ResponseStatusException;

class PublicationReadTransactionTest {
    private AnnotationConfigApplicationContext context;
    private EventRepository events;
    private OrganizationAccess access;
    private PublicationState state;
    private Event event;
    private Connection connection;

    @Configuration @EnableTransactionManagement
    static class Config {
        @Bean EventRepository events() { return mock(EventRepository.class); }
        @Bean OrganizationAccess access() { return mock(OrganizationAccess.class); }
        @Bean CatalogTimings timings() { return new CatalogTimings(new SimpleMeterRegistry()); }
        @Bean DataSource dataSource() throws Exception {
            var source = mock(DataSource.class);
            var connection = mock(Connection.class);
            when(source.getConnection()).thenReturn(connection);
            when(connection.getAutoCommit()).thenReturn(true);
            return source;
        }
        @Bean PlatformTransactionManager transactionManager(DataSource source) {
            return new DataSourceTransactionManager(source);
        }
        @Bean PublicationState state(EventRepository events, OrganizationAccess access, CatalogTimings timings) {
            return new PublicationState(events, access, timings);
        }
    }

    @BeforeEach void setup() throws Exception {
        context = new AnnotationConfigApplicationContext(Config.class);
        events = context.getBean(EventRepository.class);
        access = context.getBean(OrganizationAccess.class);
        state = context.getBean(PublicationState.class);
        connection = context.getBean(DataSource.class).getConnection();
        event = new Event(UUID.randomUUID(), new Draft("Seminar", "Description", "Campus",
                Instant.now().plusSeconds(3600), Instant.now().plusSeconds(7200), 10, 0L));
        event.status = "PUBLISHED";
        event.organizationId = UUID.randomUUID();
        var transaction = new TransactionTemplate(context.getBean(PlatformTransactionManager.class));
        transaction.setReadOnly(true);
        when(events.findById(event.id)).thenAnswer(invocation -> transaction.execute(status -> {
            assertTrue(TransactionSynchronizationManager.isActualTransactionActive());
            return Optional.of(event);
        }));
        when(access.active(event.organizationId)).thenAnswer(invocation -> {
            assertReleased();
            return new OrganizationAccess.Membership(event.organizationId, "Society", "society", "ACTIVE", null);
        });
        when(access.require(eq(event.organizationId), any(), anyBoolean())).thenAnswer(invocation -> {
            assertReleased();
            return new OrganizationAccess.Membership(event.organizationId, "Society", "society", "ACTIVE", "MEMBER");
        });
    }

    private void assertReleased() throws Exception {
        assertFalse(TransactionSynchronizationManager.isActualTransactionActive(), "Identity must run after commit");
        assertFalse(TransactionSynchronizationManager.hasResource(context.getBean(DataSource.class)));
        verify(connection, atLeastOnce()).commit();
    }

    @AfterEach void close() { context.close(); }

    @ParameterizedTest @ValueSource(booleans = {true, false})
    void snapshotReleasesConnectionBeforeOrganizationCheck(boolean published) {
        var snapshot = state.inspect(event.id, event.organizerId, published);
        assertEquals(event.id, snapshot.id());
        assertEquals(event.registrationRequirements, snapshot.registrationRequirements());
        if (published) verify(access).active(event.organizationId);
        else verify(access).require(event.organizationId, event.organizerId, true);
    }

    @Test void privatePublicationAndStaffReadStillRequireCurrentMembership() {
        event.visibility = "ORGANIZATION_ONLY";
        var user = UUID.randomUUID();
        assertEquals(event.id, state.inspect(event.id, user, true).id());
        assertEquals(event.id, state.member(event.id, user).id());
        verify(access, times(2)).require(event.organizationId, user, false);
        doThrow(new ResponseStatusException(HttpStatus.NOT_FOUND)).when(access).require(event.organizationId, user, false);
        assertEquals(404, assertThrows(ResponseStatusException.class,
                () -> state.inspect(event.id, user, true)).getStatusCode().value());
        assertEquals(404, assertThrows(ResponseStatusException.class,
                () -> state.member(event.id, user)).getStatusCode().value());
    }

    @Test void suspendedOrganizationAndIdentityFailureDoNotReturnSnapshot() {
        doThrow(new ResponseStatusException(HttpStatus.NOT_FOUND)).when(access).active(event.organizationId);
        assertEquals(404, assertThrows(ResponseStatusException.class,
                () -> state.inspect(event.id, null, true)).getStatusCode().value());
        doThrow(new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE)).when(access).active(event.organizationId);
        assertEquals(503, assertThrows(ResponseStatusException.class,
                () -> state.inspect(event.id, null, true)).getStatusCode().value());
    }
}
