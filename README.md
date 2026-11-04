# Claude 本机清理与卸载

**说清楚想保留什么，让 Agent 帮你完成 Claude 的检查、备份、清理和复查。**

`claude-local-cleanup` 是一个面向 macOS 与 Windows 的 Agent Skill。你可以用它清理 Claude Code 历史、重置本地环境，或卸载 Claude Code 和 Claude 桌面版；完成后得到资产备份、处理记录，以及没有清完的项目和原因。

它适合准备重装 Claude、清理旧会话，或停止使用 Claude、同时需要保留项目和知识库的用户。**macOS 有来源工作流的实操案例；Windows 已编写流程并完成隔离逻辑测试，仍待实机验收。**

## 先试一次：只检查，不删除

可从本仓库的 **Code → Download ZIP** 下载完整文件；若解压目录带分支名，先将其重命名为 `claude-local-cleanup`。也可解压完整 Skill 分享包，将该文件夹放在本机工作目录中，然后在能读取该目录的 Agent 里发送：

```text
请读取 claude-local-cleanup/SKILL.md，检查这台电脑的 Claude 安装和本地残留。
先只读检查，告诉我发现了什么、哪些可以清理、哪些需要保留，不执行删除。
```

这里的路径相对于该工作目录。Agent 会按系统说明核对实际安装、配置目录、进程及编辑器集成，整理可审查的清单；目录或凭据状态无法核实时，会列出缺口。

若已经安装到 Agent 的 Skills 目录，可直接使用 `$claude-local-cleanup` 调用。需要长期使用时，将**整个文件夹**放入目标 Agent 已配置的 Skills 目录，保留 `SKILL.md`、`references/` 和 `scripts/`；自动发现方式以目标工具配置为准。

清理时，Skill 自身和输出目录都应位于待删除范围之外。要清理 `~/.claude` 时，先将安装在其中的本 Skill 复制出来，再从副本运行。

## 你想做什么，就这样说

### 只清缓存，保留全部会话

```text
使用 $claude-local-cleanup，只清理 Claude Code 的可再生缓存。
保留历史、会话、项目记忆、登录、设置和 Skills。
```

对应 `cache`：只处理已识别的缓存与分析缓存。执行前需正常退出相关 Claude 工作会话；现有设置，包括遥测开关，保持原文。

### 清历史，继续使用 Claude

```text
使用 $claude-local-cleanup，只清理 Claude Code 的本地会话历史、日志和缓存。
保留登录、配置、Skills 和项目记忆。
```

对应 `history`：处理已识别的 CLI 会话、输入/编辑历史、调试及分析缓存，保留程序和工作配置。

### 重置环境，准备重新配置

```text
使用 $claude-local-cleanup，重置 Claude Code 的本地环境，保留程序。
先备份可复用的 Skills、CLAUDE.md 和 hooks，说明哪些数据无法恢复。
```

对应 `reset`：清理 Code 用户数据、配置和登录关系。用户目录中的会话、自动记忆及插件状态等也会丢失；资产备份只覆盖其中一部分。

### 完全卸载，保留业务资料

```text
使用 $claude-local-cleanup，卸载 Claude Code 和 Claude 桌面版，清除本机数据。
保留项目源码、知识库和共享 Skills；先备份可复用资产，完成后列出剩余项。
```

对应 `uninstall`：按实际渠道卸载程序，处理用户目录、所选编辑器集成、专属凭据和环境残留。也可明确指定“只卸载 Code”或“只卸载桌面版”。

以上是**调用示例**。执行范围以你的请求和本机检查结果为准；第三方客户端、未知安装位置及不同 IDE 需要分别核实。

## 完成后，你会得到什么

| 产出 | 能帮助你确认什么 |
| --- | --- |
| 路径与范围清单 | 实际发现了哪些目标，准备处理哪些内容 |
| 可复用资产备份 | 保留了哪些 Skills、规则及 hook 文件，哪些被跳过 |
| 文件处理记录 | 哪些已删除、哪些已不存在、哪些失败或仍有残留 |
| 原生操作与复查说明 | 程序、登录、凭据、扩展和终端配置的实际处理结果，以及权限限制 |

文件助手实际执行后，指定输出目录的结构如下。`reusable-assets/` 仅在 reset/uninstall 涉及 Code 时生成：

```text
清理输出目录/
├── reviewed-plan.json
├── reusable-assets/
│   └── backup-manifest.json
└── cleanup-report.json
```

**资产备份不等于完整恢复。** 它保留存在的 `CLAUDE.md`、Skills、hooks、commands、agents 及少数安全设置，校验文件副本；不包含聊天、凭据、自动记忆或原始配置中的 env、MCP、内嵌 hook 等。共享链接目标不跟随，跳过项会记录。如需保留完整配置，应在清理前另做经授权的私密加密备份。

