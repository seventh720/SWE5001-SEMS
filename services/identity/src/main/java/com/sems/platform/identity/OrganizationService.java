package com.sems.platform.identity;

import java.util.*;
import java.time.*;
import java.nio.charset.StandardCharsets;
import java.security.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.annotation.Isolation;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

@Service
public class OrganizationService {
 private final JdbcTemplate jdbc;
 public OrganizationService(JdbcTemplate jdbc){this.jdbc=jdbc;}
 public record Organization(UUID id,String name,String slug,String status,String role,long version,boolean closureRequested){}
 public record Member(UUID userId,String username,String email,String role,String status,long version){}
 public record Invitation(UUID id,UUID userId,String email,String role,String status,Instant expiresAt){}
 public record CreatedInvitation(UUID id,String token,Instant expiresAt){}
 public List<Organization> mine(UUID user){return jdbc.query("SELECT o.*,m.role FROM organizations o JOIN organization_memberships m ON m.organization_id=o.id JOIN users u ON u.id=m.user_id WHERE m.user_id=? AND m.status='ACTIVE' AND o.status='ACTIVE' AND u.status='ACTIVE' ORDER BY o.name,o.id",(r,n)->new Organization(r.getObject("id",UUID.class),r.getString("name"),r.getString("slug"),r.getString("status"),r.getString("role"),r.getLong("version"),false),user);}
 public record OrganizationPage(List<Organization> items,int page,int size,long totalElements,long totalPages){}
 @Transactional(readOnly=true,isolation=Isolation.REPEATABLE_READ)
 public OrganizationPage all(int page,int size,String search){
  if(page<0||page>100000||size<1||size>50||search.length()>200)throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Invalid pagination or search");
  String filter=" FROM organizations o WHERE status<>'DELETED' AND (strpos(lower(name),?)>0 OR strpos(lower(slug),?)>0)";
  String query=search.strip().toLowerCase(Locale.ROOT);
  long total=jdbc.queryForObject("SELECT count(*)"+filter,Long.class,query,query);
  var items=jdbc.query("SELECT o.*,EXISTS(SELECT 1 FROM organization_closures c WHERE c.organization_id=o.id) AS closure_requested"+filter+" ORDER BY name,id LIMIT ? OFFSET ?",(r,n)->new Organization(r.getObject("id",UUID.class),r.getString("name"),r.getString("slug"),r.getString("status"),null,r.getLong("version"),r.getBoolean("closure_requested")),query,query,size,(long)page*size);
  return new OrganizationPage(items,page,size,total,(total+size-1)/size);
 }
 public List<Organization> active(List<UUID> ids){
  if(ids.isEmpty())return List.of();
  return jdbc.query("SELECT * FROM organizations WHERE status='ACTIVE' AND id IN ("+String.join(",",Collections.nCopies(ids.size(),"?"))+")",(r,n)->new Organization(r.getObject("id",UUID.class),r.getString("name"),r.getString("slug"),r.getString("status"),null,r.getLong("version"),false),ids.toArray());
 }
 public void require(UUID org,UUID user,boolean admin){var found=mine(user).stream().filter(o->o.id().equals(org)).findFirst();if(found.isEmpty() || (admin&&!found.get().role().equals("ORG_ADMIN")))throw new ResponseStatusException(HttpStatus.FORBIDDEN,"Organization access denied");}
 private void lock(UUID org){if(jdbc.queryForList("SELECT id FROM organizations WHERE id=? AND status<>'DELETED' FOR UPDATE",org).isEmpty())throw new ResponseStatusException(HttpStatus.NOT_FOUND,"Organization not found");}
 private UUID account(String email){var rows=jdbc.queryForList("SELECT id,status FROM users WHERE lower(email)=?",email.strip().toLowerCase(Locale.ROOT));if(rows.isEmpty())throw new ResponseStatusException(HttpStatus.NOT_FOUND,"This email is not registered. Ask the person to create an account first, then invite them again.");if(!rows.getFirst().get("status").equals("ACTIVE"))throw new ResponseStatusException(HttpStatus.CONFLICT,"This account is inactive. It must be reactivated before joining an organization.");return (UUID)rows.getFirst().get("id");}
 @Transactional public Organization create(String name,String slug,String email){UUID user=account(email),id=UUID.randomUUID();if(Boolean.TRUE.equals(jdbc.queryForObject("SELECT EXISTS(SELECT 1 FROM organizations WHERE slug=?)",Boolean.class,slug)))throw new ResponseStatusException(HttpStatus.CONFLICT,"Organization address is already used");jdbc.update("INSERT INTO organizations(id,name,slug) VALUES(?,?,?)",id,name.strip(),slug);jdbc.update("INSERT INTO organization_memberships(organization_id,user_id,role,status) VALUES(?,?,'ORG_ADMIN','ACTIVE')",id,user);return new Organization(id,name.strip(),slug,"ACTIVE","ORG_ADMIN",0,false);}
 @Transactional public void platformUpdate(UUID org,String status,String adminEmail){lock(org);if(Boolean.TRUE.equals(jdbc.queryForObject("SELECT EXISTS(SELECT 1 FROM organization_closures WHERE organization_id=?)",Boolean.class,org)))throw new ResponseStatusException(HttpStatus.CONFLICT,"A closing or closed organization cannot be reactivated or reassigned");if(status!=null)jdbc.update("UPDATE organizations SET status=?,version=version+1 WHERE id=?",status,org);if(adminEmail!=null&&!adminEmail.isBlank())jdbc.update("INSERT INTO organization_memberships(organization_id,user_id,role,status) VALUES(?,?,'ORG_ADMIN','ACTIVE') ON CONFLICT(organization_id,user_id) DO UPDATE SET role='ORG_ADMIN',status='ACTIVE',version=organization_memberships.version+1",org,account(adminEmail));}
 public record MemberPage(List<Member> items,int page,int size,long totalElements,long totalMembers,long totalPages){}
 @Transactional(readOnly=true,isolation=Isolation.REPEATABLE_READ)
 public MemberPage members(UUID org,UUID actor,int page,int size,String search){
  require(org,actor,false);
  if(page<0||size<1||size>50||(long)page*size>Integer.MAX_VALUE||search.length()>200)throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Invalid member search or pagination");
  String query=search.strip().toLowerCase(Locale.ROOT);
  String filter=" FROM organization_memberships m JOIN users u ON u.id=m.user_id WHERE m.organization_id=? AND (strpos(lower(u.username),?)>0 OR strpos(lower(u.email),?)>0)";
  long total=jdbc.queryForObject("SELECT count(*)"+filter,Long.class,org,query,query);
  long all=jdbc.queryForObject("SELECT count(*) FROM organization_memberships WHERE organization_id=?",Long.class,org);
  var items=jdbc.query("SELECT m.*,u.username,u.email"+filter+" ORDER BY lower(u.username),m.user_id LIMIT ? OFFSET ?",(r,n)->new Member(r.getObject("user_id",UUID.class),r.getString("username"),r.getString("email"),r.getString("role"),r.getString("status"),r.getLong("version")),org,query,query,size,(long)page*size);
  return new MemberPage(items,page,size,total,all,(total+size-1)/size);
 }

