package com.sems.platform.admission;

import java.security.SecureRandom;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Timestamp;
import java.time.Instant;
import java.util.*;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;
import static com.sems.platform.admission.BookingContracts.*;

@Service
public class BookingService {
    private final JdbcTemplate jdbc;
    private final com.fasterxml.jackson.databind.ObjectMapper json;
    private final SecureRandom random = new SecureRandom();
    public BookingService(JdbcTemplate jdbc,com.fasterxml.jackson.databind.ObjectMapper json) { this.jdbc=jdbc;this.json=json; }
    private void requestLock(UUID user, UUID key) {
        jdbc.query("SELECT pg_advisory_xact_lock(hashtextextended(?,0))",
            (org.springframework.jdbc.core.RowCallbackHandler) rs -> {}, "booking:"+user+":"+key);
    }
    private void eventLock(UUID event) {
        if (jdbc.queryForList("SELECT event_id FROM sales WHERE event_id=? FOR UPDATE",event).isEmpty())
            throw new ResponseStatusException(HttpStatus.NOT_FOUND,"Event not found");
    }
    static void sameRequest(UUID event, UUID type, int quantity, Request input) {
        if (!event.equals(input.eventId()) || !type.equals(input.ticketTypeId()) || quantity!=input.quantity())
            conflict("This request key was used with different booking details");
    }
    @Transactional(readOnly=true, isolation=org.springframework.transaction.annotation.Isolation.REPEATABLE_READ)
    public Booking replay(UUID user, Request input) {
        var rows=jdbc.queryForList("SELECT id,event_id,ticket_type_id,quantity,attendee_info FROM bookings WHERE user_id=? AND request_key=?",user,input.requestKey());
        if (rows.isEmpty()) return null;
        var row=rows.getFirst();
        sameRequest((UUID)row.get("event_id"),(UUID)row.get("ticket_type_id"),((Number)row.get("quantity")).intValue(),input);
        if (!readInfo(row.get("attendee_info").toString()).equals(input.attendeeInfo())) conflict("This request key was used with different registration information");
        return owned(user,(UUID)row.get("id"));
    }
    @Transactional
    public Booking create(UUID user, Request input, TicketContracts.Snapshot snapshot) {
        requestLock(user,input.requestKey());
        Booking prior=replay(user,input);
        if (prior!=null) return prior;
        eventLock(input.eventId());
        var rows=jdbc.queryForList("SELECT s.state,s.capacity,s.starts_at,s.ends_at,t.name,t.opens_at,t.closes_at FROM sales s JOIN ticket_types t ON t.event_id=s.event_id WHERE s.event_id=? AND t.id=?",input.eventId(),input.ticketTypeId());
        if (rows.isEmpty()) throw new ResponseStatusException(HttpStatus.NOT_FOUND,"Ticket type not found for this event");
        var row=rows.getFirst();
        Instant now=Instant.now();
        Instant starts=((Timestamp)row.get("starts_at")).toInstant();
        if (!snapshot.id().equals(input.eventId()) || !snapshot.status().equals("PUBLISHED") || !row.get("state").equals("ACTIVE")) conflict("Event is not available for booking");
        if (!starts.equals(snapshot.startsAt()) || !((Timestamp)row.get("ends_at")).toInstant().equals(snapshot.endsAt()) || ((Number)row.get("capacity")).intValue()!=snapshot.capacity() || !starts.isAfter(now)) conflict("Event has started or changed");
        if (now.isBefore(((Timestamp)row.get("opens_at")).toInstant()) || !now.isBefore(((Timestamp)row.get("closes_at")).toInstant())) conflict("Ticket sales are not open");
        input.attendeeInfo().validate(snapshot.registrationRequirements());
        int updated=jdbc.update("UPDATE ticket_types SET reserved=reserved+? WHERE id=? AND ?<=quota-reserved",input.quantity(),input.ticketTypeId(),input.quantity());
        if (updated!=1) conflict("Not enough places available");
        UUID id=UUID.randomUUID();
        jdbc.update("INSERT INTO bookings(id,user_id,request_key,event_id,ticket_type_id,quantity,status,event_title,event_location,starts_at,ends_at,ticket_name,attendee_info,custom_field_label) VALUES (?,?,?,?,?,?,'CONFIRMED',?,?,?,?,?,?::jsonb,?)",
            id,user,input.requestKey(),input.eventId(),input.ticketTypeId(),input.quantity(),snapshot.title(),snapshot.location(),Timestamp.from(starts),row.get("ends_at"),row.get("name"),writeInfo(input.attendeeInfo()),snapshot.registrationRequirements().customFieldLabel());
        for (int n=0;n<input.quantity();n++) {
            byte[] bytes=new byte[24]; random.nextBytes(bytes);
            String code=HexFormat.of().formatHex(bytes);
            jdbc.update("INSERT INTO tickets(id,booking_id,credential,state) VALUES (?,?,?,'VALID')",UUID.randomUUID(),id,code);
        }
        jdbc.update("DELETE FROM pre_registrations WHERE user_id=? AND event_id=? AND ticket_type_id=?",user,input.eventId(),input.ticketTypeId());
        NotificationService.add(jdbc,user,"booking-confirmed:"+id,"BOOKING_CONFIRMED","Booking confirmed",snapshot.title()+" · "+input.quantity()+" ticket(s). Your tickets are ready.","/bookings/"+id);
        return owned(user,id);
    }
    @Transactional(readOnly=true, isolation=org.springframework.transaction.annotation.Isolation.REPEATABLE_READ)
    public Booking owned(UUID user, UUID id) {
        var rows=jdbc.query("SELECT * FROM bookings WHERE id=? AND user_id=?",this::map,id,user);
        if (rows.isEmpty()) throw new ResponseStatusException(HttpStatus.NOT_FOUND,"Booking not found");
        return rows.getFirst();
    }
    private Booking map(ResultSet rs,int n) throws SQLException {
        UUID id=rs.getObject("id",UUID.class);
        var tickets=jdbc.query("SELECT * FROM tickets WHERE booking_id=? ORDER BY id",(r,i)->new Ticket(r.getObject("id",UUID.class),r.getString("credential"),r.getString("state")),id);
        return new Booking(id,rs.getObject("event_id",UUID.class),rs.getObject("ticket_type_id",UUID.class),rs.getInt("quantity"),rs.getString("status"),rs.getString("event_title"),rs.getString("event_location"),rs.getTimestamp("starts_at").toInstant(),rs.getTimestamp("ends_at").toInstant(),rs.getString("ticket_name"),rs.getInt("amount"),rs.getTimestamp("created_at").toInstant(),tickets,readInfo(rs.getString("attendee_info")),rs.getString("custom_field_label"));
    }
    @Transactional(readOnly=true, isolation=org.springframework.transaction.annotation.Isolation.REPEATABLE_READ)
    public Page list(UUID user,int page,int size,String status) {
        if (page<0 || page>100000 || size<1 || size>50) throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Page must be 0–100000 and size 1–50");
        if (status!=null && !status.equals("CONFIRMED") && !status.equals("CANCELLED")) throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Status must be CONFIRMED or CANCELLED");
        String filter=status==null ? "user_id=?" : "user_id=? AND status=?";
        Object[] countArgs=status==null ? new Object[]{user} : new Object[]{user,status};
        Object[] pageArgs=status==null ? new Object[]{user,size,(long)page*size} : new Object[]{user,status,size,(long)page*size};
        long total=jdbc.queryForObject("SELECT count(*) FROM bookings WHERE "+filter,Long.class,countArgs);
        var items=jdbc.query("SELECT * FROM bookings WHERE "+filter+" ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?",this::map,pageArgs);
        return new Page(items,page,size,total,(total+size-1)/size);
    }
    @Transactional(readOnly=true,isolation=org.springframework.transaction.annotation.Isolation.REPEATABLE_READ)
    public Page upcoming(UUID user){
        var now=Timestamp.from(Instant.now());
        long total=jdbc.queryForObject("SELECT count(*) FROM bookings WHERE user_id=? AND status='CONFIRMED' AND ends_at>?",Long.class,user,now);
        var items=jdbc.query("SELECT * FROM bookings WHERE user_id=? AND status='CONFIRMED' AND ends_at>? ORDER BY starts_at,id LIMIT 5",this::map,user,now);
        return new Page(items,0,5,total,(total+4)/5);
    }
    @Transactional
    public Booking cancel(UUID user,UUID id) {
        // All booking writers acquire the sales row before changing tickets or inventory.
        var existing=owned(user,id);
        eventLock(existing.eventId());
        var booking=owned(user,id);
        if (booking.status().equals("CANCELLED")) return booking;
        if (!booking.startsAt().isAfter(Instant.now())) conflict("Cancellation closes when the event starts");
        if (booking.tickets().stream().anyMatch(t->t.state().equals("CHECKED_IN"))) conflict("A checked-in booking cannot be cancelled");
        jdbc.update("UPDATE bookings SET status='CANCELLED',cancelled_at=CURRENT_TIMESTAMP WHERE id=? AND status='CONFIRMED'",id);
        jdbc.update("UPDATE tickets SET state='CANCELLED' WHERE booking_id=?",id);
        int released=jdbc.update("UPDATE ticket_types SET reserved=reserved-? WHERE id=? AND reserved>=?",booking.quantity(),booking.ticketTypeId(),booking.quantity());
        if (released!=1) throw new IllegalStateException("Inventory invariant violated");
        NotificationService.add(jdbc,user,"booking-cancelled:"+id,"BOOKING_CANCELLED","Booking cancelled",booking.eventTitle()+" · Your booking has been cancelled and the places released.","/bookings/"+id);
        return owned(user,id);
    }
    private String writeInfo(AttendeeInfo info) {try{return json.writeValueAsString(info);}catch(com.fasterxml.jackson.core.JsonProcessingException e){throw new IllegalStateException(e);}}
    private AttendeeInfo readInfo(String value) {try{return json.readValue(value,AttendeeInfo.class);}catch(com.fasterxml.jackson.core.JsonProcessingException e){throw new IllegalStateException(e);}}
    @Transactional(readOnly=true,isolation=org.springframework.transaction.annotation.Isolation.REPEATABLE_READ)
    public OrganizerPage organizer(UUID event,int page,int size) {
        if(page<0||page>100000||size<1||size>50)throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Invalid pagination");
        long total=jdbc.queryForObject("SELECT count(*) FROM bookings WHERE event_id=?",Long.class,event);
        var items=jdbc.query("SELECT id,status,ticket_name,quantity,created_at,attendee_info,custom_field_label FROM bookings WHERE event_id=? ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?",
            (rs,n)->new OrganizerBooking(rs.getObject("id",UUID.class),rs.getString("status"),rs.getString("ticket_name"),rs.getInt("quantity"),rs.getTimestamp("created_at").toInstant(),readInfo(rs.getString("attendee_info")),rs.getString("custom_field_label")),event,size,(long)page*size);
        return new OrganizerPage(items,page,size,total,(total+size-1)/size);
    }
    private static void conflict(String message) { throw new ResponseStatusException(HttpStatus.CONFLICT,message); }
}
