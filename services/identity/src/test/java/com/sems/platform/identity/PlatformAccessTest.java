package com.sems.platform.identity;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
class PlatformAccessTest {
 @Test void sameTokenImmediatelyLosesAdminWhenDatabaseRoleIsRevoked(){
  var jdbc=mock(JdbcTemplate.class);var user=UUID.randomUUID();
  var auth=new UsernamePasswordAuthenticationToken(user.toString(),"",List.of(new SimpleGrantedAuthority("ROLE_ADMIN")));
  when(jdbc.queryForObject(anyString(),eq(Boolean.class),eq(user))).thenReturn(true,false);
  var access=new PlatformAccess(jdbc);assertTrue(access.isAdmin(auth));assertFalse(access.isAdmin(auth));
  verify(jdbc,times(2)).queryForObject(anyString(),eq(Boolean.class),eq(user));
 }
 @Test void attendeeClaimCannotBecomeAdminWithoutANewToken(){
  var jdbc=mock(JdbcTemplate.class);var auth=new UsernamePasswordAuthenticationToken(UUID.randomUUID().toString(),"",List.of(new SimpleGrantedAuthority("ROLE_ATTENDEE")));
  assertFalse(new PlatformAccess(jdbc).isAdmin(auth));verifyNoInteractions(jdbc);
 }
}
