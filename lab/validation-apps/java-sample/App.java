import com.sun.net.httpserver.HttpExchange;
import com.sun.net.httpserver.HttpServer;
import java.io.IOException;
import java.io.OutputStream;
import java.net.InetSocketAddress;
import java.time.Instant;

public class App {
    public static void main(String[] args) throws Exception {
        HttpServer server = HttpServer.create(new InetSocketAddress(8080), 0);
        server.createContext("/", exchange -> respond(exchange, 200, json("las-validation-java", "ok", "Aplicacao Java minima para validacao LAS")));
        server.createContext("/health", exchange -> respond(exchange, 200, "{\"status\":\"ok\",\"service\":\"java\"}"));
        server.createContext("/work", exchange -> {
            try {
                Thread.sleep(50 + (long) (Math.random() * 200));
            } catch (InterruptedException ignored) {
                Thread.currentThread().interrupt();
            }
            respond(exchange, 200, "{\"status\":\"processed\",\"service\":\"java\"}");
        });
        server.start();
        System.out.println("las-validation-java listening on :8080");
    }

    private static String json(String service, String status, String message) {
        return "{\"service\":\"" + service + "\",\"status\":\"" + status + "\",\"message\":\"" + message + "\",\"timestamp\":\"" + Instant.now() + "\"}";
    }

    private static void respond(HttpExchange exchange, int status, String body) throws IOException {
        byte[] payload = body.getBytes();
        exchange.getResponseHeaders().add("Content-Type", "application/json; charset=utf-8");
        exchange.sendResponseHeaders(status, payload.length);
        try (OutputStream stream = exchange.getResponseBody()) {
            stream.write(payload);
        }
    }
}
