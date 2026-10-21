package com.sems.platform.catalog;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;

import com.fasterxml.jackson.databind.ObjectMapper;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import java.sql.*;
import java.time.Instant;
import java.util.*;
import javax.sql.DataSource;
import org.junit.jupiter.api.*;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.context.annotation.*;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.annotation.EnableTransactionManagement;
import org.springframework.transaction.support.*;
import org.springframework.web.server.ResponseStatusException;

class PublicationReadTransactionTest {
    private AnnotationConfigApplicationContext context;
    private OrganizationAccess access;
    private PublicationState state;
    private Event event;
    private Connection connection;
    private boolean present;

    @Configuration @EnableTransactionManagement
    static class Config {
        @Bean EventRepository events() { return mock(EventRepository.class); }
        @Bean OrganizationAccess access() { return mock(OrganizationAccess.class); }
        @Bean CatalogTimings timings() { return new CatalogTimings(new SimpleMeterRegistry()); }
        @Bean Connection connection() { return mock(Connection.class); }
        @Bean DataSource dataSource(Connection connection) throws Exception {
            var source = mock(DataSource.class);
            when(source.getConnection()).thenReturn(connection);
            when(connection.getAutoCommit()).thenReturn(true);
            return source;
        }
        @Bean InternalEventReadRepository reads(DataSource source) {
            return new InternalEventReadRepository(new NamedParameterJdbcTemplate(source), new ObjectMapper());
        }
        @Bean PlatformTransactionManager transactionManager(DataSource source) {
            return new DataSourceTransactionManager(source);
        }
        @Bean PublicationState state(EventRepository events, InternalEventReadRepository reads,
                OrganizationAccess access, CatalogTimings timings) {
            return new PublicationState(events, reads, access, timings);
        }
    }

    @BeforeEach void setup() throws Exception {
        context = new AnnotationConfigApplicationContext(Config.class);
        access = context.getBean(OrganizationAccess.class);
        state = context.getBean(PublicationState.class);
        connection = context.getBean(Connection.class);
        present = true;
        event = new Event(UUID.randomUUID(), new Draft("Seminar", "Description", "Campus",
                Instant.now().plusSeconds(3600), Instant.now().plusSeconds(7200), 10, 0L));
        event.status = "PUBLISHED";
        event.organizationId = UUID.randomUUID();
        when(connection.prepareStatement(anyString())).thenAnswer(invocation -> {
            var statement = mock(PreparedStatement.class);
            when(statement.executeQuery()).thenAnswer(query -> resultSet());
            return statement;
        });
        when(access.active(event.organizationId)).thenAnswer(invocation -> {
            assertReleased();
            return new OrganizationAccess.Membership(event.organizationId, "Society", "society", "ACTIVE", null);
        });
        when(access.require(eq(event.organizationId), any(), anyBoolean())).thenAnswer(invocation -> {
            assertReleased();
            return new OrganizationAccess.Membership(event.organizationId, "Society", "society", "ACTIVE", "MEMBER");
        });
    }

    private ResultSet resultSet() throws Exception {
        var result = mock(ResultSet.class);
        when(result.next()).thenReturn(present, false);
        when(result.getObject("id", UUID.class)).thenReturn(event.id);
        when(result.getObject("organizer_id", UUID.class)).thenReturn(event.organizerId);
        when(result.getObject("organization_id", UUID.class)).thenReturn(event.organizationId);
        when(result.getInt("capacity")).thenReturn(event.capacity);
        when(result.getTimestamp("starts_at")).thenReturn(Timestamp.from(event.startsAt));
        when(result.getTimestamp("ends_at")).thenReturn(Timestamp.from(event.endsAt));
        when(result.getString("status")).thenReturn(event.status);
        when(result.getString("title")).thenReturn(event.title);
        when(result.getString("location")).thenReturn(event.location);
        when(result.getString("visibility")).thenReturn(event.visibility);
        when(result.getString("registration_requirements"))
                .thenReturn(new ObjectMapper().writeValueAsString(event.registrationRequirements));
        return result;
    }

    private void assertReleased() throws Exception {
        assertFalse(TransactionSynchronizationManager.isActualTransactionActive(), "Identity must run after JDBC releases the connection");
        assertFalse(TransactionSynchronizationManager.hasResource(context.getBean(DataSource.class)));
        verify(connection, atLeastOnce()).close();
        verify(connection, never()).commit();
        verify(connection, never()).rollback();
    }

    @AfterEach void close() { context.close(); }

    @ParameterizedTest @ValueSource(booleans = {true, false})
    void snapshotReleasesConnectionWithoutExtraTransactionBeforeOrganizationCheck(boolean published) {
        var snapshot = state.inspect(event.id, event.organizerId, published);
        assertEquals(event.id, snapshot.id());
        assertEquals(new PublicationState.Snapshot(event.id, event.organizerId, event.capacity,
                event.startsAt, event.endsAt, event.status, event.title, event.location,
                event.registrationRequirements, event.organizationId, event.visibility), snapshot);
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

    @Test void unpublishedStartedAndMissingEventsDoNotReachIdentity() {
        for (String status : List.of("DRAFT", "PAUSED", "CANCELLED")) {
            event.status = status;
            assertEquals(404, assertThrows(ResponseStatusException.class,
                    () -> state.inspect(event.id, null, true)).getStatusCode().value());
        }
        event.status = "PUBLISHED";
        event.startsAt = Instant.now().minusSeconds(1);
        assertEquals(404, assertThrows(ResponseStatusException.class,
                () -> state.inspect(event.id, null, true)).getStatusCode().value());
        present = false;
        assertEquals(404, assertThrows(ResponseStatusException.class,
                () -> state.inspect(event.id, event.organizerId, false)).getStatusCode().value());
        assertEquals(404, assertThrows(ResponseStatusException.class,
                () -> state.member(event.id, event.organizerId)).getStatusCode().value());
        verifyNoInteractions(access);
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
