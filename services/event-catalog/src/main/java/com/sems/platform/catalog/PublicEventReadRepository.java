package com.sems.platform.catalog;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.*;
import org.springframework.data.domain.*;
import org.springframework.data.support.PageableExecutionUtils;
import org.springframework.jdbc.core.namedparam.MapSqlParameterSource;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.stereotype.Repository;

/** Read-only public projections; writes and their locks remain in EventRepository. */
@Repository
public class PublicEventReadRepository {
    public record Row(UUID id, String title, String description, String location, Instant startsAt,
            Instant endsAt, int capacity, EventCategory category, CardTheme cardTheme,
            RegistrationRequirements registrationRequirements, UUID organizationId, String visibility,
            String status) {}
    private static final String FIELDS = "id,title,description,location,starts_at,ends_at,capacity,"
            + "category,card_theme,registration_requirements,organization_id,visibility,status";
    private final NamedParameterJdbcTemplate jdbc;
    private final ObjectMapper mapper;

    public PublicEventReadRepository(NamedParameterJdbcTemplate jdbc, ObjectMapper mapper) {
        this.jdbc = jdbc;
        this.mapper = mapper;
    }

    private String where(UUID organization, EventCategory category) {
        // Hibernate disables PostgreSQL's default backslash escape for JPQL LIKE.
        return " where status='PUBLISHED' and starts_at>:now and lower(title) like lower(:keyword) escape ''"
                + (category == null ? "" : " and category=:category")
                + (organization == null ? " and visibility='PUBLIC'" : " and organization_id=:organization");
    }

    private MapSqlParameterSource parameters(UUID organization, Instant now, String keyword,
            EventCategory category) {
        return new MapSqlParameterSource().addValue("organization", organization)
                .addValue("now", Timestamp.from(now)).addValue("keyword", "%" + keyword + "%")
                .addValue("category", category == null ? null : category.name());
    }

    public Slice<UUID> discoveryOrganizations(UUID organization, Instant now, String keyword,
            EventCategory category, Pageable page) {
        var params = parameters(organization, now, keyword, category)
                .addValue("limit", page.getPageSize() + 1).addValue("offset", page.getOffset());
        var ids = jdbc.query("select distinct organization_id from catalog.events" + where(organization, category)
                + " order by organization_id limit :limit offset :offset", params,
                (rs, index) -> rs.getObject(1, UUID.class));
        boolean more = ids.size() > page.getPageSize();
        return new SliceImpl<>(more ? ids.subList(0, page.getPageSize()) : ids, page, more);
    }

    public Page<Row> discover(List<UUID> activeOrganizations, UUID organization, Instant now,
            String keyword, EventCategory category, Pageable page) {
        if (activeOrganizations.isEmpty()) return Page.empty(page);
        var predicate = where(organization, category) + " and organization_id in (:activeOrganizations)";
        var params = parameters(organization, now, keyword, category)
                .addValue("activeOrganizations", activeOrganizations)
                .addValue("limit", page.getPageSize()).addValue("offset", page.getOffset());
        var rows = jdbc.query("select " + FIELDS + " from catalog.events" + predicate
                + " order by starts_at,id limit :limit offset :offset", params, this::row);
        return PageableExecutionUtils.getPage(rows, page,
                () -> Objects.requireNonNull(jdbc.queryForObject("select count(*) from catalog.events"
                        + predicate, params, Long.class)));
    }

    public Optional<Row> findById(UUID id) {
        return jdbc.query("select " + FIELDS + " from catalog.events where id=:id",
                new MapSqlParameterSource("id", id), this::row).stream().findFirst();
    }

    private Row row(ResultSet rs, int index) throws SQLException {
        try {
            return new Row(rs.getObject("id", UUID.class), rs.getString("title"), rs.getString("description"),
                    rs.getString("location"), rs.getTimestamp("starts_at").toInstant(),
                    rs.getTimestamp("ends_at").toInstant(), rs.getInt("capacity"),
                    EventCategory.valueOf(rs.getString("category")), CardTheme.valueOf(rs.getString("card_theme")),
                    mapper.readValue(rs.getString("registration_requirements"), RegistrationRequirements.class),
                    rs.getObject("organization_id", UUID.class), rs.getString("visibility"), rs.getString("status"));
        } catch (JsonProcessingException e) {
            throw new SQLException("Invalid event registration requirements", e);
        }
    }
}
