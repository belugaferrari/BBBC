# BBBC - traz a versao nova sem desmontar o que ja esta instalado.
#
# Antes, cada ajuste custava: baixar o zip, extrair, rodar a instalacao inteira
# de novo. O caro ali nunca foi o download - foram os minutos reinstalando as
# bibliotecas do Python e as do Node, que na maior parte das vezes nao mudaram.
#
# Este arquivo troca SO o codigo. Fica onde esta:
#
#   * o banco de dados, que nem mora nesta pasta - ele vive no PostgreSQL, e
#     nada aqui o toca. Nenhum lancamento, nenhuma categoria, nenhuma meta se
#     perde numa atualizacao;
#   * backend\.venv e mobile\node_modules, as bibliotecas instaladas. Quando a
#     lista de dependencias nao mudou, a partida seguinte nem reinstala (a marca
#     dentro do .venv cuida disso);
#   * os relatos de instalacao e qualquer .env local.
#
# Dois caminhos, na ordem de preferencia:
#
#   1. se a pasta for um clone do git, um `git pull` resolve - e preserva tudo
#      sozinho, porque .venv e node_modules estao no .gitignore;
#   2. se for uma pasta baixada como zip (o caso de quem clicou em "Download
#      ZIP"), baixa o zip novo e copia por cima, pulando o que nao deve ser
#      tocado.
#
# UMA COISA QUE ESTE ARQUIVO NAO FAZ: reiniciar o que ja esta rodando. Trocar os
# arquivos nao troca o programa que esta de pe - o Python leu o codigo quando
# subiu e continua com a versao velha na memoria. Sem fechar e abrir, o resultado
# e um sistema meio atualizado: tela nova conversando com servidor velho, que e
# pior que nao ter atualizado, porque parece que deu certo. Por isso o script
# detecta o que esta ligado e, quando ha algo, termina mandando fechar em vez de
# abrir por cima.

$ErrorActionPreference = 'Continue'
$RAIZ = Split-Path -Parent $PSScriptRoot
Set-Location $RAIZ

function Titulo($t) { Write-Host "`n$t" -ForegroundColor White }
function Ok($t)     { Write-Host "  [ok] $t" -ForegroundColor Green }
function Erro($t)   { Write-Host "`n[x] $t" -ForegroundColor Red }
function Aviso($t)  { Write-Host "  [!] $t" -ForegroundColor Yellow }

function Fim($codigo) {
    Write-Host ""
    Read-Host "Aperte Enter para sair"
    exit $codigo
}

# De onde a versao nova vem. O ramo esta numa variavel porque o nome dele aparece
# tambem na mensagem de "nada mudou", e os dois tem de contar a mesma historia.
$REPO_RAMO = 'main'
$REPO_ZIP = "https://github.com/belugaferrari/BBBC/archive/refs/heads/$REPO_RAMO.zip"

function SistemaNoAr {
    try {
        Invoke-WebRequest -Uri 'http://localhost:8000/health' -UseBasicParsing -TimeoutSec 2 |
            Out-Null
        return $true
    } catch { return $false }
}

function AplicativoNoAr {
    # O Metro, do Expo, escuta na 8081. Aberto a socket na mao em vez de cmdlet de
    # rede: os nomes dos cmdlets de rede variam entre versoes do Windows, e um
    # nome errado aqui daria "nao esta aberto" para um aplicativo que esta - o
    # erro silencioso que este script existe para evitar. Porta fechada em
    # localhost recusa na hora, entao nao ha espera.
    $cliente = $null
    try {
        $cliente = New-Object Net.Sockets.TcpClient
        $cliente.Connect('127.0.0.1', 8081)
        return $cliente.Connected
    } catch {
        return $false
    } finally {
        if ($cliente) { $cliente.Dispose() }
    }
}

