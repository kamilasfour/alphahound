# Rebuilds the AH2 Function App deployment zip with forced forward-slash
# path separators (this environment's Compress-Archive and
# ZipFile.CreateFromDirectory both emit backslashes, which Linux does not
# treat as directory separators, breaking package imports).
# Also excludes local.settings.json and __pycache__ (stale bytecode from
# the local Python 3.13 venv, irrelevant to the deployed 3.11 runtime).

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

$srcDir = "C:\alphahound_project\docs\AH2\src"
$zipPath = "C:\alphahound_project\docs\AH2\ah2-dev-func-deploy.zip"

if (Test-Path $zipPath) { Remove-Item $zipPath -Force }

$zip = [System.IO.Compression.ZipFile]::Open($zipPath, [System.IO.Compression.ZipArchiveMode]::Create)

Get-ChildItem -Path $srcDir -Recurse -File | Where-Object {
    $_.Name -ne "local.settings.json" -and $_.FullName -notmatch "__pycache__"
} | ForEach-Object {
    $relativePath = $_.FullName.Substring($srcDir.Length + 1).Replace('\', '/')
    [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, $_.FullName, $relativePath) | Out-Null
    Write-Host "Added: $relativePath"
}

$zip.Dispose()
Write-Host "Done. Zip created at $zipPath"
