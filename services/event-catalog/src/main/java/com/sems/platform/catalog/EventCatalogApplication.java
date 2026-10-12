package com.sems.platform.catalog;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@org.springframework.scheduling.annotation.EnableScheduling
@SpringBootApplication
public class EventCatalogApplication {
    public static void main(String[] args) {
        SpringApplication.run(EventCatalogApplication.class, args);
    }
}
