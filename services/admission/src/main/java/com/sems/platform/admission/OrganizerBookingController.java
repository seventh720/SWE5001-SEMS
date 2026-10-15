package com.sems.platform.admission;
import java.util.UUID;
import org.springframework.web.bind.annotation.*;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.http.*;
@RestController
public class OrganizerBookingController {
 private final CatalogClient catalog;private final BookingService bookings;
 public OrganizerBookingController(CatalogClient catalog,BookingService bookings){this.catalog=catalog;this.bookings=bookings;}
 @GetMapping("/api/v1/organizer/events/{id}/bookings")
 public ResponseEntity<BookingContracts.OrganizerPage> list(@PathVariable UUID id,@AuthenticationPrincipal Jwt jwt,
  @RequestParam(defaultValue="0") int page,@RequestParam(defaultValue="10") int size){
  catalog.owned(id,UUID.fromString(jwt.getSubject()));
  return ResponseEntity.ok().cacheControl(CacheControl.noStore()).body(bookings.organizer(id,page,size));
 }
}
