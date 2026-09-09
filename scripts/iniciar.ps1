# BBBC - inicia o sistema. Chamado pelo INICIAR-windows.bat.
# Faz o mesmo que o INICIAR-mac.command: confere o Docker, sobe tudo, cria a
# familia na primeira vez e abre o navegador. Pode rodar quantas vezes quiser.

$ErrorActionPreference = 'Continue'
Set-Location (Split-Path -Parent $PSScriptRoot)

function Titulo($texto) { Write-Host "`n$texto" -ForegroundColor White }
function Ok($texto)     { Write-Host "  [ok] $texto" -ForegroundColor Green }
function Erro($texto)   { Write-Host "`n[x] $texto" -ForegroundColor Red }

function Fim($codigo) {
    Write-Host "`nPode fechar esta janela." -ForegroundColor White
    Read-Host "Aperte Enter para sair"
    exit $codigo
}

Write-Host "============================================"
Write-Host "  BBBC - Financas da familia"
Write-Host "============================================"

# ---------------------------------------------------------------- Docker ---
Titulo "1. Conferindo o Docker"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Erro "O Docker nao esta instalado."
    Write-Host "  Baixe em https://www.docker.com/products/docker-desktop/"
    Write-Host "  Instale, abra o Docker Desktop e rode este arquivo de novo."
    Start-Process "https://www.docker.com/products/docker-desktop/"
    Fim 1
}
Ok "Docker instalado"

docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Erro "O Docker esta instalado, mas nao esta em execucao."
    Write-Host "  Abra o 'Docker Desktop', espere o icone da baleia parar de se"
    Write-Host "  mexer, e rode este arquivo de novo."
    Fim 1
}
Ok "Docker em execucao"

# ------------------------------------------------------------- Subir tudo ---
Titulo "2. Ligando o sistema"
Write-Host "  (na primeira vez demora alguns minutos - esta baixando o necessario)"
Write-Host ""

docker compose up -d --build
if ($LASTEXITCODE -ne 0) {
    Erro "Nao consegui subir o sistema."
    Write-Host "  A causa mais comum e ja existir outro programa usando a porta"
    Write-Host "  5432 ou a 8000. Feche-o e tente de novo."
    Fim 1
}
Ok "Banco de dados e API no ar"

# ------------------------------------------------------------- Esperar API ---
Titulo "3. Esperando a API responder"
$pronto = $false
foreach ($tentativa in 1..60) {
    try {
        Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 3 | Out-Null
        $pronto = $true
        break
    } catch {
        Write-Host "." -NoNewline
        Start-Sleep -Seconds 2
    }
}
Write-Host ""
if (-not $pronto) {
    Erro "A API nao respondeu a tempo."
    Write-Host "  Veja o que aconteceu com: docker compose logs api"
    Fim 1
}
Ok "API respondendo em http://localhost:8000"

# ----------------------------------------------------------------- Familia ---
Titulo "4. Conferindo o seu cadastro"

function Perguntar-Email($rotulo, $padrao) {
    while ($true) {
        $resposta = Read-Host "  $rotulo [$padrao]"
        if ([string]::IsNullOrWhiteSpace($resposta)) { $resposta = $padrao }
        # e-mail e a chave do login: digitado errado, nao ha como adivinhar depois
        if ($resposta -match '^[^@\s]+@[^@\s]+\.[^@\s]+$') { return $resposta }
        Write-Host "  Isso nao parece um e-mail. Tente de novo."
    }
}

function Perguntar-Senha($rotulo) {
    while ($true) {
        $primeira = Read-Host "  $rotulo (minimo 8 caracteres)" -AsSecureString
        $texto = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
            [Runtime.InteropServices.Marshal]::SecureStringToBSTR($primeira))
        if ($texto.Length -lt 8) {
            Write-Host "  Muito curta. Tente outra."
            continue
        }
        $segunda = Read-Host "  Digite a mesma senha de novo" -AsSecureString
        $confirmacao = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
            [Runtime.InteropServices.Marshal]::SecureStringToBSTR($segunda))
        # digitada as cegas: sem conferencia, um dedo errado tranca o usuario fora
        if ($texto -ne $confirmacao) {
            Write-Host "  As duas nao bateram. Vamos de novo."
            continue
        }
        return $texto
    }
}

$situacao = docker compose exec -T api python -m app.cli status 2>$null
if ($situacao -match 'familias:\s+0') {
    Write-Host ""
    Write-Host "  Primeira vez por aqui. Vou criar o seu acesso."
    Write-Host "  (e so apertar Enter para aceitar o que esta entre colchetes)"
    Write-Host ""

    $emailTitular = Perguntar-Email "Seu e-mail" "felipe@exemplo.com"
    $senha        = Perguntar-Senha "Escolha uma senha"
    $emailConjuge = Perguntar-Email "E-mail da Clarissa" "clarissa@exemplo.com"
    $senhaConjuge = Perguntar-Senha "Senha da Clarissa"

    $filha1 = Read-Host "  Nome da filha mais velha [Filha 1]"
    if ([string]::IsNullOrWhiteSpace($filha1)) { $filha1 = "Filha 1" }
    $filha2 = Read-Host "  Nome da filha mais nova  [Filha 2]"
    if ([string]::IsNullOrWhiteSpace($filha2)) { $filha2 = "Filha 2" }

    docker compose exec -T api python -m app.cli seed-family --skip-if-exists `
        --name "Familia BBBC" `
        --titular "Felipe" --titular-email $emailTitular --titular-password $senha `
        --conjuge "Clarissa" --conjuge-email $emailConjuge --conjuge-password $senhaConjuge `
        --dependente $filha1 --dependente $filha2 | Out-Null

    if ($LASTEXITCODE -ne 0) { Erro "Nao consegui criar o cadastro."; Fim 1 }
    Ok "Cadastro criado"
} else {
    Ok "Cadastro ja existe (nada foi alterado)"
}

# -------------------------------------------------------------------- Fim ---
Titulo "Pronto!"
docker compose exec -T api python -m app.cli status 2>$null | ForEach-Object { "  $_" }

Write-Host @"

  O sistema esta rodando. Duas maneiras de usar:

  1. NO NAVEGADOR (ja vou abrir)
     http://localhost:8000/docs
     Clique em "Authorize", entre com o seu e-mail e senha.

  2. NO CELULAR
     Abra o arquivo INICIAR-APP-windows.bat e escaneie o QR code
     com o aplicativo Expo Go.

  Para desligar tudo depois, abra o arquivo PARAR-windows.bat.
"@

Start-Sleep -Seconds 1
Start-Process "http://localhost:8000/docs"
Fim 0
