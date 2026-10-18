package com.sems.platform.catalog;
import java.util.UUID;
import org.springframework.stereotype.Service;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.web.client.*;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.http.HttpStatus;
@Service
public class RevisionService {
 private final RevisionState state;private final DraftService drafts;private final RestClient client;
 public RevisionService(RevisionState state,DraftService drafts,RestClient client){this.state=state;this.drafts=drafts;this.client=client;}
 public Event.View update(UUID owner,UUID id,Draft input){advance(state.begin(owner,id,input));return drafts.detail(owner,id);}
 public void advance(RevisionState.Operation op){
  try{client.post().uri("/internal/v1/events/{id}/revise",op.eventId()).body(op).retrieve().toBodilessEntity();}
  catch(RestClientResponseException e){org.slf4j.LoggerFactory.getLogger(getClass()).warn("Catalog command pending/rejected event={} operation={} httpStatus={}",op.eventId(),op.operationId(),e.getStatusCode().value());if(e.getStatusCode().value()==409){String message="Update rejected. Review ticket quotas, sales windows and versions. Quotas cannot fall below issued places, and ticket types used by bookings or pre-registrations cannot be removed. Reload before retrying.";state.reject(op,message);throw new ResponseStatusException(HttpStatus.CONFLICT,message);}return;}
  catch(RestClientException e){org.slf4j.LoggerFactory.getLogger(getClass()).warn("Revision retry pending event={} operation={} failure={}",op.eventId(),op.operationId(),e.getClass().getSimpleName());return;}
  state.finish(op);
 }
 @Scheduled(fixedDelayString="${sems.publication.retry-ms:5000}") public void recover(){for(var op:state.pending())try{advance(op);}catch(ResponseStatusException ignored){}}
}
