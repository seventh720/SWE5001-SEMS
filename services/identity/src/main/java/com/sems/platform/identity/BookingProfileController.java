package com.sems.platform.identity;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import java.util.UUID;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.http.*;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.*;
@RestController
@RequestMapping("/api/v1/profile")
public class BookingProfileController {
 private final JdbcTemplate jdbc;
 public BookingProfileController(JdbcTemplate jdbc){this.jdbc=jdbc;}
 public record Profile(@Size(max=100) String realName,@Email @Size(max=254) String email,@Size(max=40) String phone,@Size(max=100) String studentId,@Size(max=100) String passportNumber) {
  public Profile {realName=clean(realName);email=clean(email);phone=clean(phone);studentId=null;passportNumber=clean(passportNumber);}
  private static String clean(String s){return s==null||s.isBlank()?null:s.trim();}
 }
 private ResponseEntity<Profile> response(Profile p){return ResponseEntity.ok().cacheControl(CacheControl.noStore()).body(p);}
 @GetMapping public ResponseEntity<Profile> get(@AuthenticationPrincipal Jwt jwt){
  var rows=jdbc.query("SELECT * FROM booking_profiles WHERE user_id=? AND id=user_id",(rs,n)->new Profile(rs.getString("real_name"),rs.getString("email"),rs.getString("phone"),null,rs.getString("passport_number")),UUID.fromString(jwt.getSubject()));
  return response(rows.isEmpty()?new Profile(null,null,null,null,null):rows.getFirst());
 }
 @PutMapping public ResponseEntity<Profile> save(@AuthenticationPrincipal Jwt jwt,@Valid @RequestBody Profile p){
  var owner=UUID.fromString(jwt.getSubject());
  jdbc.update("INSERT INTO booking_profiles(id,user_id,real_name,email,phone,passport_number) VALUES (?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET real_name=EXCLUDED.real_name,email=EXCLUDED.email,phone=EXCLUDED.phone,passport_number=EXCLUDED.passport_number,version=booking_profiles.version+1",owner,owner,p.realName(),p.email(),p.phone(),p.passportNumber());return response(p);
 }
 @DeleteMapping public ResponseEntity<Void> clear(@AuthenticationPrincipal Jwt jwt){jdbc.update("DELETE FROM booking_profiles WHERE user_id=? AND id=user_id",UUID.fromString(jwt.getSubject()));return ResponseEntity.noContent().cacheControl(CacheControl.noStore()).build();}
}
