package com.sems.platform.identity;

import java.util.*;
import java.time.Instant;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.annotation.Isolation;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.http.HttpStatus;

@Service
public class OrganizationGovernanceService {
 private final JdbcTemplate jdbc;private final OrganizationService organizations;
 public OrganizationGovernanceService(JdbcTemplate jdbc,OrganizationService organizations){this.jdbc=jdbc;this.organizations=organizations;}
 public record Request(UUID id,UUID organizationId,String organizationName,UUID requesterId,String kind,String name,String slug,String reason,long baseVersion,String status,String reviewNote,Instant createdAt){}
 private final RowMapper<Request> mapper=(r,n)->new Request(r.getObject("id",UUID.class),r.getObject("organization_id",UUID.class),r.getString("organization_name"),r.getObject("requester_id",UUID.class),r.getString("kind"),r.getString("name"),r.getString("slug"),r.getString("reason"),r.getLong("base_version"),r.getString("status"),r.getString("review_note"),r.getTimestamp("created_at").toInstant());
 private Map<String,Object> lock(UUID org){var rows=jdbc.queryForList("SELECT * FROM organizations WHERE id=? FOR UPDATE",org);if(rows.isEmpty()||rows.getFirst().get("status").equals("DELETED"))throw new ResponseStatusException(HttpStatus.NOT_FOUND,"Organization not found");if(rows.getFirst().get("status").equals("CLOSING"))throw new ResponseStatusException(HttpStatus.CONFLICT,"Organization closure is already in progress");return rows.getFirst();}
 private void version(Map<String,Object> org,long version){if(((Number)org.get("version")).longValue()!=version)throw new ResponseStatusException(HttpStatus.CONFLICT,"Organization changed. Reload and submit a new request.");}
 private void notice(UUID org,UUID user,String title,String message,String link){jdbc.update("INSERT INTO membership_notifications(user_id,organization_id,title,message,link,kind) VALUES(?,?,?,?,?,'ORGANIZATION_REQUEST')",user,org,title,message,link);}
 private void notifyMembers(UUID org,String message){for(UUID user:jdbc.queryForList("SELECT user_id FROM organization_memberships WHERE organization_id=? AND status<>'REMOVED'",UUID.class,org))notice(org,user,"Organization updated",message,"/organizations");}
 public record RequestPage(List<Request> items,int page,int size,long totalElements,long totalPages,boolean hasPending){}
 private RequestPage page(UUID org,int page,int size){
  if(page<0||page>100000||size<1||size>50)throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Invalid pagination");
  String filter=org==null?"":" WHERE r.organization_id=?";
  Object[] args=org==null?new Object[]{}:new Object[]{org};
  long total=jdbc.queryForObject("SELECT count(*) FROM organization_requests r"+filter,Long.class,args);
  boolean pending=Boolean.TRUE.equals(jdbc.queryForObject("SELECT EXISTS(SELECT 1 FROM organization_requests r"+(org==null?" WHERE":" WHERE r.organization_id=? AND")+" r.status='PENDING')",Boolean.class,args));
  var queryArgs=new ArrayList<Object>(Arrays.asList(args));queryArgs.add(size);queryArgs.add((long)page*size);
  var items=jdbc.query("SELECT r.*,o.name AS organization_name FROM organization_requests r JOIN organizations o ON o.id=r.organization_id"+filter+" ORDER BY CASE WHEN r.status='PENDING' THEN 0 ELSE 1 END,r.created_at DESC,r.id DESC LIMIT ? OFFSET ?",mapper,queryArgs.toArray());
  return new RequestPage(items,page,size,total,(total+size-1)/size,pending);
 }
 @Transactional(readOnly=true,isolation=Isolation.REPEATABLE_READ)
 public RequestPage requests(UUID org,UUID user,int page,int size){organizations.require(org,user,true);return page(org,page,size);}
 @Transactional(readOnly=true,isolation=Isolation.REPEATABLE_READ)
 public RequestPage reviewQueue(int page,int size){return page(null,page,size);}
 @Transactional public Request submit(UUID org,UUID user,String kind,String name,String slug,String reason,long baseVersion){
  var old=lock(org);organizations.require(org,user,true);version(old,baseVersion);
  if(kind.equals("UPDATE")){validateProfile(name,slug);if(old.get("name").equals(name.strip())&&old.get("slug").equals(slug))throw new ResponseStatusException(HttpStatus.CONFLICT,"No organization details changed");}
  UUID id=UUID.randomUUID();jdbc.update("INSERT INTO organization_requests(id,organization_id,requester_id,kind,name,slug,reason,base_version) VALUES(?,?,?,?,?,?,?,?)",id,org,user,kind,kind.equals("UPDATE")?name.strip():null,kind.equals("UPDATE")?slug:null,reason.strip(),baseVersion);
  for(UUID admin:jdbc.queryForList("SELECT u.id FROM users u JOIN user_roles r ON r.user_id=u.id WHERE r.role_code='ADMIN' AND u.status='ACTIVE'",UUID.class))notice(org,admin,"Organization request awaiting review",old.get("name")+": "+(kind.equals("CLOSE")?"closure":"profile change")+" requested.","/admin/organizations");
  return jdbc.queryForObject("SELECT r.*,o.name AS organization_name FROM organization_requests r JOIN organizations o ON o.id=r.organization_id WHERE r.id=?",mapper,id);
 }
 static void validateProfile(String name,String slug){if(name==null||name.isBlank()||name.strip().length()>160||slug==null||!slug.matches("[a-z0-9][a-z0-9-]{1,99}"))throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Enter a valid organization name and address");}
 private void profile(UUID org,String name,String slug){validateProfile(name,slug);jdbc.update("UPDATE organizations SET name=?,slug=?,version=version+1 WHERE id=?",name.strip(),slug,org);notifyMembers(org,"Organization details changed to "+name.strip()+" ("+slug+").");}
 @Transactional public void edit(UUID org,String name,String slug,long expected){var old=lock(org);version(old,expected);profile(org,name,slug);}
 private void close(UUID org,String state){
  // A completed closure cannot be reopened. Soft deletion of a closed org is immediate.
  if(Boolean.TRUE.equals(jdbc.queryForObject("SELECT EXISTS(SELECT 1 FROM organization_closures WHERE organization_id=? AND completed_at IS NOT NULL)",Boolean.class,org))){
   jdbc.update("UPDATE organizations SET status=?,version=version+1 WHERE id=?",state,org);
   jdbc.update("UPDATE organization_closures SET target_status=? WHERE organization_id=?",state,org);return;
  }
  jdbc.update("INSERT INTO organization_closures(organization_id,operation_id,target_status) VALUES(?,?,?)",org,UUID.randomUUID(),state);
  jdbc.update("UPDATE organizations SET status='CLOSING',version=version+1 WHERE id=?",org);
  notifyMembers(org,"Organization closure is in progress. New organization operations are closed; unfinished events and tickets will be cancelled before closure completes.");
 }

 @Transactional public void delete(UUID org,long expected){var old=lock(org);version(old,expected);close(org,"DELETED");jdbc.update("UPDATE organization_requests SET status='CANCELLED',review_note='Organization deleted by platform administrator',reviewed_at=CURRENT_TIMESTAMP WHERE organization_id=? AND status='PENDING'",org);}
 @Transactional public void review(UUID id,UUID reviewer,boolean approve,String note){
  var rows=jdbc.queryForList("SELECT organization_id FROM organization_requests WHERE id=?",UUID.class,id);if(rows.isEmpty())throw new ResponseStatusException(HttpStatus.NOT_FOUND,"Request not found");UUID org=rows.getFirst();var old=lock(org);
  var r=jdbc.queryForMap("SELECT * FROM organization_requests WHERE id=? FOR UPDATE",id);if(!r.get("status").equals("PENDING"))throw new ResponseStatusException(HttpStatus.CONFLICT,"Request already reviewed");
  if(approve){version(old,((Number)r.get("base_version")).longValue());organizations.require(org,(UUID)r.get("requester_id"),true);if(r.get("kind").equals("CLOSE"))close(org,"SUSPENDED");else profile(org,(String)r.get("name"),(String)r.get("slug"));}
  jdbc.update("UPDATE organization_requests SET status=?,reviewer_id=?,review_note=?,reviewed_at=CURRENT_TIMESTAMP WHERE id=?",approve?"APPROVED":"REJECTED",reviewer,note.strip(),id);
  notice(org,(UUID)r.get("requester_id"),"Organization request "+(approve?"approved":"rejected"),old.get("name")+": "+r.get("kind")+" request "+(approve?"approved":"rejected")+". "+note.strip(),"/organizations");
 }
}
