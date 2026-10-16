package com.sems.platform.catalog;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import java.time.Instant;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.springframework.web.server.ResponseStatusException;
class DraftServiceTest {
 EventRepository repo=mock(EventRepository.class); DraftService service=new DraftService(repo,mock(OrganizationAccess.class));
 Draft input=new Draft("Seminar","Description","Campus",Instant.parse("2030-01-01T10:00:00Z"),Instant.parse("2030-01-01T11:00:00Z"),10,0L);
 @Test void cannotReadAnotherOwnersEvent(){var owner=UUID.randomUUID();var id=UUID.randomUUID();when(repo.findById(id)).thenReturn(Optional.empty());assertEquals(404,assertThrows(ResponseStatusException.class,()->service.detail(owner,id)).getStatusCode().value());}
 @Test void staleUpdateDoesNotMutateEvent(){var owner=UUID.randomUUID();var event=new Event(owner,input);event.version=2;when(repo.findById(event.id)).thenReturn(Optional.of(event));assertEquals(409,assertThrows(ResponseStatusException.class,()->service.update(owner,event.id,input)).getStatusCode().value());verify(repo,never()).flush();}
 @Test void rejectsEndBeforeStart(){var invalid=new Draft("x","x","x",input.endsAt(),input.startsAt(),10,null);assertEquals(400,assertThrows(ResponseStatusException.class,()->service.create(UUID.randomUUID(),invalid)).getStatusCode().value());verifyNoInteractions(repo);}
 @Test void publishedPresentationKeepsTicketContract(){var owner=UUID.randomUUID();var event=new Event(owner,input);event.status="PUBLISHED";event.salesConfigured=true;when(repo.findById(event.id)).thenReturn(Optional.of(event));
 var updated=service.presentation(owner,event.id,new PresentationUpdate("New title","New description","New venue",EventCategory.MUSIC,CardTheme.PEACH,0L));
 assertEquals("New title",updated.title());assertEquals(input.startsAt(),updated.startsAt());assertEquals(input.capacity(),updated.capacity());assertEquals(RegistrationRequirements.none(),updated.registrationRequirements());assertEquals("PUBLISHED",updated.status());
 assertEquals(409,assertThrows(ResponseStatusException.class,()->service.presentation(owner,event.id,new PresentationUpdate("X","X","X",EventCategory.ART,CardTheme.SKY,5L))).getStatusCode().value());
 }
}