 @Transactional public void update(UUID org,UUID actor,UUID user,String role,String status,long version){lock(org);require(org,actor,true);var rows=jdbc.queryForList("SELECT * FROM organization_memberships WHERE organization_id=? AND user_id=?",org,user);if(rows.isEmpty())throw new ResponseStatusException(HttpStatus.NOT_FOUND,"Member not found");var old=rows.getFirst();if(((Number)old.get("version")).longValue()!=version)throw new ResponseStatusException(HttpStatus.CONFLICT,"Membership changed; reload");if(old.get("role").equals("ORG_ADMIN")&&old.get("status").equals("ACTIVE")&&(!role.equals("ORG_ADMIN")||!status.equals("ACTIVE"))&&jdbc.queryForObject("SELECT count(*) FROM organization_memberships m JOIN users u ON u.id=m.user_id WHERE m.organization_id=? AND m.role='ORG_ADMIN' AND m.status='ACTIVE' AND u.status='ACTIVE'",Long.class,org)<=1)throw new ResponseStatusException(HttpStatus.CONFLICT,"Keep at least one active organization administrator");jdbc.update("UPDATE organization_memberships SET role=?,status=?,version=version+1 WHERE organization_id=? AND user_id=?",role,status,org,user);}
 public List<Invitation> invitations(UUID org,UUID actor){require(org,actor,true);return jdbc.query("SELECT i.*,u.email FROM organization_invitations i JOIN users u ON u.id=i.user_id WHERE organization_id=? ORDER BY created_at DESC",(r,n)->new Invitation(r.getObject("id",UUID.class),r.getObject("user_id",UUID.class),r.getString("email"),r.getString("role"),r.getString("status"),r.getTimestamp("expires_at").toInstant()),org);}
 static String digest(String token){try{return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(token.getBytes(StandardCharsets.UTF_8)));}catch(NoSuchAlgorithmException e){throw new IllegalStateException(e);}}
 @Transactional public CreatedInvitation invite(UUID org,UUID actor,String email,String role){lock(org);require(org,actor,true);UUID user=account(email);if(Boolean.TRUE.equals(jdbc.queryForObject("SELECT EXISTS(SELECT 1 FROM organization_memberships WHERE organization_id=? AND user_id=? AND status IN ('ACTIVE','SUSPENDED'))",Boolean.class,org,user)))throw new ResponseStatusException(HttpStatus.CONFLICT,"This person is already in this organization. Manage their role or status in Members.");if(Boolean.TRUE.equals(jdbc.queryForObject("SELECT EXISTS(SELECT 1 FROM organization_invitations WHERE organization_id=? AND user_id=? AND status='PENDING' AND expires_at>CURRENT_TIMESTAMP)",Boolean.class,org,user)))throw new ResponseStatusException(HttpStatus.CONFLICT,"An invitation is already waiting in this person's notifications. Revoke it before sending a replacement.");jdbc.update("UPDATE organization_invitations SET status='REVOKED' WHERE organization_id=? AND user_id=? AND status='PENDING'",org,user);byte[] bytes=new byte[32];new SecureRandom().nextBytes(bytes);String token=HexFormat.of().formatHex(bytes);UUID id=UUID.randomUUID();Instant expires=Instant.now().plus(Duration.ofDays(7));jdbc.update("INSERT INTO organization_invitations(id,organization_id,user_id,role,token_hash,expires_at) VALUES(?,?,?,?,?,?)",id,org,user,role,digest(token),java.sql.Timestamp.from(expires));return new CreatedInvitation(id,token,expires);}
 @Transactional public void revoke(UUID org,UUID actor,UUID id){lock(org);require(org,actor,true);jdbc.update("UPDATE organization_invitations SET status='REVOKED' WHERE id=? AND organization_id=? AND status='PENDING'",id,org);}
 @Transactional public void accept(UUID user,String token){var rows=jdbc.queryForList("SELECT * FROM organization_invitations WHERE token_hash=?",digest(token));if(rows.isEmpty())throw new ResponseStatusException(HttpStatus.NOT_FOUND,"Invitation not found");acceptInvitation(user,(UUID)rows.getFirst().get("id"));}
 private void acceptInvitation(UUID user,UUID id){var invite=jdbc.queryForMap("SELECT * FROM organization_invitations WHERE id=?",id);UUID org=(UUID)invite.get("organization_id");lock(org);invite=jdbc.queryForMap("SELECT * FROM organization_invitations WHERE id=? FOR UPDATE",invite.get("id"));if(!user.equals(invite.get("user_id")))throw new ResponseStatusException(HttpStatus.FORBIDDEN,"Sign in with the invited account");if(!Boolean.TRUE.equals(jdbc.queryForObject("SELECT EXISTS(SELECT 1 FROM users u,organizations o WHERE u.id=? AND u.status='ACTIVE' AND o.id=? AND o.status='ACTIVE')",Boolean.class,user,org)))throw new ResponseStatusException(HttpStatus.FORBIDDEN,"Account or organization is inactive");if(invite.get("status").equals("ACCEPTED"))return;if(!invite.get("status").equals("PENDING")||!((java.sql.Timestamp)invite.get("expires_at")).toInstant().isAfter(Instant.now()))throw new ResponseStatusException(HttpStatus.CONFLICT,"Invitation expired or revoked");if(Boolean.TRUE.equals(jdbc.queryForObject("SELECT EXISTS(SELECT 1 FROM organization_memberships WHERE organization_id=? AND user_id=? AND status='ACTIVE')",Boolean.class,org,user)))throw new ResponseStatusException(HttpStatus.CONFLICT,"Membership already active; ask an administrator to change roles");jdbc.update("INSERT INTO organization_memberships(organization_id,user_id,role,status) VALUES(?,?,?,'ACTIVE') ON CONFLICT(organization_id,user_id) DO UPDATE SET role=EXCLUDED.role,status='ACTIVE',version=organization_memberships.version+1",org,user,invite.get("role"));jdbc.update("UPDATE organization_invitations SET status='ACCEPTED' WHERE id=?",invite.get("id"));}

 public record InboxInvitation(UUID id,UUID organizationId,String organizationName,String role,String status,Instant expiresAt,Instant createdAt){}
 public record InvitationInbox(List<InboxInvitation> items,long pendingCount,boolean hasMore){}
 public long pendingInvitations(UUID user){return jdbc.queryForObject("SELECT count(*) FROM organization_invitations i JOIN organizations o ON o.id=i.organization_id WHERE i.user_id=? AND i.status='PENDING' AND i.expires_at>CURRENT_TIMESTAMP AND o.status='ACTIVE'",Long.class,user);}
 public InvitationInbox inbox(UUID user,int page){
  if(page<0||page>100000)throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Invalid page");
  var items=jdbc.query("SELECT i.*,o.name,CASE WHEN i.status='PENDING' AND i.expires_at<=CURRENT_TIMESTAMP THEN 'EXPIRED' WHEN i.status='PENDING' AND o.status<>'ACTIVE' THEN 'UNAVAILABLE' ELSE i.status END AS display_status FROM organization_invitations i JOIN organizations o ON o.id=i.organization_id WHERE i.user_id=? ORDER BY CASE WHEN i.status='PENDING' AND i.expires_at>CURRENT_TIMESTAMP AND o.status='ACTIVE' THEN 0 ELSE 1 END,i.created_at DESC,i.id DESC LIMIT 21 OFFSET ?",(r,n)->new InboxInvitation(r.getObject("id",UUID.class),r.getObject("organization_id",UUID.class),r.getString("name"),r.getString("role"),r.getString("display_status"),r.getTimestamp("expires_at").toInstant(),r.getTimestamp("created_at").toInstant()),user,page*20L);
  return new InvitationInbox(items.stream().limit(20).toList(),pendingInvitations(user),items.size()>20);
 }
 @Transactional public void respond(UUID user,UUID id,boolean accept){
  var rows=jdbc.queryForList("SELECT * FROM organization_invitations WHERE id=? AND user_id=?",id,user);
  if(rows.isEmpty())throw new ResponseStatusException(HttpStatus.NOT_FOUND,"Invitation not found");
  if(accept){acceptInvitation(user,id);return;}
  lock((UUID)rows.getFirst().get("organization_id"));
  var current=jdbc.queryForMap("SELECT * FROM organization_invitations WHERE id=? FOR UPDATE",id);
  if(current.get("status").equals("DECLINED"))return;
  if(!current.get("status").equals("PENDING")||!((java.sql.Timestamp)current.get("expires_at")).toInstant().isAfter(Instant.now()))throw new ResponseStatusException(HttpStatus.CONFLICT,"Invitation is no longer pending");
  jdbc.update("UPDATE organization_invitations SET status='DECLINED' WHERE id=?",id);
 }
}
