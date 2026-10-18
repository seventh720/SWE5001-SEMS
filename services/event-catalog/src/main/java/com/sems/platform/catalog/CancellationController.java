package com.sems.platform.catalog;
import java.util.UUID;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.*;
@RestController
public class CancellationController {
 private final CancellationState state;private final CancellationService service;private final DraftService drafts;
 public CancellationController(CancellationState state,CancellationService service,DraftService drafts){this.state=state;this.service=service;this.drafts=drafts;}
 public record Request(@NotNull @Min(0) Long version,@NotBlank @Size(max=500) String reason){}
 @PostMapping("/api/v1/organizer/events/{id}/cancel")
 public ResponseEntity<Event.View> cancel(@PathVariable UUID id,@AuthenticationPrincipal Jwt jwt,@Valid @RequestBody Request request){
  var actor=UUID.fromString(jwt.getSubject());var op=state.begin(actor,id,request.version(),request.reason());
  boolean done=service.advance(op);return ResponseEntity.status(done?200:202).body(drafts.detail(actor,id));
 }
}
