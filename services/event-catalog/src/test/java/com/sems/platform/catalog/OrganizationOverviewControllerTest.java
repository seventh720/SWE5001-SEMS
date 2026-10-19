package com.sems.platform.catalog;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.client.RestClient;
import org.springframework.web.server.ResponseStatusException;
class OrganizationOverviewControllerTest {
 @Test void organizerCannotReadAdminOverview(){
  var access=mock(OrganizationAccess.class);var jdbc=mock(JdbcTemplate.class);var admission=mock(RestClient.class);
  var organization=UUID.randomUUID();var user=UUID.randomUUID();
  when(access.require(organization,user,true)).thenReturn(new OrganizationAccess.Membership(organization,"Org","org","ACTIVE","ORGANIZER"));
  var jwt=Jwt.withTokenValue("token").header("alg","RS256").subject(user.toString()).build();
  var controller=new OrganizationOverviewController(access,jdbc,admission);
  assertEquals(403,assertThrows(ResponseStatusException.class,()->controller.overview(organization,jwt)).getStatusCode().value());
  verifyNoInteractions(jdbc,admission);
 }
}
