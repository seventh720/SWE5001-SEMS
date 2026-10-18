package com.sems.platform.identity;

import java.time.Instant;
import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/api/v1/me/membership-notifications")
public class MembershipNotificationController {
 private final JdbcTemplate jdbc;
 public MembershipNotificationController(JdbcTemplate jdbc){this.jdbc=jdbc;}
 public record Notice(UUID id,String kind,String title,String message,String link,Instant createdAt,Instant readAt){}
 public record Page(List<Notice> items,long unreadCount,boolean hasMore){}
 private UUID user(Jwt jwt){return UUID.fromString(jwt.getSubject());}
 @GetMapping("/unread-count") public long unread(@AuthenticationPrincipal Jwt jwt){return jdbc.queryForObject("SELECT count(*) FROM membership_notifications WHERE user_id=? AND read_at IS NULL",Long.class,user(jwt));}
 @GetMapping public Page list(@AuthenticationPrincipal Jwt jwt,@RequestParam(defaultValue="0") int page){
  if(page<0||page>100000)throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Invalid page");
  var rows=jdbc.query("SELECT * FROM membership_notifications WHERE user_id=? ORDER BY created_at DESC,id DESC LIMIT 21 OFFSET ?",(r,n)->new Notice(r.getObject("id",UUID.class),r.getString("kind"),r.getString("title"),r.getString("message"),r.getString("link")==null?"/organizations?organizationId="+r.getObject("organization_id",UUID.class):r.getString("link"),r.getTimestamp("created_at").toInstant(),r.getTimestamp("read_at")==null?null:r.getTimestamp("read_at").toInstant()),user(jwt),page*20L);
  return new Page(rows.stream().limit(20).toList(),unread(jwt),rows.size()>20);
 }
 @PostMapping("/{id}/read") @ResponseStatus(HttpStatus.NO_CONTENT) public void read(@AuthenticationPrincipal Jwt jwt,@PathVariable UUID id){
  if(jdbc.update("UPDATE membership_notifications SET read_at=COALESCE(read_at,CURRENT_TIMESTAMP) WHERE id=? AND user_id=?",id,user(jwt))==0)throw new ResponseStatusException(HttpStatus.NOT_FOUND,"Notification not found");
 }
 @PostMapping("/read-all") @ResponseStatus(HttpStatus.NO_CONTENT) public void readAll(@AuthenticationPrincipal Jwt jwt){jdbc.update("UPDATE membership_notifications SET read_at=CURRENT_TIMESTAMP WHERE user_id=? AND read_at IS NULL",user(jwt));}
}
