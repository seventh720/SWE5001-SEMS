package com.sems.platform.catalog;
import java.util.*;
import org.springframework.stereotype.Component;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpStatus;
import org.springframework.web.client.*;
import org.springframework.web.server.ResponseStatusException;
@Component
public class OrganizationAccess {
 public record Membership(UUID id,String name,String slug,String status,String role){}
 private final RestClient client;
 public OrganizationAccess(@Value("${IDENTITY_URL:http://identity:8081}") String url,@Value("${ORGANIZATION_ACCESS_TOKEN}") String token){var factory=new org.springframework.http.client.SimpleClientHttpRequestFactory();factory.setConnectTimeout(2000);factory.setReadTimeout(3000);client=RestClient.builder().baseUrl(url).requestFactory(factory).defaultHeader("X-Service-Token",token).build();}
 public List<Membership> memberships(UUID user){if(user==null)return List.of();try{return Arrays.asList(Objects.requireNonNull(client.get().uri("/internal/v1/users/{id}/organizations",user).retrieve().body(Membership[].class)));}catch(RestClientException e){throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE,"Organization access service unavailable; retry later");}}
 public Membership require(UUID org,UUID user,boolean manage){return memberships(user).stream().filter(m->m.id().equals(org)&&(!manage||m.role().equals("ORG_ADMIN")||m.role().equals("ORGANIZER"))).findFirst().orElseThrow(()->new ResponseStatusException(HttpStatus.NOT_FOUND,"Organization or event not found"));}
 public List<Membership> activeOrganizations(List<UUID> ids){
  if(ids.isEmpty())return List.of();
  try{return Arrays.asList(Objects.requireNonNull(client.post().uri("/internal/v1/organizations/lookup").body(Map.of("ids",ids)).retrieve().body(Membership[].class)));}
  catch(RestClientException e){throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE,"Organization access service unavailable; retry later");}
 }
 public Membership active(UUID org){return activeOrganizations(List.of(org)).stream().findFirst().orElseThrow(()->new ResponseStatusException(HttpStatus.NOT_FOUND,"Organization or event not found"));}
}
