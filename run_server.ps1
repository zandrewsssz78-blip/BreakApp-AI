Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  Iniciando Microservicio del Agente Break IA (8000)..." -ForegroundColor Yellow
Write-Host "========================================================" -ForegroundColor Cyan

if (Get-Command python -ErrorAction SilentlyContinue) {
    python server.py 8000
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    py server.py 8000
} else {
    Write-Host "[ALERTA] Python no fue encontrado en PATH. Asegurate de instalar Python 3.11+." -ForegroundColor Red
}