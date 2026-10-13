package com.sems.platform.admission;
import java.time.Instant;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
class PreRegistrationTest {
 @Test void openingAndClosingBoundaries(){var open=Instant.parse("2030-01-01T00:00:00Z");var close=open.plusSeconds(100);var start=close.plusSeconds(100);
 assertEquals("WAITING",PreRegistrationService.status(open.minusSeconds(1),open,close,start,"ACTIVE",10));
 assertEquals("READY",PreRegistrationService.status(open,open,close,start,"ACTIVE",10));
 assertEquals("SOLD_OUT",PreRegistrationService.status(open,open,close,start,"ACTIVE",0));
 assertEquals("CLOSED",PreRegistrationService.status(close,open,close,start,"ACTIVE",10));
 assertEquals("CLOSED",PreRegistrationService.status(open,open,close,start,"DRAFT",10));
 }
}
