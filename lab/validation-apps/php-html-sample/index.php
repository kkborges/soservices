<?php
$path = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);
header('X-LAS-Sample: php-html');

if ($path === '/health') {
    header('Content-Type: application/json');
    echo json_encode(['status' => 'ok', 'service' => 'php-html']);
    exit;
}

if ($path === '/work') {
    usleep(random_int(50000, 250000));
    header('Content-Type: application/json');
    echo json_encode(['status' => 'processed', 'service' => 'php-html']);
    exit;
}
?>
<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LAS Validation PHP/HTML</title>
</head>
<body>
  <main>
    <h1>LAS Validation PHP/HTML</h1>
    <p>Aplicacao minima para validacao de disponibilidade, logs e experiencia de usuario.</p>
    <ul>
      <li><a href="/health">/health</a></li>
      <li><a href="/work">/work</a></li>
    </ul>
  </main>
</body>
</html>