# O que a copia por cima nao deve tocar.
#
# Vale dizer por que a atualizacao e segura mesmo sem esta lista: o robocopy e
# chamado sem /MIR e sem /PURGE, entao ele SO adiciona e sobrescreve - nunca
# apaga. Tudo o que existe aqui e nao existe no zip (o .venv, o node_modules, um
# .env) sobrevive por construcao, porque o zip nao tem essas pastas para
# sobrescrever. A lista e cinto e suspensorio.
#
# A contrapartida de nunca apagar: um arquivo que saiu do projeto continua aqui
# depois da atualizacao. Para scripts antigos isso e so entulho; se algum dia um
# deles passar a confundir, o caminho e apagar a pasta e baixar de novo - os
# dados estao no PostgreSQL e nao se mexem.
$PRESERVAR = @(
    '.venv', 'node_modules', '.expo', '.git', '__pycache__',
    '.env', '.env.local', 'dist', '.pytest_cache', '.ruff_cache'
)

Write-Host "============================================"
Write-Host "  BBBC - atualizar"
Write-Host "============================================"
Write-Host ""
Write-Host "  Vou atualizar ESTA pasta:" -ForegroundColor White
Write-Host "    $RAIZ" -ForegroundColor Cyan

# Dizer em voz alta qual pasta e, antes de tocar em qualquer coisa.
#
# Quem atualiza pelo zip acaba com duas pastas iguais: a instalada e a recem
# extraida, que so serviu de fonte. Elas tem o mesmo nome e os mesmos arquivos, e
# abrir a errada nao da erro nenhum - o sistema sobe, o banco e o mesmo, e tudo
# parece normal, so que o trabalho vai para a copia que sera jogada fora. A pasta
# instalada tem .venv e node_modules dentro; a extraida, nao. Nao da para ter
# certeza so por isso - uma instalacao nova tambem nao os tem - mas da para
# desconfiar em voz alta.
$pareceInstalada = (Test-Path (Join-Path $RAIZ 'backend\.venv')) -or
                   (Test-Path (Join-Path $RAIZ 'mobile\node_modules'))
if (-not $pareceInstalada) {
    Write-Host ""
    Aviso "Esta pasta nao parece a sua instalacao."
    Write-Host "      Nao achei nem backend\.venv nem mobile\node_modules aqui, e e"
    Write-Host "      neles que ficam as bibliotecas ja instaladas."
    Write-Host ""
    Write-Host "      Se voce extraiu um zip e esta rodando o ATUALIZAR de dentro"
    Write-Host "      dele, feche isto e rode o da pasta onde o BBBC esta instalado"
    Write-Host "      (a do Desktop, em geral). Atualizar a copia extraida nao"
    Write-Host "      estraga nada, mas tambem nao serve para nada."
    Write-Host ""
    $segue = Read-Host "  Atualizar esta pasta mesmo assim? (s/n) [n]"
    if (-not $segue -or $segue.ToLower() -ne 's') {
        Write-Host "  Nada foi alterado."
        Fim 0
    }
}

Write-Host ""
Write-Host "  Seus dados NAO estao nesta pasta - eles vivem no PostgreSQL." -ForegroundColor White
Write-Host "  Atualizar troca o programa, e nao os lancamentos." -ForegroundColor White

# Conferido ANTES de mexer em arquivo: e o que decide a mensagem do fim.
$sistemaEstavaNoAr = SistemaNoAr
$appEstavaNoAr = AplicativoNoAr

if ($sistemaEstavaNoAr -or $appEstavaNoAr) {
    Write-Host ""
    Aviso "O BBBC esta aberto agora, em outra janela."
    Write-Host "      Pode deixar aberto: a troca dos arquivos nao estraga nada."
    Write-Host "      Mas o programa que esta de pe continua com a versao velha na"
    Write-Host "      memoria, entao no fim vou pedir para fechar e abrir de novo -"
    Write-Host "      e so assim a atualizacao passa a valer."
    Write-Host ""
}

# ---------------------------------------------------------------- 1. git ---
$temGit = (Test-Path (Join-Path $RAIZ '.git')) -and
          (Get-Command git -ErrorAction SilentlyContinue)

