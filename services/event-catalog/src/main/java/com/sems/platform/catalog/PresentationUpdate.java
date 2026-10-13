package com.sems.platform.catalog;
import jakarta.validation.constraints.*;
public record PresentationUpdate(@NotBlank @Size(max=200) String title,@NotBlank @Size(max=10000) String description,@NotBlank @Size(max=500) String location,@NotNull EventCategory category,@NotNull CardTheme cardTheme,@NotNull @Min(0) Long version) {}
