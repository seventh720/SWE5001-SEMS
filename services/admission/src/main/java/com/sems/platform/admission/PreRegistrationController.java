package com.sems.platform.admission;
import jakarta.validation.Valid;
import java.util.UUID;
import org.springframework.http.*;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.*;
@RestController
@RequestMapping("/api/v1/pre-registrations")
public class PreRegistrationController {
 private final PreRegistrationService service;private final CatalogClient catalog;
 public PreRegistrationController(PreRegistrationService service,CatalogClient catalog){this.service=service;this.catalog=catalog;}
    private java.util.Map<UUID,CatalogClient.EventDetails> details(java.util.List<UUID> ids) {
        try {return catalog.details(ids);}
        catch(org.springframework.web.server.ResponseStatusException e) {
            if(e.getStatusCode().value()!=503)throw e;
            return java.util.Map.of(); // Ticket access remains available; UI explicitly labels unavailable current details.
        }
    }
    private ResponseEntity<PreRegistrationService.View> response(PreRegistrationService.View body) {
        return ResponseEntity.ok().cacheControl(CacheControl.noStore()).body(body.withCurrentEvent(details(java.util.List.of(body.eventId())).get(body.eventId())));
    }
    private ResponseEntity<PreRegistrationService.Page> response(PreRegistrationService.Page body) {
        var current=details(body.items().stream().map(PreRegistrationService.View::eventId).toList());
        return ResponseEntity.ok().cacheControl(CacheControl.noStore()).body(new PreRegistrationService.Page(body.items().stream().map(b->b.withCurrentEvent(current.get(b.eventId()))).toList(),body.page(),body.size(),body.totalElements(),body.totalPages()));
    }
 @GetMapping public ResponseEntity<PreRegistrationService.Page> list(@AuthenticationPrincipal Jwt jwt,@RequestParam(defaultValue="0") int page,@RequestParam(defaultValue="10") int size){return response(service.list(UUID.fromString(jwt.getSubject()),page,size));}
 @GetMapping("/{event}") public ResponseEntity<PreRegistrationService.View> get(@AuthenticationPrincipal Jwt jwt,@PathVariable UUID event){return response(service.get(UUID.fromString(jwt.getSubject()),event));}
 @PutMapping("/{event}") public ResponseEntity<PreRegistrationService.View> save(@AuthenticationPrincipal Jwt jwt,@PathVariable UUID event,@Valid @RequestBody PreRegistrationService.Input input){return response(service.save(UUID.fromString(jwt.getSubject()),event,input,catalog.published(event,UUID.fromString(jwt.getSubject()))));}
 @DeleteMapping("/{event}") public ResponseEntity<Void> delete(@AuthenticationPrincipal Jwt jwt,@PathVariable UUID event){service.delete(UUID.fromString(jwt.getSubject()),event);return ResponseEntity.noContent().cacheControl(CacheControl.noStore()).build();}
}
