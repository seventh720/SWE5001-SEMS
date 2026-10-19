package com.sems.platform.catalog;

import java.time.Instant;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.*;
import org.springframework.web.server.ResponseStatusException;

@RestController
public class OrganizationOverviewController {
 private final OrganizationAccess access;private final JdbcTemplate jdbc;private final RestClient admission;
 public OrganizationOverviewController(OrganizationAccess access,JdbcTemplate jdbc,RestClient admission){this.access=access;this.jdbc=jdbc;this.admission=admission;}
 public record Attendance(long validTickets,long checkedIn){}
 public record Overview(long totalEvents,long validTickets,long checkedIn,Instant updatedAt){}
 @GetMapping("/api/v1/organizer/organizations/{id}/overview")
 public Overview overview(@PathVariable UUID id,@AuthenticationPrincipal Jwt jwt){
  var membership=access.require(id,UUID.fromString(jwt.getSubject()),true);
  if(!membership.role().equals("ORG_ADMIN"))throw new ResponseStatusException(HttpStatus.FORBIDDEN,"Organization administrator access required");
  var total=jdbc.queryForObject("SELECT count(*) FROM events WHERE organization_id=?",Long.class,id);
  try{
   var tickets=admission.get().uri("/internal/v1/organizations/{id}/attendance-summary",id).retrieve().body(Attendance.class);
   if(tickets==null)throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE,"Organization overview unavailable; retry later");
   return new Overview(total,tickets.validTickets(),tickets.checkedIn(),Instant.now());
  }catch(RestClientException e){throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE,"Organization overview unavailable; retry later");}
 }
}
