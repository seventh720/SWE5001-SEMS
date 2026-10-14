package com.sems.platform.admission;

import jakarta.validation.Valid;
import java.util.UUID;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.*;
import static com.sems.platform.admission.TicketContracts.*;
@RestController
public class TicketController {
    private final EventRevisionService revisions; private final InventoryService inventory; private final CatalogClient catalog;
    public TicketController(InventoryService inventory,CatalogClient catalog,EventRevisionService revisions) { this.inventory=inventory;this.catalog=catalog;this.revisions=revisions; }
    @GetMapping("/api/v1/organizer/events/{id}/ticket-types") @PreAuthorize("hasAnyRole('ORGANIZER','ADMIN')")
    public Inventory owned(@PathVariable UUID id,@AuthenticationPrincipal Jwt jwt) {
        catalog.owned(id,UUID.fromString(jwt.getSubject())); return inventory.inventory(id);
    }
    @PutMapping("/api/v1/organizer/events/{id}/ticket-types") @PreAuthorize("hasAnyRole('ORGANIZER','ADMIN')")
    public Inventory configure(@PathVariable UUID id,@AuthenticationPrincipal Jwt jwt,@Valid @RequestBody Configuration input) {
        // The remote call completes before the Admission transaction acquires any locks.
        var event=catalog.prepare(id,UUID.fromString(jwt.getSubject()),input.eventVersion());
        return inventory.configure(event,input);
    }
    @GetMapping("/api/v1/events/{id}/ticket-types")
    public Inventory published(@PathVariable UUID id) {
        catalog.published(id); return inventory.inventory(id);
    }
    @PostMapping("/internal/v1/events/{id}/revise") public void revise(@PathVariable UUID id,@Valid @RequestBody EventRevisionService.Operation input){revisions.revise(id,input);}
    @PostMapping("/internal/v1/events/{id}/activate-sales")
    public void activate(@PathVariable UUID id,@Valid @RequestBody Activate input) { inventory.activate(id,input); }
}
