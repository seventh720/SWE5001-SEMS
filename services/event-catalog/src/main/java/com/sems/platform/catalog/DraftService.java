package com.sems.platform.catalog;
import java.util.*;
import org.springframework.data.domain.*;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;
@Service @Transactional
public class DraftService {
 private final EventRepository events;
 public DraftService(EventRepository events){this.events=events;}
 public Event.View create(UUID owner,Draft input){validate(input);return events.saveAndFlush(new Event(owner,input)).view();}
 public Event.View update(UUID owner,UUID id,Draft input){
  Event event=owned(owner,id);
  if(input.version()==null)throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"version is required when updating");
  if(event.version!=input.version())throw new ResponseStatusException(HttpStatus.CONFLICT,"Event changed; reload before editing");
  if(!event.status.equals("DRAFT"))throw new ResponseStatusException(HttpStatus.CONFLICT,"Only drafts can be edited");
  validate(input);event.apply(input);events.flush();return event.view();
 }
 @Transactional(readOnly=true) public Event.View detail(UUID owner,UUID id){return owned(owner,id).view();}
 @Transactional(readOnly=true) public EventPage list(UUID owner,int page,int size){
  if(page<0||size<1||size>50||(long)page*size>Integer.MAX_VALUE)throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Invalid pagination");
  var result=events.findByOrganizerId(owner,PageRequest.of(page,size,Sort.by(Sort.Direction.DESC,"createdAt","id")));
  return new EventPage(result.getContent().stream().map(Event::view).toList(),page,size,result.getTotalElements(),result.getTotalPages());
 }
 private Event owned(UUID owner,UUID id){return events.findByIdAndOrganizerId(id,owner).orElseThrow(()->new ResponseStatusException(HttpStatus.NOT_FOUND,"Event not found"));}
 private void validate(Draft input){if(!input.endsAt().isAfter(input.startsAt()))throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"End must be after start");}
 public record EventPage(List<Event.View> items,int page,int size,long totalElements,int totalPages){}
}
