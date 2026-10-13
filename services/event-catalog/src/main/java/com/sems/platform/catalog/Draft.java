package com.sems.platform.catalog;
import jakarta.validation.constraints.*;
import java.time.Instant;
public record Draft(
 @NotBlank @Size(max=200) String title,
 @NotBlank @Size(max=10000) String description,
 @NotBlank @Size(max=500) String location,
 @NotNull Instant startsAt, @NotNull Instant endsAt,
 @NotNull @Min(1) Integer capacity,
 @Min(0) Long version, EventCategory category, CardTheme cardTheme,
 @jakarta.validation.Valid RegistrationRequirements registrationRequirements) {
 public Draft { category=category==null?EventCategory.GENERAL:category; cardTheme=cardTheme==null?CardTheme.LILAC:cardTheme; registrationRequirements=registrationRequirements==null?RegistrationRequirements.none():registrationRequirements; }
 public Draft(String title,String description,String location,Instant startsAt,Instant endsAt,Integer capacity,Long version) {
  this(title,description,location,startsAt,endsAt,capacity,version,EventCategory.GENERAL,CardTheme.LILAC,RegistrationRequirements.none());
 }
}
