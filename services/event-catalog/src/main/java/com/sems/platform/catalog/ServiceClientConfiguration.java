package com.sems.platform.catalog;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.*;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.web.client.RestClient;
@Configuration
public class ServiceClientConfiguration {
    @Bean RestClient serviceClient(@Value("${sems.internal.remote-url}") String url,
            @Value("${sems.internal.outbound-token}") String token) {
        var factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(2000); factory.setReadTimeout(3000);
        return RestClient.builder().baseUrl(url).requestFactory(factory)
                .defaultHeader("X-Service-Token", token).build();
    }
}
