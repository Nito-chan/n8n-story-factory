param(
    [Parameter(Mandatory=$true)]
    [string]$ApiKey
)

$body = @{
    text = "Hello, this is a test of the Fish Audio API."
    voice = "7f7e3c8b-8b3a-4b5c-8c3a-4b5c8c3a4b5c"
} | ConvertTo-Json

try {
    $url = "https://api.fish.audio/v1/tts"
    $response = Invoke-RestMethod -Uri $url -Method Post -Body $body -ContentType "application/json" -Headers @{"Authorization" = "Bearer $ApiKey"}
    Write-Host "✅ Fish Audio API OK" -ForegroundColor Green
}
catch {
    Write-Host "❌ Fish Audio API FAILED: $_" -ForegroundColor Red
}
