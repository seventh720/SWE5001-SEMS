package com.sems.platform.catalog;

import java.time.Instant;
import java.util.*;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;
@Service
public class PublicationState {
    private final EventRepository events;
    public PublicationState(EventRepository events) { this.events=events; }
    public record Snapshot(UUID id,UUID organizerId,int capacity,Instant startsAt,Instant endsAt,String status,String title,String location,RegistrationRequirements registrationRequirements) {}
    public record Operation(UUID eventId,UUID operationId,UUID organizerId,int capacity,Instant startsAt,Instant endsAt,long ticketVersion,String status) {}
    private Snapshot snapshot(Event e) { return new Snapshot(e.id,e.organizerId,e.capacity,e.startsAt,e.endsAt,e.status,e.title,e.location,e.registrationRequirements); }
    private Operation operation(Event e) { return new Operation(e.id,e.publicationId,e.organizerId,e.capacity,e.startsAt,e.endsAt,e.ticketVersion,e.status); }
    private Event owned(UUID owner,UUID id) {
        var e=events.lockById(id).orElseThrow(()->new ResponseStatusException(HttpStatus.NOT_FOUND,"Event not found"));
        if (!e.organizerId.equals(owner)) throw new ResponseStatusException(HttpStatus.NOT_FOUND,"Event not found"); return e;
    }
    @Transactional(readOnly=true) public Snapshot inspect(UUID id,UUID owner,boolean published) {
        var e=events.findById(id).orElseThrow(()->new ResponseStatusException(HttpStatus.NOT_FOUND,"Event not found"));
        if ((owner!=null&&!owner.equals(e.organizerId)) || (published&&(!e.status.equals("PUBLISHED")||!e.startsAt.isAfter(Instant.now()))))
            throw new ResponseStatusException(HttpStatus.NOT_FOUND,"Event not found");
        return snapshot(e);
    }
    @Transactional public Snapshot prepare(UUID owner,UUID id,long version) {
        var e=owned(owner,id);
        if (!e.status.equals("DRAFT") || e.version!=version) conflict("Event changed; reload");
        if (!e.salesConfigured) { e.salesConfigured=true; e.updatedAt=Instant.now();events.flush(); }
        return snapshot(e);
    }
    @Transactional public Operation begin(UUID owner,UUID id,long version,long ticketVersion) {
        var e=owned(owner,id);
        if ((e.status.equals("PUBLISHING")||e.status.equals("PUBLISHED")) && e.publicationId!=null && Objects.equals(e.publicationVersion,version) && Objects.equals(e.ticketVersion,ticketVersion)) return operation(e);
        if (!e.status.equals("DRAFT") || e.version!=version) conflict("Event changed; reload");
        if (!e.salesConfigured || !e.startsAt.isAfter(Instant.now())) conflict("Configure tickets for a future event before publishing");
        e.publicationId=UUID.randomUUID();e.publicationVersion=version;e.ticketVersion=ticketVersion;
        e.publicationError=null;e.status="PUBLISHING";e.updatedAt=Instant.now();events.flush();return operation(e);
    }
    @Transactional public void finish(Operation op) {
        var e=events.lockById(op.eventId()).orElseThrow();
        if (e.status.equals("PUBLISHING") && op.operationId().equals(e.publicationId)) { e.status="PUBLISHED";e.updatedAt=Instant.now(); }
    }
    @Transactional public void rejected(Operation op) {
        var e=events.lockById(op.eventId()).orElseThrow();
        if(e.status.equals("PUBLISHING")&&op.operationId().equals(e.publicationId)) {
            e.status="DRAFT";e.publicationId=null;e.publicationVersion=null;e.ticketVersion=null;
            e.publicationError="Ticket configuration changed or is invalid. Review tickets and publish again.";e.updatedAt=Instant.now();
        }
    }
    @Transactional(readOnly=true) public List<Operation> pending() {
        return events.findTop20ByStatusOrderByUpdatedAtAsc("PUBLISHING").stream().map(this::operation).toList();
    }
    private static void conflict(String message) { throw new ResponseStatusException(HttpStatus.CONFLICT,message); }
}
