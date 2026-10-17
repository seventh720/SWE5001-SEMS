package com.sems.platform.catalog;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.springframework.web.client.*;
class CancellationServiceTest {
 private final CancellationState state=mock(CancellationState.class);
 private final RestClient client=mock(RestClient.class,RETURNS_DEEP_STUBS);
 private final CancellationState.Operation op=new CancellationState.Operation(UUID.randomUUID(),UUID.randomUUID(),"Venue unavailable");
 @Test void lostAcknowledgementRemainsPendingAndRecoveryReplaysSameOperation(){
  when(client.post().uri("/internal/v1/events/{id}/cancel",op.eventId()).body(op).retrieve().toBodilessEntity())
   .thenThrow(new ResourceAccessException("response lost")).thenReturn(null);
  var service=new CancellationService(state,client);
  assertFalse(service.advance(op));verify(state).retryLater(op);verify(state,never()).finish(any());
  when(state.pending()).thenReturn(List.of(op));service.recover();verify(state).finish(op);
 }
 @Test void completedCancellationDoesNotDependOnAdmissionAvailability(){
  when(state.completed(op)).thenReturn(true);assertTrue(new CancellationService(state,client).advance(op));verifyNoInteractions(client);
 }
 @Test void conflictNeverRestoresPublication(){
  when(client.post().uri("/internal/v1/events/{id}/cancel",op.eventId()).body(op).retrieve().toBodilessEntity())
   .thenThrow(new RestClientResponseException("conflict",409,"Conflict",null,null,null));
  assertFalse(new CancellationService(state,client).advance(op));verify(state).retryLater(op);verify(state,never()).finish(any());
 }
}
