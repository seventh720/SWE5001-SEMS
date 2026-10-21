package com.sems.platform.catalog;

import static org.junit.jupiter.api.Assertions.*;

import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.Test;

class CatalogDiagnosticsTest {
    @Test void reportsReadAndPoolTimingWithoutOtherApplicationMeters() {
        var registry = new SimpleMeterRegistry();
        var timings = new CatalogTimings(registry);
        assertEquals("value", timings.read("public-detail", () -> "value"));
        assertThrows(IllegalStateException.class,
                () -> timings.identity("active-organizations", () -> { throw new IllegalStateException(); }));
        registry.timer("hikaricp.connections.acquire", "pool", "catalog").record(25, TimeUnit.MILLISECONDS);
        registry.timer("hikaricp.connections.usage", "pool", "catalog").record(50, TimeUnit.MILLISECONDS);
        registry.gauge("hikaricp.connections.pending", 3);
        registry.counter("unrelated", "email", "private@example.com").increment();
        var response = new CatalogDiagnosticsController(registry).snapshot();
        assertEquals("no-store", response.getHeaders().getCacheControl());
        var result = response.getBody();
        assertNotNull(result);
        assertEquals(4, result.timers().size());
        assertTrue(result.timers().stream().allMatch(t -> t.count() == 1));
        assertEquals(25, result.timers().stream().filter(t -> t.name().endsWith("acquire")).findFirst().orElseThrow().totalMs());
        assertEquals(50, result.timers().stream().filter(t -> t.name().endsWith("usage")).findFirst().orElseThrow().totalMs());
        assertEquals(3, result.pool().getFirst().value());
        assertFalse(result.toString().contains("private@example.com"));
    }
}
