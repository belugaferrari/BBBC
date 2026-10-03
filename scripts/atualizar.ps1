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

$REPO_ZIP = 'https://github.com/belugaferrari/BBBC/archive/refs/heads/main.zip'

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
Write-Host "  Seus dados NAO estao nesta pasta - eles vivem no PostgreSQL." -ForegroundColor White
Write-Host "  Atualizar troca o programa, e nao os lancamentos." -ForegroundColor White

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

    & git pull --ff-only origin main 2>&1 | ForEach-Object { "    $_" }
    if ($LASTEXITCODE -ne 0) {
        Erro "O git nao conseguiu trazer a versao nova."
        Write-Host "  O relato esta acima. Nada foi desmontado - o sistema"
        Write-Host "  continua funcionando na versao de antes."
        Fim 1
    }
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
    Remove-Item $temp -Recurse -Force -ErrorAction SilentlyContinue
    Ok "Codigo atualizado"
}

# ---------------------------------------------------------------- pronto ---
Titulo "Pronto"
Write-Host "  O que acontece agora:"
Write-Host "    - as bibliotecas so sao reinstaladas se a lista mudou;"
Write-Host "    - as tabelas novas do banco sao criadas na proxima partida;"
Write-Host "    - os seus dados continuam todos la."
Write-Host ""

$r = Read-Host "  Abrir o BBBC agora? (s/n) [s]"
if ($r -and $r.ToLower() -ne 's') {
    Write-Host "  Quando quiser: ABRIR-BBBC-windows.bat"
    Fim 0
}

& (Join-Path $PSScriptRoot 'abrir-tudo.ps1')
