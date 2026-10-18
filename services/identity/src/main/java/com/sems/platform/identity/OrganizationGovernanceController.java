package com.sems.platform.identity;
import java.util.*;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import org.springframework.web.bind.annotation.*;
import org.springframework.http.HttpStatus;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
@RestController
public class OrganizationGovernanceController {
 private final OrganizationGovernanceService service;
 public OrganizationGovernanceController(OrganizationGovernanceService service){this.service=service;}
 public record Profile(@NotBlank @Size(max=160) String name,@NotBlank @Pattern(regexp="[a-z0-9][a-z0-9-]{1,99}") String slug,@Min(0) long version){}
 public record Submit(@NotNull @Pattern(regexp="UPDATE|CLOSE") String kind,@Size(max=160) String name,@Size(max=100) String slug,@NotBlank @Size(max=2000) String reason,@Min(0) long version){}
 public record Review(boolean approve,@NotBlank @Size(max=2000) String note){}
 @PutMapping("/api/v1/admin/organizations/{org}/profile") @PreAuthorize("@platformAccess.isAdmin(authentication)") @ResponseStatus(HttpStatus.NO_CONTENT) public void edit(@PathVariable UUID org,@Valid @RequestBody Profile b){service.edit(org,b.name(),b.slug(),b.version());}
 @DeleteMapping("/api/v1/admin/organizations/{org}") @PreAuthorize("@platformAccess.isAdmin(authentication)") @ResponseStatus(HttpStatus.NO_CONTENT) public void delete(@PathVariable UUID org,@RequestParam long version){service.delete(org,version);}
 @PostMapping("/api/v1/organizations/{org}/requests") public OrganizationGovernanceService.Request submit(@PathVariable UUID org,@AuthenticationPrincipal Jwt jwt,@Valid @RequestBody Submit b){return service.submit(org,UUID.fromString(jwt.getSubject()),b.kind(),b.name(),b.slug(),b.reason(),b.version());}
 @GetMapping("/api/v1/organizations/{org}/requests") public OrganizationGovernanceService.RequestPage requests(@PathVariable UUID org,@AuthenticationPrincipal Jwt jwt,@RequestParam(defaultValue="0") int page,@RequestParam(defaultValue="20") int size){return service.requests(org,UUID.fromString(jwt.getSubject()),page,size);}
 @GetMapping("/api/v1/admin/organizations/requests") @PreAuthorize("@platformAccess.isAdmin(authentication)") public OrganizationGovernanceService.RequestPage queue(@RequestParam(defaultValue="0") int page,@RequestParam(defaultValue="20") int size){return service.reviewQueue(page,size);}
 @PostMapping("/api/v1/admin/organizations/requests/{id}/review") @PreAuthorize("@platformAccess.isAdmin(authentication)") @ResponseStatus(HttpStatus.NO_CONTENT) public void review(@PathVariable UUID id,@AuthenticationPrincipal Jwt jwt,@Valid @RequestBody Review b){service.review(id,UUID.fromString(jwt.getSubject()),b.approve(),b.note());}
}
