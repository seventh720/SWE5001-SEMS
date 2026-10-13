package com.sems.platform.admission;
import static org.junit.jupiter.api.Assertions.*;
import java.time.Instant;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.springframework.web.server.ResponseStatusException;
import static com.sems.platform.admission.TicketContracts.*;
class InventoryServiceTest {
    Instant start=Instant.parse("2030-01-01T10:00:00Z");
    Snapshot event=new Snapshot(UUID.randomUUID(),UUID.randomUUID(),10,start,start.plusSeconds(3600),"DRAFT","Seminar","Campus");
    TicketInput ticket(String name,int quota){return new TicketInput(name,quota,start.minusSeconds(3600),start);}
    @Test void allocationMayReachCapacity(){assertDoesNotThrow(()->InventoryService.validate(event,List.of(ticket("General",6),ticket("Student",4))));}
    @Test void rejectsExcessiveTotalIncludingIntegerOverflow(){assertThrows(ResponseStatusException.class,()->InventoryService.validate(event,List.of(ticket("A",Integer.MAX_VALUE),ticket("B",Integer.MAX_VALUE))));}
    @Test void rejectsDuplicateTrimmedNames(){assertThrows(ResponseStatusException.class,()->InventoryService.validate(event,List.of(ticket("A",1),ticket(" A ",1))));}
    @Test void rejectsWindowAfterEventStarts(){assertThrows(ResponseStatusException.class,()->InventoryService.validate(event,List.of(new TicketInput("A",1,start,start.plusSeconds(10)))));}
}
