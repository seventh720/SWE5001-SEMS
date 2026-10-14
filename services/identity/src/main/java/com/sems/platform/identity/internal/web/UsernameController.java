package com.sems.platform.identity.internal.web;
import com.sems.platform.identity.UserView;
import com.sems.platform.identity.internal.application.AuthService;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.oauth2.jwt.Jwt;
import org.springframework.web.bind.annotation.*;
@RestController
@RequestMapping("/api/v1/profile/username")
public class UsernameController {
 private final AuthService service;
 public UsernameController(AuthService service){this.service=service;}
 public record Rename(@NotBlank @Size(max=50) String username) {}
 @GetMapping public AuthService.UsernameAvailability check(@AuthenticationPrincipal Jwt jwt,@RequestParam String value){return service.usernameAvailability(jwt.getSubject(),value);}
 @PutMapping public UserView rename(@AuthenticationPrincipal Jwt jwt,@Valid @RequestBody Rename request){return service.rename(jwt.getSubject(),request.username());}
}
