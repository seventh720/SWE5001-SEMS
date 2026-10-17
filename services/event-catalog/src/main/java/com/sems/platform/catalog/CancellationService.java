package com.sems.platform.catalog;
import org.springframework.stereotype.Service;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.web.client.*;
@Service
public class CancellationService {
 private final CancellationState state;private final RestClient client;
 public CancellationService(CancellationState state,RestClient client){this.state=state;this.client=client;}
 public boolean advance(CancellationState.Operation op){
  if(state.completed(op))return true;
  try{client.post().uri("/internal/v1/events/{id}/cancel",op.eventId()).body(op).retrieve().toBodilessEntity();}
  catch(RestClientException ex){state.retryLater(op);return false;}
  state.finish(op);return true;
 }
 @Scheduled(fixedDelayString="${sems.cancellation.retry-ms:5000}")
 public void recover(){for(var op:state.pending())advance(op);}
}
