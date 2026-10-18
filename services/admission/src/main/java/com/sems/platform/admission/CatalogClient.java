package com.sems.platform.admission;

import java.util.*;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;
import org.springframework.web.client.*;
import org.springframework.web.server.ResponseStatusException;
import static com.sems.platform.admission.TicketContracts.*;
@Component
public class CatalogClient {
    public record EventDetails(UUID id,String title,String location,java.time.Instant startsAt,java.time.Instant endsAt,String status) {}
    public Map<UUID,EventDetails> details(List<UUID> ids) {
        if (ids.isEmpty()) return Map.of();
        try {
            var rows=Objects.requireNonNull(client.post().uri("/internal/v1/events/details").body(Map.of("ids",ids.stream().distinct().toList())).retrieve().body(EventDetails[].class));
            return Arrays.stream(rows).collect(java.util.stream.Collectors.toMap(EventDetails::id,java.util.function.Function.identity()));
        } catch(RestClientException e) {
            throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE,"Current event details unavailable; retry later");
        }
    }
    private final RestClient client;
    public CatalogClient(RestClient client) { this.client=client; }
    public Snapshot owned(UUID event, UUID owner) {
        return request(() -> client.get().uri("/internal/v1/events/{id}?owner={owner}",event,owner).retrieve().body(Snapshot.class));
    }
    public Snapshot prepare(UUID event, UUID owner, long version) {
        return request(() -> client.post().uri("/internal/v1/events/{id}/prepare-sales",event)
                .body(Map.of("owner",owner,"version",version)).retrieve().body(Snapshot.class));
    }
    public Snapshot member(UUID event,UUID user) {return request(()->client.get().uri("/internal/v1/events/{id}/member?user={user}",event,user).retrieve().body(Snapshot.class));}
    public Snapshot published(UUID event,UUID user) {
        return request(() -> client.get().uri(b->b.path("/internal/v1/events/{id}/published").queryParamIfPresent("user",Optional.ofNullable(user)).build(event)).retrieve().body(Snapshot.class));
    }
    private Snapshot request(java.util.function.Supplier<Snapshot> call) {
        try { return Objects.requireNonNull(call.get()); }
        catch (RestClientResponseException e) {
            if (e.getStatusCode().value()==404) throw new ResponseStatusException(HttpStatus.NOT_FOUND,"Event not found");
            if (e.getStatusCode().value()==409) throw new ResponseStatusException(HttpStatus.CONFLICT,"Event changed or is no longer a draft; reload it");
            throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE,"Catalog unavailable; retry later");
        } catch (RestClientException e) { throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE,"Catalog unavailable; retry later"); }
    }
}
