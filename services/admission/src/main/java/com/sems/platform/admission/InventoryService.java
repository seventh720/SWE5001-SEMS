package com.sems.platform.admission;

import java.time.Instant;
import java.util.*;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;
import static com.sems.platform.admission.TicketContracts.*;

@Service
public class InventoryService {
    private final JdbcTemplate jdbc;
    public InventoryService(JdbcTemplate jdbc) { this.jdbc=jdbc; }
    private void lock(UUID event) {
        jdbc.query("SELECT pg_advisory_xact_lock(hashtextextended(?,0))", (org.springframework.jdbc.core.RowCallbackHandler) row -> {}, event.toString());
    }
    public static void validate(Snapshot snapshot, List<TicketInput> tickets) {
        if (tickets==null || tickets.isEmpty()) conflict("At least one ticket type is required");
        long sum=0; var names=new HashSet<String>();
        for (var ticket:tickets) {
            sum+=ticket.quota();
            if (!names.add(ticket.name().strip())) conflict("Ticket names must be unique");
            if (!ticket.closesAt().isAfter(ticket.opensAt()) || ticket.closesAt().isAfter(snapshot.startsAt()))
                conflict("Sales must close after opening and no later than the event start");
        }
        if (sum>snapshot.capacity()) conflict("Total ticket quota exceeds event capacity");
    }
    @Transactional
    public Inventory configure(Snapshot event, Configuration input) {
        validate(event,input.ticketTypes()); lock(event.id());
        var rows=jdbc.queryForList("SELECT * FROM sales WHERE event_id=?",event.id());
        if (rows.isEmpty()) {
            if (input.version()!=0) conflict("Inventory changed; reload");
            jdbc.update("INSERT INTO sales(event_id,organizer_id,capacity,starts_at,ends_at,state,version) VALUES (?,?,?,?,?,'DRAFT',0)",
                    event.id(),event.organizerId(),event.capacity(),java.sql.Timestamp.from(event.startsAt()),java.sql.Timestamp.from(event.endsAt()));
        } else {
            var current=rows.getFirst();
            if (!current.get("organizer_id").equals(event.organizerId())) conflict("Event owner mismatch");
            if (!current.get("state").equals("DRAFT")) conflict("Published ticket configuration is immutable");
            if (((Number)current.get("version")).longValue()!=input.version()) conflict("Inventory changed; reload");
        }
        jdbc.update("DELETE FROM ticket_types WHERE event_id=?",event.id());
        for (var ticket:input.ticketTypes()) jdbc.update("INSERT INTO ticket_types(id,event_id,name,quota,opens_at,closes_at) VALUES (?,?,?,?,?,?)",
                UUID.randomUUID(),event.id(),ticket.name().strip(),ticket.quota(),java.sql.Timestamp.from(ticket.opensAt()),java.sql.Timestamp.from(ticket.closesAt()));
        jdbc.update("UPDATE sales SET version=version+1 WHERE event_id=?",event.id());
        return inventory(event.id());
    }
    @Transactional
    public void activate(UUID event, Activate input) {
        lock(event);
        var rows=jdbc.queryForList("SELECT * FROM sales WHERE event_id=?",event);
        if (rows.isEmpty()) conflict("Configure ticket types before publication");
        var row=rows.getFirst();
        boolean matches=row.get("organizer_id").equals(input.organizerId()) && ((Number)row.get("capacity")).intValue()==input.capacity()
                && ((java.sql.Timestamp)row.get("starts_at")).toInstant().equals(input.startsAt())
                && ((java.sql.Timestamp)row.get("ends_at")).toInstant().equals(input.endsAt())
                && ((Number)row.get("version")).longValue()==input.ticketVersion();
        if (!matches) conflict("Event or ticket configuration changed; reload");
        if (row.get("state").equals("ACTIVE")) {
            if (input.operationId().equals(row.get("activation_id"))) return;
            conflict("Sales already activated by another operation");
        }
        if (!input.startsAt().isAfter(Instant.now())) conflict("Event already started");
        if (inventory(event).ticketTypes().isEmpty()) conflict("At least one ticket type is required");
        jdbc.update("UPDATE sales SET state='ACTIVE',activation_id=? WHERE event_id=?",input.operationId(),event);
    }
    @Transactional(readOnly=true)
    public Inventory inventory(UUID event) {
        var rows=jdbc.queryForList("SELECT version,state FROM sales WHERE event_id=?",event);
        if (rows.isEmpty()) return new Inventory(event,0,"DRAFT",List.of());
        var tickets=jdbc.query("SELECT * FROM ticket_types WHERE event_id=? ORDER BY name,id",(rs,n)->new TicketView(
                rs.getObject("id",UUID.class),rs.getString("name"),rs.getInt("quota"),rs.getInt("quota")-rs.getInt("reserved"),
                rs.getTimestamp("opens_at").toInstant(),rs.getTimestamp("closes_at").toInstant(),0),event);
        return new Inventory(event,((Number)rows.getFirst().get("version")).longValue(),rows.getFirst().get("state").toString(),tickets);
    }
    private static void conflict(String message) { throw new ResponseStatusException(HttpStatus.CONFLICT,message); }
}
