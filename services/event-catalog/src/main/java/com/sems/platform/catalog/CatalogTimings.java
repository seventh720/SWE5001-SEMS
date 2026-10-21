package com.sems.platform.catalog;

import io.micrometer.core.instrument.MeterRegistry;
import java.util.function.Supplier;
import org.springframework.stereotype.Component;

@Component
public class CatalogTimings {
    private final MeterRegistry registry;

    public CatalogTimings(MeterRegistry registry) { this.registry = registry; }

    public <T> T read(String operation, Supplier<T> action) {
        return registry.timer("catalog.read", "operation", operation).record(action);
    }

    public <T> T identity(String operation, Supplier<T> action) {
        return registry.timer("catalog.identity", "operation", operation).record(action);
    }
}
