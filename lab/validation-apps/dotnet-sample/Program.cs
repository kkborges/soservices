var builder = WebApplication.CreateBuilder(args);
var app = builder.Build();

app.MapGet("/", () => Results.Ok(new
{
    service = "las-validation-dotnet",
    message = "Aplicacao .NET minima para validacao LAS",
    timestamp = DateTimeOffset.UtcNow
}));

app.MapGet("/health", () => Results.Ok(new { status = "ok", service = "dotnet" }));

app.MapGet("/work", async () =>
{
    await Task.Delay(Random.Shared.Next(50, 250));
    return Results.Ok(new { status = "processed", service = "dotnet" });
});

app.Run();
