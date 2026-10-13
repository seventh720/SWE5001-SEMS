package com.sems.platform.admission;
import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;
import org.springframework.web.server.ResponseStatusException;
class AttendeeInfoTest {
 @Test void normalizedRetryDataHasStableEquality() {
  assertEquals(new AttendeeInfo("Alice",null,null,null,null,null),new AttendeeInfo(" Alice ","",null,null,null,null));
 }
 @Test void requiresRequestedFieldsAndRejectsUnrequestedPersonalData() {
  var r=new RegistrationRequirements(true,true,false,false,false,"Dietary needs");
  assertThrows(ResponseStatusException.class,()->AttendeeInfo.empty().validate(r));
  assertDoesNotThrow(()->new AttendeeInfo("Alice","alice@example.com",null,null,null,"None").validate(r));
  assertThrows(ResponseStatusException.class,()->new AttendeeInfo("Alice","alice@example.com",null,null,"passport","None").validate(r));
 }
}
