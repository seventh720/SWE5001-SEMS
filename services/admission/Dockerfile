FROM eclipse-temurin:21-jre-noble
WORKDIR /app
COPY services/admission/target/admission-service-0.1.0-SNAPSHOT.jar app.jar
USER 10001:10001
EXPOSE 8083
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
