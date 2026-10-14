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
    private <T> ResponseEntity<T> privateResponse(T body) { return ResponseEntity.ok().cacheControl(CacheControl.noStore()).body(body); }
    @PostMapping
    public ResponseEntity<Booking> create(@AuthenticationPrincipal Jwt jwt,@Valid @RequestBody Request input) {
        UUID user=UUID.fromString(jwt.getSubject());
        var prior=bookings.replay(user,input);
        if (prior!=null) return privateResponse(prior);
        // Verify publication over HTTP before starting the local reservation transaction.
        return privateResponse(bookings.create(user,input,catalog.published(input.eventId())));
    }
    @GetMapping public ResponseEntity<Page> list(@AuthenticationPrincipal Jwt jwt,@RequestParam(defaultValue="0") int page,@RequestParam(defaultValue="10") int size,@RequestParam(required=false) String status) {return privateResponse(bookings.list(UUID.fromString(jwt.getSubject()),page,size,status));}
    @GetMapping("/upcoming") public ResponseEntity<Page> upcoming(@AuthenticationPrincipal Jwt jwt){return privateResponse(bookings.upcoming(UUID.fromString(jwt.getSubject())));}
    @GetMapping("/{id}") public ResponseEntity<Booking> detail(@AuthenticationPrincipal Jwt jwt,@PathVariable UUID id) {return privateResponse(bookings.owned(UUID.fromString(jwt.getSubject()),id));}
    @PostMapping("/{id}/cancel") public ResponseEntity<Booking> cancel(@AuthenticationPrincipal Jwt jwt,@PathVariable UUID id) {return privateResponse(bookings.cancel(UUID.fromString(jwt.getSubject()),id));}
}
