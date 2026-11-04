# Windows 原生与 WSL

Windows 流程基于官方文档及路径检测，**待 Windows 实机验收**。助手用 Python 3.9+；优先 `py -3`，不假定预装。无 Python 时按下述原生流程操作，不静默下载安装依赖。

## 只读定位（PowerShell）

```powershell
Get-Command claude -All -ErrorAction SilentlyContinue |
  Select-Object CommandType, Name, Source, Path
Get-Process -ErrorAction SilentlyContinue |
  Where-Object { $_.ProcessName -match '^claude($|[- ])' } |
  Select-Object Id, ProcessName, Path
winget list --name Claude
```

只输出 `$env:USERPROFILE`、`$env:APPDATA`、`$env:LOCALAPPDATA`、`$env:CLAUDE_CONFIG_DIR` 等目录变量，不输出环境全集。`where.exe claude` 补查其他 PATH 安装。

注册表仅检查卸载项 `DisplayName`、`Publisher`、`InstallLocation`、`PSChildName`；不输出/直接执行未知 `UninstallString`。MSIX 用 `Get-AppxPackage` 查实际 Name、PackageFullName、Publisher、InstallLocation，不猜包 ID。

以下只是需存在并核对的候选：

- Code：`%USERPROFILE%\.claude`、`.claude.json`、native `.local\bin\claude.exe`、`.local\share\claude`、`.local\state\claude`。
- npm：以 `npm root -g` 和命令元数据为准，不删整个 `%APPDATA%\npm`。
- 桌面数据：`%APPDATA%\Claude`；fork 名字单独核实。
- 桌面程序/更新器：可能在 `%LOCALAPPDATA%\AnthropicClaude` 或其他实际 InstallLocation，交由原生卸载，不让 helper 猜安装根。
- MSIX：精确实际 PackageFullName；残留按实际 PackageFamilyName 查，不递归删除 `%LOCALAPPDATA%\Packages`/WindowsApps。
- VS Code：`%USERPROFILE%\.vscode\extensions`、`%APPDATA%\Code\User` 和 `CachedExtensionVSIXs`。Insiders/portable/Cursor 不套用稳定版路径。

## 备份、登出与卸载

先 plan/审核，正常退出相关工作会话后 backup，再登出和卸载。退出相关程序，不默认 `Stop-Process -Force` 或结束所有 node。助手通过 PowerShell CIM 查询进程元数据（不读取 CommandLine），读取失败就拒绝写入；无法识别所有 node/fork/IDE，仍需人工核对。此进程查询亦待 Windows 实机验收。

```powershell
# 本机帮助确认支持后
claude auth --help
claude auth logout

# 仅在 winget list 确认真实 ID 后，官方 Code 当前示例：
winget uninstall --id Anthropic.ClaudeCode --exact --source winget

# 仅在确认 npm 安装后
npm uninstall -g @anthropic-ai/claude-code

# 仅在确认对应 IDE/扩展后
code --uninstall-extension anthropic.claude-code
```

桌面版不预设 winget ID。用实际精确 ID 或“设置 → 应用 → 已安装的应用”卸载已核实产品。MSIX：`Remove-AppxPackage -Package <实际 PackageFullName>`，不使用 `-AllUsers` 或通配批量卸载。native 文件和用户数据交给精确 plan。提权需说明具体项，不静默提权、不改执行策略。

PowerShell profile 和环境变量只移除专属项；保留其他行/共享 PATH。API 变量可能有其他消费者，先核对。保留 Git Bash、Node、Python、WebView2、VC runtime。

## 凭据

Code Windows 凭据通常为配置根中的 `.credentials.json`；reset/uninstall 处理已确认根即可，不读取内容。桌面/fork 不保证相同。

优先应用自身登出。确有 Credential Manager 项时，在“凭据管理器 → Windows 凭据 → 普通凭据”核对精确 target，不展示密码；仅针对该项：

```powershell
cmdkey /delete:<已核实的精确TargetName>
```

不输出/保存 `cmdkey /list` 全集，不猜 `Claude`/`Anthropic` 批删，不删除 Microsoft Credentials、Vault、DPAPI、共享密码库。无法核查就记录凭据验收缺口。

## 文件锁、链接与 WSL

junction/reparse point 不等于普通目录。助手拒绝穿过重解析父路径，目录链接不自动删；Agent 单独核对共享消费者。AccessDenied/占用时报告，关闭对应程序后重扫；不改 ACL、不取得整个目录所有权、不静默安排重启后删除。

JSON 为 UTF-8；PowerShell 5.1 不用 `>` 写 manifest，使用助手 `--out`。路径带空格/中文加引号，不用 `Invoke-Expression`。

Windows 与 WSL 的 home/安装/凭据独立。`wsl --list --quiet` 仅列发行版；在用户授权的指定发行版里单独核查命令、版本、根目录、安装方式。此助手不支持 Linux apply；不可假冒 Windows 平台运行。需清理时按当时官方 Linux 说明独立制作清单/备份/登出/验证；不删发行版、VHD 或 `/mnt/c` 项目。

## 验收

命令/PATH/alias、winget/安装元数据、桌面程序/进程、目录、扩展注册/目录、已确认凭据。MSIX、fork、WSL、其他用户和系统级残留分别记录，“未查”不等于“不存在”。
