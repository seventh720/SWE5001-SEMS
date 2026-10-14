package com.sems.platform.identity.internal.application;
import org.junit.jupiter.api.Test;
import org.springframework.web.server.ResponseStatusException;
import static org.junit.jupiter.api.Assertions.*;
class UsernamePolicyTest {
 @Test void normalizesAndAcceptsCommonNames() { assertEquals("alex.tan-2", UsernamePolicy.normalize(" Alex.Tan-2 ")); }
 @Test void rejectsInvalidAndReservedNames() {
  for(String name : new String[]{"ab", "bad name", "<script>", "...", "Admin", "SUPPORT", "x".repeat(51)})
   assertThrows(ResponseStatusException.class, () -> UsernamePolicy.normalize(name), name);
 }
}
