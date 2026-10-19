package com.sems.platform.admission;

import java.util.UUID;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.*;

@RestController
public class OrganizationAttendanceController {
 private final JdbcTemplate jdbc;
 public OrganizationAttendanceController(JdbcTemplate jdbc){this.jdbc=jdbc;}
 public record Summary(long validTickets,long checkedIn){}
 @GetMapping("/internal/v1/organizations/{id}/attendance-summary")
 @Transactional(readOnly=true)
 public Summary summary(@PathVariable UUID id){
  return jdbc.queryForObject("SELECT count(*) AS valid_tickets, count(*) FILTER (WHERE t.state='CHECKED_IN') AS checked_in FROM tickets t JOIN bookings b ON b.id=t.booking_id JOIN sales s ON s.event_id=b.event_id WHERE s.organization_id=? AND s.state<>'CANCELLED' AND b.status='CONFIRMED' AND t.state IN ('VALID','CHECKED_IN')",(r,n)->new Summary(r.getLong("valid_tickets"),r.getLong("checked_in")),id);
 }
}
