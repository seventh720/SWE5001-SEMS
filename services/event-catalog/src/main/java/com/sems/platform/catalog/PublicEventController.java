package com.sems.platform.catalog;

import java.time.Instant;
import java.util.*;
import org.springframework.data.domain.*;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;
@RestController @RequestMapping("/api/v1/events")
public class PublicEventController {
    private final EventRepository events;
    public PublicEventController(EventRepository events){this.events=events;}
    public record Offering(UUID id,String title,String description,String location,Instant startsAt,Instant endsAt,int capacity) {}
    private Offering view(Event e){return new Offering(e.id,e.title,e.description,e.location,e.startsAt,e.endsAt,e.capacity);}
    public record OfferingPage(List<Offering> items,int page,int size,long totalElements,int totalPages) {}
    @GetMapping public OfferingPage list(@RequestParam(defaultValue="0") int page,@RequestParam(defaultValue="10") int size,@RequestParam(defaultValue="") String keyword) {
        if(page<0||size<1||size>50||(long)page*size>Integer.MAX_VALUE||keyword.length()>200)throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Invalid search or pagination");
        var result=events.findByStatusAndStartsAtAfterAndTitleContainingIgnoreCase("PUBLISHED",Instant.now(),keyword.strip(),PageRequest.of(page,size,Sort.by("startsAt","id")));
        return new OfferingPage(result.getContent().stream().map(this::view).toList(),page,size,result.getTotalElements(),result.getTotalPages());
    }
    @GetMapping("/{id}") public Offering detail(@PathVariable UUID id) {
        var event=events.findById(id).filter(e->e.status.equals("PUBLISHED")&&e.startsAt.isAfter(Instant.now()))
                .orElseThrow(()->new ResponseStatusException(HttpStatus.NOT_FOUND,"Event not found"));return view(event);
    }
}
