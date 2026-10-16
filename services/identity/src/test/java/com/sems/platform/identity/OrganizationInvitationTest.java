package com.sems.platform.identity;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.server.ResponseStatusException;
class OrganizationInvitationTest {
 @Test void unregisteredEmailHasSpecificGuidance(){
  var jdbc=mock(JdbcTemplate.class);
  when(jdbc.queryForList("SELECT id,status FROM users WHERE lower(email)=?","new@example.com")).thenReturn(List.of());
  var error=assertThrows(ResponseStatusException.class,()->new OrganizationService(jdbc).create("Org","org","new@example.com"));
  assertEquals(404,error.getStatusCode().value());assertTrue(error.getReason().contains("not registered"));
 }
 @Test void inactiveAccountIsNotReportedAsUnregistered(){
  var jdbc=mock(JdbcTemplate.class);
  when(jdbc.queryForList("SELECT id,status FROM users WHERE lower(email)=?","old@example.com")).thenReturn(List.of(Map.of("id",UUID.randomUUID(),"status","SUSPENDED")));
  var error=assertThrows(ResponseStatusException.class,()->new OrganizationService(jdbc).create("Org","org","old@example.com"));
  assertEquals(409,error.getStatusCode().value());assertTrue(error.getReason().contains("inactive"));
 }
 @Test void existingMemberIsRejectedWithoutCreatingAnInvitation(){
  var jdbc=mock(JdbcTemplate.class);var org=UUID.randomUUID();var actor=UUID.randomUUID();var user=UUID.randomUUID();
  when(jdbc.queryForList("SELECT id FROM organizations WHERE id=? FOR UPDATE",org)).thenReturn(List.of(Map.of("id",org)));
  when(jdbc.queryForList("SELECT id,status FROM users WHERE lower(email)=?","member@example.com")).thenReturn(List.of(Map.of("id",user,"status","ACTIVE")));
  when(jdbc.queryForObject("SELECT EXISTS(SELECT 1 FROM organization_memberships WHERE organization_id=? AND user_id=? AND status IN ('ACTIVE','SUSPENDED'))",Boolean.class,org,user)).thenReturn(true);
  var service=spy(new OrganizationService(jdbc));doNothing().when(service).require(org,actor,true);
  var error=assertThrows(ResponseStatusException.class,()->service.invite(org,actor,"member@example.com","MEMBER"));
  assertEquals(409,error.getStatusCode().value());assertTrue(error.getReason().contains("already in this organization"));
  verify(jdbc,never()).update(anyString(),any(Object[].class));
 }
}
