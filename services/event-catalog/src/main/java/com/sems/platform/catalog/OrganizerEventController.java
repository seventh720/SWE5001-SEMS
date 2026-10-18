package com.sems.platform.catalog;
import jakarta.validation.Valid;
import java.net.URI;
import java.util.UUID;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.*;
@RestController @RequestMapping("/api/v1/organizer/events")

public class OrganizerEventController {
 private final DraftService drafts;private final RevisionService revisions;
 public OrganizerEventController(DraftService drafts,RevisionService revisions){this.drafts=drafts;this.revisions=revisions;}
 @GetMapping public DraftService.EventPage list(@AuthenticationPrincipal Jwt jwt,@RequestParam UUID organizationId,@RequestParam(defaultValue="0") int page,@RequestParam(defaultValue="10") int size,@RequestParam(defaultValue="") String keyword){return drafts.list(UUID.fromString(jwt.getSubject()),organizationId,page,size,keyword);}
 @GetMapping("/{id}") public Event.View detail(@AuthenticationPrincipal Jwt jwt,@PathVariable UUID id){return drafts.detail(UUID.fromString(jwt.getSubject()),id);}
 @PostMapping public ResponseEntity<Event.View> create(@AuthenticationPrincipal Jwt jwt,@Valid @RequestBody Draft body){
  var event=drafts.create(UUID.fromString(jwt.getSubject()),body);return ResponseEntity.created(URI.create("/api/v1/organizer/events/"+event.id())).body(event);
 }
 @PutMapping("/{id}/revision") public Event.View revise(@AuthenticationPrincipal Jwt jwt,@PathVariable UUID id,@Valid @RequestBody Draft body){return revisions.update(UUID.fromString(jwt.getSubject()),id,body);}
 @PatchMapping("/{id}/presentation") public Event.View presentation(@AuthenticationPrincipal Jwt jwt,@PathVariable UUID id,@Valid @RequestBody PresentationUpdate body){return drafts.presentation(UUID.fromString(jwt.getSubject()),id,body);}
 @PutMapping("/{id}") public Event.View update(@AuthenticationPrincipal Jwt jwt,@PathVariable UUID id,@Valid @RequestBody Draft body){return drafts.update(UUID.fromString(jwt.getSubject()),id,body);}
}
