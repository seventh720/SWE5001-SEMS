package com.sems.platform.admission;
import java.util.UUID;
import jakarta.validation.Valid;
import org.springframework.web.bind.annotation.*;
@RestController
public class EventCancellationController {
 private final EventCancellationService service;
 public EventCancellationController(EventCancellationService service){this.service=service;}
 @PostMapping("/internal/v1/events/{id}/cancel")
 public void cancel(@PathVariable UUID id,@Valid @RequestBody EventCancellationService.Operation input){service.cancel(id,input);}
}
