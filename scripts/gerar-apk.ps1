# BBBC - gera o aplicativo instalavel (APK) do Android. Chamado pelo
# GERAR-APK-windows.bat.
#
# POR QUE ISTO EXISTE. No Expo Go, o aplicativo nao mora no celular: ele e
# baixado deste computador a cada abertura. Com o PC desligado nao ha de onde
# baixar, e nem a copia local dos numeros nem a fila de lancamentos ajudam -
# elas estao dentro de um aplicativo que nao subiu. O APK instalado resolve
# isso: o codigo fica no aparelho.
#
# O que este arquivo faz e so conduzir. Quem compila e o EAS Build, na nuvem da
# propria Expo - compilar Android aqui exigiria Android Studio e uns 10 GB.
#
# Tres armadilhas que ja estao tratadas aqui, porque cada uma e meia hora
# perdida descobrindo sozinho:
#
#   1. O eas-cli NAO e instalado globalmente. `npm install -g` no Windows
#      costuma pedir administrador e, quando nao pede, deixa o comando fora do
#      PATH da janela atual - o erro seguinte e "eas nao e reconhecido" num
#      terminal onde a instalacao acabou de dizer que deu certo. `npx` roda a
#      versao certa sem instalar nada.
#   2. Esta pasta nao e um repositorio git (ela nasceu de um zip). O EAS, por
#      padrao, se recusa a enviar um projeto sem git. `EAS_NO_VCS=1` manda ele
#      enviar a pasta como ela esta.
#   3. O APK e um aplicativo de verdade, sem servidor do Expo de onde deduzir o
#      endereco da API. Por isso o fim do script mostra o endereco desta maquina
#      e manda digitar na tela de login - e a primeira coisa a fazer depois de
#      instalar.

$ErrorActionPreference = 'Continue'
$RAIZ = Split-Path -Parent $PSScriptRoot
Set-Location (Join-Path $RAIZ 'mobile')

function Titulo($texto) { Write-Host "`n$texto" -ForegroundColor White }
function Ok($texto)     { Write-Host "  [ok] $texto" -ForegroundColor Green }
function Erro($texto)   { Write-Host "`n[x] $texto" -ForegroundColor Red }
function Aviso($texto)  { Write-Host "  [!] $texto" -ForegroundColor Yellow }

function Fim($codigo) {
    Write-Host ""
    Read-Host "Aperte Enter para sair"
    exit $codigo
}

