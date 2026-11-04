# Claude Local Cleanup

**清理电脑上 Claude Code 和 Claude 桌面版的本地数据与卸载残留，保留项目源码和知识库。**

[![MIT License](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

这是给 Codex 等能访问本机文件的 AI 助手使用的一套清理技能，附带 Python 工具。它帮助你查找 Claude 的安装文件、缓存、聊天历史、配置和登录残留，再按需要清缓存、重置环境或完整卸载，并说明哪些内容已处理、哪些还留着。

适合三种情况：清理缓存但继续使用 Claude；准备重装、清掉旧环境；停止使用 Claude、清除本机残留。提供 macOS 与 Windows 流程，**Windows 原生操作仍待实机验收**。

## 快速开始

先获取完整技能。需要 Git；也可[下载 ZIP](https://github.com/javenhub/claude-local-cleanup/archive/refs/heads/main.zip)，解压后进入包含 `SKILL.md` 的目录。

```sh
git clone https://github.com/javenhub/claude-local-cleanup.git
cd claude-local-cleanup
```

在能访问该目录的 Codex 或其他本机 AI 助手中发送：

```text
读取当前目录的 SKILL.md，检查这台电脑的 Claude 安装和本地残留。
先只读检查，列出实际发现的内容和建议清理范围，不执行删除。
```

首次会得到安装与残留检查结果、待处理清单和无法核实的项目。确认具体需求后再让 Agent 清理，例如：

```text
只清理 Claude Code 的可再生缓存，保留聊天、登录、配置和 Skills。
```

已经安装到 Agent 的 Skills 目录时，可以用 `$claude-local-cleanup` 调用。复制安装时保留整个目录；实际执行位置及输出目录须在待删范围之外。

## 可以帮你做什么

### 1. 选择清理范围，保留继续使用的内容

| 你的需求 | 模式 | 主要保留内容 |
| --- | --- | --- |
| 只清可再生缓存 | `cache` | 聊天、历史、记忆、登录和设置 |
| 清掉本地聊天与使用历史 | `history` | 程序、登录、配置、Skills 和项目记忆 |
| 重置 Claude Code，准备重新配置 | `reset` | 程序；可复用资产另做有限备份 |
| 卸载 Code、桌面版或两者 | `uninstall` | 项目源码、知识库和其他工具 |

重置和卸载会丢失所选范围内的本地状态，包括会话、自动记忆或插件状态等。项目内的 `.claude`、`.mcp.json` 和 `CLAUDE.md` 不默认删除；共享资产先检查依赖。

### 2. 先检查、备份，再处理与复查

流程是：检查实际路径与安装渠道 → 备份可复用资产 → 按范围登出/卸载 → 执行清单 → 复查残留。

你会得到路径清单、资产备份，以及已处理、失败和剩余目标的记录。reset/uninstall 涉及 Code 时，备份存在的 Skills、`CLAUDE.md`、hook 文件等并校验副本；**它不包含完整聊天、凭据、自动记忆或所有配置，不能完整恢复旧环境**。有权限限制或未知客户端时，Agent 会报告缺口。

助手在写入前检查已知 Claude 进程，不读取完整命令行，也不自动结束进程。Claude 自身执行本技能时仅检查和预览；实际写入交由其他 Agent 或普通终端。旧 npm/node 包装、未知 fork 和 IDE 状态仍需人工核查。

### 3. 需要恢复机会时，选择文件隔离

生成清单时可显式选择 `--disposition quarantine`，将目标同卷移入私有输出目录，并记录原路径；失败时保留已移动和未移动的数据，停止继续处理。

**隔离仍保留原始数据，可能含聊天和凭据，也不释放对应空间。** 它不是系统回收站，不自动清空，不能撤销登出、原生卸载或数据库状态清理。默认 `delete` 会永久删除清单目标，执行前应核对清单和处理方式。

## 支持范围与验证

| 环境 | 当前状态 |
| --- | --- |
| macOS | 有来源工作流的实际清理案例；脚本通过隔离测试 |
| Windows 原生 | 已提供安装、凭据和清理流程；路径及进程查询有模拟测试，原生卸载、权限、文件锁和 junction 待实机验收 |
| WSL | 作为独立环境核查；Python 助手不支持 Linux/WSL 执行清理，不删除发行版 |

Python 助手要求 **Python 3.9+**，仅使用标准库。没有 Python 时可由 Agent 按系统说明走原生流程。程序卸载、系统凭据和 shell 修改由 Agent 配合原生工具完成，文件脚本成功不代表这些步骤也已完成。

已有 **40 项隔离测试**覆盖清理范围、项目记忆、备份、链接、进程保护、文件隔离与部分失败。测试只操作临时目录，不等于所有系统和客户端都已实机验证。

卸载不取消订阅、不删除云端账号数据，也不吊销其他平台 API key。备份与隔离目录应保存在本机私密位置，不纳入公开仓库。

## 详细文档

- [Agent 操作入口](SKILL.md)
- [macOS 清理与卸载](references/macos.md)
- [Windows 与 WSL](references/windows.md)
- [脚本参数、预览、备份、隔离与结果记录](references/helper.md)
- [来源案例、官方资料与验证边界](references/sources.md)

## 反馈与贡献

维护者：[javenhub](https://github.com/javenhub)。可通过 [Issues](https://github.com/javenhub/claude-local-cleanup/issues) 反馈问题或提交改进；涉及清理行为的修改请附隔离测试，不提交真实聊天、配置或凭据。

## 许可证

采用 [MIT License](LICENSE)。使用、修改或分发时保留许可证和版权声明。
