package com.sems.platform.catalog;

import java.time.Instant;
import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

@Service
public class CancellationState {
 private final EventRepository events;
 private final OrganizationAccess access;
 private final JdbcTemplate jdbc;
 public CancellationState(EventRepository events,OrganizationAccess access,JdbcTemplate jdbc){this.events=events;this.access=access;this.jdbc=jdbc;}
 public record Operation(UUID eventId,UUID operationId,String reason) {}
 private Operation operation(UUID id){return jdbc.queryForObject("SELECT * FROM event_cancellations WHERE event_id=?",(r,n)->new Operation(id,r.getObject("operation_id",UUID.class),r.getString("reason")),id);}
 @Transactional public Operation begin(UUID actor,UUID id,long version,String reason){
  var before=events.findById(id).orElseThrow(()->new ResponseStatusException(HttpStatus.NOT_FOUND,"Event not found"));
  access.require(before.organizationId,actor,true);
  var event=events.lockById(id).orElseThrow();
  reason=reason.strip();
  if(reason.isEmpty())throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Provide a cancellation reason");
  if(event.status.equals("CANCELLING")||event.status.equals("CANCELLED")){
   var op=operation(id);
   long original=jdbc.queryForObject("SELECT requested_version FROM event_cancellations WHERE event_id=?",Long.class,id);
   if(original==version&&op.reason().equals(reason))return op;
   throw new ResponseStatusException(HttpStatus.CONFLICT,"Cancellation already requested; reload the event");
  }
  if(event.version!=version||!(event.status.equals("PUBLISHED")||event.status.equals("PAUSED")))throw new ResponseStatusException(HttpStatus.CONFLICT,"Reload the event; finish any pending publication or edit before cancelling");
  var op=new Operation(id,UUID.randomUUID(),reason);
  jdbc.update("INSERT INTO event_cancellations(event_id,operation_id,requested_version,reason) VALUES(?,?,?,?)",id,op.operationId(),version,reason);
  event.cancellationReason=reason;event.status="CANCELLING";event.publicationError=null;event.updatedAt=Instant.now();events.flush();return op;
 }
 @Transactional(readOnly=true) public boolean completed(Operation op){return Boolean.TRUE.equals(jdbc.queryForObject("SELECT EXISTS(SELECT 1 FROM event_cancellations WHERE event_id=? AND operation_id=? AND completed_at IS NOT NULL)",Boolean.class,op.eventId(),op.operationId()));}
 @Transactional public void finish(Operation op){
  var event=events.lockById(op.eventId()).orElseThrow();
  if(event.status.equals("CANCELLING")&&operation(op.eventId()).equals(op)){
   event.status="CANCELLED";event.publicationError=null;event.updatedAt=Instant.now();
   jdbc.update("UPDATE event_cancellations SET completed_at=CURRENT_TIMESTAMP WHERE event_id=?",op.eventId());
  }
 }
 @Transactional public void retryLater(Operation op){
  var event=events.lockById(op.eventId()).orElseThrow();
  if(event.status.equals("CANCELLING")){
   event.publicationError="Cancellation is pending. Automatic recovery will retry; new registrations are closed.";
   jdbc.update("UPDATE event_cancellations SET last_attempt_at=CURRENT_TIMESTAMP WHERE event_id=?",op.eventId());
  }
 }
 @Transactional(readOnly=true) public List<Operation> pending(){return jdbc.query("SELECT * FROM event_cancellations WHERE completed_at IS NULL ORDER BY last_attempt_at LIMIT 20",(r,n)->new Operation(r.getObject("event_id",UUID.class),r.getObject("operation_id",UUID.class),r.getString("reason")));}
}
