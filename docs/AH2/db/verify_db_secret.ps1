# Verifies the ah2-database-url secret in Key Vault matches the length of
# AH2_DATABASE_URL in .env, WITHOUT ever printing either value. Confirms
# the secret wasn't truncated/corrupted during az keyvault secret set.

$envContent = Get-Content "C:\alphahound_project\.env"
$line = $envContent | Where-Object { $_ -match '^AH2_DATABASE_URL=' } | Select-Object -First 1
$expectedValue = $line -replace '^AH2_DATABASE_URL=', ''
$expectedLength = $expectedValue.Length

$actualValue = az keyvault secret show --vault-name ah2-dev-kv --name ah2-database-url --query "value" -o tsv
$actualLength = $actualValue.Length

Write-Host "Expected length (from .env): $expectedLength"
Write-Host "Actual length (from Key Vault): $actualLength"

if ($expectedLength -eq $actualLength) {
    Write-Host "MATCH: secret was stored correctly."
} else {
    Write-Host "MISMATCH: secret does not match .env value. Re-run set_db_secret.ps1."
}
