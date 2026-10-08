# BBBC - troca a senha de quem entra no aplicativo.
#
# Existe por uma noite concreta: o aplicativo instalado nao deixava entrar, a
# suspeita caiu na senha, e nao havia o que fazer - nao dava para ver o que
# estava sendo digitado nem para trocar. Esquecer a senha do proprio sistema
# virava um beco sem saida, com o unico jeito sendo mexer no banco a mao.
#
# So funciona NESTE computador, o que guarda o banco. Nao ha "esqueci minha
# senha" pela rede, e nao vai haver: um e-mail de recuperacao seria uma porta a
# mais para um sistema que, de proposito, nao tem porta nenhuma para fora. Quem
# esta na frente desta maquina ja tem acesso a tudo de qualquer forma.
#
# A senha NAO passa pela linha de comando em momento nenhum - ela vai pelo cano
# da entrada padrao. Escrita como parametro, apareceria na lista de processos do
# Windows enquanto o comando roda, e ficaria no historico do terminal depois.

$ErrorActionPreference = 'Continue'
$RAIZ = Split-Path -Parent $PSScriptRoot
Set-Location (Join-Path $RAIZ 'backend')

function Titulo($t) { Write-Host "`n$t" -ForegroundColor White }
function Ok($t)     { Write-Host "  [ok] $t" -ForegroundColor Green }
function Erro($t)   { Write-Host "`n[x] $t" -ForegroundColor Red }
function Aviso($t)  { Write-Host "  [!] $t" -ForegroundColor Yellow }

function Fim($codigo) {
    Write-Host ""
    Read-Host "Aperte Enter para sair" | Out-Null
    exit $codigo
}

Write-Host ""
Write-Host "  TROCAR A SENHA DO BBBC" -ForegroundColor White
Write-Host "  (so vale neste computador, o que guarda o banco)" -ForegroundColor DarkGray

# ------------------------------------------------- por onde falar com o banco ---
#
# Duas instalacoes possiveis, e o script serve as duas: a nativa (um .venv dentro
# de backend) e a com Docker (o Python mora no container). Perguntar ao usuario
# qual ele tem seria pedir que ele soubesse de algo que nunca precisou saber.
$BANCO_USUARIO = 'bbbc'
$BANCO_SENHA   = 'bbbc'
$BANCO_NOME    = 'bbbc'

$pyVenv = Join-Path (Get-Location) '.venv\Scripts\python.exe'
$comDocker = $false

if (Test-Path $pyVenv) {
    $env:DATABASE_URL = "postgresql+psycopg://${BANCO_USUARIO}:${BANCO_SENHA}@localhost:5432/${BANCO_NOME}"
    if (-not $env:SECRET_KEY) { $env:SECRET_KEY = 'dev-secret-change-me' }
} else {
    Set-Location $RAIZ
    $docker = Get-Command docker -ErrorAction SilentlyContinue
    if (-not $docker) {
        Erro "Nao achei a instalacao do sistema neste computador."
        Write-Host "  Esperava encontrar backend\.venv (instalacao sem Docker)"
        Write-Host "  ou o Docker rodando. Rode o INICIAR primeiro."
        Fim 1
    }
    & docker compose ps api *> $null
    if ($LASTEXITCODE -ne 0) {
        Erro "O sistema precisa estar ligado para eu trocar a senha."
        Write-Host "  Clique no INICIAR-windows.bat e tente de novo."
        Fim 1
    }
    $comDocker = $true
}

function Chamar-CLI {
    param([string[]]$Argumentos, [string]$PelaEntrada)

    if ($comDocker) {
        if ($null -ne $PelaEntrada) {
            return ($PelaEntrada | & docker compose exec -T api python -m app.cli @Argumentos 2>&1)
        }
        return (& docker compose exec -T api python -m app.cli @Argumentos 2>&1)
    }
    if ($null -ne $PelaEntrada) {
        return ($PelaEntrada | & $pyVenv -m app.cli @Argumentos 2>&1)
    }
    return (& $pyVenv -m app.cli @Argumentos 2>&1)
}

