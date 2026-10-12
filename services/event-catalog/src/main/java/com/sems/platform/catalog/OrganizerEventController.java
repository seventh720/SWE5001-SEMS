package com.sems.platform.catalog;
import jakarta.validation.Valid;
import java.net.URI;
import java.util.UUID;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.*;
@RestController @RequestMapping("/api/v1/organizer/events")
@PreAuthorize("hasAnyRole('ORGANIZER','ADMIN')")
public class OrganizerEventController {
 private final DraftService drafts;
 public OrganizerEventController(DraftService drafts){this.drafts=drafts;}
 @GetMapping public DraftService.EventPage list(@AuthenticationPrincipal Jwt jwt,@RequestParam(defaultValue="0") int page,@RequestParam(defaultValue="10") int size){return drafts.list(UUID.fromString(jwt.getSubject()),page,size);}
 @GetMapping("/{id}") public Event.View detail(@AuthenticationPrincipal Jwt jwt,@PathVariable UUID id){return drafts.detail(UUID.fromString(jwt.getSubject()),id);}
 @PostMapping public ResponseEntity<Event.View> create(@AuthenticationPrincipal Jwt jwt,@Valid @RequestBody Draft body){
  var event=drafts.create(UUID.fromString(jwt.getSubject()),body);return ResponseEntity.created(URI.create("/api/v1/organizer/events/"+event.id())).body(event);
 }
 @PutMapping("/{id}") public Event.View update(@AuthenticationPrincipal Jwt jwt,@PathVariable UUID id,@Valid @RequestBody Draft body){return drafts.update(UUID.fromString(jwt.getSubject()),id,body);}
}
