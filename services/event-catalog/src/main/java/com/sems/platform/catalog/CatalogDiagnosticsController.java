package com.sems.platform.catalog;

import io.micrometer.core.instrument.Gauge;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;
import java.util.*;
import java.util.concurrent.TimeUnit;
import org.springframework.http.CacheControl;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

/** Uses the existing internal service-token filter; never routed by the public gateway. */
@RestController
public class CatalogDiagnosticsController {
    private final MeterRegistry registry;
    private static final Set<String> TIMERS = Set.of("catalog.read", "catalog.identity",
            "hikaricp.connections.acquire", "hikaricp.connections.usage");
    private static final Set<String> GAUGES = Set.of("hikaricp.connections", "hikaricp.connections.active",
            "hikaricp.connections.idle", "hikaricp.connections.pending", "hikaricp.connections.max");

    public CatalogDiagnosticsController(MeterRegistry registry) { this.registry = registry; }

    public record Timing(String name, String operation, String pool, long count,
                         double totalMs, double maxMs) {}
    public record PoolGauge(String name, String pool, double value) {}
    public record Snapshot(List<Timing> timers, List<PoolGauge> pool) {}

    @GetMapping("/internal/v1/diagnostics/catalog")
    public ResponseEntity<Snapshot> snapshot() {
        var timers = new ArrayList<Timing>();
        var pool = new ArrayList<PoolGauge>();
        for (var meter : registry.getMeters()) {
            var id = meter.getId();
            if (meter instanceof Timer timer && TIMERS.contains(id.getName())) {
                timers.add(new Timing(id.getName(), id.getTag("operation"), id.getTag("pool"),
                        timer.count(), timer.totalTime(TimeUnit.MILLISECONDS), timer.max(TimeUnit.MILLISECONDS)));
            } else if (meter instanceof Gauge gauge && GAUGES.contains(id.getName())) {
                double value = gauge.value();
                if (Double.isFinite(value)) pool.add(new PoolGauge(id.getName(), id.getTag("pool"), value));
            }
        }
        timers.sort(Comparator.comparing(Timing::name).thenComparing(t -> Objects.toString(t.operation(), ""))
                .thenComparing(t -> Objects.toString(t.pool(), "")));
        pool.sort(Comparator.comparing(PoolGauge::name).thenComparing(g -> Objects.toString(g.pool(), "")));
        return ResponseEntity.ok().cacheControl(CacheControl.noStore()).body(new Snapshot(timers, pool));
    }
}
