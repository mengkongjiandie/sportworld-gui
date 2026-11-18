# ============================================================
# 构建 SportWorld.exe（零依赖单目录版）
#
# 前置条件：
#   - Python 3.12      (winget install Python.Python.3.12)
#   - Node.js 18+      (winget install OpenJS.NodeJS)
#   - playwright       (npm install -g playwright)
#
# 用法：
#   .\build.ps1
# 输出：
#   dist\SportWorld\    （整个目录即为可分发版本）
# ============================================================

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$py   = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $py) { throw "找不到 Python，请先安装：winget install Python.Python.3.12" }

Write-Host "==> 1/5 安装 PyInstaller" -ForegroundColor Cyan
& $py -m pip install --quiet --upgrade pyinstaller

Write-Host "==> 2/5 PyInstaller 打包" -ForegroundColor Cyan
Push-Location $root
try {
    & $py -m PyInstaller --onedir --noconfirm --clean --windowed `
        --name "SportWorld" `
        --paths "." `
        --paths "com.zjwh.android_wh_physicalfitness\协议\7.3.92" `
        --hidden-import sport_client --hidden-import login `
        --hidden-import run --hidden-import stats --hidden-import logout `
        gui.py
} finally { Pop-Location }

$dist = Join-Path $root "dist\SportWorld"

Write-Host "==> 3/5 复制协议代码（按清单，排除版本库与备份）" -ForegroundColor Cyan
$protoDst = Join-Path $dist "com.zjwh.android_wh_physicalfitness"
$protoSrc = Join-Path $root "com.zjwh.android_wh_physicalfitness"

# 用 robocopy 做白名单式复制：排除 .git / 缓存 / 备份 / 运行时文件
# /XD 排除目录  /XF 排除文件  /NFL /NDL /NJH /NJS 静默
$null = robocopy $protoSrc $protoDst /E `
    /XD ".git" "__pycache__" ".idea" ".vscode" `
    /XF "*.bak" "*.pyc" "_session.json" "settings.json" "error.log" `
        "_device_id.txt" "_checkpoints_cache.json" `
    /NFL /NDL /NJH /NJS /NP
if ($LASTEXITCODE -ge 8) { throw "robocopy 复制失败，退出码 $LASTEXITCODE" }

# 兜底再清一遍（robocopy 对不同版本的排除支持有差异）
Get-ChildItem $protoDst -Recurse -Force -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -in @(".git", "__pycache__") } | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem $protoDst -Recurse -Force -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Extension -in @(".bak", ".pyc") -or
                   $_.Name -in @("_session.json","settings.json","error.log","_device_id.txt","_checkpoints_cache.json") } |
    Remove-Item -Force -ErrorAction SilentlyContinue

# 许可证与说明随包分发
foreach ($doc in @("LICENSE", "THIRD-PARTY-NOTICES.md")) {
    $p = Join-Path $root $doc
    if (Test-Path $p) { Copy-Item $p (Join-Path $dist $doc) -Force }
}
if (-not (Test-Path (Join-Path $dist "LICENSE"))) {
    Write-Warning "缺少 LICENSE，请补齐后再分发"
}

Write-Host "==> 4/5 复制便携 Node + Playwright" -ForegroundColor Cyan
$npmRoot = (npm root -g 2>$null)
if (-not $npmRoot -or -not (Test-Path "$npmRoot\playwright")) {
    throw "找不到全局 playwright，请先运行：npm install -g playwright"
}
New-Item -ItemType Directory -Force -Path "$dist\node\node_modules" | Out-Null
Copy-Item (Get-Command node).Source "$dist\node\node.exe" -Force
Copy-Item "$npmRoot\playwright" "$dist\node\node_modules\playwright" -Recurse -Force

Write-Host "==> 5/5 完成" -ForegroundColor Green
$total = (Get-ChildItem $dist -Recurse -File | Measure-Object Length -Sum).Sum
Write-Host ("    输出目录: {0}" -f $dist)
Write-Host ("    总大小  : {0:N1} MB" -f ($total / 1MB))
Write-Host ""
Write-Host "把整个 dist\SportWorld 目录打包即可分发。" -ForegroundColor Yellow
Write-Host "注意：运行环境需要 Microsoft Edge（Windows 10/11 自带）。" -ForegroundColor Yellow