package com.sems.platform.catalog;

import java.time.Instant;
import java.util.*;
import org.springframework.data.domain.*;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;
@RestController @RequestMapping("/api/v1/events")
public class PublicEventController {
    private final PublicEventReadRepository events; private final OrganizationAccess access; private final CatalogTimings timings;
    public PublicEventController(PublicEventReadRepository events,OrganizationAccess access,CatalogTimings timings){this.events=events;this.access=access;this.timings=timings;}
    public record Offering(UUID id,String title,String description,String location,Instant startsAt,Instant endsAt,int capacity,EventCategory category,CardTheme cardTheme,RegistrationRequirements registrationRequirements,UUID organizationId,String visibility,String organizationName) {}
    private Offering view(PublicEventReadRepository.Row e,String organizationName){return new Offering(e.id(),e.title(),e.description(),e.location(),e.startsAt(),e.endsAt(),e.capacity(),e.category(),e.cardTheme(),e.registrationRequirements(),e.organizationId(),e.visibility(),organizationName);}
    public record OfferingPage(List<Offering> items,int page,int size,long totalElements,int totalPages) {}
    @GetMapping public OfferingPage list(@org.springframework.security.core.annotation.AuthenticationPrincipal org.springframework.security.oauth2.jwt.Jwt jwt,@RequestParam(required=false) UUID organizationId,@RequestParam(defaultValue="0") int page,@RequestParam(defaultValue="10") int size,@RequestParam(defaultValue="") String keyword,@RequestParam(required=false) EventCategory category) {
        if(page<0||size<1||size>50||(long)page*size>Integer.MAX_VALUE||keyword.length()>200)throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Invalid search or pagination");
        var paging=PageRequest.of(page,size,Sort.by("startsAt","id"));
        if(organizationId!=null)access.require(organizationId,jwt==null?null:UUID.fromString(jwt.getSubject()),false);
        // Query only organizations represented in matching offerings, in bounded batches.
        // No membership/status cache: suspension and closure remain immediately effective.
        var active=new ArrayList<OrganizationAccess.Membership>();
        var now=Instant.now();
        for(int batch=0;;batch++){
            var orgPage=PageRequest.of(batch,100);
            var ids=timings.read("discovery-organizations", () -> events.discoveryOrganizations(organizationId,now,keyword.strip(),category,orgPage));
            active.addAll(access.activeOrganizations(ids.getContent()));
            if(!ids.hasNext())break;
        }
        if(active.isEmpty())return new OfferingPage(List.of(),page,size,0,0);
        var names=new HashMap<UUID,String>();active.forEach(o->names.put(o.id(),o.name()));
        var result=timings.read("public-list", () -> events.discover(active.stream().map(OrganizationAccess.Membership::id).toList(),organizationId,now,keyword.strip(),category,paging));
        return new OfferingPage(result.getContent().stream().map(e->view(e,names.get(e.organizationId()))).toList(),page,size,result.getTotalElements(),result.getTotalPages());
    }
    @GetMapping("/{id}") public Offering detail(@PathVariable UUID id,@org.springframework.security.core.annotation.AuthenticationPrincipal org.springframework.security.oauth2.jwt.Jwt jwt) {
        var event=timings.read("public-detail", () -> events.findById(id)).filter(e->e.status().equals("PUBLISHED")&&e.startsAt().isAfter(Instant.now()))
                .orElseThrow(()->new ResponseStatusException(HttpStatus.NOT_FOUND,"Event not found"));if(event.visibility().equals("ORGANIZATION_ONLY"))access.require(event.organizationId(),jwt==null?null:UUID.fromString(jwt.getSubject()),false);return view(event,access.active(event.organizationId()).name());
    }
}