function Descobrir-IpDaRede {
    # Mesma logica do INICIAR-APP: a placa que carrega a rota padrao e a que
    # fala com o roteador. Adaptador virtual do Docker e do WSL nao tem rota
    # padrao, entao escolher por aqui ja os deixa de fora.
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
Write-Host "  BBBC - gerar o aplicativo para instalar"
Write-Host "============================================"
Write-Host ""
Write-Host "  Isto gera um arquivo .apk para instalar no Android." -ForegroundColor White
Write-Host "  Com ele, o aplicativo abre com o PC desligado: mostra os"
Write-Host "  numeros da ultima vez que falou com o servidor (dizendo de"
Write-Host "  quando sao) e guarda os lancamentos para subir depois."
Write-Host ""
Write-Host "  Precisa de: internet, uma conta gratuita na Expo, e uns 20"
Write-Host "  minutos - a maior parte e a fila do servico, nao esta maquina."
Write-Host ""
Write-Host "  No iPhone nao da: a Apple cobra US$ 99/ano para instalar" -ForegroundColor Yellow
Write-Host "  aplicativo fora da App Store. La o caminho continua sendo o" -ForegroundColor Yellow
Write-Host "  Expo Go, com o PC ligado." -ForegroundColor Yellow
Write-Host ""

$resposta = Read-Host "Gerar agora? [s/n]"
if ($resposta -notmatch '^[sS]') {
    Write-Host "`nNada feito."
    Fim 0
}

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

# Sem isto o EAS recusa a pasta por nao achar um repositorio git (ver o
# comentario 2 no topo).
$env:EAS_NO_VCS = '1'

# ------------------------------------------------------------------ Conta ---
Titulo "2. Conferindo a conta da Expo"
Write-Host "  (a primeira vez abre o navegador para criar ou entrar)"
Write-Host ""

$quem = (npx --yes eas-cli@latest whoami 2>&1 | ForEach-Object { "$_" }) -join "`n"
if ($LASTEXITCODE -ne 0 -or $quem -match 'Not logged in') {
    Aviso "Nao ha conta conectada nesta maquina. Vou pedir o login."
    Write-Host "      Se voce ainda nao tem conta, crie em https://expo.dev"
    Write-Host "      (gratuita; serve so para compilar)."
    Write-Host ""
    npx --yes eas-cli@latest login
    if ($LASTEXITCODE -ne 0) {
        Erro "Nao consegui conectar a conta da Expo."
        Write-Host "  Sem conta, o servico nao compila. Tente de novo mais tarde."
        Fim 1
    }
    $quem = (npx --yes eas-cli@latest whoami 2>&1 | ForEach-Object { "$_" }) -join "`n"
}
Ok "Conta: $($quem.Trim())"

# ---------------------------------------------------------------- Compilar ---
Titulo "3. Mandando compilar (demora, e normal)"
Write-Host "  O trabalho acontece na nuvem da Expo. Esta janela vai mostrando"
Write-Host "  o andamento; pode deixar aberta e ir fazer outra coisa."
Write-Host ""
Write-Host "  Se ele perguntar sobre criar o projeto na sua conta, responda" -ForegroundColor White
Write-Host "  sim: e so o cadastro do aplicativo na conta, uma vez so." -ForegroundColor White
Write-Host ""

npx --yes eas-cli@latest build --platform android --profile preview
$deuCerto = ($LASTEXITCODE -eq 0)

if (-not $deuCerto) {
    Erro "A compilacao nao terminou."
    Write-Host ""
    Write-Host "  As causas mais comuns, em ordem:" -ForegroundColor White
    Write-Host "    1. internet oscilou no meio do envio - rodar de novo resolve;"
    Write-Host "    2. a fila do plano gratuito estourou o limite do mes;"
    Write-Host "    3. a conta nao confirmou o e-mail."
    Write-Host ""
    Write-Host "  O proprio EAS guarda o relato completo em https://expo.dev"
    Write-Host "  (menu Builds), inclusive o motivo exato."
    Fim 1
}

# ------------------------------------------------------------- O que fazer ---
$ip = Descobrir-IpDaRede

Titulo "4. Pronto. Agora no celular:"
Write-Host ""
Write-Host "  1. O endereco que apareceu acima (termina em .apk) abre no" -ForegroundColor White
Write-Host "     celular - o jeito mais facil e escanear o QR code que o"
Write-Host "     EAS desenhou nesta janela."
Write-Host "  2. O Android vai avisar que o arquivo vem de fonte desconhecida."
Write-Host "     Permita: o 'desconhecido' aqui e voce mesmo."
Write-Host "  3. Abra o BBBC instalado (o icone novo, nao o Expo Go)."
Write-Host "  4. Na tela de login, o campo do servidor abre sozinho. Digite:"
Write-Host ""
if ($ip) {
    Write-Host "         $($ip):8000" -ForegroundColor Green
    Write-Host ""
    Write-Host "     (e o endereco desta maquina na rede; a porta 8000 e a do"
    Write-Host "     servidor). Fica guardado - voce nao digita de novo."
} else {
    Aviso "Nao consegui descobrir o endereco desta maquina na rede."
    Write-Host "      Abra o INICIAR-APP e olhe o passo 3: o numero que ele"
    Write-Host "      mostra, com :8000 no fim, e o que vai no campo."
}
Write-Host ""
Write-Host "  5. Entre com o mesmo e-mail e senha de sempre."
Write-Host ""
Write-Host "  Depois disso, com o PC LIGADO e o celular no Wi-Fi de casa, o" -ForegroundColor White
Write-Host "  aplicativo funciona igual. Com o PC desligado, ele abre e mostra" -ForegroundColor White
Write-Host "  os numeros da ultima sincronizacao, dizendo de quando sao - e" -ForegroundColor White
Write-Host "  aceita lancamento, que sobe quando o PC voltar." -ForegroundColor White
Write-Host ""
Write-Host "  Dois lembretes que valem o tempo:" -ForegroundColor White
Write-Host "    * abra o aplicativo em casa uma vez antes de precisar dele fora:"
Write-Host "      a copia local so existe depois da primeira conversa com o PC;"
Write-Host "    * se o roteador trocar o endereco deste computador, o campo do"
Write-Host "      servidor precisa ser corrigido (Sair, e digitar o novo)."
Write-Host "      Reservar um IP fixo no roteador evita isso de vez."
Write-Host ""
Write-Host "  A cada atualizacao do sistema que mexa no aplicativo, gere o APK" -ForegroundColor Yellow
Write-Host "  de novo e instale por cima - o ATUALIZAR troca o codigo desta" -ForegroundColor Yellow
Write-Host "  maquina, nao o que ja esta instalado no celular." -ForegroundColor Yellow

Fim 0
