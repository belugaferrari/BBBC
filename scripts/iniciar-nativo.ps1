# BBBC - liga o sistema SEM Docker, direto no Windows.
#
# Existe porque o Docker Desktop roda um Linux inteiro numa maquina virtual, e
# em computador modesto isso vira o gargalo: motor que nao liga, imagem levando
# quinze minutos, banco que nao responde a tempo. Aqui o Python e o PostgreSQL
# rodam nativos - mais leves, e sem nada para "subir" antes.
#
# Em troca, sao dois programas a instalar uma vez. O INICIAR-windows.bat, com
# Docker, continua valendo para quem preferir.

$ErrorActionPreference = 'Continue'
$RAIZ = Split-Path -Parent $PSScriptRoot
Set-Location (Join-Path $RAIZ 'backend')

function Titulo($t) { Write-Host "`n$t" -ForegroundColor White }
function Ok($t)     { Write-Host "  [ok] $t" -ForegroundColor Green }
function Erro($t)   { Write-Host "`n[x] $t" -ForegroundColor Red }
function Aviso($t)  { Write-Host "  [!] $t" -ForegroundColor Yellow }

function Fim($codigo) {
    Write-Host "`nPode fechar esta janela." -ForegroundColor White
    Read-Host "Aperte Enter para sair"
    exit $codigo
}

# O banco so escuta em localhost, entao a senha aqui nao protege de ninguem de
# fora - ela existe porque o Postgres exige uma. Mesma da versao com Docker, de
# proposito: o DATABASE_URL fica identico nos dois caminhos.
$BANCO_USUARIO = 'bbbc'
$BANCO_SENHA   = 'bbbc'
$BANCO_NOME    = 'bbbc'

# Guarda o que foi encontrado mas recusado, para a mensagem de erro poder
# dizer "achei o 3.10" em vez de "nao achei nada".
$script:PythonsRecusados = @()

function Versao-De($exe, $parametros) {
    # O parametro NAO pode se chamar $args: e variavel automatica do PowerShell,
    # e o valor passado se perde em silencio. Com ela, 'py -3.13' virava 'py'
    # puro, respondia com o Python velho da maquina, e a deteccao reportava uma
    # versao que nunca foi pedida.
    if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { return $null }
    try {
        $saida = (& $exe @($parametros + '--version') 2>&1 | Out-String).Trim()
    } catch { return $null }

    # O codigo de saida decide primeiro. Sem ele, 'py -3.12' numa maquina que
    # so tem o 3.10 responde "Python 3.12 not found!" e sai com erro - e
    # procurar a versao solta no meio do texto aceita essa frase como se fosse
    # a resposta. Foi exatamente o que aconteceu: o passo 1 anunciou Python
    # 3.12 e o passo 4 morreu dizendo que o 3.12 nao existe.
    if ($LASTEXITCODE -ne 0) { return $null }

    # Ancorado no inicio: a resposta legitima e exatamente "Python X.Y.Z".
    if ($saida -notmatch '^Python (\d+)\.(\d+)') { return $null }

    return @{ maior = [int]$Matches[1]; menor = [int]$Matches[2] }
}

function Achar-Python {
    # O 'python' do Windows pode ainda ser o atalho da Microsoft Store, que nao
    # e Python nenhum: abre a loja e sai com erro. O teste de codigo de saida em
    # Versao-De cobre esse caso junto com o do 'py'.
    foreach ($candidato in @(
        @{ exe = 'py';      args = @('-3.13') },
        @{ exe = 'py';      args = @('-3.12') },
        @{ exe = 'py';      args = @('-3.11') },
        @{ exe = 'py';      args = @('-3')    },
        @{ exe = 'python';  args = @()        },
        @{ exe = 'python3'; args = @()        }
    )) {
        $v = Versao-De $candidato.exe $candidato.args
        if (-not $v) { continue }

        if ($v.maior -eq 3 -and $v.menor -ge 11) {
            return @{
                exe    = $candidato.exe
                args   = $candidato.args
                versao = "$($v.maior).$($v.menor)"
            }
        }
        # Serve como Python, mas e velho demais: guarda para o aviso.
        $script:PythonsRecusados += "$($candidato.exe) $($candidato.args) -> Python $($v.maior).$($v.menor)"
    }
    return $null
}

function Achar-Psql {
    $cmd = Get-Command psql -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    # O instalador oficial nao poe o psql no PATH. Procura onde ele instala,
    # da versao mais nova para a mais antiga.
    $achados = Get-ChildItem 'C:\Program Files\PostgreSQL\*\bin\psql.exe' -ErrorAction SilentlyContinue |
               Sort-Object { [int]($_.Directory.Parent.Name) } -Descending
    if ($achados) { return $achados[0].FullName }
    return $null
}

Write-Host "============================================"
Write-Host "  BBBC - Financas da familia (sem Docker)"
Write-Host "============================================"

