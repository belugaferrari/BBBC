# BBBC - abre o aplicativo do celular. Chamado pelo INICIAR-APP-windows.bat.
#
# O trabalho que justifica este arquivo existir e descobrir o IP desta maquina
# na rede de casa. O Expo tenta sozinho, mas quando a deteccao falha ele nao
# reclama: devolve 127.0.0.1 e desenha um QR code apontando para o proprio
# celular, que nunca vai carregar. Os adaptadores virtuais que o Docker Desktop
# cria no Windows sao uma causa comum - e o Docker e obrigatorio aqui.

$ErrorActionPreference = 'Continue'
Set-Location (Join-Path (Split-Path -Parent $PSScriptRoot) 'mobile')

function Titulo($texto) { Write-Host "`n$texto" -ForegroundColor White }
function Ok($texto)     { Write-Host "  [ok] $texto" -ForegroundColor Green }
function Erro($texto)   { Write-Host "`n[x] $texto" -ForegroundColor Red }
function Aviso($texto)  { Write-Host "  [!] $texto" -ForegroundColor Yellow }

function Fim($codigo) {
    Write-Host "`nPode fechar esta janela." -ForegroundColor White
    Read-Host "Aperte Enter para sair"
    exit $codigo
}

function Descobrir-IpDaRede {
    # A placa que carrega a rota padrao e a que fala com o roteador. Adaptador
    # virtual de Docker e de WSL nao tem rota padrao, entao escolher por aqui ja
    # os deixa de fora - e sao justamente eles que confundem o Expo.
    try {
        $rota = Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction Stop |
                Sort-Object -Property RouteMetric, ifMetric |
                Select-Object -First 1
        if ($rota) {
            $end = Get-NetIPAddress -InterfaceIndex $rota.ifIndex -AddressFamily IPv4 -ErrorAction Stop |
                   Where-Object { $_.IPAddress -notmatch '^(127\.|169\.254\.)' } |
                   Select-Object -First 1
            if ($end) { return $end.IPAddress }
        }
    } catch { }

    # Plano B, para Windows onde Get-NetRoute nao existe: descarta pelo nome da
    # placa. Menos confiavel que a rota, por isso nao vem primeiro.
    try {
        $end = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop |
               Where-Object {
                   $_.IPAddress -notmatch '^(127\.|169\.254\.)' -and
                   $_.InterfaceAlias -notmatch 'vEthernet|WSL|Docker|Hyper-V|Loopback'
               } |
               Select-Object -First 1
        if ($end) { return $end.IPAddress }
    } catch { }

    return $null
}

Write-Host "============================================"
Write-Host "  BBBC - aplicativo do celular"
Write-Host "============================================"

# ------------------------------------------------------------------ Node ---
Titulo "1. Conferindo o Node.js"
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Erro "O Node.js nao esta instalado."
    Write-Host "  Baixe a versao LTS em https://nodejs.org, instale, e rode"
    Write-Host "  este arquivo de novo."
    Start-Process "https://nodejs.org"
    Fim 1
}
Ok "Node.js instalado"

function Instalar-Dependencias($log) {
    # A saida vai por um cano de proposito. Alem de guardar o relato, isso faz o
    # npm perceber que nao esta num terminal e desligar a barra de progresso -
    # que, quando a instalacao morre no meio, fica congelada por cima justamente
    # da mensagem de erro que interessa.
    #
    # O Out-Host no fim nao e enfeite: sem ele as linhas do npm sairiam pelo
    # cano da funcao e entrariam no valor de retorno, que deixaria de ser um
    # booleano e viraria um array. Array nao vazio e sempre verdadeiro, entao
    # `if (-not (Instalar-Dependencias ...))` concluiria que deu certo mesmo
    # com as duas tentativas falhando.
    npm install --no-audit --no-fund 2>&1 | Tee-Object -FilePath $log | Out-Host
    if ($LASTEXITCODE -eq 0) { return $true }

    Write-Host ""
    Aviso "A primeira tentativa nao terminou. Vou limpar e tentar de novo."
    Write-Host "      Instalacao interrompida deixa a pasta pela metade, e a"
    Write-Host "      tentativa seguinte tropeca no que ficou."
    Write-Host ""

    if (Test-Path 'node_modules') { Remove-Item 'node_modules' -Recurse -Force -ErrorAction SilentlyContinue }
    # O package-lock fixa a arvore exata validada no desenvolvimento, o que e
    # melhor quando funciona. Quando nao funciona, resolver na hora costuma
    # passar - e ter o aplicativo rodando vale mais que a arvore identica.
    if (Test-Path 'package-lock.json') {
        Move-Item 'package-lock.json' 'package-lock.json.nao-usado' -Force -ErrorAction SilentlyContinue
    }

    npm install --no-audit --no-fund 2>&1 | Tee-Object -FilePath $log -Append | Out-Host
    return ($LASTEXITCODE -eq 0)
}

