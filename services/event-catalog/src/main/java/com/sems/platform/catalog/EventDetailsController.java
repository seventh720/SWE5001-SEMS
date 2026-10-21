package com.sems.platform.catalog;

import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import java.util.*;
import org.springframework.web.bind.annotation.*;

/** Admission checks booking ownership or staff membership before requesting these details. */
@RestController
public class EventDetailsController {
    private final EventRepository events;
    private final CatalogTimings timings;
    public EventDetailsController(EventRepository events, CatalogTimings timings) {
        this.events = events;
        this.timings = timings;
    }
    public record Request(@NotNull @Size(max=50) List<@NotNull UUID> ids) {}
    @PostMapping("/internal/v1/events/details")
    public List<EventDetails> details(@Valid @RequestBody Request request) {
        if (request.ids().isEmpty()) return List.of();
        return timings.read("internal-details", () -> events.detailsByIds(request.ids().stream().distinct().toList()));
    }
}
