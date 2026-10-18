package com.sems.platform.identity;
import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
@Service
public class OrganizationClosureState {
 private final JdbcTemplate jdbc;
 public OrganizationClosureState(JdbcTemplate jdbc){this.jdbc=jdbc;}
 public record Operation(UUID organizationId,UUID operationId,java.time.Instant requestedAt){}
 public List<Operation> pending(){return jdbc.query("SELECT * FROM organization_closures WHERE completed_at IS NULL ORDER BY last_attempt_at LIMIT 20",(r,n)->new Operation(r.getObject("organization_id",UUID.class),r.getObject("operation_id",UUID.class),r.getTimestamp("created_at").toInstant()));}
 @Transactional public void attempted(Operation op){jdbc.update("UPDATE organization_closures SET last_attempt_at=CURRENT_TIMESTAMP WHERE organization_id=? AND operation_id=? AND completed_at IS NULL",op.organizationId(),op.operationId());}
 @Transactional public void finish(Operation op){
  var org=jdbc.queryForMap("SELECT * FROM organizations WHERE id=? FOR UPDATE",op.organizationId());
  var rows=jdbc.queryForList("SELECT target_status FROM organization_closures WHERE organization_id=? AND operation_id=? AND completed_at IS NULL",String.class,op.organizationId(),op.operationId());
  if(rows.isEmpty()||!org.get("status").equals("CLOSING"))return;
  var target=rows.getFirst();
  jdbc.update("INSERT INTO membership_notifications(user_id,organization_id,title,message,link,kind) SELECT user_id,organization_id,'Organization closed',?,'/organizations','ORGANIZATION_REQUEST' FROM organization_memberships WHERE organization_id=? AND status<>'REMOVED'",org.get("name")+" was "+(target.equals("DELETED")?"deleted":"closed (Suspended)")+". Unfinished events have been cancelled. Your personal account and history are retained.",op.organizationId());
  jdbc.update("UPDATE organization_memberships SET role='MEMBER',status='REMOVED',version=version+1 WHERE organization_id=? AND status<>'REMOVED'",op.organizationId());
  jdbc.update("UPDATE organization_invitations SET status='REVOKED' WHERE organization_id=? AND status='PENDING'",op.organizationId());
  jdbc.update("UPDATE organizations SET status=?,version=version+1 WHERE id=?",target,op.organizationId());
  jdbc.update("UPDATE organization_closures SET completed_at=CURRENT_TIMESTAMP WHERE organization_id=?",op.organizationId());
 }
}
