# Writes AH2_DATABASE_URL from .env into the ah2-dev-kv Key Vault secret
# named ah2-database-url, without ever printing the value to the console.
# Uses --file (not --value) to avoid command-line argument escaping
# issues with special characters in the connection string (e.g. the
# sslmode=require query string). Checks the actual exit code rather than
# assuming success.

$envContent = Get-Content "C:\alphahound_project\.env"
$line = $envContent | Where-Object { $_ -match '^AH2_DATABASE_URL=' } | Select-Object -First 1

if (-not $line) {
    Write-Host "AH2_DATABASE_URL not found in .env. Run docs\AH2\db\create_database.py first."
    exit 1
}

$value = $line -replace '^AH2_DATABASE_URL=', ''

$tempFile = [System.IO.Path]::GetTempFileName()
try {
    [System.IO.File]::WriteAllText($tempFile, $value, [System.Text.Encoding]::ASCII)
    az keyvault secret set --vault-name ah2-dev-kv --name ah2-database-url --file $tempFile | Out-Null

    if ($LASTEXITCODE -ne 0) {
        Write-Host "FAILED: az keyvault secret set returned exit code $LASTEXITCODE"
        exit 1
    }

    Write-Host "Secret ah2-database-url set in ah2-dev-kv (exit code 0)."
} finally {
    Remove-Item $tempFile -Force -ErrorAction SilentlyContinue
}
