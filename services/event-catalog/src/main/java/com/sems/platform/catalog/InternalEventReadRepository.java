package com.sems.platform.catalog;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.*;
import org.springframework.jdbc.core.namedparam.MapSqlParameterSource;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.stereotype.Repository;

/** Single-statement projections. JDBC releases the connection before remote access checks. */
@Repository
public class InternalEventReadRepository {
    private final NamedParameterJdbcTemplate jdbc;
    private final ObjectMapper mapper;

    public InternalEventReadRepository(NamedParameterJdbcTemplate jdbc, ObjectMapper mapper) {
        this.jdbc = jdbc;
        this.mapper = mapper;
    }

    public List<EventDetails> details(Collection<UUID> ids) {
        if (ids.isEmpty()) return List.of();
        return jdbc.query("select id,title,location,starts_at,ends_at,status from catalog.events where id in (:ids)",
                new MapSqlParameterSource("ids", ids), (rs, index) -> new EventDetails(
                        rs.getObject("id", UUID.class), rs.getString("title"), rs.getString("location"),
                        rs.getTimestamp("starts_at").toInstant(), rs.getTimestamp("ends_at").toInstant(),
                        rs.getString("status")));
    }

    public Optional<PublicationState.Snapshot> snapshot(UUID id) {
        return jdbc.query("select id,organizer_id,capacity,starts_at,ends_at,status,title,location,"
                        + "registration_requirements,organization_id,visibility from catalog.events where id=:id",
                new MapSqlParameterSource("id", id), this::snapshotRow).stream().findFirst();
    }

    private PublicationState.Snapshot snapshotRow(ResultSet rs, int index) throws SQLException {
        try {
            return new PublicationState.Snapshot(rs.getObject("id", UUID.class),
                    rs.getObject("organizer_id", UUID.class), rs.getInt("capacity"),
                    rs.getTimestamp("starts_at").toInstant(), rs.getTimestamp("ends_at").toInstant(),
                    rs.getString("status"), rs.getString("title"), rs.getString("location"),
                    mapper.readValue(rs.getString("registration_requirements"), RegistrationRequirements.class),
                    rs.getObject("organization_id", UUID.class), rs.getString("visibility"));
        } catch (JsonProcessingException e) {
            throw new SQLException("Invalid event registration requirements", e);
        }
    }
}
