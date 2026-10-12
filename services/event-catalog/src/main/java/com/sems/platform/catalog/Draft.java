package com.sems.platform.catalog;
import jakarta.validation.constraints.*;
import java.time.Instant;
public record Draft(
 @NotBlank @Size(max=200) String title,
 @NotBlank @Size(max=10000) String description,
 @NotBlank @Size(max=500) String location,
 @NotNull Instant startsAt, @NotNull Instant endsAt,
 @NotNull @Min(1) Integer capacity,
 @Min(0) Long version) {}
