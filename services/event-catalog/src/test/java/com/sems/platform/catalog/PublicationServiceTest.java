package com.sems.platform.catalog;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import java.time.Instant;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.web.client.*;
import org.springframework.web.server.ResponseStatusException;
class PublicationServiceTest {
    PublicationState state=mock(PublicationState.class);
    RestClient client=mock(RestClient.class,RETURNS_DEEP_STUBS);
    PublicationState.Operation op=new PublicationState.Operation(UUID.randomUUID(),UUID.randomUUID(),UUID.randomUUID(),10,Instant.now().plusSeconds(600),Instant.now().plusSeconds(1200),1,"PUBLISHING");
    @Test void unavailableAdmissionKeepsDurablePendingState(){
        when(client.post().uri("/internal/v1/events/{id}/activate-sales",op.eventId()).body(op).retrieve().toBodilessEntity()).thenThrow(new ResourceAccessException("timeout"));
        assertFalse(new PublicationService(state,client).advance(op));verifyNoInteractions(state);
    }
    @Test void successfulActivationCompletesCatalog(){assertTrue(new PublicationService(state,client).advance(op));verify(state).finish(op);}
    @Test void definiteConflictReturnsToDraft(){
        when(client.post().uri("/internal/v1/events/{id}/activate-sales",op.eventId()).body(op).retrieve().toBodilessEntity()).thenThrow(new RestClientResponseException("conflict",409,"Conflict",null,null,null));
        assertThrows(ResponseStatusException.class,()->new PublicationService(state,client).advance(op));verify(state).rejected(op);
    }
}
