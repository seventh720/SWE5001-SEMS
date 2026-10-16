package com.sems.platform.admission;
import java.util.UUID;
import org.springframework.web.bind.annotation.*;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.http.HttpStatus;
@RestController
public class NotificationController {
 private final NotificationService service;
 public NotificationController(NotificationService service){this.service=service;}
 @GetMapping("/api/v1/me/notifications") public NotificationService.Page list(@AuthenticationPrincipal Jwt jwt,@RequestParam(defaultValue="0") int page){return service.list(UUID.fromString(jwt.getSubject()),page);}
 @GetMapping("/api/v1/me/notifications/unread-count") public long unread(@AuthenticationPrincipal Jwt jwt){return service.unread(UUID.fromString(jwt.getSubject()));}
 @PostMapping("/api/v1/me/notifications/{id}/read") @ResponseStatus(HttpStatus.NO_CONTENT) public void read(@AuthenticationPrincipal Jwt jwt,@PathVariable UUID id){service.read(UUID.fromString(jwt.getSubject()),id);}
 @PostMapping("/api/v1/me/notifications/read-all") @ResponseStatus(HttpStatus.NO_CONTENT) public void readAll(@AuthenticationPrincipal Jwt jwt){service.readAll(UUID.fromString(jwt.getSubject()));}
 @PostMapping("/internal/v1/notifications/event-changes/{id}") @ResponseStatus(HttpStatus.NO_CONTENT) public void change(@PathVariable UUID id,@RequestBody NotificationService.EventChange event){service.eventChanged(id,event);}
}