如果希望文件移除后仍有恢复机会，可在生成清单时显式选择 `--disposition quarantine`。文件会移到私有输出目录的 `quarantine/`，原路径映射记录在 `quarantine-map.json`；同卷移动，跨卷拒绝。**隔离仍保留原始数据，可能包含会话和凭据，也不释放对应空间。** 它不是系统回收站，不会自动清空，也无法回滚登出、原生卸载或数据库状态清理。缺省 `delete` 仍为永久删除清单目标，详细使用见 [助手说明](references/helper.md)。

## 来源案例：一次 macOS 完整清理

这个 Skill 从一次实际清理工作中整理而来。当时的需求是：根据一篇本地清理笔记，卸载 Claude Code 和桌面版、清除本机数据，同时保留业务资产。

实际处理包括 native CLI、桌面版残留及虚拟机数据、VS Code 扩展与专属状态、终端别名，以及已核实的专属钥匙串项。

- 删除目标清理前的磁盘占用估算约 **14.2 GiB**，该数值不是实际释放空间的测量结果。
- 备份并校验了 **410 个可复用文件**，项目源码和知识库保留。
- 扩展卸载后继续复查，清除了仍留在磁盘上的扩展目录和专属状态。
- 两个名为 Claude 的 ZIP 经检查实为业务 Skills 包，因此保留。
- 系统“最近使用的文稿”记录因权限不足未检查；只核对了确认的精确钥匙串名称，没有宣称覆盖所有变体。

这是来源工作流的实操结果，不代表当前 Skill 已在所有系统或客户端上完成端到端验证。

## 支持范围与重要边界

| 环境 | 当前覆盖与验证情况 |
| --- | --- |
| macOS | 提供 native、Homebrew、npm、桌面版和编辑器处理说明；来源工作流有实操案例，助手有隔离测试 |
| Windows 原生 | 提供 native、winget、npm、桌面版、凭据及扩展流程；路径和重解析属性已模拟测试，原生操作待实机验收 |
| WSL | 作为独立环境核查；Python 助手不支持在 Linux/WSL 中执行清理，不删除发行版 |

使用完整流程需要 Agent 具备本机文件和命令访问能力。Python 助手要求 **Python 3.9+**，只用标准库；缺少 Python 时可按系统说明走原生流程，不会静默安装依赖。

清理遵循几条边界：

- 项目 `.claude`、`.mcp.json`、`CLAUDE.md`、Git worktree、知识库及其他工具不默认删除；共享资产先核对消费者。
- 不全盘按名称批删，不因 ZIP/DMG 叫 Claude 就认定为安装包。
- 不输出凭据值，不删除共享密码库，不改系统机器标识或绕过安全策略。
- 权限拒绝、文件占用、未知凭据或客户端变体会作为剩余项报告；不能据脚本成功就说“所有痕迹已彻底清除”。
- 实际写入前会检查已知 Claude 进程，读取失败或发现运行态就拒绝；不读取完整进程命令行。npm/node 包装和未知 fork 仍需人工核对。Claude 自身执行此 Skill 时只做检查与预览。

卸载不会取消订阅、删除云端账号数据，或吊销其他平台的 API key。自定义资产中也可能有敏感内容，备份和清理记录应保存在本机私密位置；Windows 输出目录需具有适当的私有权限。

## 想直接用脚本？从预览开始

从完整 Skill 目录运行以下命令。`review/` 必须位于待删范围之外，输出名称不得与旧记录重复。

macOS：

```sh
python3 scripts/claude_cleanup.py plan --mode uninstall --product both --out review/plan.json
python3 scripts/claude_cleanup.py apply --plan review/plan.json --out review/cleanup-preview
```

Windows PowerShell（已有 Python Launcher 时）：

```powershell
py -3 scripts/claude_cleanup.py plan --mode uninstall --product both --out review/plan.json
py -3 scripts/claude_cleanup.py apply --plan review/plan.json --out review/cleanup-preview
```

成功时生成 `review/plan.json`，预览返回 `dry_run: true`，不删除文件，也不创建 `cleanup-preview` 目录。路径链接等阻断项需先核查。

实际清理还需备份、按范围登出/卸载、停止相关应用，再用新清单执行。助手不会自动调用卸载器、删除系统凭据或修改 shell；这些由 Agent 配合原生工具完成。执行开关、备份范围和故障处理见 [助手说明](references/helper.md)，不要将预览命令当作完整卸载流程。

## 文档与验证

- [SKILL.md：Agent 入口、范围与工作流程](SKILL.md)
- [macOS 操作说明](references/macos.md)
- [Windows 与 WSL 操作说明](references/windows.md)
- [Python 助手：参数、备份、执行与输出](references/helper.md)
- [官方来源与验证边界](references/sources.md)

现有 **40 项隔离测试**覆盖预览、缓存与历史范围隔离、项目记忆、备份、链接、路径伪造、部分失败、进程保护、文件隔离、幂等性和 VS Code 专属状态。测试只操作临时目录；Windows 的模拟检查不能代替实机验收。可在 Skill 目录运行：

```sh
python3 scripts/test_cleanup.py
```

Windows 可使用已确认可用的 `py -3`；创建符号链接权限不足时，相关测试会跳过。

当前包未附许可证文件，使用和再分发许可尚未明确。
