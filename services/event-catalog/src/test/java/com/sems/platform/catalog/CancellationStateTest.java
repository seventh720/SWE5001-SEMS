package com.sems.platform.catalog;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import java.time.Instant;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.web.server.ResponseStatusException;

class CancellationStateTest {
 private final EventRepository events=mock(EventRepository.class);
 private final OrganizationAccess access=mock(OrganizationAccess.class);
 private final JdbcTemplate jdbc=mock(JdbcTemplate.class);
 private final CancellationState service=new CancellationState(events,access,jdbc);
 private final UUID actor=UUID.randomUUID();
 private final Event event=new Event(UUID.randomUUID(),new Draft("Seminar","Details","Campus",Instant.parse("2030-01-01T10:00:00Z"),Instant.parse("2030-01-01T11:00:00Z"),20,0L));
 private void existing(String status){event.organizationId=UUID.randomUUID();event.status=status;event.version=4;when(events.findById(event.id)).thenReturn(Optional.of(event));when(events.lockById(event.id)).thenReturn(Optional.of(event));}
 @SuppressWarnings("unchecked")
 private void receipt(CancellationState.Operation op){doReturn(op).when(jdbc).queryForObject(anyString(),any(RowMapper.class),eq(event.id));when(jdbc.queryForObject(anyString(),eq(Long.class),eq(event.id))).thenReturn(4L);}
 @Test void unauthorizedActorCannotLockOrCancel(){
  existing("PUBLISHED");when(access.require(event.organizationId,actor,true)).thenThrow(new ResponseStatusException(HttpStatus.NOT_FOUND));
  assertEquals(404,assertThrows(ResponseStatusException.class,()->service.begin(actor,event.id,4,"Reason")).getStatusCode().value());
  verify(events,never()).lockById(any());verifyNoInteractions(jdbc);assertEquals("PUBLISHED",event.status);
 }
 @Test void blankReasonDoesNotChangePublication(){
  existing("PUBLISHED");assertEquals(400,assertThrows(ResponseStatusException.class,()->service.begin(actor,event.id,4,"  ")).getStatusCode().value());
  assertEquals("PUBLISHED",event.status);verifyNoInteractions(jdbc);verify(events,never()).flush();
 }
 @Test void staleVersionCannotCancelAChangedEvent(){
  existing("PAUSED");assertEquals(409,assertThrows(ResponseStatusException.class,()->service.begin(actor,event.id,3,"Reason")).getStatusCode().value());
  assertEquals("PAUSED",event.status);verifyNoInteractions(jdbc);
 }
 @Test void cannotCancelWhileDraftPublicationOrRevisionIsPending(){
  for(String status:List.of("DRAFT","PUBLISHING","UPDATING")){
   existing(status);assertEquals(409,assertThrows(ResponseStatusException.class,()->service.begin(actor,event.id,4,"Reason")).getStatusCode().value());assertEquals(status,event.status);
  }
  verifyNoInteractions(jdbc);
 }
 @Test void pausedEventBeginsDurableCancellationWithTrimmedReason(){
  existing("PAUSED");event.publicationError="Old error";var op=service.begin(actor,event.id,4," Venue closed ");
  assertEquals(event.id,op.eventId());assertEquals("Venue closed",op.reason());assertNotNull(op.operationId());
  assertEquals("CANCELLING",event.status);assertEquals(op.reason(),event.cancellationReason);assertNull(event.publicationError);
  verify(jdbc).update(startsWith("INSERT INTO event_cancellations"),eq(event.id),eq(op.operationId()),eq(4L),eq("Venue closed"));verify(events).flush();
 }
 @Test void matchingRetriesReuseOperationButChangedReasonIsRejected(){
  existing("CANCELLING");var op=new CancellationState.Operation(event.id,UUID.randomUUID(),"Reason");receipt(op);
  assertEquals(op,service.begin(actor,event.id,4," Reason "));
  assertEquals(409,assertThrows(ResponseStatusException.class,()->service.begin(actor,event.id,4,"Different reason")).getStatusCode().value());
  event.status="CANCELLED";assertEquals(op,service.begin(actor,event.id,4,"Reason"));verify(events,never()).flush();
 }
 @Test void staleAcknowledgementCannotCompleteAnotherOperation(){
  existing("CANCELLING");var current=new CancellationState.Operation(event.id,UUID.randomUUID(),"Reason");receipt(current);
  service.finish(new CancellationState.Operation(event.id,UUID.randomUUID(),"Reason"));assertEquals("CANCELLING",event.status);
  verify(jdbc,never()).update(anyString(),eq(event.id));
  service.finish(current);assertEquals("CANCELLED",event.status);verify(jdbc).update(startsWith("UPDATE event_cancellations SET completed_at"),eq(event.id));
 }
}
