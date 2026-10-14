package com.sems.platform.admission;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import java.time.Instant;
import java.sql.*;
import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;
@Service
public class PreRegistrationService {
 private final JdbcTemplate jdbc;private final ObjectMapper json;
 public PreRegistrationService(JdbcTemplate jdbc,ObjectMapper json){this.jdbc=jdbc;this.json=json;}
 public record Input(@NotNull UUID ticketTypeId,@Min(1) @Max(10) int quantity,@Valid AttendeeInfo attendeeInfo){public Input{attendeeInfo=attendeeInfo==null?new AttendeeInfo(null,null,null,null,null,null):attendeeInfo;}}
 public record View(UUID eventId,UUID ticketTypeId,int quantity,AttendeeInfo attendeeInfo,String eventTitle,String eventLocation,String ticketName,Instant opensAt,Instant closesAt,Instant startsAt,String status,String customFieldLabel){}
 public record Page(List<View> items,int page,int size,long totalElements,long totalPages){}
 private static final String SELECT="SELECT p.*,t.name,t.opens_at,t.closes_at,t.quota-t.reserved AS available,s.starts_at,s.state FROM pre_registrations p JOIN ticket_types t ON t.id=p.ticket_type_id JOIN sales s ON s.event_id=p.event_id ";
 static String status(Instant now,Instant opens,Instant closes,Instant starts,String state,int available){
  if(!state.equals("ACTIVE")||!now.isBefore(closes)||!now.isBefore(starts))return "CLOSED";
  if(now.isBefore(opens))return "WAITING";
  return available>0?"READY":"SOLD_OUT";
 }
 private View map(ResultSet rs,int n)throws SQLException{
  try {var opens=rs.getTimestamp("opens_at").toInstant();var closes=rs.getTimestamp("closes_at").toInstant();var starts=rs.getTimestamp("starts_at").toInstant();
   return new View(rs.getObject("event_id",UUID.class),rs.getObject("ticket_type_id",UUID.class),rs.getInt("quantity"),json.readValue(rs.getString("attendee_info"),AttendeeInfo.class),rs.getString("event_title"),rs.getString("event_location"),rs.getString("name"),opens,closes,starts,status(Instant.now(),opens,closes,starts,rs.getString("state"),rs.getInt("available")),rs.getString("custom_field_label"));
  }catch(com.fasterxml.jackson.core.JsonProcessingException e){throw new IllegalStateException(e);}
 }
 @Transactional(readOnly=true) public View get(UUID user,UUID event){var rows=jdbc.query(SELECT+"WHERE p.user_id=? AND p.event_id=?",this::map,user,event);if(rows.isEmpty())throw new ResponseStatusException(HttpStatus.NOT_FOUND,"Pre-registration not found");return rows.getFirst();}
 @Transactional public View save(UUID user,UUID event,Input input,TicketContracts.Snapshot snapshot){
  var sales=jdbc.queryForList("SELECT state,starts_at,ends_at,capacity FROM sales WHERE event_id=? FOR UPDATE",event);
  if(sales.isEmpty())throw new ResponseStatusException(HttpStatus.NOT_FOUND,"Event not found");
  var tickets=jdbc.queryForList("SELECT opens_at,quota FROM ticket_types WHERE event_id=? AND id=?",event,input.ticketTypeId());
  if(tickets.isEmpty())throw new ResponseStatusException(HttpStatus.NOT_FOUND,"Ticket type not found");
  var now=Instant.now();
  var sale=sales.getFirst();if(!((Timestamp)sale.get("starts_at")).toInstant().equals(snapshot.startsAt())||!((Timestamp)sale.get("ends_at")).toInstant().equals(snapshot.endsAt())||((Number)sale.get("capacity")).intValue()!=snapshot.capacity())throw new ResponseStatusException(HttpStatus.CONFLICT,"Event changed; reload");
  if(!snapshot.id().equals(event)||!snapshot.status().equals("PUBLISHED")||!sales.getFirst().get("state").equals("ACTIVE")||!snapshot.startsAt().isAfter(now)||!now.isBefore(((Timestamp)tickets.getFirst().get("opens_at")).toInstant()))throw new ResponseStatusException(HttpStatus.CONFLICT,"Pre-registration is only available before registration opens");
  if(input.quantity()>((Number)tickets.getFirst().get("quota")).intValue())throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Quantity exceeds ticket quota");
  input.attendeeInfo().validate(snapshot.registrationRequirements());
  try {jdbc.update("INSERT INTO pre_registrations(user_id,event_id,ticket_type_id,quantity,attendee_info,event_title,event_location,custom_field_label) VALUES (?,?,?,?,?::jsonb,?,?,?) ON CONFLICT(user_id,event_id) DO UPDATE SET ticket_type_id=EXCLUDED.ticket_type_id,quantity=EXCLUDED.quantity,attendee_info=EXCLUDED.attendee_info,event_title=EXCLUDED.event_title,event_location=EXCLUDED.event_location,custom_field_label=EXCLUDED.custom_field_label,updated_at=CURRENT_TIMESTAMP",user,event,input.ticketTypeId(),input.quantity(),json.writeValueAsString(input.attendeeInfo()),snapshot.title(),snapshot.location(),snapshot.registrationRequirements().customFieldLabel());}catch(com.fasterxml.jackson.core.JsonProcessingException e){throw new IllegalStateException(e);}
  return get(user,event);
 }
 @Transactional(readOnly=true,isolation=org.springframework.transaction.annotation.Isolation.REPEATABLE_READ) public Page list(UUID user,int page,int size){
  if(page<0||page>100000||size<1||size>50)throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Invalid pagination");
  long total=jdbc.queryForObject("SELECT count(*) FROM pre_registrations WHERE user_id=?",Long.class,user);
  return new Page(jdbc.query(SELECT+"WHERE p.user_id=? ORDER BY p.updated_at DESC,p.event_id LIMIT ? OFFSET ?",this::map,user,size,(long)page*size),page,size,total,(total+size-1)/size);
 }
 @Transactional public void delete(UUID user,UUID event){jdbc.update("DELETE FROM pre_registrations WHERE user_id=? AND event_id=?",user,event);}
}
