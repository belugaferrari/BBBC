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

# A saida vai gravada tambem: falhando, e ela que diz o motivo, e adivinhar
# em cima ("deve ser porta ocupada") manda o usuario para o lado errado.
$logSubida = Join-Path (Get-Location) 'subida.log'
docker compose up -d --build 2>&1 | Tee-Object -FilePath $logSubida | Out-Host

if ($LASTEXITCODE -ne 0) {
    Erro "Nao consegui subir o sistema."
    $relato = (Get-Content $logSubida -Raw -ErrorAction SilentlyContinue)

    if ($relato -match 'already allocated|address already in use|bind: ') {
        Write-Host ""
        Write-Host "  Outro programa ja esta usando a porta 5432 ou a 8000." -ForegroundColor White
        Write-Host "  O mais comum e um PostgreSQL instalado direto no Windows."
        Write-Host "  Feche-o e rode este arquivo de novo."
    }
    elseif ($relato -match 'unhealthy|dependency failed to start') {
        Write-Host ""
        Write-Host "  O banco de dados nao respondeu a tempo." -ForegroundColor White
        Write-Host "  Isso costuma ser so demora, e nao defeito - especialmente"
        Write-Host "  com o computador carregado. Rodar de novo quase sempre"
        Write-Host "  resolve, porque na segunda vez o banco ja subiu antes."
        Write-Host ""
        Write-Host "  O que o banco registrou:" -ForegroundColor White
        Write-Host ""
        docker compose logs --tail=30 db 2>&1 | ForEach-Object { Write-Host "    $_" }
        Write-Host ""
        Write-Host "  Se aparecer ali que os dados estao corrompidos, e possivel"
        Write-Host "  recomecar o banco do zero com estes dois comandos - mas"
        Write-Host "  isso apaga os lancamentos ja cadastrados:"
        Write-Host ""
        Write-Host "      docker compose down -v" -ForegroundColor Yellow
        Write-Host "      (e rodar este arquivo de novo)" -ForegroundColor Yellow
    }
    else {
        Write-Host ""
        Write-Host "  As ultimas linhas do que o Docker respondeu:" -ForegroundColor White
        Write-Host ""
        Get-Content $logSubida -Tail 25 -ErrorAction SilentlyContinue |
            ForEach-Object { Write-Host "    $_" }
    }

    Write-Host ""
    Write-Host "  O relato inteiro ficou guardado em:" -ForegroundColor White
    Write-Host "    $logSubida"
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

# Codigo de saida em vez de ler texto: 0 precisa cadastrar, 1 ja existe,
# 2 sem banco. Ler a mensagem faria uma falha de conexao parecer "ja existe" -
# justamente quando o cadastro e necessario.
docker compose exec -T api python -m app.cli needs-setup *> $null
$precisaCadastro = $LASTEXITCODE

if ($precisaCadastro -eq 2) {
    Erro "A API subiu, mas nao esta falando com o banco de dados."
    Write-Host "  Veja o que aconteceu com: docker compose logs"
    Fim 1
}

if ($precisaCadastro -eq 0) {
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

    # As senhas vao pela entrada padrao, e nao como argumento: aspas, cifrao e
    # acento se perdem ou quebram ao atravessar a linha de comando do Windows.
    $OutputEncoding = [System.Text.UTF8Encoding]::new($false)
    $entrada = "$senha`n$senhaConjuge"

    $entrada | docker compose exec -T api python -m app.cli seed-family `
        --skip-if-exists --passwords-from-stdin `
        --name "Familia BBBC" `
        --titular "Felipe" --titular-email $emailTitular `
        --conjuge "Clarissa" --conjuge-email $emailConjuge `
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
