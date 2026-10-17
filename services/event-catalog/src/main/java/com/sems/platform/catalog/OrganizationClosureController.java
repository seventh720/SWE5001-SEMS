package com.sems.platform.catalog;
import java.util.UUID;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotNull;
import org.springframework.web.bind.annotation.*;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;
@RestController
public class OrganizationClosureController {
 private final OrganizationClosureState state;
 public OrganizationClosureController(OrganizationClosureState state){this.state=state;}
 public record Request(@NotNull UUID organizationId,@NotNull UUID operationId,@NotNull java.time.Instant requestedAt){}
 public record Result(boolean complete){}
 @PostMapping("/internal/v1/organization-closures/{id}")
 public Result close(@PathVariable UUID id,@Valid @RequestBody Request input){
  if(!id.equals(input.organizationId()))throw new ResponseStatusException(HttpStatus.CONFLICT,"Organization mismatch");
  state.freeze(id,input.operationId(),input.requestedAt());for(var event:state.candidates(id))state.cancel(id,event);return new Result(state.complete(id));
 }
}