# ------------------------------------------------------------- quem existe ---
#
# A lista vem antes da pergunta porque o engano mais provavel aqui e o e-mail, e
# quem chegou neste script ja esta irritado por nao conseguir entrar. Mostrar
# antes evita o chute - e o chute errado manda procurar o problema no lugar
# errado outra vez.
Titulo "1. Quem entra no sistema"
$saida = Chamar-CLI -Argumentos @('logins')
if ($LASTEXITCODE -ne 0) {
    Erro "Nao consegui falar com o banco de dados."
    $saida | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray }
    Write-Host ""
    Write-Host "  O sistema precisa estar ligado. Clique no INICIAR e tente de novo."
    Fim 1
}

$logins = @()
foreach ($linha in @($saida)) {
    $partes = "$linha".Split("`t")
    if ($partes.Count -ge 2 -and $partes[1].Contains('@')) {
        $logins += [pscustomobject]@{ Nome = $partes[0].Trim(); Email = $partes[1].Trim() }
    }
}

if ($logins.Count -eq 0) {
    Erro "Nao ha ninguem cadastrado ainda."
    Write-Host "  Rode o INICIAR uma vez: ele faz o cadastro da familia."
    Fim 1
}

foreach ($l in $logins) {
    Write-Host ("    {0,-12} {1}" -f $l.Nome, $l.Email) -ForegroundColor Cyan
}

# ------------------------------------------------------------- de quem e ---
Titulo "2. De quem e a senha que vamos trocar?"
if ($logins.Count -eq 1) {
    # Com um login so nao ha o que escolher, e pedir que ele copie o proprio
    # e-mail a mao seria so uma chance a mais de errar de letra.
    $email = $logins[0].Email
    Write-Host "    $email (o unico cadastrado)" -ForegroundColor Cyan
} else {
    $email = (Read-Host "    Digite o e-mail").Trim()
    if (-not $email) { Erro "Sem e-mail nao da. Nada foi alterado."; Fim 1 }
    $achado = $logins | Where-Object { $_.Email -ieq $email }
    if (-not $achado) {
        Erro "Nao ha login com o e-mail '$email'."
        Write-Host "  Os que existem estao na lista acima. Nada foi alterado."
        Fim 1
    }
}

# ------------------------------------------------------------- a senha nova ---
Titulo "3. A senha nova"
Write-Host "    Ela nao aparece na tela enquanto voce digita (nem fica gravada"
Write-Host "    no historico). Pelo menos 8 caracteres."
Write-Host ""

function Texto-De($segura) {
    # Read-Host -AsSecureString guarda a senha cifrada na memoria; para mandar
    # pelo cano ela precisa voltar a ser texto. O ponteiro e liberado logo em
    # seguida - deixa-lo vivo manteria a senha em claro na memoria do processo
    # ate o Windows resolver limpar.
    $ponteiro = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($segura)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ponteiro) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ponteiro) }
}

$senha = Texto-De (Read-Host "    Senha nova" -AsSecureString)
if ($senha.Length -lt 8) {
    Erro "A senha precisa de pelo menos 8 caracteres. Nada foi alterado."
    Fim 1
}
$repetida = Texto-De (Read-Host "    De novo, para conferir" -AsSecureString)
if ($senha -ne $repetida) {
    # Digitar errado duas vezes a mesma coisa e comum; gravar a primeira sem
    # conferir seria trocar um "nao consigo entrar" por outro igual.
    Erro "As duas senhas nao sao iguais. Nada foi alterado."
    Fim 1
}

# --------------------------------------------------------------- a troca ---
Titulo "4. Trocando"
$saida = Chamar-CLI -Argumentos @('trocar-senha', '--email', $email, '--senha-de-stdin') -PelaEntrada $senha
$deuCerto = ($LASTEXITCODE -eq 0)
$senha = $null
$repetida = $null

if (-not $deuCerto) {
    Erro "Nao deu."
    $saida | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray }
    Fim 1
}

Ok "Senha trocada para $email"
Write-Host ""
Write-Host "  No celular, entre com essa senha nova." -ForegroundColor White
Write-Host "  O botao 'mostrar' na tela de login deixa conferir o que foi digitado." -ForegroundColor DarkGray
Write-Host ""
Write-Host "  E se o aplicativo disser que nao achou o servidor: o endereco" -ForegroundColor DarkGray
Write-Host "  termina em :8000. O 8081 e a porta da tela, nao a do servidor." -ForegroundColor DarkGray
Fim 0
