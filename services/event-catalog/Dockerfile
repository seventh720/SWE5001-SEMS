FROM eclipse-temurin:21-jre
WORKDIR /app
COPY services/event-catalog/target/event-catalog-service-0.1.0-SNAPSHOT.jar app.jar
USER 10001:10001
EXPOSE 8082
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