# ---------------------------------------------------------------- Python ---
Titulo "1. Conferindo o Python"
$py = Achar-Python
if (-not $py) {
    Erro "Nao encontrei o Python 3.11 ou mais novo."
    if ($script:PythonsRecusados.Count -gt 0) {
        Write-Host ""
        Write-Host "  Achei Python nesta maquina, mas velho demais:" -ForegroundColor Yellow
        $script:PythonsRecusados | Select-Object -Unique | ForEach-Object {
            Write-Host "    $_"
        }
        Write-Host ""
        Write-Host "  Instalar o novo nao remove nem estraga esse que ja esta ai."
        Write-Host ""
    }
    Write-Host "  Baixe em https://www.python.org/downloads/"
    Write-Host ""
    Write-Host "  IMPORTANTE: na primeira tela do instalador, marque a caixinha" -ForegroundColor Yellow
    Write-Host "  'Add python.exe to PATH' antes de clicar em Install." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Depois feche esta janela e rode este arquivo de novo."
    Start-Process "https://www.python.org/downloads/"
    Fim 1
}
Ok "Python $($py.versao) (via $($py.exe) $($py.args))"

# ------------------------------------------------------------ PostgreSQL ---
Titulo "2. Conferindo o PostgreSQL"
$psql = Achar-Psql
if (-not $psql) {
    Erro "Nao encontrei o PostgreSQL."
    Write-Host "  Baixe em https://www.postgresql.org/download/windows/"
    Write-Host "  (clique em 'Download the installer')"
    Write-Host ""
    Write-Host "  Durante a instalacao:" -ForegroundColor Yellow
    Write-Host "    - ele pede uma senha para o usuario 'postgres'. ANOTE-A." -ForegroundColor Yellow
    Write-Host "      Vou pedi-la aqui daqui a pouco." -ForegroundColor Yellow
    Write-Host "    - aceite o resto como vem, inclusive a porta 5432."
    Write-Host ""
    Write-Host "  Depois feche esta janela e rode este arquivo de novo."
    Start-Process "https://www.postgresql.org/download/windows/"
    Fim 1
}
Ok "PostgreSQL encontrado"

# --------------------------------------------------------------- Banco ---
Titulo "3. Preparando o banco de dados"

$env:PGPASSWORD = $BANCO_SENHA
& $psql -U $BANCO_USUARIO -h localhost -d $BANCO_NOME -c 'SELECT 1' *> $null
$jaExiste = ($LASTEXITCODE -eq 0)

if ($jaExiste) {
    Ok "Banco ja preparado"
} else {
    Write-Host "  Preciso criar o banco. Para isso uso a senha do 'postgres'"
    Write-Host "  que voce escolheu ao instalar o PostgreSQL."
    Write-Host ""
    $senhaSegura = Read-Host "  Senha do usuario postgres" -AsSecureString
    $env:PGPASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
        [Runtime.InteropServices.Marshal]::SecureStringToBSTR($senhaSegura))

    & $psql -U postgres -h localhost -d postgres -c 'SELECT 1' *> $null
    if ($LASTEXITCODE -ne 0) {
        Erro "A senha nao foi aceita, ou o PostgreSQL nao esta rodando."
        Write-Host "  Se errou a senha, e so rodar este arquivo de novo."
        Write-Host "  Se nao for a senha: abra 'Servicos' no Windows e confira se"
        Write-Host "  o servico postgresql esta 'Em execucao'."
        Fim 1
    }

    # DO $$ para nao falhar se a role ja existir de uma tentativa anterior.
    $criarRole = "DO `$`$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='$BANCO_USUARIO') THEN CREATE ROLE $BANCO_USUARIO LOGIN PASSWORD '$BANCO_SENHA'; END IF; END `$`$;"
    & $psql -U postgres -h localhost -d postgres -c $criarRole *> $null
    if ($LASTEXITCODE -ne 0) { Erro "Nao consegui criar o usuario do banco."; Fim 1 }

    # CREATE DATABASE nao roda dentro de bloco, entao vai solto - e falha de
    # boa se ja existir, o que nao e problema.
    & $psql -U postgres -h localhost -d postgres -c "CREATE DATABASE $BANCO_NOME OWNER $BANCO_USUARIO" *> $null

    $env:PGPASSWORD = $BANCO_SENHA
    & $psql -U $BANCO_USUARIO -h localhost -d $BANCO_NOME -c 'SELECT 1' *> $null
    if ($LASTEXITCODE -ne 0) { Erro "Criei o banco, mas nao consigo entrar nele."; Fim 1 }
    Ok "Banco criado"
}
Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue

# ------------------------------------------------------------ Bibliotecas ---
Titulo "4. Instalando o que o sistema precisa"
$venv = Join-Path (Get-Location) '.venv'
$pyVenv = Join-Path $venv 'Scripts\python.exe'

