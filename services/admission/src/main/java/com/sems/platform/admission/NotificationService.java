package com.sems.platform.admission;
import java.util.*;
import java.time.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.http.HttpStatus;
@Service
public class NotificationService {
 private final JdbcTemplate jdbc;
 public NotificationService(JdbcTemplate jdbc){this.jdbc=jdbc;}
 public record Notice(UUID id,String kind,String title,String message,String link,Instant createdAt,Instant readAt){}
 public record Page(List<Notice> items,long unreadCount,boolean hasMore){}
 public record EventChange(UUID eventId,String title,String location,Instant startsAt,Instant endsAt,String status,String visibility){}
 static void add(JdbcTemplate jdbc,UUID user,String key,String kind,String title,String message,String link){
  jdbc.update("INSERT INTO notifications(id,user_id,dedup_key,kind,title,message,link) VALUES(?,?,?,?,?,?,?) ON CONFLICT(user_id,dedup_key) DO NOTHING",UUID.randomUUID(),user,key,kind,title,message,link);
 }
 public long unread(UUID user){return jdbc.queryForObject("SELECT count(*) FROM notifications WHERE user_id=? AND read_at IS NULL",Long.class,user);}
 @Transactional(readOnly=true) public Page list(UUID user,int page){
  if(page<0||page>100000)throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Invalid page");
  var rows=jdbc.query("SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC,id DESC LIMIT 21 OFFSET ?",(r,n)->new Notice(r.getObject("id",UUID.class),r.getString("kind"),r.getString("title"),r.getString("message"),r.getString("link"),r.getTimestamp("created_at").toInstant(),r.getTimestamp("read_at")==null?null:r.getTimestamp("read_at").toInstant()),user,page*20L);
  return new Page(rows.stream().limit(20).toList(),unread(user),rows.size()>20);
 }
 @Transactional public void read(UUID user,UUID id){
  if(jdbc.update("UPDATE notifications SET read_at=COALESCE(read_at,CURRENT_TIMESTAMP) WHERE id=? AND user_id=?",id,user)==0)throw new ResponseStatusException(HttpStatus.NOT_FOUND,"Notification not found");
 }
 @Transactional public void readAll(UUID user){jdbc.update("UPDATE notifications SET read_at=CURRENT_TIMESTAMP WHERE user_id=? AND read_at IS NULL",user);}
 @Transactional public void eventChanged(UUID delivery,EventChange e){
  var states=jdbc.queryForList("SELECT state FROM sales WHERE event_id=? FOR UPDATE",String.class,e.eventId());
  if(states.isEmpty()||states.getFirst().equals("CANCELLED"))return;
  var users=jdbc.queryForList("SELECT user_id FROM bookings WHERE event_id=? AND status='CONFIRMED' UNION SELECT user_id FROM pre_registrations WHERE event_id=?",UUID.class,e.eventId(),e.eventId());
  String when=java.time.format.DateTimeFormatter.ofPattern("d MMM yyyy, HH:mm 'SGT'").withZone(ZoneId.of("Asia/Singapore")).format(e.startsAt());
  for(var user:users)add(jdbc,user,"event-change:"+delivery,"EVENT_UPDATED","Event updated: "+e.title(),"The organizer updated this event. Starts "+when+" at "+e.location()+". Status: "+e.status()+". Visibility: "+e.visibility()+". Review the latest event details.","/events/"+e.eventId());
 }
 @Scheduled(fixedDelayString="${sems.notifications.reminder-ms:15000}")
 @Transactional public void remind(){
  // The unique delivery key makes concurrent scheduler instances and retries safe.
  jdbc.update("""
   INSERT INTO notifications(id,user_id,dedup_key,kind,title,message,link)
   SELECT gen_random_uuid(),p.user_id,'opening:'||p.event_id||':'||p.ticket_type_id||':'||t.opens_at,
   'REGISTRATION_OPENING','Registration opens soon: '||p.event_title,
   'Your saved ticket '||t.name||' opens at '||to_char(t.opens_at AT TIME ZONE 'Asia/Singapore','DD Mon YYYY, HH24:MI')||' SGT. Places are not reserved; return to complete your booking.',
   '/pre-registrations'
   FROM pre_registrations p JOIN ticket_types t ON t.id=p.ticket_type_id JOIN sales s ON s.event_id=p.event_id
   WHERE s.state='ACTIVE' AND s.starts_at>CURRENT_TIMESTAMP
   AND t.opens_at>CURRENT_TIMESTAMP AND t.opens_at<=CURRENT_TIMESTAMP+interval '5 minutes'
   AND t.closes_at>CURRENT_TIMESTAMP AND t.quota>t.reserved
   ON CONFLICT(user_id,dedup_key) DO NOTHING
   """);
 }
}
