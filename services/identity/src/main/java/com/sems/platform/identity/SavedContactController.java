package com.sems.platform.identity;

import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import java.util.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.http.*;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/api/v1/profile/contacts")
public class SavedContactController {
 private final JdbcTemplate jdbc;
 public SavedContactController(JdbcTemplate jdbc){this.jdbc=jdbc;}
 public record Contact(UUID id, @NotBlank @Size(max=60) String label,
   @Size(max=100) String realName, @Email @Size(max=254) String email,
   @Size(max=40) String phone, @Size(max=100) String passportNumber, @Min(0) long version) {
   public Contact {label=clean(label);realName=clean(realName);email=clean(email);phone=clean(phone);passportNumber=clean(passportNumber);}
 }
 static String clean(String s){return s==null||s.isBlank()?null:s.strip();}
 private static UUID owner(Jwt jwt){return UUID.fromString(jwt.getSubject());}
 private <T> ResponseEntity<T> response(T data){return ResponseEntity.ok().cacheControl(CacheControl.noStore()).body(data);}
 @GetMapping public ResponseEntity<List<Contact>> list(@AuthenticationPrincipal Jwt jwt){
  return response(jdbc.query("SELECT * FROM booking_profiles WHERE user_id=? ORDER BY lower(label),id",(rs,n)->new Contact(rs.getObject("id",UUID.class),rs.getString("label"),rs.getString("real_name"),rs.getString("email"),rs.getString("phone"),rs.getString("passport_number"),rs.getLong("version")),owner(jwt)));
 }
 @PostMapping public ResponseEntity<Contact> create(@AuthenticationPrincipal Jwt jwt,@Valid @RequestBody Contact c){
  UUID id=UUID.randomUUID();
  jdbc.update("INSERT INTO booking_profiles(id,user_id,label,real_name,email,phone,passport_number) VALUES(?,?,?,?,?,?,?)",id,owner(jwt),c.label(),c.realName(),c.email(),c.phone(),c.passportNumber());
  return response(new Contact(id,c.label(),c.realName(),c.email(),c.phone(),c.passportNumber(),0));
 }
 @PutMapping("/{id}") public ResponseEntity<Contact> update(@AuthenticationPrincipal Jwt jwt,@PathVariable UUID id,@Valid @RequestBody Contact c){
  int changed=jdbc.update("UPDATE booking_profiles SET label=?,real_name=?,email=?,phone=?,passport_number=?,version=version+1 WHERE id=? AND user_id=? AND version=?",c.label(),c.realName(),c.email(),c.phone(),c.passportNumber(),id,owner(jwt),c.version());
  if(changed==0) fail(id,owner(jwt));
  return response(new Contact(id,c.label(),c.realName(),c.email(),c.phone(),c.passportNumber(),c.version()+1));
 }
 @DeleteMapping("/{id}") public ResponseEntity<Void> delete(@AuthenticationPrincipal Jwt jwt,@PathVariable UUID id,@RequestParam long version){
  if(jdbc.update("DELETE FROM booking_profiles WHERE id=? AND user_id=? AND version=?",id,owner(jwt),version)==0) fail(id,owner(jwt));
  return ResponseEntity.noContent().cacheControl(CacheControl.noStore()).build();
 }
 private void fail(UUID id,UUID owner){
  boolean exists=Boolean.TRUE.equals(jdbc.queryForObject("SELECT EXISTS(SELECT 1 FROM booking_profiles WHERE id=? AND user_id=?)",Boolean.class,id,owner));
  throw new ResponseStatusException(exists?HttpStatus.CONFLICT:HttpStatus.NOT_FOUND,exists?"These details changed. Reload before saving.":"Saved contact not found");
 }
}
