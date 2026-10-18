package com.sems.platform.identity.internal.application;

import com.sems.platform.identity.internal.domain.UserAccount;
import org.junit.jupiter.api.Test;
import org.springframework.security.oauth2.jwt.*;
import static org.mockito.Mockito.*;
import static org.junit.jupiter.api.Assertions.*;
class TokenLifetimeTest {
    @Test void issuesOneHourToken() {
        var encoder=mock(JwtEncoder.class);
        when(encoder.encode(any())).thenAnswer(call->{
            var params=call.getArgument(0,JwtEncoderParameters.class);
            assertEquals(3600,java.time.Duration.between(params.getClaims().getIssuedAt(),params.getClaims().getExpiresAt()).getSeconds());
            return Jwt.withTokenValue("signed").header("alg","RS256").claims(c->c.putAll(params.getClaims().getClaims())).build();
        });
        var issued=new TokenService(encoder,"sems-identity").issue(UserAccount.bootstrapAdmin("admin","a@example.com","hash"));
        assertEquals(3600,issued.expiresInSeconds());
    }
}
