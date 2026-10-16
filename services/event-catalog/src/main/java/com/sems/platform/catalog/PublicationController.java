package com.sems.platform.catalog;

import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import java.util.UUID;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.*;
@RestController
public class PublicationController {
    private final PublicationState state;private final PublicationService publication;private final DraftService drafts;
    public PublicationController(PublicationState state,PublicationService publication,DraftService drafts) {this.state=state;this.publication=publication;this.drafts=drafts;}
    public record Publish(@NotNull @Min(0) Long version,@NotNull @Min(1) Long ticketVersion) {}
    public record Prepare(@NotNull UUID owner,@Min(0) long version) {}
    @PostMapping("/api/v1/organizer/events/{id}/publish")
    public ResponseEntity<Event.View> publish(@PathVariable UUID id,@AuthenticationPrincipal Jwt jwt,@Valid @RequestBody Publish body) {
        var owner=UUID.fromString(jwt.getSubject());var op=state.begin(owner,id,body.version(),body.ticketVersion());
        boolean done=publication.advance(op);return ResponseEntity.status(done?200:202).body(drafts.detail(owner,id));
    }
    @GetMapping("/internal/v1/events/{id}")
    public PublicationState.Snapshot owned(@PathVariable UUID id,@RequestParam UUID owner) {return state.inspect(id,owner,false);}
    @PostMapping("/internal/v1/events/{id}/prepare-sales")
    public PublicationState.Snapshot prepare(@PathVariable UUID id,@Valid @RequestBody Prepare body) {return state.prepare(body.owner(),id,body.version());}
    @GetMapping("/internal/v1/events/{id}/member")
    public PublicationState.Snapshot member(@PathVariable UUID id,@RequestParam UUID user) {return state.member(id,user);}
    @GetMapping("/internal/v1/events/{id}/published")
    public PublicationState.Snapshot published(@PathVariable UUID id,@RequestParam(required=false) UUID user) {return state.inspect(id,user,true);}
}
