# BBBC - faz (ou desfaz) o sistema ligar junto com o Windows.
#
# Poe um atalho na pasta Inicializar do usuario. E o caminho mais simples que
# existe no Windows e, principalmente, o unico que nao precisa de administrador:
# Agendador de Tarefas e servico pedem elevacao, e cada permissao a mais e uma
# chance de o atalho sumir numa atualizacao sem ninguem notar.
#
# O que liga sozinho e o SISTEMA (banco e servidor), nao o aplicativo. Sao coisas
# diferentes: o sistema precisa estar de pe para o celular consultar e para a
# fila de lancamentos subir, e isso tem de valer o dia inteiro, sem janela
# nenhuma aberta. O aplicativo e uma tela - abrir uma aba de navegador a cada
# boot seria atrapalhar, nao ajudar.

$ErrorActionPreference = 'Continue'
$RAIZ = Split-Path -Parent $PSScriptRoot

function Titulo($t) { Write-Host "`n$t" -ForegroundColor White }
function Ok($t)     { Write-Host "  [ok] $t" -ForegroundColor Green }
function Erro($t)   { Write-Host "`n[x] $t" -ForegroundColor Red }
function Aviso($t)  { Write-Host "  [!] $t" -ForegroundColor Yellow }

function Fim($codigo) {
    Write-Host ""
    Read-Host "Aperte Enter para sair"
    exit $codigo
}

$pastaInicializar = [Environment]::GetFolderPath('Startup')
$atalho = Join-Path $pastaInicializar 'BBBC - sistema.lnk'
$script = Join-Path $PSScriptRoot 'iniciar-nativo.ps1'

Write-Host "============================================"
Write-Host "  BBBC - ligar junto com o Windows"
Write-Host "============================================"

if (-not (Test-Path $script)) {
    Erro "Nao achei o iniciar-nativo.ps1 ao lado deste arquivo."
    Write-Host "  A pasta do BBBC foi movida ou renomeada?"
    Fim 1
}

$jaLigado = Test-Path $atalho

Titulo "Como esta hoje"
if ($jaLigado) {
    Ok "O sistema JA liga junto com o Windows."
} else {
    Write-Host "  O sistema NAO liga junto com o Windows - voce abre a mao."
}

Write-Host ""
Write-Host "    [1] Ligar junto com o Windows"
Write-Host "    [2] Nao ligar mais (volta a abrir a mao)"
Write-Host "    [3] Deixar como esta e sair"
Write-Host ""

$escolha = Read-Host "  Digite 1, 2 ou 3 e aperte Enter [1]"
if ([string]::IsNullOrWhiteSpace($escolha)) { $escolha = '1' }

if ($escolha -eq '3') {
    Write-Host "  Nada foi alterado."
    Fim 0
}

if ($escolha -eq '2') {
    if (-not $jaLigado) {
        Write-Host "  Ja nao estava ligado. Nada a fazer."
        Fim 0
    }
    Remove-Item $atalho -Force -ErrorAction SilentlyContinue
    if (Test-Path $atalho) {
        Erro "Nao consegui remover o atalho."
        Write-Host "  Ele esta em: $atalho"
        Fim 1
    }
    Ok "Pronto. O sistema nao vai mais ligar sozinho."
    Write-Host "  Para abrir quando quiser: ABRIR-BBBC-windows.bat"
    Fim 0
}

# ------------------------------------------------------------------ ligar ---
Titulo "Conferindo se da para ligar sozinho"

# O modo automatico nao pergunta nada - entao a instalacao precisa estar feita.
# Conferir isso AGORA, com o usuario olhando, e melhor que descobrir amanha de
# manha por um sistema que nao subiu e nao disse por que.
$venvPython = Join-Path $RAIZ 'backend\.venv\Scripts\python.exe'
if (-not (Test-Path $venvPython)) {
    Erro "O sistema ainda nao foi instalado nesta maquina."
    Write-Host "  Abra o ABRIR-BBBC-windows.bat uma vez e responda as perguntas"
    Write-Host "  (a senha do PostgreSQL, o seu e-mail). Depois volte aqui."
    Fim 1
}
Ok "Instalacao encontrada"

$ws = New-Object -ComObject WScript.Shell
$lnk = $ws.CreateShortcut($atalho)
$lnk.TargetPath = (Get-Command powershell).Source
# -WindowStyle Minimized: o sistema sobe sem roubar a tela de quem acabou de
# ligar o computador. A janela continua existindo, e e ela que segura o servidor.
$lnk.Arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Minimized -File `"$script`" -AoLigar"
$lnk.WorkingDirectory = $RAIZ
$lnk.Description = 'BBBC - sobe o banco e o servidor das financas da familia'
$lnk.WindowStyle = 7   # minimizada
$lnk.Save()

if (-not (Test-Path $atalho)) {
    Erro "Nao consegui criar o atalho em $pastaInicializar"
    Fim 1
}

Ok "Pronto. O sistema vai subir sozinho a cada vez que o Windows ligar."
Write-Host ""
Write-Host "  O que esperar:" -ForegroundColor White
Write-Host "    - uma janela minimizada aparece na barra de tarefas; e ela que"
Write-Host "      segura o servidor, e precisa ficar aberta."
Write-Host "    - o aplicativo NAO abre sozinho. Para ver as telas, use o"
Write-Host "      INICIAR-APP-windows.bat quando quiser."
Write-Host "    - se algo falhar no boot, o motivo fica em:"
Write-Host "      $(Join-Path $RAIZ 'ao-ligar.log')"
Write-Host ""
Write-Host "  Para desfazer: rode este mesmo arquivo e escolha a opcao 2."
Fim 0
