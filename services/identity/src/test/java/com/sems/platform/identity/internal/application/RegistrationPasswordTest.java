package com.sems.platform.identity.internal.application;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.sems.platform.identity.ApiExceptionHandler;
import com.sems.platform.identity.internal.persistence.UserAccountRepository;
import com.sems.platform.identity.internal.web.AuthController;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.http.MediaType;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.server.ResponseStatusException;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

class RegistrationPasswordTest {
    private final UserAccountRepository users = mock(UserAccountRepository.class);
    private final PasswordEncoder encoder = mock(PasswordEncoder.class);
    private final AuthService auth = new AuthService(users, encoder, mock(TokenService.class));
    private MockMvc mvc;

    @BeforeEach
    void setup() {
        mvc = MockMvcBuilders.standaloneSetup(new AuthController(auth))
                .setControllerAdvice(new ApiExceptionHandler()).build();
    }

    @ParameterizedTest
    @ValueSource(strings = {"abcdefgh", "12345678", "Ab123456", "Ab12345678901234",
            "Passw0rd!", "!@#$%^&*", "[]{}()\\\"", "<>;'`~?/", "Ab12!@#$%^&*()_+"})
    void acceptsLettersNumbersAndPrintableSymbolsAtLengthBoundaries(String password) throws Exception {
        when(encoder.encode(password)).thenReturn("hash");
        when(users.saveAndFlush(any())).thenAnswer(invocation -> invocation.getArgument(0));

        mvc.perform(post("/api/v1/auth/register").contentType(MediaType.APPLICATION_JSON)
                .content(body(password)))
                .andExpect(status().isCreated())
                .andExpect(jsonPath("username").value("alice"));

        verify(encoder).encode(password);
        verify(users).saveAndFlush(any());
    }

    @ParameterizedTest
    @ValueSource(strings = {"", "Ab12345", "Ab123456789012345", "Passw0rd！", "Pass word", "Pass\tword",
            "密码Ab123456", "Ａb123456", "Ab123456\n", " Ab123456", "Ab123456 "})
    void rejectsInvalidPasswordsInBothHttpAndApplicationEntryPoints(String password) throws Exception {
        mvc.perform(post("/api/v1/auth/register").contentType(MediaType.APPLICATION_JSON)
                .content(body(password)))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("fieldErrors.password").value(PasswordPolicy.MESSAGE));

        var exception = assertThrows(ResponseStatusException.class,
                () -> auth.register("alice", "alice@example.com", password));
        assertEquals(400, exception.getStatusCode().value());
        verifyNoInteractions(users, encoder);
    }

    private String body(String password) throws Exception {
        return new ObjectMapper().writeValueAsString(Map.of(
                "username", "alice", "email", "alice@example.com", "password", password));
    }
}
