package com.sems.platform.catalog;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
@Component
public class EventNotificationDelivery {
 private final JdbcTemplate jdbc;private final RestClient client;private final ObjectMapper json;
 public EventNotificationDelivery(JdbcTemplate jdbc,RestClient client,ObjectMapper json){this.jdbc=jdbc;this.client=client;this.json=json;}
 @Scheduled(fixedDelayString="${sems.notifications.delivery-ms:3000}")
 public void deliver(){
  var rows=jdbc.queryForList("SELECT id,payload FROM event_notification_outbox WHERE delivered_at IS NULL ORDER BY created_at,id LIMIT 50");
  for(var row:rows)try{
   client.post().uri("/internal/v1/notifications/event-changes/{id}",row.get("id")).body(json.readTree(row.get("payload").toString())).retrieve().toBodilessEntity();
   jdbc.update("UPDATE event_notification_outbox SET delivered_at=CURRENT_TIMESTAMP WHERE id=?",row.get("id"));
  }catch(Exception e){org.slf4j.LoggerFactory.getLogger(getClass()).warn("Event notification delivery will retry: {}",row.get("id"));break;}
 }
}
