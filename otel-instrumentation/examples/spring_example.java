/**
 * Exemplo: Spring Boot com OpenTelemetry
 */

package com.example.LAS;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Import;
import org.springframework.web.bind.annotation.*;
import io.opentelemetry.api.trace.Tracer;
import org.springframework.beans.factory.annotation.Autowired;
import java.util.Arrays;
import java.util.List;

import com.las.OTelConfig;

@SpringBootApplication
@Import(OTelConfig.class)
public class ExampleApplication {

    @Autowired
    private Tracer tracer;

    public static void main(String[] args) {
        SpringApplication.run(ExampleApplication.class, args);
    }

    @RestController
    @RequestMapping("/api")
    public class TaskController {

        @GetMapping("/tasks")
        public TaskResponse getTasks() {
            // Rastrear com span
            var span = tracer.spanBuilder("fetch_tasks")
                .setAttribute("db.system", "postgresql")
                .startSpan();
            
            try (var scope = span.makeCurrent()) {
                List<Task> tasks = Arrays.asList(
                    new Task(1, "Task 1"),
                    new Task(2, "Task 2")
                );
                
                span.setAttribute("db.rows_returned", tasks.size());
                return new TaskResponse(tasks, tasks.size());
                
            } finally {
                span.end();
            }
        }

        @PostMapping("/tasks")
        public TaskResponse createTask(@RequestBody Task task) {
            var span = tracer.spanBuilder("create_task")
                .setAttribute("task.id", task.id)
                .setAttribute("task.title", task.title)
                .startSpan();
            
            try (var scope = span.makeCurrent()) {
                System.out.println("âœ“ Task criada: " + task.title);
                return new TaskResponse(Arrays.asList(task), 1);
                
            } finally {
                span.end();
            }
        }

        @GetMapping("/health")
        public String health() {
            return "OK";
        }
    }

    // DTOs
    static class Task {
        public int id;
        public String title;

        public Task(int id, String title) {
            this.id = id;
            this.title = title;
        }
    }

    static class TaskResponse {
        public List<Task> tasks;
        public int count;

        public TaskResponse(List<Task> tasks, int count) {
            this.tasks = tasks;
            this.count = count;
        }
    }
}

