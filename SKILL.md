---
name: claude-local-cleanup
description: 安全检查、清理、重置或完整卸载 macOS 与 Windows 上的 Claude Code 和 Claude 桌面版，处理本地会话、缓存、配置、登录凭据及编辑器扩展残留。用于“把 Claude 清理干净”“重置 Claude Code”“卸载 Claude 并清除本机数据”等请求；不用于删除云端账号、取消订阅、修改机器标识或清理其他 AI 工具。
---

# Claude 本机清理与卸载

将用户指定范围落实为可审查清单，备份可复用资产，按安装渠道卸载，核验剩余项。默认中文。支持 macOS、Windows 原生；WSL 作为独立环境另行核对。

## 范围

| 模式 | 清理内容 | 保留内容 |
| --- | --- | --- |
| `cache` | Code 可再生缓存、已知分析缓存 | 会话、历史、调试日志、记忆、登录和设置全部保留 |
| `history` | CLI transcript、输入/编辑历史、调试及已知分析缓存 | 程序、登录、配置、Skills、项目记忆 |
| `reset` | Code 用户目录、配置及登录关系 | 程序、桌面版自身数据、项目源码；可复用资产另行备份 |
| `uninstall` | 程序、用户数据、所选桌面版、所选编辑器集成及专属凭据 | 项目源码、知识库、共享资产、其他工具、浏览器资料 |

“清理干净”不明确时询问一次，同时继续只读检查。已经明确完全卸载则按授权推进，不重复确认。`uninstall` 默认涵盖 Code/桌面版；只要其一时用助手 `--product code`/`--product desktop`。cache/history/reset 仅适用于 Code。

设备标识仅随授权范围内的配置删除而清除，不编辑系统机器标识，不承诺消除服务端关联。卸载不等于取消订阅、删除云端数据或吊销其他平台 API key。

## 流程

1. **先说明文件和计划。** 只读核对 OS、版本、安装渠道、`CLAUDE_CONFIG_DIR`、真实目录、进程、桌面版及编辑器。不要启动模型会话或自动更新。执行命令前说明用途。若当前执行者是 Claude Code/Claude 桌面版，只做检查和预览，把实际写入交给其他 Agent 或普通终端，避免清理正在使用的自身环境。
2. 读取 [macOS](references/macos.md) 或 [Windows](references/windows.md)。用脚本时再读 [助手说明](references/helper.md)；版本差异查 [官方来源](references/sources.md)。
3. 用 `scripts/claude_cleanup.py plan` 写预览，审查实际存在的路径与范围。默认 `--disposition delete` 永久删除清单文件；用户要可恢复移除时，可生成 `--disposition quarantine` 清单，说明它保留原始数据且不释放对应空间。这不是系统回收站，不自动清空。脚本不执行包管理器、不读密码。候选名称只是线索；未知 fork、扩展 ID、外部配置目录和安装位置由 Agent 核验后单独处理，不扩充 glob 删除范围。
4. 检查其他工具的 symlink/junction、hooks、绝对路径引用；迁出仍有消费者的资产并验证。先正常退出相关工作会话，**登出/原生卸载前运行 `backup`。** 助手仅备份可复用资产和少数安全设置，校验副本；不备份会话、凭据或原始 settings。不是完整回滚备份。若要恢复 MCP/env/hook 内嵌配置，先在用户授权的私密位置做加密备份，不写入报告/Skill。自定义 Skills/脚本也可能含敏感数据，备份保持本机私有。
5. reset/uninstall 优先当前版本支持的 `claude auth logout`（先查帮助）或交互 `/logout`；cache/history 不登出。停止相关 Claude 工作后按实际渠道卸载程序/扩展，不强退其他开发任务。只处理已确认的专属凭据；精确名称检查不代表覆盖所有变体。
6. 应用/扩展停止后运行 `apply --execute --apps-stopped`。助手在写入前和备份后读取进程元数据；发现已知 Claude 进程或无法核查就停止，不读取完整命令行或 kill。它不能识别所有 npm/node 包装及 IDE 进程，Agent 仍需核对。助手重新计算允许路径、核对文件身份和备份，拒绝危险配置根及父路径链接。卸载改变了文件身份时重新生成 plan，清单外新目录不顺手删除。
7. 复查目录、命令、进程、包管理器、扩展注册/目录、已核对凭据。uninstall 且选择 Code 时运行 `editor-state` 核查 VS Code 专属状态。修改 shell 后检查语法。记录权限缺口，区分逻辑大小、磁盘占用估算和实际回收量。

## 边界

- 不全盘按 `*claude*` 删除。不默认删除项目 `.claude`、`CLAUDE.md`、`.mcp.json`、Git worktree、知识库、其他用户或共享 Skills 平台。
- ZIP/DMG 先看归档结构或应用元数据；业务工作流包保留，不按文件名删除。
- 不输出令牌、密码、OAuth JSON、环境变量全集、原始 Keychain/凭据清单；不调用 `security ... -w/-g` 或 dump 整个凭据库。
- 不删除 Windows Credential/Vault/DPAPI、整个注册表分支、WindowsApps、WSL 发行版、共享 `Code Safe Storage` 或浏览器 cookie 库。系统最近文稿/TCC 等需归属明确且可访问；拒绝访问就报告，不绕过安全设置。
- 可选减少后续遥测仅适用于保留程序的用户；不擅自改代理、云后端、账号或创建自动任务。
- cache/history 保持设置原文，包括遥测、env、模型和权限。隔离目录可能含原始聊天、配置与凭据，须私有保存；文件移回不能恢复已登出的凭据或已卸载程序，不宣称完整回滚。
- 不把路径示例当成必然存在；不把 macOS 经验写成 Windows 已实机验证。

## 交付

简述实际范围，链接私有备份与机器可读记录，列剩余项和原因。凭据检查不全、权限拒绝或原生卸载尚未完成时，不宣称“所有痕迹已彻底清除”。