if (-not (Test-Path $pyVenv)) {
    Write-Host "  (so na primeira vez, alguns minutos)"
    Write-Host ""
    & $py.exe @($py.args + @('-m', 'venv', $venv))
    if (-not (Test-Path $pyVenv)) { Erro "Nao consegui criar o ambiente do Python."; Fim 1 }
}

$logPip = Join-Path (Get-Location) 'instalacao.log'
& $pyVenv -m pip install --upgrade pip --quiet 2>&1 | Tee-Object -FilePath $logPip | Out-Host
# -e (vinculado a pasta) e nao copia: o cli.py localiza as migrations a partir
# de onde ele proprio esta. Copiado para dentro do Python, procuraria db\migrations
# ao lado da copia, onde nao ha nada, e "criar as tabelas" falharia.
& $pyVenv -m pip install -e . 2>&1 | Tee-Object -FilePath $logPip -Append | Out-Host
if ($LASTEXITCODE -ne 0) {
    Erro "Nao consegui instalar as bibliotecas."
    Write-Host ""
    Get-Content $logPip -Tail 20 -ErrorAction SilentlyContinue | ForEach-Object { Write-Host "    $_" }
    Write-Host ""
    Write-Host "  O relato inteiro esta em: $logPip"
    Fim 1
}
Ok "Bibliotecas instaladas"

# -------------------------------------------------------------- Tabelas ---
$env:DATABASE_URL = "postgresql+psycopg://${BANCO_USUARIO}:${BANCO_SENHA}@localhost:5432/${BANCO_NOME}"
$env:APP_ENV = 'development'
if (-not $env:SECRET_KEY) { $env:SECRET_KEY = 'dev-secret-change-me' }

Titulo "5. Criando as tabelas"
& $pyVenv -m app.cli migrate
if ($LASTEXITCODE -ne 0) { Erro "Nao consegui criar as tabelas."; Fim 1 }
Ok "Tabelas prontas"

# ------------------------------------------------------------- Cadastro ---
Titulo "6. Conferindo o seu cadastro"

function Perguntar-Email($rotulo, $padrao) {
    while ($true) {
        $r = Read-Host "  $rotulo [$padrao]"
        if ([string]::IsNullOrWhiteSpace($r)) { $r = $padrao }
        if ($r -match '^[^@\s]+@[^@\s]+\.[^@\s]+$') { return $r }
        Write-Host "  Isso nao parece um e-mail. Tente de novo."
    }
}

function Perguntar-Senha($rotulo) {
    while ($true) {
        $a = Read-Host "  $rotulo (minimo 8 caracteres)" -AsSecureString
        $t1 = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
            [Runtime.InteropServices.Marshal]::SecureStringToBSTR($a))
        if ($t1.Length -lt 8) { Write-Host "  Muito curta. Tente outra."; continue }
        $b = Read-Host "  Digite a mesma senha de novo" -AsSecureString
        $t2 = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
            [Runtime.InteropServices.Marshal]::SecureStringToBSTR($b))
        if ($t1 -ne $t2) { Write-Host "  As duas nao bateram. Vamos de novo."; continue }
        return $t1
    }
}

& $pyVenv -m app.cli needs-setup *> $null
$precisa = $LASTEXITCODE

if ($precisa -eq 2) {
    Erro "As tabelas existem, mas nao consigo falar com o banco."
    Fim 1
}

if ($precisa -eq 0) {
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

    # Pela entrada padrao: aspas, cifrao e acento se perdem ao atravessar a
    # linha de comando do Windows, e em silencio.
    $OutputEncoding = [System.Text.UTF8Encoding]::new($false)
    "$senha`n$senhaConjuge" | & $pyVenv -m app.cli seed-family `
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

# ------------------------------------------------------------------ API ---
Titulo "Pronto!"
& $pyVenv -m app.cli status 2>$null | ForEach-Object { "  $_" }

Write-Host ""
Write-Host "  Vou ligar o sistema agora. ESTA JANELA PRECISA FICAR ABERTA" -ForegroundColor Yellow
Write-Host "  enquanto voce usar o aplicativo - e ela que segura tudo." -ForegroundColor Yellow
Write-Host ""
Write-Host "  Para ver no navegador:  http://localhost:8000/docs"
Write-Host "  Para ver no celular:    abra o INICIAR-APP-windows.bat"
Write-Host "                          (em OUTRA janela, deixando esta aqui)"
Write-Host ""
Write-Host "  Para desligar: aperte Ctrl+C aqui, ou feche a janela."
Write-Host ""

Start-Sleep -Seconds 2
Start-Process "http://localhost:8000/docs"

# 0.0.0.0 e nao localhost: o celular precisa alcancar esta maquina pela rede.
& $pyVenv -m uvicorn app.main:app --host 0.0.0.0 --port 8000
