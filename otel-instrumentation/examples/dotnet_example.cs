// Exemplo: .NET com OpenTelemetry

using Microsoft.AspNetCore.Builder;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.AspNetCore.Mvc;
using LAS.Instrumentation;
using OpenTelemetry.Trace;
using System.Collections.Generic;
using System.Linq;

var builder = WebApplication.CreateBuilder(args);

// â† IMPORTANTE: Adicionar LAS OTel
builder.Services.AddLasOpenTelemetry();

builder.Services.AddControllers();
builder.Services.AddCors(options =>
{
    options.AddDefaultPolicy(builder =>
    {
        builder.AllowAnyOrigin()
               .AllowAnyMethod()
               .AllowAnyHeader();
    });
});

var app = builder.Build();
app.UseCors();

// Rotas
app.MapGet("/", () => """
<!DOCTYPE html>
<html>
<head>
    <title>.NET + LAS</title>
    <style>
        body { font-family: Arial; margin: 40px; }
        button { padding: 10px; margin: 5px; }
    </style>
</head>
<body>
    <h1>.NET com OpenTelemetry para LAS</h1>
    <button onclick="fetchTasks()">Buscar tasks</button>
    <button onclick="createTask()">Criar task</button>
    <pre id="output"></pre>
    <script>
        async function fetchTasks() {
            const resp = await fetch('/api/tasks');
            const data = await resp.json();
            document.getElementById('output').textContent = JSON.stringify(data, null, 2);
        }
        
        async function createTask() {
            const resp = await fetch('/api/tasks', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ id: 3, title: 'New Task' })
            });
            const data = await resp.json();
            document.getElementById('output').textContent = JSON.stringify(data, null, 2);
        }
    </script>
</body>
</html>
""");

app.MapGet("/api/tasks", () =>
{
    var tasks = new List<object>
    {
        new { id = 1, title = "Task 1" },
        new { id = 2, title = "Task 2" }
    };
    return new { tasks, count = tasks.Count };
});

app.MapPost("/api/tasks", ([FromBody] dynamic task) =>
{
    System.Console.WriteLine($"âœ“ Task criada: {task.title}");
    return new { message = "Task criada", task };
});

app.MapGet("/health", () => "OK");

app.Run();