if ($temGit) {
    Titulo "1. Baixando a versao nova (git)"

    # Mudanca local nao commitada faria o pull parar pela metade. Melhor saber
    # agora, com o usuario olhando, que no meio da atualizacao.
    $sujo = (& git status --porcelain 2>$null | Measure-Object -Line).Lines
    if ($sujo -gt 0) {
        Aviso "Ha arquivos alterados nesta pasta."
        Write-Host "      Se voce nao mexeu no codigo de proposito, pode seguir:"
        Write-Host "      vou guardar as alteracoes de lado antes de atualizar."
        Write-Host ""
        $r = Read-Host "  Seguir? (s/n) [s]"
        if ($r -and $r.ToLower() -ne 's') { Write-Host "  Nada foi alterado."; Fim 0 }
        & git stash push -u -m "antes da atualizacao de $(Get-Date -Format 'yyyy-MM-dd HH:mm')" 2>&1 |
            ForEach-Object { "    $_" }
    }

    $antesDoPull = (& git rev-parse HEAD 2>$null)
    & git pull --ff-only origin main 2>&1 | ForEach-Object { "    $_" }
    if ($LASTEXITCODE -ne 0) {
        Erro "O git nao conseguiu trazer a versao nova."
        Write-Host "  O relato esta acima. Nada foi desmontado - o sistema"
        Write-Host "  continua funcionando na versao de antes."
        Fim 1
    }
    $novidade = ((& git rev-parse HEAD 2>$null) -ne $antesDoPull)
    Ok "Codigo atualizado"
} else {
    # ------------------------------------------------------------ 2. zip ---
    Titulo "1. Baixando a versao nova"

    $temp = Join-Path $env:TEMP "bbbc-atualizacao-$(Get-Date -Format 'yyyyMMddHHmmss')"
    New-Item -ItemType Directory -Path $temp -Force | Out-Null
    $zip = Join-Path $temp 'main.zip'

    try {
        # ProgressPreference silencioso: a barra do Invoke-WebRequest em
        # PowerShell 5 deixa o download varias vezes mais lento.
        $antes = $ProgressPreference
        $ProgressPreference = 'SilentlyContinue'
        Invoke-WebRequest -Uri $REPO_ZIP -OutFile $zip -UseBasicParsing
        $ProgressPreference = $antes
    } catch {
        Erro "Nao consegui baixar a versao nova."
        Write-Host "  $($_.Exception.Message)"
        Write-Host ""
        Write-Host "  Nada foi desmontado - o sistema continua na versao de antes."
        Remove-Item $temp -Recurse -Force -ErrorAction SilentlyContinue
        Fim 1
    }
    Ok "Baixado"

    Titulo "2. Trocando o codigo"
    try {
        Expand-Archive -Path $zip -DestinationPath $temp -Force
    } catch {
        Erro "O arquivo baixado nao abriu. O download pode ter vindo pela metade."
        Remove-Item $temp -Recurse -Force -ErrorAction SilentlyContinue
        Fim 1
    }

    # O zip do GitHub traz tudo dentro de uma pasta 'BBBC-main'.
    $extraido = Get-ChildItem $temp -Directory | Select-Object -First 1
    if (-not $extraido) {
        Erro "O arquivo baixado veio vazio."
        Remove-Item $temp -Recurse -Force -ErrorAction SilentlyContinue
        Fim 1
    }

    # Copia por cima, pulando o que e estado local. robocopy existe em todo
    # Windows e sabe pular pasta por nome, o que Copy-Item nao faz.
    # O ForEach-Object nao e enfeite: com 2>&1, cada linha que o programa manda
    # pelo canal de erro chega aqui como objeto de erro, e nao como texto - e
    # imprimir isso pinta a saida normal de vermelho, como se tudo tivesse dado
    # errado. Converter para texto resolve, e o codigo de saida sobrevive.
    $robo = & robocopy "$($extraido.FullName)" "$RAIZ" /E /NFL /NDL /NJH /NJS /NP `
                       /XD $PRESERVAR /XF '*.log' 2>&1 | ForEach-Object { "$_" }
    # robocopy usa o codigo de saida como mapa de bits: 0 a 7 e sucesso, 8+ e
    # falha de verdade. Tratar "nada a copiar" (0) ou "copiei arquivos" (1) como
    # erro faria toda atualizacao parecer quebrada.
    if ($LASTEXITCODE -ge 8) {
        Erro "A copia dos arquivos falhou."
        $robo | Select-Object -Last 10 | ForEach-Object { Write-Host "    $_" }
        Remove-Item $temp -Recurse -Force -ErrorAction SilentlyContinue
        Fim 1
    }
    # O codigo de saida do robocopy e um mapa de bits, e o bit 0 (valor 1) quer
    # dizer "copiei pelo menos um arquivo". Zero, entao, e "o que esta aqui ja
    # era igual ao que baixei" - nada mudou.
    $novidade = (($LASTEXITCODE -band 1) -ne 0)
    Remove-Item $temp -Recurse -Force -ErrorAction SilentlyContinue
    Ok "Codigo atualizado"
}

# ---------------------------------------------------------------- pronto ---
# "Atualizei e a novidade nao apareceu" custou uma hora uma vez, e a causa nao
# estava aqui: a novidade ainda nao tinha ido para o `main`, que e de onde este
# script baixa. Quando nada muda, o script agora DIZ que nada mudou - e diz onde
# procurar o que falta, em vez de deixar o silencio parecer sucesso.
if (-not $novidade) {
    Titulo "Nada mudou"
    Aviso "Esta pasta ja estava na versao mais nova do $REPO_RAMO."
    Write-Host ""
    Write-Host "  Se voce foi avisado de uma novidade e ela nao apareceu, ela" -ForegroundColor White
    Write-Host "  provavelmente ainda nao entrou no ${REPO_RAMO}: fica esperando" -ForegroundColor White
    Write-Host "  aprovacao num 'pull request'." -ForegroundColor White
    Write-Host ""
    Write-Host "    1. abra https://github.com/belugaferrari/BBBC/pulls"
    Write-Host "    2. clique no pull request aberto"
    Write-Host "    3. clique em 'Merge pull request' e confirme"
    Write-Host "    4. rode este ATUALIZAR de novo"
    Write-Host ""
    Write-Host "  Nao precisa fechar nem reabrir nada: o sistema que esta no ar"
    Write-Host "  continua sendo o mesmo de antes, e esta correto."
    Fim 0
}

Titulo "Pronto"
Write-Host "  O que acontece agora:"
Write-Host "    - as bibliotecas so sao reinstaladas se a lista mudou;"
Write-Host "    - as tabelas novas do banco sao criadas na proxima partida;"
Write-Host "    - os seus dados continuam todos la."

if ($sistemaEstavaNoAr -or $appEstavaNoAr) {
    # Oferecer "abrir agora" aqui seria uma armadilha: o abrir-tudo veria o
    # servidor velho respondendo, concluiria "ja estava no ar" e abriria so a
    # tela. Tela nova com servidor velho e o estado mais confuso possivel.
    Write-Host ""
    Write-Host "  FALTA UM PASSO, e so voce pode dar:" -ForegroundColor Yellow
    Write-Host ""
    $n = 1
    if ($sistemaEstavaNoAr) {
        Write-Host "    $n. feche a janela do SISTEMA (a que diz 'ESTA JANELA PRECISA" -ForegroundColor Yellow
        Write-Host "       FICAR ABERTA'). Ctrl+C nela, ou o X." -ForegroundColor Yellow
        $n++
    }
    if ($appEstavaNoAr) {
        Write-Host "    $n. feche a janela do APLICATIVO (a do QR code). Ctrl+C, ou o X." -ForegroundColor Yellow
        $n++
    }
    Write-Host "    $n. abra o ABRIR-BBBC-windows.bat." -ForegroundColor Yellow
    Write-Host ""
    if ($sistemaEstavaNoAr) {
        Write-Host "  Enquanto nao fizer isso, o sistema continua rodando a versao de"
        Write-Host "  antes - a tela pode ate parecer nova, mas quem responde e o velho."
    } else {
        Write-Host "  Enquanto nao fizer isso, a tela continua montada com a versao de"
        Write-Host "  antes, guardada na memoria de quem a serve."
    }
    Fim 0
}

Write-Host ""
$r = Read-Host "  Abrir o BBBC agora? (s/n) [s]"
if ($r -and $r.ToLower() -ne 's') {
    Write-Host "  Quando quiser: ABRIR-BBBC-windows.bat"
    Fim 0
}

& (Join-Path $PSScriptRoot 'abrir-tudo.ps1')
