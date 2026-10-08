param(
    [Parameter(Mandatory=$true)][string]$AssetsDir,
    [Parameter(Mandatory=$true)][string]$OutputFile,
    [Parameter(Mandatory=$false)][string]$Title = "Story Video"
)

$ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
if (-not $ffmpeg) {
    $p = "C:\Users\tanji\AppData\Local\CapCut\Apps\8.7.0.3706"
    if (Test-Path "$p\ffmpeg.exe") { $env:Path = "$p;$env:Path"; $ffmpeg = Get-Command ffmpeg }
}
if (-not $ffmpeg) { Write-Host "FFmpeg not found"; exit 1 }
$ff = $ffmpeg.Source
Write-Host "   Using FFmpeg: $ff"

$images = @(Get-ChildItem "$AssetsDir\scene_*" -Include "*.png","*.jpg","*.jpeg" | Sort-Object Name)
$audio = Get-ChildItem "$AssetsDir\narration.mp3" -ErrorAction SilentlyContinue
if ($images.Count -eq 0) { Write-Host "No images"; exit 1 }
if (-not $audio) { Write-Host "No narration.mp3"; exit 1 }

Write-Host "Assembling video..."
Write-Host "   Images: $($images.Count)"
Write-Host "   Audio: $($audio.Name)"
Write-Host "   Output: $OutputFile"

$per = [math]::Max(6, [math]::Min(20, [math]::Round(120 / $images.Count)))
$totalDur = $per * $images.Count + 4
Write-Host "   Per scene: ${per}s, Total: ${totalDur}s"

# Step 1: Build each image into a short video segment, then concat segments
$segDir = "$AssetsDir\segments"
New-Item -ItemType Directory -Force -Path $segDir | Out-Null
$segList = "$AssetsDir\segments.txt"

for ($i = 0; $i -lt $images.Count; $i++) {
    $d = if ($i -eq $images.Count - 1) { $per + 4 } else { $per }
    $seg = "$segDir\seg_$( '{0:D2}' -f $i ).mp4"
    & $ff -y -loop 1 -i "$($images[$i].FullName)" -c:v h264_qsv -t $d -pix_fmt yuv420p -vf "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080" -an "$seg" 2>&1 | Out-Null
    Add-Content -Path $segList -Value "file '$seg'"
}

# Concatenate segments
$slideshow = "$AssetsDir\slideshow.mp4"
& $ff -y -f concat -safe 0 -i "$segList" -c copy "$slideshow" 2>&1 | Out-Null

Remove-Item "$segDir" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item "$segList" -Force -ErrorAction SilentlyContinue

if (-not (Test-Path $slideshow) -or (Get-Item $slideshow).Length -lt 10000) {
    Write-Host "Failed to create slideshow"
    exit 1
}

# Step 2: Loop slideshow + add audio
$final = if ($OutputFile -match '\.') { $OutputFile } else { "$OutputFile.mp4" }
& $ff -y -stream_loop -1 -i "$slideshow" -i $audio.FullName -c:v copy -c:a aac -map 0:v:0 -map 1:a:0 -shortest -movflags +faststart "$final" 2>&1 | Out-Null

Remove-Item "$slideshow" -Force -ErrorAction SilentlyContinue

if (Test-Path $final) {
    $size = (Get-Item $final).Length / 1MB
    $dur = & $ff -i "$final" 2>&1 | Select-String "Duration"
    $dur = if ($dur) { ($dur -split ",")[0] -replace "Duration: ","" } else { "unknown" }
    Write-Host "Video created: $final"
    Write-Host "   Duration: $dur"
    Write-Host "   Size: $([math]::Round($size,1)) MB"
    return $final
} else {
    Write-Host "Failed to create final video"
    exit 1
}
