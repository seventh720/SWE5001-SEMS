package com.sems.platform.admission;

import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import java.time.Instant;
import java.util.*;
public class TicketContracts {
    public record TicketInput(@NotBlank @Size(max=100) String name, @Min(1) int quota,
            @NotNull Instant opensAt, @NotNull Instant closesAt) {}
    public record Configuration(@Min(0) long eventVersion, @Min(0) long version,
            @NotEmpty @Size(max=20) List<@NotNull @Valid TicketInput> ticketTypes) {}
    public record Snapshot(UUID id, UUID organizerId, int capacity, Instant startsAt, Instant endsAt, String status, String title, String location, RegistrationRequirements registrationRequirements,UUID organizationId,String visibility) {
        public Snapshot(UUID id,UUID organizerId,int capacity,Instant startsAt,Instant endsAt,String status,String title,String location,RegistrationRequirements requirements){this(id,organizerId,capacity,startsAt,endsAt,status,title,location,requirements,null,"PUBLIC");}
        public Snapshot { registrationRequirements=registrationRequirements==null?RegistrationRequirements.none():registrationRequirements; }
        public Snapshot(UUID id,UUID organizerId,int capacity,Instant startsAt,Instant endsAt,String status,String title,String location) {
            this(id,organizerId,capacity,startsAt,endsAt,status,title,location,RegistrationRequirements.none(),null,"PUBLIC");
        }
    }
    public record Activate(@NotNull UUID operationId, @NotNull UUID organizerId,
            @Min(1) int capacity, @NotNull Instant startsAt, @NotNull Instant endsAt, @Min(1) long ticketVersion,UUID organizationId) {}
    public record TicketView(UUID id, String name, int quota, int available, Instant opensAt, Instant closesAt, int amount) {}
    public record Inventory(UUID eventId, long version, String state, List<TicketView> ticketTypes) {}
}
