package com.sems.platform.catalog;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import java.time.Instant;
import java.util.*;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.server.ResponseStatusException;
class RevisionStateTest {
 @ParameterizedTest @ValueSource(strings={"DRAFT","PUBLISHED","PAUSED"})
 void endedEventsCannotBeReopenedWithFutureDates(String status){
  var repo=mock(EventRepository.class);var jdbc=mock(JdbcTemplate.class);
  var state=new RevisionState(repo,jdbc,new ObjectMapper(),mock(OrganizationAccess.class));
  var input=new Draft("Event","Description","Campus",Instant.now().plusSeconds(3600),Instant.now().plusSeconds(7200),10,0L);
  var event=new Event(UUID.randomUUID(),input);event.status=status;event.salesConfigured=true;event.endsAt=Instant.now().minusSeconds(1);
  when(repo.findById(event.id)).thenReturn(Optional.of(event));when(repo.lockById(event.id)).thenReturn(Optional.of(event));
  assertEquals(409,assertThrows(ResponseStatusException.class,()->state.begin(event.organizerId,event.id,input)).getStatusCode().value());
  assertEquals(status,event.status);verify(repo,never()).flush();
 }
}
