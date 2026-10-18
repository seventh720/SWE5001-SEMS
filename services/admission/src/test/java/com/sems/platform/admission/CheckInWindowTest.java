package com.sems.platform.admission;
import java.time.Instant;
import java.sql.Timestamp;
import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;
import static org.mockito.Mockito.*;
import org.junit.jupiter.api.Test;
import org.springframework.web.server.ResponseStatusException;
import static org.junit.jupiter.api.Assertions.*;
class CheckInWindowTest {
 private final Instant start=Instant.parse("2030-01-01T10:00:00Z");
 @Test void rejectsEvenOneNanosecondBeforeOpening(){
  var error=assertThrows(ResponseStatusException.class,()->CheckInService.requireCheckInOpen(start,start.minusSeconds(900).minusNanos(1)));
  assertEquals(409,error.getStatusCode().value());
 }
 @Test void allowsExactOpeningAndAfterStart(){
  assertDoesNotThrow(()->CheckInService.requireCheckInOpen(start,start.minusSeconds(900)));
  assertDoesNotThrow(()->CheckInService.requireCheckInOpen(start,start.plusSeconds(1)));
 }
 @Test void usesRevisedStart(){
  Instant now=start.minusSeconds(600);
  assertDoesNotThrow(()->CheckInService.requireCheckInOpen(start,now));
  assertThrows(ResponseStatusException.class,()->CheckInService.requireCheckInOpen(start.plusSeconds(3600),now));
 }
 @Test void earlyScanDoesNotWriteAttendance(){
  var jdbc=mock(JdbcTemplate.class);var event=UUID.randomUUID();var user=UUID.randomUUID();
  when(jdbc.queryForList("SELECT event_id FROM sales WHERE event_id=? FOR UPDATE",event)).thenReturn(List.of(Map.of("event_id",event)));
  when(jdbc.queryForObject(anyString(),eq(Boolean.class),eq(event),eq(user))).thenReturn(true);
  when(jdbc.queryForList(anyString(),eq(event),eq("ticket"))).thenReturn(List.of(Map.of("id",UUID.randomUUID(),"booking_status","CONFIRMED","state","VALID")));
  when(jdbc.queryForMap(anyString(),eq(event))).thenReturn(Map.of("starts_at",Timestamp.from(start),"now",Timestamp.from(start.minusSeconds(901))));
  assertEquals(409,assertThrows(ResponseStatusException.class,()->new CheckInService(jdbc).check(event,user,"ticket")).getStatusCode().value());
  verify(jdbc,never()).update(anyString(),any(UUID.class),any(UUID.class));
 }
}
