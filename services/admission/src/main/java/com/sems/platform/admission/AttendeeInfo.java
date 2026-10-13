package com.sems.platform.admission;
import jakarta.validation.constraints.*;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;
public record AttendeeInfo(@Size(max=100) String realName, @Email @Size(max=254) String email,
 @Size(max=40) String phone, @Size(max=100) String studentId, @Size(max=100) String passportNumber,
 @Size(max=500) String customAnswer) {
 public AttendeeInfo {realName=clean(realName);email=clean(email);phone=clean(phone);studentId=clean(studentId);passportNumber=clean(passportNumber);customAnswer=clean(customAnswer);}
 private static String clean(String s){return s==null||s.isBlank()?null:s.strip();}
 public static AttendeeInfo empty(){return new AttendeeInfo(null,null,null,null,null,null);}
 public void validate(RegistrationRequirements r){
  check(r.realName(),realName,"Full name");check(r.email(),email,"Contact email");check(r.phone(),phone,"Phone number");
  check(r.studentId(),studentId,"Student ID");check(r.passport(),passportNumber,"Passport number");check(r.customFieldLabel()!=null,customAnswer,"Custom answer");
 }
 private void check(boolean required,String value,String label){
  if(required&&value==null)throw new ResponseStatusException(HttpStatus.BAD_REQUEST,label+" is required for this event");
  if(!required&&value!=null)throw new ResponseStatusException(HttpStatus.BAD_REQUEST,label+" is not requested by this event");
 }
}
