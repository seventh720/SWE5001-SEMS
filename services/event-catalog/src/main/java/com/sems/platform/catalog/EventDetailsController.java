package com.sems.platform.catalog;

import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import java.time.Instant;
import java.util.*;
import org.springframework.web.bind.annotation.*;

/** Admission checks booking ownership or staff membership before requesting these details. */
@RestController
public class EventDetailsController {
    private final EventRepository events;
    public EventDetailsController(EventRepository events) { this.events = events; }
    public record Request(@NotNull @Size(max=50) List<@NotNull UUID> ids) {}
    public record Details(UUID id, String title, String location, Instant startsAt, Instant endsAt, String status) {}
    @PostMapping("/internal/v1/events/details")
    public List<Details> details(@Valid @RequestBody Request request) {
        return events.findAllById(request.ids()).stream()
                .map(e -> new Details(e.id,e.title,e.location,e.startsAt,e.endsAt,e.status)).toList();
    }
}
