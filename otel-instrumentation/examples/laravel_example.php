<?php
/**
 * Exemplo: Laravel com OpenTelemetry
 */

// config/bootstrap.php - Adicionar no bootstrap
require_once __DIR__ . '/otel-init.php';

// routes/web.php
use Illuminate\Support\Facades\Route;
use Illuminate\Http\Request;

Route::get('/', function () {
    return view('welcome');
});

Route::get('/api/tasks', function () {
    $tracer = app('tracer');
    $span = $tracer->spanBuilder('fetch_tasks')
        ->setAttribute('db.system', 'postgresql')
        ->startSpan();
    
    try {
        $tasks = [
            ['id' => 1, 'title' => 'Task 1'],
            ['id' => 2, 'title' => 'Task 2'],
        ];
        
        $span->setAttribute('db.rows_returned', count($tasks));
        return response()->json(['tasks' => $tasks, 'count' => count($tasks)]);
        
    } finally {
        $span->end();
    }
});

Route::post('/api/tasks', function (Request $request) {
    $tracer = app('tracer');
    $span = $tracer->spanBuilder('create_task')
        ->setAttribute('task.id', $request->id)
        ->setAttribute('task.title', $request->title)
        ->startSpan();
    
    try {
        \Log::info('Task criada: ' . $request->title);
        return response()->json(['message' => 'Task criada', 'task' => $request->all()]);
        
    } finally {
        $span->end();
    }
});

// resources/views/welcome.blade.php
?>
<!DOCTYPE html>
<html>
<head>
    <title>Laravel + LAS</title>
    <style>
        body { font-family: Arial; margin: 40px; }
        button { padding: 10px; margin: 5px; }
    </style>
</head>
<body>
    <h1>Laravel com OpenTelemetry para LAS</h1>
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

