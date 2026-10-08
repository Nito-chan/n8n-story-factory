param(
    [Parameter(Mandatory=$true)]
    [string]$ApiKey
)

$body = @{
    contents = @(
        @{
            parts = @(
                @{
                    text = "Say 'Gemini API is working! Reply with just that sentence.'"
                }
            )
        }
    )
} | ConvertTo-Json -Depth 10

try {
    $url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=$ApiKey"
    $response = Invoke-RestMethod -Uri $url -Method Post -Body $body -ContentType "application/json"
    $text = $response.candidates[0].content.parts[0].text
    Write-Host "✅ Gemini API OK: $text" -ForegroundColor Green
}
catch {
    Write-Host "❌ Gemini API FAILED: $_" -ForegroundColor Red
}
