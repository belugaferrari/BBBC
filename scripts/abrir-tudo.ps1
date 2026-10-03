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

    # As ASPAS em volta do caminho nao sao enfeite, e a falta delas era um bug.
    #
    # O -ArgumentList junta a lista num unico texto de linha de comando e NAO
    # poe aspas em nada. Com a pasta num caminho que tenha espaco - e no Windows
    # em portugues a Area de Trabalho do OneDrive tem dois - o PowerShell do
    # outro lado recebe o caminho picado, recusa o arquivo, imprime o modo de
    # usar e sai. Numa janela recem-aberta isso aparece como um piscar: ela abre
    # e fecha, levando o erro junto, e esta aqui fica contando pontinhos ate o
    # relogio estourar.
    #
    # -PassThru para ficar com o processo na mao e perceber quando ele morre.
    $scriptDoSistema = Join-Path $PSScriptRoot 'iniciar-nativo.ps1'
    $janelaDoSistema = Start-Process powershell -PassThru -ArgumentList @(
        '-NoProfile', '-ExecutionPolicy', 'Bypass',
        '-File', "`"$scriptDoSistema`""
    )

    Write-Host ""
    Write-Host "  A OUTRA JANELA e quem esta trabalhando. Ela pode estar atras" -ForegroundColor Yellow
    Write-Host "  desta ou do navegador - procure na barra de tarefas." -ForegroundColor Yellow
    Write-Host "  Na primeira vez ela faz perguntas (a senha do PostgreSQL, o" -ForegroundColor Yellow
    Write-Host "  seu e-mail). Responda la; eu espero aqui." -ForegroundColor Yellow
    Write-Host ""
    Write-Host -NoNewline "  Esperando o sistema responder"

    # Generoso de proposito: na primeira vez ha perguntas a responder, e numa
    # maquina lenta a instalacao das bibliotecas leva minutos.
    $comeco = Get-Date
    $limite = $comeco.AddMinutes(15)
    $pronto = $false
    $morreu = $false
    $jaAvisou = $false

    while ((Get-Date) -lt $limite) {
        if (ApiNoAr) { $pronto = $true; break }

        # A janela sumiu sem o servidor subir. Dois casos, e os dois terminam
        # aqui em vez de esperar o relogio: ela nao conseguiu abrir, ou alguem a
        # fechou. Continuar esperando seria esperar por algo que ja nao existe.
        if ($janelaDoSistema -and $janelaDoSistema.HasExited) { $morreu = $true; break }

        $esperando = ((Get-Date) - $comeco).TotalSeconds
        if (-not $jaAvisou -and $esperando -gt 45) {
            # Quarenta e cinco segundos e mais do que uma partida normal leva.
            # Passou disso, ou ha instalacao rodando, ou a outra janela esta
            # parada esperando alguem - e so olhando para ela da para saber.
            $jaAvisou = $true
            Write-Host ""
            Write-Host ""
            Aviso "Ja passou de 45 segundos. Va ver a outra janela agora."
            Write-Host "      Se ela estiver instalando (linhas correndo), e normal:"
            Write-Host "      depois de atualizar, a primeira partida reinstala uma vez."
            Write-Host "      Se ela estiver parada numa pergunta, responda la."
            Write-Host "      Se ela mostrar um erro em vermelho, e ele que importa."
            Write-Host ""
            Write-Host -NoNewline "  Continuo esperando"
        }

        Write-Host -NoNewline "."
        # Um segundo, e nao tres: numa partida em que nada mudou o servidor sobe
        # em poucos segundos, e esperar tres a mais depois de ele estar de pe e
        # tempo jogado fora todo dia.
        Start-Sleep -Seconds 1
    }
    Write-Host ""

    if ($morreu) {
        Erro "A janela do sistema fechou sem o servidor subir."
        Write-Host "  Ou ela nao chegou a abrir, ou foi fechada antes da hora."
        Write-Host ""
        Write-Host "  Para ver o que aconteceu, abra a mao e leia com calma:"
        Write-Host "    INICIAR-SEM-DOCKER-windows.bat"
        Write-Host "  Essa janela fica aberta mostrando o erro, em vez de sumir."
        Write-Host "`nPode fechar esta janela." -ForegroundColor White
        Read-Host "Aperte Enter para sair"
        exit 1
    }

    if (-not $pronto) {
        Erro "O sistema nao subiu em quinze minutos."
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
