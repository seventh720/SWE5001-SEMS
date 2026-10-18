package com.sems.platform.admission;
import java.util.*;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import org.springframework.web.bind.annotation.*;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
@RestController
public class CheckInController {
 private final CheckInService service;private final CatalogClient catalog;private final OrganizationAccess access;
 public CheckInController(CheckInService service,CatalogClient catalog,OrganizationAccess access){this.service=service;this.catalog=catalog;this.access=access;}
 private UUID user(Jwt jwt){return UUID.fromString(jwt.getSubject());}
 public record Assign(@NotNull UUID userId,boolean active){}
 public record Check(@NotBlank @Size(max=128) String credential){}
 @GetMapping("/api/v1/organizer/events/{id}/staff") public List<CheckInService.Assignment> assignments(@PathVariable UUID id,@AuthenticationPrincipal Jwt jwt){catalog.owned(id,user(jwt));return service.assignments(id);}
 @PutMapping("/api/v1/organizer/events/{id}/staff") @ResponseStatus(org.springframework.http.HttpStatus.NO_CONTENT) public void assign(@PathVariable UUID id,@AuthenticationPrincipal Jwt jwt,@Valid @RequestBody Assign b){var event=catalog.owned(id,user(jwt));if(b.active())access.require(event.organizationId(),b.userId(),false);service.assign(id,b.userId(),user(jwt),b.active());}
 @GetMapping("/api/v1/me/staff-assignments") public CheckInService.TaskPage tasks(@AuthenticationPrincipal Jwt jwt,@RequestParam(defaultValue="0") int page,@RequestParam(defaultValue="20") int size){
  var orgs=access.memberships(user(jwt)).stream().map(OrganizationAccess.Membership::id).toList();
  var result=service.tasks(user(jwt),orgs,page,size);
  var details=catalog.details(result.items().stream().map(CheckInService.Task::eventId).toList());
  var items=result.items().stream().map(t->{var e=details.get(t.eventId());if(e==null)throw new org.springframework.web.server.ResponseStatusException(org.springframework.http.HttpStatus.SERVICE_UNAVAILABLE,"Event details unavailable; retry later");return new CheckInService.Task(t.eventId(),t.organizationId(),e.title(),e.startsAt(),e.endsAt());}).toList();
  return new CheckInService.TaskPage(items,page,size,result.totalElements(),result.totalPages());
 }
 @PostMapping("/api/v1/events/{id}/check-ins") public CheckInService.Result check(@PathVariable UUID id,@AuthenticationPrincipal Jwt jwt,@Valid @RequestBody Check b){access.require(service.organization(id),user(jwt),false);return service.check(id,user(jwt),b.credential());}
 @GetMapping("/api/v1/organizer/events/{id}/summary") public CheckInService.Summary summary(@PathVariable UUID id,@AuthenticationPrincipal Jwt jwt){catalog.owned(id,user(jwt));return service.summary(id);}
}
