package com.sems.platform.catalog;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.List;
import jakarta.servlet.*;
import jakarta.servlet.http.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.*;
import org.springframework.core.annotation.Order;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.AnonymousAuthenticationFilter;
import org.springframework.web.filter.OncePerRequestFilter;

@Configuration
public class InternalSecurityConfiguration {
    @Bean @Order(1)
    SecurityFilterChain internalSecurity(HttpSecurity http,
            @Value("${sems.internal.inbound-token}") String secret,@Value("${ORGANIZATION_ACCESS_TOKEN}") String organizationSecret) throws Exception {
        if (secret.length() < 32) throw new IllegalArgumentException("Internal token must be at least 32 characters");
        var filter = new OncePerRequestFilter() {
            @Override protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response,
                    FilterChain chain) throws ServletException, IOException {
                String supplied = request.getHeader("X-Service-Token");
                String expected=request.getRequestURI().startsWith("/internal/v1/organization-closures/")?organizationSecret:secret;
                if (supplied == null || !MessageDigest.isEqual(expected.getBytes(StandardCharsets.UTF_8), supplied.getBytes(StandardCharsets.UTF_8))) {
                    response.sendError(401); return;
                }
                SecurityContextHolder.getContext().setAuthentication(
                        new UsernamePasswordAuthenticationToken("service", null, List.of(new SimpleGrantedAuthority("ROLE_SERVICE"))));
                chain.doFilter(request, response);
            }
        };
        return http.securityMatcher("/internal/**").csrf(c -> c.disable())
                .sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
                .authorizeHttpRequests(a -> a.anyRequest().hasRole("SERVICE"))
                .addFilterBefore(filter, AnonymousAuthenticationFilter.class).build();
    }
}