if (-not (Test-Path 'node_modules')) {
    Titulo "2. Preparando o aplicativo"
    Write-Host "  (so na primeira vez, alguns minutos)"
    Write-Host ""

    $log = Join-Path (Get-Location) 'instalacao.log'
    if (-not (Instalar-Dependencias $log)) {
        Erro "Nao consegui preparar o aplicativo."
        Write-Host ""
        Write-Host "  As ultimas linhas do que o npm respondeu:" -ForegroundColor White
        Write-Host ""
        Get-Content $log -Tail 25 -ErrorAction SilentlyContinue | ForEach-Object {
            Write-Host "    $_"
        }
        Write-Host ""
        Write-Host "  O relato inteiro ficou guardado em:" -ForegroundColor White
        Write-Host "    $log"
        Write-Host ""
        Write-Host "  A causa mais comum e a internet ter oscilado no meio do"
        Write-Host "  download. Rodar este arquivo de novo costuma resolver."
        Fim 1
    }
    Ok "Aplicativo preparado"
}

# -------------------------------------------------------------- Endereco ---
Titulo "3. Descobrindo o endereco deste computador na rede"
$ip = Descobrir-IpDaRede
if ($ip) {
    Ok "Este computador e o $ip"
} else {
    Aviso "Nao consegui descobrir o endereco desta maquina na rede."
    Write-Host "      O modo Wi-Fi provavelmente nao vai funcionar. Use a opcao 2."
}

# ----------------------------------------------------------------- Modo ---
Titulo "4. Como o celular vai se conectar?"
Write-Host ""
Write-Host "    [1] Pelo Wi-Fi da casa - mais rapido."
Write-Host "    [2] Pela internet      - mais lenta, mas atravessa firewall e"
Write-Host "                             roteador que separa os aparelhos."
Write-Host ""
Write-Host "  Se a 1 falhar com 'Failed to download remote update', use a 2."
Write-Host ""

# Enter aceita a 1: o caminho normal nao deve exigir escolha.
$modo = Read-Host "  Digite 1 ou 2 e aperte Enter [1]"
if ([string]::IsNullOrWhiteSpace($modo)) { $modo = '1' }

Write-Host ""
Write-Host "  Vai aparecer um QR code aqui embaixo."
Write-Host ""
Write-Host "  ANDROID: abra o aplicativo Expo Go e escaneie por dentro dele."
Write-Host "  IPHONE:  escaneie com a camera normal do celular."
Write-Host ""
Write-Host "  Para parar, aperte Ctrl+C nesta janela."
Write-Host ""

if ($modo -eq '2') {
    Write-Host "  Modo internet: a primeira vez demora mais, esta abrindo o caminho."
    Write-Host ""
    npm run start:tunnel
} else {
    if ($ip) {
        # Sem isto o Expo usa o que ele mesmo detectou - e quando erra, erra
        # para 127.0.0.1, que manda o celular procurar o app nele proprio.
        $env:REACT_NATIVE_PACKAGER_HOSTNAME = $ip
        Write-Host "  O celular vai buscar o app em exp://${ip}:8081"
        Write-Host "  Confira, quando aparecer, se o endereco abaixo bate com esse."
        Write-Host "  Se aparecer 127.0.0.1, feche e use a opcao 2."
    } else {
        Aviso "Seguindo sem endereco conhecido - o Expo vai tentar adivinhar."
    }
    Write-Host ""
    Write-Host "  O celular precisa estar no MESMO Wi-Fi que este computador."
    Write-Host "  Se o Windows perguntar se libera o Node.js na rede, responda PERMITIR."
    Write-Host ""
    npm start
}
