# BBBC - abre o sistema e o aplicativo com um clique so.
#
# Sao dois processos que precisam ficar de pe ao mesmo tempo: o sistema (banco
# e servidor) e o aplicativo (a tela). Este arquivo existe so para tirar do
# usuario a tarefa de abrir dois arquivos na ordem certa e esperar o primeiro
# ficar pronto - erro facil de cometer, e que aparece como "nao conecta".

$ErrorActionPreference = 'Continue'
$RAIZ = Split-Path -Parent $PSScriptRoot

function Titulo($t) { Write-Host "`n$t" -ForegroundColor White }
function Ok($t)     { Write-Host "  [ok] $t" -ForegroundColor Green }
function Erro($t)   { Write-Host "`n[x] $t" -ForegroundColor Red }
function Aviso($t)  { Write-Host "  [!] $t" -ForegroundColor Yellow }

Write-Host "============================================"
Write-Host "  BBBC - abrindo tudo"
Write-Host "============================================"

$saude = 'http://localhost:8000/health'

function ApiNoAr {
    try {
        Invoke-WebRequest -Uri $saude -UseBasicParsing -TimeoutSec 3 | Out-Null
        return $true
    } catch { return $false }
}

Titulo "1. O sistema"
if (ApiNoAr) {
    Ok "Ja estava no ar - nao vou abrir de novo"
} else {
    Write-Host "  Abrindo numa janela separada..."
    Start-Process powershell -ArgumentList @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass',
        '-File', (Join-Path $PSScriptRoot 'iniciar-nativo.ps1')
    )

    Write-Host ""
    Write-Host "  NA PRIMEIRA VEZ aquela janela faz perguntas (a senha do" -ForegroundColor Yellow
    Write-Host "  PostgreSQL, o seu e-mail). Responda la; eu espero aqui." -ForegroundColor Yellow
    Write-Host ""
    Write-Host -NoNewline "  Esperando o sistema responder"

    # Generoso de proposito: na primeira vez ha perguntas a responder, e numa
    # maquina lenta a instalacao das bibliotecas leva minutos.
    $limite = (Get-Date).AddMinutes(15)
    $pronto = $false
    while ((Get-Date) -lt $limite) {
        if (ApiNoAr) { $pronto = $true; break }
        Write-Host -NoNewline "."
        # Um segundo, e nao tres: numa partida em que nada mudou o servidor sobe
        # em poucos segundos, e esperar tres a mais depois de ele estar de pe e
        # tempo jogado fora todo dia.
        Start-Sleep -Seconds 1
    }
    Write-Host ""

    if (-not $pronto) {
        Erro "O sistema nao subiu."
        Write-Host "  Olhe a outra janela: ou ela esta esperando uma resposta sua,"
        Write-Host "  ou mostra o que deu errado."
        Write-Host "`nPode fechar esta janela." -ForegroundColor White
        Read-Host "Aperte Enter para sair"
        exit 1
    }
    Ok "Sistema no ar"
}

Aviso "Nao feche a outra janela enquanto estiver usando o BBBC."

Titulo "2. O aplicativo"
& (Join-Path $PSScriptRoot 'iniciar-app.ps1')
