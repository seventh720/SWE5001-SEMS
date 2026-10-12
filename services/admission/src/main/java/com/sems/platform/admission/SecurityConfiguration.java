package com.sems.platform.admission;
import java.nio.file.*;
import java.security.*;
import java.security.interfaces.*;
import java.security.spec.*;
import java.util.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.*;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.oauth2.core.*;
import org.springframework.security.oauth2.jwt.*;
import org.springframework.security.oauth2.server.resource.authentication.*;
import org.springframework.security.web.SecurityFilterChain;
@Configuration
@EnableMethodSecurity
public class SecurityConfiguration {
 @Bean RSAPublicKey publicKey(@Value("${sems.jwt.public-key}") String path) throws Exception {
  String pem=Files.readString(Path.of(path)).replace("-----BEGIN PUBLIC KEY-----", "").replace("-----END PUBLIC KEY-----", "").replaceAll("\\s", "");
  return (RSAPublicKey)KeyFactory.getInstance("RSA").generatePublic(new X509EncodedKeySpec(Base64.getDecoder().decode(pem)));
 }
 @Bean JwtDecoder decoder(RSAPublicKey key, @Value("${sems.jwt.issuer}") String issuer) {
  var decoder=NimbusJwtDecoder.withPublicKey(key).build();
  OAuth2TokenValidator<Jwt> required=jwt -> {
   boolean valid=jwt.getAudience()!=null && jwt.getAudience().contains("sems-platform") && jwt.getExpiresAt()!=null;
   try { UUID.fromString(jwt.getSubject()); } catch(Exception e) { valid=false; }
   return valid ? OAuth2TokenValidatorResult.success() : OAuth2TokenValidatorResult.failure(new OAuth2Error("invalid_token"));
  };
  decoder.setJwtValidator(new DelegatingOAuth2TokenValidator<>(JwtValidators.createDefaultWithIssuer(issuer),required));return decoder;
 }
 @Bean @org.springframework.core.annotation.Order(2) SecurityFilterChain security(HttpSecurity http) throws Exception {
  var roles=new JwtGrantedAuthoritiesConverter();roles.setAuthoritiesClaimName("roles");roles.setAuthorityPrefix("ROLE_");
  var converter=new JwtAuthenticationConverter();converter.setJwtGrantedAuthoritiesConverter(roles);
  return http.csrf(c->c.disable()).sessionManagement(s->s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
   .authorizeHttpRequests(a->a.requestMatchers("/actuator/health", "/actuator/health/**").permitAll().requestMatchers(org.springframework.http.HttpMethod.GET,"/api/v1/events/*/ticket-types").permitAll().anyRequest().authenticated())
   .oauth2ResourceServer(o->o.jwt(j->j.jwtAuthenticationConverter(converter))).build();
 }

}
