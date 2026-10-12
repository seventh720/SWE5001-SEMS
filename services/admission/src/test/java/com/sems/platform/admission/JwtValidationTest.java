package com.sems.platform.admission;

import static org.junit.jupiter.api.Assertions.*;
import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.interfaces.RSAPublicKey;
import java.security.interfaces.RSAPrivateKey;
import java.time.Instant;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.springframework.security.oauth2.jwt.*;
import org.springframework.security.oauth2.jose.jws.SignatureAlgorithm;
import com.nimbusds.jose.jwk.*;
import com.nimbusds.jose.jwk.source.ImmutableJWKSet;

class JwtValidationTest {
    KeyPair key() throws Exception {
        var generator = KeyPairGenerator.getInstance("RSA");
        generator.initialize(2048);
        return generator.generateKeyPair();
    }

    String token(KeyPair pair, String issuer, String audience, Instant expiry) {
        var jwk = new RSAKey.Builder((RSAPublicKey) pair.getPublic())
                .privateKey((RSAPrivateKey) pair.getPrivate()).build();
        var encoder = new NimbusJwtEncoder(new ImmutableJWKSet<>(new JWKSet(jwk)));
        var claims = JwtClaimsSet.builder().issuer(issuer).subject(UUID.randomUUID().toString())
                .audience(List.of(audience)).issuedAt(Instant.now().minusSeconds(600))
                .expiresAt(expiry).build();
        return encoder.encode(JwtEncoderParameters.from(
                JwsHeader.with(SignatureAlgorithm.RS256).build(), claims)).getTokenValue();
    }

    @Test void rejectsWrongIssuerAudienceExpiredAndForeignSignature() throws Exception {
        var pair = key();
        var decoder = new SecurityConfiguration().decoder((RSAPublicKey) pair.getPublic(), "sems-identity");
        var later = Instant.now().plusSeconds(300);
        assertNotNull(decoder.decode(token(pair, "sems-identity", "sems-platform", later)));
        assertThrows(JwtException.class, () -> decoder.decode(token(pair, "other", "sems-platform", later)));
        assertThrows(JwtException.class, () -> decoder.decode(token(pair, "sems-identity", "other", later)));
        assertThrows(JwtException.class, () -> decoder.decode(token(pair, "sems-identity", "sems-platform", Instant.now().minusSeconds(300))));
        var foreign = key();
        assertThrows(JwtException.class, () -> decoder.decode(token(foreign, "sems-identity", "sems-platform", later)));
    }
}
