package com.portfolio.investigation;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;

@SpringBootApplication
@ConfigurationPropertiesScan
public class ExperienceApplication {
    public static void main(String[] args) {
        SpringApplication.run(ExperienceApplication.class, args);
    }
}
