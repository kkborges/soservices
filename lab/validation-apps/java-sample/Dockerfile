FROM eclipse-temurin:21-jdk AS build
WORKDIR /src
COPY App.java .
RUN javac App.java

FROM eclipse-temurin:21-jre
WORKDIR /app
COPY --from=build /src/App.class .
EXPOSE 8080
CMD ["java", "App"]
