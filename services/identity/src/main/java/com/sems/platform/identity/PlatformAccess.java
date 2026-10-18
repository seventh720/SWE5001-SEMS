package com.sems.platform.identity;
import java.util.UUID;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.core.Authentication;
import org.springframework.stereotype.Component;
@Component("platformAccess")
public class PlatformAccess {
 private final JdbcTemplate jdbc;
 public PlatformAccess(JdbcTemplate jdbc){this.jdbc=jdbc;}
 public boolean isAdmin(Authentication authentication){
  if(authentication==null||!authentication.isAuthenticated()||authentication.getAuthorities().stream().noneMatch(a->a.getAuthority().equals("ROLE_ADMIN")))return false;
  UUID user;try{user=UUID.fromString(authentication.getName());}catch(IllegalArgumentException e){return false;}
  return Boolean.TRUE.equals(jdbc.queryForObject("SELECT EXISTS(SELECT 1 FROM users u JOIN user_roles r ON r.user_id=u.id WHERE u.id=? AND u.status='ACTIVE' AND r.role_code='ADMIN')",Boolean.class,user));
 }
}
