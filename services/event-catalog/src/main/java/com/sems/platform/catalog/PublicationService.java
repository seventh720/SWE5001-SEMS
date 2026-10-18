package com.sems.platform.catalog;

import org.springframework.http.HttpStatus;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.web.client.*;
import org.springframework.web.server.ResponseStatusException;
import static com.sems.platform.catalog.PublicationState.Operation;
@Service
public class PublicationService {
    private final PublicationState state; private final RestClient client;
    public PublicationService(PublicationState state,RestClient client) { this.state=state;this.client=client; }
    public boolean advance(Operation op) {
        if(op.status().equals("PUBLISHED")) return true;
        try {
            client.post().uri("/internal/v1/events/{id}/activate-sales",op.eventId()).body(op).retrieve().toBodilessEntity();
        } catch(RestClientResponseException e) {
            org.slf4j.LoggerFactory.getLogger(getClass()).warn("Catalog command pending/rejected event={} operation={} httpStatus={}",op.eventId(),op.operationId(),e.getStatusCode().value());
            if(e.getStatusCode().value()==409) {state.rejected(op);throw new ResponseStatusException(HttpStatus.CONFLICT,"Review ticket configuration and retry publication");}
            return false;
        } catch(RestClientException e) { org.slf4j.LoggerFactory.getLogger(getClass()).warn("Publication retry pending event={} operation={} failure={}",op.eventId(),op.operationId(),e.getClass().getSimpleName()); return false; }
        state.finish(op);return true;
    }
    @Scheduled(fixedDelayString="${sems.publication.retry-ms:5000}")
    public void recover() {
        for(var op:state.pending()) {
            try { advance(op); } catch(ResponseStatusException ignored) { /* Persisted back to DRAFT with an actionable message. */ }
        }
    }
}
