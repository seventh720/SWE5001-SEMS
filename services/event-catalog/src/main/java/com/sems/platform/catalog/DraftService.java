package com.sems.platform.catalog;
import java.util.*;
import org.springframework.data.domain.*;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;
@Service @Transactional
public class DraftService {
 private final EventRepository events; private final OrganizationAccess access;
 public DraftService(EventRepository events,OrganizationAccess access){this.events=events;this.access=access;}
 public Event.View create(UUID owner,Draft input){var membership=access.require(input.organizationId(),owner,true);validate(input);var event=new Event(owner,input);event.organizationName=membership==null?"Organization":membership.name();return events.saveAndFlush(event).view();}
 public Event.View update(UUID owner,UUID id,Draft input){
  Event event=owned(owner,id);
  if(input.organizationId()!=null&&!input.organizationId().equals(event.organizationId))throw new ResponseStatusException(HttpStatus.CONFLICT,"Event organization cannot change");
  if(input.version()==null)throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"version is required when updating");
  if(event.version!=input.version())throw new ResponseStatusException(HttpStatus.CONFLICT,"Event changed; reload before editing");
  if(!event.status.equals("DRAFT"))throw new ResponseStatusException(HttpStatus.CONFLICT,"Only drafts can be edited");
  if(event.salesConfigured && (event.capacity!=input.capacity() || !event.startsAt.equals(input.startsAt()) || !event.endsAt.equals(input.endsAt())))
   throw new ResponseStatusException(HttpStatus.CONFLICT,"Time and capacity are fixed after ticket setup begins");
  validate(input);event.apply(input);events.flush();return event.view();
 }
 public Event.View presentation(UUID owner,UUID id,PresentationUpdate input){
  Event event=owned(owner,id);
  if(!event.status.equals("PUBLISHED"))throw new ResponseStatusException(HttpStatus.CONFLICT,"Only published events use presentation editing");
  if(event.version!=input.version())throw new ResponseStatusException(HttpStatus.CONFLICT,"Event changed; reload before editing");
  event.title=input.title().strip();event.description=input.description().strip();event.location=input.location().strip();event.category=input.category();event.cardTheme=input.cardTheme();event.updatedAt=java.time.Instant.now();events.flush();return event.view();
 }
 @Transactional(readOnly=true) public Event.View detail(UUID owner,UUID id){return owned(owner,id).view();}
 @Transactional(readOnly=true) public EventPage list(UUID owner,UUID organizationId,int page,int size){
  access.require(organizationId,owner,true);
  if(page<0||size<1||size>50||(long)page*size>Integer.MAX_VALUE)throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Invalid pagination");
  var result=events.findByOrganizationId(organizationId,PageRequest.of(page,size,Sort.by(Sort.Direction.DESC,"createdAt","id")));
  return new EventPage(result.getContent().stream().map(Event::view).toList(),page,size,result.getTotalElements(),result.getTotalPages());
 }
 private Event owned(UUID owner,UUID id){var e=events.findById(id).orElseThrow(()->new ResponseStatusException(HttpStatus.NOT_FOUND,"Event not found"));access.require(e.organizationId,owner,true);return e;}
 private void validate(Draft input){if(!input.endsAt().isAfter(input.startsAt()))throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"End must be after start");}
 public record EventPage(List<Event.View> items,int page,int size,long totalElements,int totalPages){}
}
