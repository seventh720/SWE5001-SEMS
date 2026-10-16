package com.sems.platform.catalog;

import java.time.Instant;
import java.util.*;
import org.springframework.data.domain.*;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;
@RestController @RequestMapping("/api/v1/events")
public class PublicEventController {
    private final EventRepository events; private final OrganizationAccess access;
    public PublicEventController(EventRepository events,OrganizationAccess access){this.events=events;this.access=access;}
    public record Offering(UUID id,String title,String description,String location,Instant startsAt,Instant endsAt,int capacity,EventCategory category,CardTheme cardTheme,RegistrationRequirements registrationRequirements,UUID organizationId,String visibility,String organizationName) {}
    private Offering view(Event e){return new Offering(e.id,e.title,e.description,e.location,e.startsAt,e.endsAt,e.capacity,e.category,e.cardTheme,e.registrationRequirements,e.organizationId,e.visibility,e.organizationName);}
    public record OfferingPage(List<Offering> items,int page,int size,long totalElements,int totalPages) {}
    @GetMapping public OfferingPage list(@org.springframework.security.core.annotation.AuthenticationPrincipal org.springframework.security.oauth2.jwt.Jwt jwt,@RequestParam(required=false) UUID organizationId,@RequestParam(defaultValue="0") int page,@RequestParam(defaultValue="10") int size,@RequestParam(defaultValue="") String keyword,@RequestParam(required=false) EventCategory category) {
        if(page<0||size<1||size>50||(long)page*size>Integer.MAX_VALUE||keyword.length()>200)throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Invalid search or pagination");
        var paging=PageRequest.of(page,size,Sort.by("startsAt","id"));
        if(organizationId!=null)access.require(organizationId,jwt==null?null:UUID.fromString(jwt.getSubject()),false);
        var result=events.discover(organizationId,Instant.now(),keyword.strip(),category,paging);
        return new OfferingPage(result.getContent().stream().map(this::view).toList(),page,size,result.getTotalElements(),result.getTotalPages());
    }
    @GetMapping("/{id}") public Offering detail(@PathVariable UUID id,@org.springframework.security.core.annotation.AuthenticationPrincipal org.springframework.security.oauth2.jwt.Jwt jwt) {
        var event=events.findById(id).filter(e->e.status.equals("PUBLISHED")&&e.startsAt.isAfter(Instant.now()))
                .orElseThrow(()->new ResponseStatusException(HttpStatus.NOT_FOUND,"Event not found"));if(event.visibility.equals("ORGANIZATION_ONLY"))access.require(event.organizationId,jwt==null?null:UUID.fromString(jwt.getSubject()),false);return view(event);
    }
}
