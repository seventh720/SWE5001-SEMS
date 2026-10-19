package com.sems.platform.catalog;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.time.Instant;
import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;
@Service
public class RevisionState {
 private final EventRepository events;private final OrganizationAccess access;private final JdbcTemplate jdbc;private final ObjectMapper json;
 public RevisionState(EventRepository events,JdbcTemplate jdbc,ObjectMapper json,OrganizationAccess access){this.access=access;this.events=events;this.jdbc=jdbc;this.json=json;}
 public record Operation(UUID operationId,UUID eventId,UUID organizerId,String sourceStatus,int oldCapacity,Instant oldStartsAt,Instant oldEndsAt,Draft desired,UUID organizationId){}
 private String write(Operation o){try{return json.writeValueAsString(o);}catch(Exception e){throw new IllegalStateException(e);}}
 private Operation read(String s){try{return json.readValue(s,Operation.class);}catch(Exception e){throw new IllegalStateException(e);}}
 @Transactional public Operation begin(UUID owner,UUID id,Draft input){
  var before=events.findById(id).orElseThrow(()->new ResponseStatusException(HttpStatus.NOT_FOUND,"Event not found"));access.require(before.organizationId,owner,true);
  var e=events.lockById(id).orElseThrow(()->new ResponseStatusException(HttpStatus.NOT_FOUND,"Event not found"));
  var pending=jdbc.query("SELECT payload FROM event_revisions WHERE event_id=? AND status='PENDING'",(rs,n)->read(rs.getString(1)),id);
  if(!pending.isEmpty()){if(pending.getFirst().desired().equals(input))return pending.getFirst();conflict("An event update is pending. Wait for it to complete, then reload.");}
  if(!e.endsAt.isAfter(Instant.now()))conflict("Ended events cannot be edited or reopened. Create a new event using a template.");
  if(input.version()==null||e.version!=input.version())conflict("Event changed; reload before editing");
  if((!e.salesConfigured && input.ticketConfiguration()==null)||!(e.status.equals("DRAFT")||e.status.equals("PUBLISHED")||e.status.equals("PAUSED")))conflict("Event is not ready for this update");
  if(!input.endsAt().isAfter(input.startsAt())||((!input.startsAt().equals(e.startsAt)||e.status.equals("DRAFT"))&&!input.startsAt().isAfter(Instant.now())))throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Choose a future start and an end after it");
  if(!e.status.equals("DRAFT")&&!e.registrationRequirements.equals(input.registrationRequirements()))conflict("Registration requirements are fixed after publication");
  if(input.publicationStatus()!=null && e.status.equals("DRAFT"))conflict("Use publication preview for first publication");
  if(input.organizationId()!=null&&!input.organizationId().equals(e.organizationId))conflict("Event organization cannot change");
  var op=new Operation(UUID.randomUUID(),id,e.organizerId,e.status,e.capacity,e.startsAt,e.endsAt,input,e.organizationId);
  jdbc.update("INSERT INTO event_revisions(id,event_id,payload,status) VALUES (?,?,?::jsonb,'PENDING')",op.operationId(),id,write(op));
  e.salesConfigured=true;e.status="UPDATING";e.publicationError=null;e.updatedAt=Instant.now();events.flush();return op;
 }
 @Transactional public void finish(Operation op){var e=events.lockById(op.eventId()).orElseThrow();int changed=jdbc.update("UPDATE event_revisions SET status='APPLIED' WHERE id=? AND status='PENDING'",op.operationId());if(changed==1){e.apply(op.desired());e.status=op.desired().publicationStatus()==null?op.sourceStatus():op.desired().publicationStatus();e.publicationError=null;events.flush();if(!op.sourceStatus().equals("DRAFT")){try{var payload=json.writeValueAsString(Map.of("eventId",e.id,"title",e.title,"location",e.location,"startsAt",e.startsAt,"endsAt",e.endsAt,"status",e.status,"visibility",e.visibility));jdbc.update("INSERT INTO event_notification_outbox(id,payload) VALUES(?,?::jsonb)",UUID.randomUUID(),payload);}catch(com.fasterxml.jackson.core.JsonProcessingException ex){throw new IllegalStateException(ex);}}}}
 @Transactional public void reject(Operation op,String message){var e=events.lockById(op.eventId()).orElseThrow();if(jdbc.update("UPDATE event_revisions SET status='REJECTED',error=? WHERE id=? AND status='PENDING'",message,op.operationId())==1){e.status=op.sourceStatus();e.publicationError=message;e.updatedAt=Instant.now();events.flush();}}
 @Transactional(readOnly=true) public List<Operation> pending(){return jdbc.query("SELECT payload FROM event_revisions WHERE status='PENDING' ORDER BY created_at LIMIT 20",(rs,n)->read(rs.getString(1)));}
 private static void conflict(String s){throw new ResponseStatusException(HttpStatus.CONFLICT,s);}
}
