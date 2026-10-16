package com.sems.platform.admission;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import java.time.*;
import java.sql.Timestamp;
import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;
@Service
public class EventRevisionService {
 private final JdbcTemplate jdbc;private final ObjectMapper json;
 public EventRevisionService(JdbcTemplate jdbc,ObjectMapper json){this.jdbc=jdbc;this.json=json;}
 public record Desired(@Min(1) int capacity,@NotNull Instant startsAt,@NotNull Instant endsAt,@Valid TicketRevision ticketConfiguration,@Pattern(regexp="PUBLISHED|PAUSED") String publicationStatus){}
 public record TicketRevision(@NotNull @Min(0) Long version,@NotEmpty @Size(max=20) List<@NotNull @Valid TicketEdit> ticketTypes){}
 public record TicketEdit(UUID id,@NotBlank @Size(max=100) String name,@Min(1) int quota,@NotNull Instant opensAt,@NotNull Instant closesAt){}
 public record Operation(@NotNull UUID operationId,@NotNull UUID eventId,@NotNull UUID organizerId,@NotBlank String sourceStatus,@Min(1) int oldCapacity,@NotNull Instant oldStartsAt,@NotNull Instant oldEndsAt,@Valid @NotNull Desired desired,UUID organizationId){}
 private String write(Operation o){try{return json.writeValueAsString(o);}catch(Exception e){throw new IllegalStateException(e);}}
 @Transactional public void revise(UUID event,Operation op){
  if(!event.equals(op.eventId()))conflict("Event mismatch");
  jdbc.query("SELECT pg_advisory_xact_lock(hashtextextended(?,0))",(org.springframework.jdbc.core.RowCallbackHandler)r->{},event.toString());
  var receipt=jdbc.queryForList("SELECT jsonb_strip_nulls(payload)=jsonb_strip_nulls(?::jsonb) AS matches FROM event_revision_receipts WHERE id=?",write(op),op.operationId());
  if(!receipt.isEmpty()){if(!Boolean.TRUE.equals(receipt.getFirst().get("matches")))conflict("Operation was reused with different input");return;}
  var rows=jdbc.queryForList("SELECT * FROM sales WHERE event_id=? FOR UPDATE",event);
  var d=op.desired();if(((!d.startsAt().equals(op.oldStartsAt())||op.sourceStatus().equals("DRAFT"))&&!d.startsAt().isAfter(Instant.now()))||!d.endsAt().isAfter(d.startsAt()))conflict("Invalid event schedule");
  if(rows.isEmpty()){
   if(!op.sourceStatus().equals("DRAFT"))conflict("Sales not found");
   jdbc.update("INSERT INTO sales(event_id,organizer_id,capacity,starts_at,ends_at,state,version,organization_id) VALUES (?,?,?,?,?,'DRAFT',0,?)",event,op.organizerId(),d.capacity(),Timestamp.from(d.startsAt()),Timestamp.from(d.endsAt()),op.organizationId());
  }else{
   var row=rows.getFirst();String expected=op.sourceStatus().equals("PUBLISHED")?"ACTIVE":op.sourceStatus().equals("PAUSED")?"PAUSED":"DRAFT";
   if(!row.get("organizer_id").equals(op.organizerId())||!Objects.equals(row.get("organization_id"),op.organizationId())||!row.get("state").equals(expected)||((Number)row.get("capacity")).intValue()!=op.oldCapacity()||!((Timestamp)row.get("starts_at")).toInstant().equals(op.oldStartsAt())||!((Timestamp)row.get("ends_at")).toInstant().equals(op.oldEndsAt()))conflict("Event changed; reload");
   long allocated=jdbc.queryForObject("SELECT COALESCE(sum(quota),0) FROM ticket_types WHERE event_id=?",Long.class,event);
   if(d.ticketConfiguration()==null && d.capacity()<allocated)conflict("Capacity cannot be less than allocated ticket quota");
   boolean timeChanged=!d.startsAt().equals(op.oldStartsAt())||!d.endsAt().equals(op.oldEndsAt());
   if(timeChanged && jdbc.queryForObject("SELECT count(*) FROM tickets t JOIN bookings b ON t.booking_id=b.id WHERE b.event_id=? AND t.state='CHECKED_IN'",Long.class,event)>0)conflict("Checked-in events cannot be rescheduled");
   var delta=Duration.between(op.oldStartsAt(),d.startsAt());double shift=delta.getSeconds()+delta.getNano()/1_000_000_000.0;
   if(d.ticketConfiguration()==null)jdbc.update("UPDATE ticket_types SET opens_at=opens_at+(? * interval '1 second'),closes_at=closes_at+(? * interval '1 second') WHERE event_id=?",shift,shift,event);
   jdbc.update("UPDATE sales SET capacity=?,starts_at=?,ends_at=?,version=version+1 WHERE event_id=?",d.capacity(),Timestamp.from(d.startsAt()),Timestamp.from(d.endsAt()),event);
   if(timeChanged)jdbc.update("UPDATE bookings SET starts_at=?,ends_at=? WHERE event_id=? AND status='CONFIRMED'",Timestamp.from(d.startsAt()),Timestamp.from(d.endsAt()),event);
  }
  if(d.ticketConfiguration()!=null) {
   // Existing sales have already advanced once above; match the input against the prior version.
   long current=jdbc.queryForObject("SELECT version FROM sales WHERE event_id=?",Long.class,event);
   long expectedVersion=rows.isEmpty()?0:current-1;
   if(d.ticketConfiguration().version()!=expectedVersion)conflict("Ticket configuration changed; reload");
   updateTickets(event,d);
   if(rows.isEmpty())jdbc.update("UPDATE sales SET version=version+1 WHERE event_id=?",event);
  }
  if(d.publicationStatus()!=null) {
   if(op.sourceStatus().equals("DRAFT"))conflict("First publication requires confirmation");
   jdbc.update("UPDATE sales SET state=? WHERE event_id=?",d.publicationStatus().equals("PUBLISHED")?"ACTIVE":"PAUSED",event);
  }
  jdbc.update("INSERT INTO event_revision_receipts(id,event_id,payload) VALUES (?,?,?::jsonb)",op.operationId(),event,write(op));
 }
 private void updateTickets(UUID event,Desired d){
  var existing=jdbc.queryForList("SELECT id,reserved FROM ticket_types WHERE event_id=?",event);
  var owned=new HashMap<UUID,Integer>(); for(var row:existing)owned.put((UUID)row.get("id"),((Number)row.get("reserved")).intValue());
  var ids=new HashSet<UUID>();var names=new HashSet<String>();long total=0;
  for(var t:d.ticketConfiguration().ticketTypes()){
   if(!names.add(t.name().strip()))conflict("Ticket names must be unique");
   if(!t.closesAt().isAfter(t.opensAt())||t.closesAt().isAfter(d.startsAt()))conflict("Invalid ticket sales window");
   total+=t.quota();
   if(t.id()!=null){if(!owned.containsKey(t.id())||!ids.add(t.id()))conflict("Invalid ticket type");if(t.quota()<owned.get(t.id()))conflict("Quota cannot be below issued places");}
  }
  if(total>d.capacity())conflict("Ticket quotas exceed capacity");
  for(var id:owned.keySet())if(!ids.contains(id)){
   boolean used=Boolean.TRUE.equals(jdbc.queryForObject("SELECT EXISTS(SELECT 1 FROM bookings WHERE ticket_type_id=? UNION ALL SELECT 1 FROM pre_registrations WHERE ticket_type_id=?)",Boolean.class,id,id));
   if(used)conflict("A used ticket type cannot be removed");
   jdbc.update("DELETE FROM ticket_types WHERE id=?",id);
  }
  for(var t:d.ticketConfiguration().ticketTypes()){
   if(t.id()==null)jdbc.update("INSERT INTO ticket_types(id,event_id,name,quota,opens_at,closes_at) VALUES(?,?,?,?,?,?)",UUID.randomUUID(),event,t.name().strip(),t.quota(),Timestamp.from(t.opensAt()),Timestamp.from(t.closesAt()));
   else jdbc.update("UPDATE ticket_types SET name=?,quota=?,opens_at=?,closes_at=? WHERE id=? AND event_id=?",t.name().strip(),t.quota(),Timestamp.from(t.opensAt()),Timestamp.from(t.closesAt()),t.id(),event);
  }
 }
 private static void conflict(String s){throw new ResponseStatusException(HttpStatus.CONFLICT,s);}
}
