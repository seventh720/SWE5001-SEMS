package com.sems.platform.catalog;
import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;
@Service
public class OrganizationClosureState {
 private final JdbcTemplate jdbc;private final EventRepository events;
 public OrganizationClosureState(JdbcTemplate jdbc,EventRepository events){this.jdbc=jdbc;this.events=events;}
 @Transactional public void freeze(UUID org,UUID operation,java.time.Instant requestedAt){
  jdbc.query("SELECT pg_advisory_xact_lock(hashtextextended(?,0))",(org.springframework.jdbc.core.RowCallbackHandler)r->{},"organization:"+org);
  jdbc.update("INSERT INTO organization_closures(organization_id,operation_id,created_at) VALUES(?,?,?) ON CONFLICT(organization_id) DO NOTHING",org,operation,java.sql.Timestamp.from(requestedAt));
  var receipt=jdbc.queryForMap("SELECT operation_id,created_at FROM organization_closures WHERE organization_id=?",org);
  if(!operation.equals(receipt.get("operation_id"))||!requestedAt.equals(((java.sql.Timestamp)receipt.get("created_at")).toInstant()))throw new ResponseStatusException(HttpStatus.CONFLICT,"Closure operation mismatch");
 }
 public List<UUID> candidates(UUID org){return jdbc.queryForList("SELECT e.id FROM events e JOIN organization_closures c ON c.organization_id=e.organization_id WHERE e.organization_id=? AND e.status IN ('PUBLISHED','PAUSED') AND e.ends_at>c.created_at ORDER BY e.id LIMIT 20",UUID.class,org);}
 @Transactional public void cancel(UUID org,UUID id){
  var event=events.lockById(id).orElseThrow();
  var cutoff=jdbc.queryForObject("SELECT created_at FROM organization_closures WHERE organization_id=?",java.sql.Timestamp.class,org).toInstant();
  if(!org.equals(event.organizationId)||!event.endsAt.isAfter(cutoff)||!(event.status.equals("PUBLISHED")||event.status.equals("PAUSED")))return;
  String reason="The organization is closing. This event has been cancelled.";
  jdbc.update("INSERT INTO event_cancellations(event_id,operation_id,requested_version,reason) VALUES(?,?,?,?)",id,UUID.randomUUID(),event.version,reason);
  event.cancellationReason=reason;event.status="CANCELLING";event.publicationError=null;event.updatedAt=java.time.Instant.now();events.flush();
 }
 public boolean complete(UUID org){return !Boolean.TRUE.equals(jdbc.queryForObject("SELECT EXISTS(SELECT 1 FROM events e JOIN organization_closures c ON c.organization_id=e.organization_id WHERE e.organization_id=? AND (e.status IN ('PUBLISHING','UPDATING','CANCELLING') OR (e.status IN ('PUBLISHED','PAUSED') AND e.ends_at>c.created_at)))",Boolean.class,org));}
}
