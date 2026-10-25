package com.sems.platform.admission;

import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestClient;
import org.springframework.web.server.ResponseStatusException;
import static org.junit.jupiter.api.Assertions.*;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.*;
import static org.springframework.test.web.client.response.MockRestResponseCreators.*;

class CatalogClientTest {
    private static final UUID EVENT=UUID.fromString("00000000-0000-0000-0000-000000000001");
    private static final UUID USER=UUID.fromString("00000000-0000-0000-0000-000000000002");
    private static final String BASE="http://gateway:8080";
    private static final String PUBLISHED=BASE+"/internal/v1/events/"+EVENT+"/published?user="+USER;
    private static final String SNAPSHOT="""
        {"id":"00000000-0000-0000-0000-000000000001","capacity":10,"status":"PUBLISHED"}
        """;
    private final RestClient.Builder builder=RestClient.builder().baseUrl(BASE)
        .defaultHeader("X-Service-Token","test-service-token");
    private final MockRestServiceServer server=MockRestServiceServer.bindTo(builder).build();
    private final CatalogClient client=new CatalogClient(builder.build());

    @ParameterizedTest @ValueSource(ints={502,503,504})
    void publishedReadRecoversAfterOneTransientGatewayFailure(int status) {
        server.expect(requestTo(PUBLISHED)).andExpect(method(HttpMethod.GET))
            .andExpect(header("X-Service-Token","test-service-token"))
            .andRespond(withStatus(HttpStatus.valueOf(status)));
        server.expect(requestTo(PUBLISHED)).andExpect(method(HttpMethod.GET))
            .andExpect(header("X-Service-Token","test-service-token"))
            .andRespond(withSuccess(SNAPSHOT,MediaType.APPLICATION_JSON));
        assertEquals(EVENT,client.published(EVENT,USER).id());
        server.verify();
    }

    @Test void unavailableReplicasStopAfterTwoAttempts() {
        server.expect(requestTo(PUBLISHED)).andRespond(withStatus(HttpStatus.GATEWAY_TIMEOUT));
        server.expect(requestTo(PUBLISHED)).andRespond(withStatus(HttpStatus.GATEWAY_TIMEOUT));
        var error=assertThrows(ResponseStatusException.class,()->client.published(EVENT,USER));
        assertEquals(503,error.getStatusCode().value());
        server.verify();
    }

    @ParameterizedTest @ValueSource(ints={404,409})
    void domainErrorsPreserveTheirStatusWithoutRetry(int status) {
        server.expect(requestTo(PUBLISHED)).andRespond(withStatus(HttpStatus.valueOf(status)));
        var error=assertThrows(ResponseStatusException.class,()->client.published(EVENT,USER));
        assertEquals(status,error.getStatusCode().value());
        server.verify();
    }

    @Test void readOnlyDetailsPostCanRetry() {
        String uri=BASE+"/internal/v1/events/details";
        server.expect(requestTo(uri)).andExpect(method(HttpMethod.POST))
            .andExpect(content().json("{\"ids\":[\""+EVENT+"\"]}"))
            .andRespond(withStatus(HttpStatus.BAD_GATEWAY));
        server.expect(requestTo(uri)).andExpect(method(HttpMethod.POST))
            .andExpect(content().json("{\"ids\":[\""+EVENT+"\"]}"))
            .andRespond(withSuccess("[{\"id\":\""+EVENT+"\",\"title\":\"Test\"}]",MediaType.APPLICATION_JSON));
        assertEquals("Test",client.details(List.of(EVENT)).get(EVENT).title());
        server.verify();
    }

    @Test void prepareSalesMutationIsNeverAutomaticallyReplayed() {
        server.expect(requestTo(BASE+"/internal/v1/events/"+EVENT+"/prepare-sales"))
            .andExpect(method(HttpMethod.POST)).andRespond(withStatus(HttpStatus.SERVICE_UNAVAILABLE));
        var error=assertThrows(ResponseStatusException.class,()->client.prepare(EVENT,USER,1));
        assertEquals(503,error.getStatusCode().value());
        server.verify();
    }
}
