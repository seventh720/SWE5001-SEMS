package com.sems.platform.admission;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@org.springframework.scheduling.annotation.EnableScheduling
@SpringBootApplication
public class AdmissionApplication {
    public static void main(String[] args) {
        SpringApplication.run(AdmissionApplication.class, args);
    }
}
