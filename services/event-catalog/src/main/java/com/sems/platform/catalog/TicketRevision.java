package com.sems.platform.catalog;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import java.time.Instant;
import java.util.*;
public record TicketRevision(@NotNull @Min(0) Long version, @NotEmpty @Size(max=20) List<@NotNull @Valid Item> ticketTypes) {
 public record Item(UUID id, @NotBlank @Size(max=100) String name, @Min(1) int quota, @NotNull Instant opensAt, @NotNull Instant closesAt) {}
}
