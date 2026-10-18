package com.sems.platform.identity.internal.application;
import com.sems.platform.identity.internal.domain.UserAccount;
import java.time.Instant;
import java.util.List;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.oauth2.jwt.*;
import org.springframework.security.oauth2.jose.jws.SignatureAlgorithm;
import org.springframework.stereotype.Service;
@Service
public class TokenService {
 private final JwtEncoder encoder; private final String issuer;
 public TokenService(JwtEncoder encoder,@Value("${sems.jwt.issuer}") String issuer){this.encoder=encoder;this.issuer=issuer;}
 public IssuedToken issue(UserAccount user){
  var now=Instant.now();
  var claims=JwtClaimsSet.builder().issuer(issuer).subject(user.getId().toString()).audience(List.of("sems-platform"))
   .issuedAt(now).expiresAt(now.plusSeconds(3600)).claim("roles",user.getRoles().stream().map(Enum::name).sorted().toList()).build();
  return new IssuedToken(encoder.encode(JwtEncoderParameters.from(JwsHeader.with(SignatureAlgorithm.RS256).keyId("sems-1").build(),claims)).getTokenValue(),3600);
 }
 public record IssuedToken(String value,long expiresInSeconds){}
}
