# Rebuilds and redeploys the AH2 Function App (ah2-dev-func):
#   1. Vendors dependencies for Linux/Python 3.11 (from src/requirements.txt)
#   2. Rebuilds the deployment zip with correct forward-slash entries
#      (see build_zip.ps1 for why this matters on this machine)
#   3. Uploads to blob storage
#   4. Forces a trigger sync
#   5. Restarts the app
#
# Requires: your AAD identity must currently hold Storage Blob Data
# Contributor on the "deploy" container in ah2devfuncst01 (a temporary
# grant Claude adds/removes around each deployment window).

$ErrorActionPreference = "Stop"

$AH2Root = "C:\alphahound_project\docs\AH2"

Write-Host "== Step 1: vendoring dependencies for Linux/Python 3.11 =="
Push-Location "$AH2Root\src"
pip install -r requirements.txt --target=".python_packages/lib/site-packages" `
    --platform manylinux2014_x86_64 --python-version 3.11 --implementation cp `
    --only-binary=:all: --upgrade
if ($LASTEXITCODE -ne 0) { Pop-Location; throw "pip install failed" }
Pop-Location

Write-Host "== Step 2: rebuilding deployment zip =="
& "$AH2Root\build_zip.ps1"

Write-Host "== Step 3: uploading to blob storage =="
az storage blob upload --account-name ah2devfuncst01 --auth-mode login `
    --container-name deploy --name ah2-dev-func-deploy.zip `
    --file "$AH2Root\ah2-dev-func-deploy.zip" --overwrite
if ($LASTEXITCODE -ne 0) { throw "blob upload failed" }

Write-Host "== Step 4: syncing function triggers =="
az resource invoke-action --resource-group ah2-dev-rg --name ah2-dev-func `
    --resource-type "Microsoft.Web/sites" --action syncfunctiontriggers
if ($LASTEXITCODE -ne 0) { throw "syncfunctiontriggers failed" }

Write-Host "== Step 5: restarting the function app =="
az functionapp restart --name ah2-dev-func --resource-group ah2-dev-rg
if ($LASTEXITCODE -ne 0) { throw "functionapp restart failed" }

Write-Host "== Done. Redeploy complete. =="
