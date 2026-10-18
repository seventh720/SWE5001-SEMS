package com.sems.platform.identity;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.web.client.*;
@Service
public class OrganizationClosureWorker {
 private final OrganizationClosureState state;private final RestClient client;
 public record Result(boolean complete){}
 public OrganizationClosureWorker(OrganizationClosureState state,@Value("${CATALOG_URL:http://event-catalog:8082}") String url,@Value("${ORGANIZATION_ACCESS_TOKEN}") String token){
  this.state=state;var factory=new org.springframework.http.client.SimpleClientHttpRequestFactory();factory.setConnectTimeout(2000);factory.setReadTimeout(3000);
  client=RestClient.builder().baseUrl(url).requestFactory(factory).defaultHeader("X-Service-Token",token).build();
 }
 @Scheduled(fixedDelayString="${sems.organization-closure.retry-ms:5000}")
 public void recover(){for(var op:state.pending()){
  state.attempted(op);
  try{var result=client.post().uri("/internal/v1/organization-closures/{id}",op.organizationId()).body(op).retrieve().body(Result.class);if(result!=null&&result.complete())state.finish(op);}
  catch(RestClientException e){/* Durable intent is retained; neither access nor publication is restored. */}
 }}
}
