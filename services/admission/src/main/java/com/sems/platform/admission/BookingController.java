package com.sems.platform.admission;
import jakarta.validation.Valid;
import java.util.UUID;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.*;
import org.springframework.http.CacheControl;
import org.springframework.http.ResponseEntity;
import static com.sems.platform.admission.BookingContracts.*;
@RestController
@RequestMapping("/api/v1/bookings")
public class BookingController {
    private final BookingService bookings; private final CatalogClient catalog;
    public BookingController(BookingService bookings,CatalogClient catalog) {this.bookings=bookings;this.catalog=catalog;}
    private java.util.Map<UUID,CatalogClient.EventDetails> details(java.util.List<UUID> ids) {
        try {return catalog.details(ids);}
        catch(org.springframework.web.server.ResponseStatusException e) {
            if(e.getStatusCode().value()!=503)throw e;
            return java.util.Map.of(); // Ticket access remains available; UI explicitly labels unavailable current details.
        }
    }
    private ResponseEntity<Booking> privateResponse(Booking body) {
        return ResponseEntity.ok().cacheControl(CacheControl.noStore()).body(body.withCurrentEvent(details(java.util.List.of(body.eventId())).get(body.eventId())));
    }
    private ResponseEntity<Page> privateResponse(Page body) {
        var current=details(body.items().stream().map(Booking::eventId).toList());
        return ResponseEntity.ok().cacheControl(CacheControl.noStore()).body(new Page(body.items().stream().map(b->b.withCurrentEvent(current.get(b.eventId()))).toList(),body.page(),body.size(),body.totalElements(),body.totalPages()));
    }
    @PostMapping
    public ResponseEntity<Booking> create(@AuthenticationPrincipal Jwt jwt,@Valid @RequestBody Request input) {
        UUID user=UUID.fromString(jwt.getSubject());
        var prior=bookings.replay(user,input);
        if (prior!=null) return privateResponse(prior);
        // Verify publication over HTTP before starting the local reservation transaction.
        return privateResponse(bookings.create(user,input,catalog.published(input.eventId(),UUID.fromString(jwt.getSubject()))));
    }
    @GetMapping public ResponseEntity<Page> list(@AuthenticationPrincipal Jwt jwt,@RequestParam(defaultValue="0") int page,@RequestParam(defaultValue="10") int size,@RequestParam(required=false) String status) {return privateResponse(bookings.list(UUID.fromString(jwt.getSubject()),page,size,status));}
    @GetMapping("/upcoming") public ResponseEntity<Page> upcoming(@AuthenticationPrincipal Jwt jwt){return privateResponse(bookings.upcoming(UUID.fromString(jwt.getSubject())));}
    @GetMapping("/{id}") public ResponseEntity<Booking> detail(@AuthenticationPrincipal Jwt jwt,@PathVariable UUID id) {return privateResponse(bookings.owned(UUID.fromString(jwt.getSubject()),id));}
    @PostMapping("/{id}/cancel") public ResponseEntity<Booking> cancel(@AuthenticationPrincipal Jwt jwt,@PathVariable UUID id) {return privateResponse(bookings.cancel(UUID.fromString(jwt.getSubject()),id));}
}
