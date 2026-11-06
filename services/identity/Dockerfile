FROM eclipse-temurin:21-jre-noble
# Apply the Noble APT security update for CVE-2026-109518 before dropping root.
RUN apt-get -o Acquire::Retries=0 update \
    && apt-get -o Acquire::Retries=0 install -y --no-install-recommends --only-upgrade apt libapt-pkg6.0t64 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY services/identity/target/identity-service-0.1.0-SNAPSHOT.jar app.jar
USER 10001:10001
EXPOSE 8081
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
