package com.sems.platform.identity;
import java.util.*;
import org.springframework.http.HttpStatus;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import org.springframework.web.bind.annotation.*;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
@RestController
public class OrganizationController {
 private final OrganizationService service;
 public OrganizationController(OrganizationService service){this.service=service;}
 public record Create(@NotBlank @Size(max=160) String name,@NotBlank @Pattern(regexp="[a-z0-9][a-z0-9-]{1,99}") String slug,@NotBlank @Email String adminEmail){}
 public record PlatformUpdate(@Pattern(regexp="ACTIVE|SUSPENDED") String status,@Email String adminEmail){}
 public record MemberUpdate(@NotNull @Pattern(regexp="ORG_ADMIN|ORGANIZER|MEMBER") String role,@NotNull @Pattern(regexp="ACTIVE|SUSPENDED|REMOVED") String status,@Min(0) long version){}
 public record Invite(@NotBlank @Email String email,@NotNull @Pattern(regexp="ORG_ADMIN|ORGANIZER|MEMBER") String role){}
 public record Accept(@NotBlank @Size(max=128) String token){}
 private UUID user(Jwt jwt){return UUID.fromString(jwt.getSubject());}
 @GetMapping("/api/v1/me/organizations") public List<OrganizationService.Organization> mine(@AuthenticationPrincipal Jwt jwt){return service.mine(user(jwt));}
 @GetMapping("/api/v1/admin/organizations") @PreAuthorize("@platformAccess.isAdmin(authentication)") public OrganizationService.OrganizationPage all(@RequestParam(defaultValue="0") int page,@RequestParam(defaultValue="20") int size,@RequestParam(defaultValue="") String search){return service.all(page,size,search);}
 @PostMapping("/api/v1/admin/organizations") @PreAuthorize("@platformAccess.isAdmin(authentication)") public OrganizationService.Organization create(@Valid @RequestBody Create b){return service.create(b.name(),b.slug(),b.adminEmail());}
 @PatchMapping("/api/v1/admin/organizations/{org}") @PreAuthorize("@platformAccess.isAdmin(authentication)") @ResponseStatus(HttpStatus.NO_CONTENT) public void platform(@PathVariable UUID org,@Valid @RequestBody PlatformUpdate b){service.platformUpdate(org,b.status(),b.adminEmail());}
 @GetMapping("/api/v1/organizations/{org}/members") public OrganizationService.MemberPage members(@PathVariable UUID org,@AuthenticationPrincipal Jwt jwt,@RequestParam(defaultValue="0") int page,@RequestParam(defaultValue="12") int size,@RequestParam(defaultValue="") String search,@RequestParam(defaultValue="") String role,@RequestParam(defaultValue="") String status){return service.members(org,user(jwt),page,size,search,role,status);}
 @PutMapping("/api/v1/organizations/{org}/members/{member}") @ResponseStatus(HttpStatus.NO_CONTENT) public void update(@PathVariable UUID org,@PathVariable UUID member,@AuthenticationPrincipal Jwt jwt,@Valid @RequestBody MemberUpdate b){service.update(org,user(jwt),member,b.role(),b.status(),b.version());}
 @GetMapping("/api/v1/organizations/{org}/invitations") public List<OrganizationService.Invitation> invites(@PathVariable UUID org,@AuthenticationPrincipal Jwt jwt){return service.invitations(org,user(jwt));}
 @PostMapping("/api/v1/organizations/{org}/invitations") public OrganizationService.CreatedInvitation invite(@PathVariable UUID org,@AuthenticationPrincipal Jwt jwt,@Valid @RequestBody Invite b){return service.invite(org,user(jwt),b.email(),b.role());}
 @DeleteMapping("/api/v1/organizations/{org}/invitations/{id}") @ResponseStatus(HttpStatus.NO_CONTENT) public void revoke(@PathVariable UUID org,@PathVariable UUID id,@AuthenticationPrincipal Jwt jwt){service.revoke(org,user(jwt),id);}
 @PostMapping("/api/v1/invitations/accept") @ResponseStatus(HttpStatus.NO_CONTENT) public void accept(@AuthenticationPrincipal Jwt jwt,@Valid @RequestBody Accept b){service.accept(user(jwt),b.token());}
 public record Lookup(@NotNull @Size(max=100) List<@NotNull UUID> ids){}
 @PostMapping("/internal/v1/organizations/lookup") public List<OrganizationService.Organization> lookup(@Valid @RequestBody Lookup request){return service.active(request.ids());}
 @GetMapping("/internal/v1/users/{user}/organizations") public List<OrganizationService.Organization> internal(@PathVariable UUID user){return service.mine(user);}

 @GetMapping("/api/v1/me/invitations") public OrganizationService.InvitationInbox inbox(@AuthenticationPrincipal Jwt jwt,@RequestParam(defaultValue="0") int page){return service.inbox(user(jwt),page);}
 @GetMapping("/api/v1/me/invitations/pending-count") public long count(@AuthenticationPrincipal Jwt jwt){return service.pendingInvitations(user(jwt));}
 @PostMapping("/api/v1/me/invitations/{id}/accept") @ResponseStatus(HttpStatus.NO_CONTENT) public void acceptId(@AuthenticationPrincipal Jwt jwt,@PathVariable UUID id){service.respond(user(jwt),id,true);}
 @PostMapping("/api/v1/me/invitations/{id}/decline") @ResponseStatus(HttpStatus.NO_CONTENT) public void decline(@AuthenticationPrincipal Jwt jwt,@PathVariable UUID id){service.respond(user(jwt),id,false);}
}
