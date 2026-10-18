package com.sems.platform.admission;

import java.util.UUID;
import jakarta.validation.constraints.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

@Service
public class EventCancellationService {
 private final JdbcTemplate jdbc;
 public EventCancellationService(JdbcTemplate jdbc){this.jdbc=jdbc;}
 public record Operation(@NotNull UUID eventId,@NotNull UUID operationId,@NotBlank @Size(max=500) String reason){}
 @Transactional public void cancel(UUID event,Operation input){
  if(!event.equals(input.eventId()))conflict("Event mismatch");
  jdbc.query("SELECT pg_advisory_xact_lock(hashtextextended(?,0))",(org.springframework.jdbc.core.RowCallbackHandler)r->{},event.toString());
  var sales=jdbc.queryForList("SELECT state FROM sales WHERE event_id=? FOR UPDATE",event);
  if(sales.isEmpty())conflict("Event inventory missing");
  var receipts=jdbc.queryForList("SELECT * FROM event_cancellation_receipts WHERE event_id=?",event);
  if(!receipts.isEmpty()){
   var receipt=receipts.getFirst();
   if(!input.operationId().equals(receipt.get("operation_id"))||!input.reason().equals(receipt.get("reason")))conflict("Cancellation operation mismatch");
   return;
  }
  String state=sales.getFirst().get("state").toString();
  if(!state.equals("ACTIVE")&&!state.equals("PAUSED"))conflict("Event is not published");
  // All admission mutations serialize on the sales row. The receipt and effects commit together.
  var bookings=jdbc.queryForList("SELECT id,user_id,event_title FROM bookings WHERE event_id=? AND status='CONFIRMED'",event);
  for(var booking:bookings)NotificationService.add(jdbc,(UUID)booking.get("user_id"),"event-cancel:"+booking.get("id"),"EVENT_CANCELLED","Event cancelled: "+booking.get("event_title"),input.reason()+" Your tickets are no longer valid. Previous check-in records are retained.","/bookings/"+booking.get("id"));
  var saved=jdbc.queryForList("SELECT user_id,event_title FROM pre_registrations WHERE event_id=?",event);
  for(var row:saved)NotificationService.add(jdbc,(UUID)row.get("user_id"),"event-cancel-saved:"+event,"EVENT_CANCELLED","Event cancelled: "+row.get("event_title"),input.reason()+" Your saved registration is closed.","/pre-registrations");
  jdbc.update("UPDATE tickets SET state='CANCELLED' WHERE state='VALID' AND booking_id IN (SELECT id FROM bookings WHERE event_id=?)",event);
  jdbc.update("UPDATE bookings SET status='CANCELLED',cancelled_at=CURRENT_TIMESTAMP,event_cancellation_reason=? WHERE event_id=? AND status='CONFIRMED'",input.reason(),event);
  jdbc.update("UPDATE ticket_types SET reserved=0 WHERE event_id=?",event);
  jdbc.update("UPDATE sales SET state='CANCELLED',version=version+1 WHERE event_id=?",event);
  jdbc.update("INSERT INTO event_cancellation_receipts(event_id,operation_id,reason) VALUES(?,?,?)",event,input.operationId(),input.reason());
 }
 private static void conflict(String message){throw new ResponseStatusException(HttpStatus.CONFLICT,message);}
}
