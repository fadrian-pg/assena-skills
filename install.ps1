# Instala los skills ASSENA en %USERPROFILE%\.claude\skills (uso local sin marketplace)
param([string]$Skill = "")

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$dest = Join-Path $env:USERPROFILE ".claude\skills"
New-Item -ItemType Directory -Force $dest | Out-Null

Get-ChildItem (Join-Path $root "plugins") -Directory | ForEach-Object {
    Get-ChildItem (Join-Path $_.FullName "skills") -Directory | ForEach-Object {
        if ($Skill -and $_.Name -ne $Skill) { return }
        $target = Join-Path $dest $_.Name
        if (Test-Path $target) { Remove-Item -Recurse -Force $target }
        Copy-Item -Recurse $_.FullName $target
        Get-ChildItem $target -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
        Write-Host "Instalado: $($_.Name) -> $target"
    }
}
Write-Host "Listo. Reinicia Claude Code para que detecte los skills."
