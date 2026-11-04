# macOS

## 只读核查

- `command -v claude`、`type -a claude`，追踪真实文件判断 native/npm/Homebrew/alias；`claude --version`、`claude auth --help`、`claude purge --help` 只查看版本/帮助。
- native 常见：`~/.local/bin/claude`、`~/.local/share/claude`、`~/.local/state/claude`。
- Code：`~/.claude`、`~/.claude.json`、实际 `CLAUDE_CONFIG_DIR`；有自定义目录时还检查默认目录的旧数据，但不自动删除旧根。
- 枚举 `/Applications`、`~/Applications` 的 `.app/Contents/Info.plist` 确认 bundle ID/产品；符号链接不跟随删除目标。
- `~/Library/{Application Support,Caches,Preferences,Logs,Saved Application State,HTTPStorages,WebKit}` 按已确认 app name/bundle ID 定位。`Claude-3p` 只是本次遇到的 fork，助手候选仍需验证。
- `ps -axo pid=,comm=` 只输出 PID/程序路径，避免完整命令行中的凭据。
- 定位 shell 别名和专属变量，敏感值不输出；共享 `~/.local/bin` PATH 保留。

## 顺序

先计划、正常退出相关工作会话并备份，再登出和卸载；helper `apply` 也做备份，但不可取代卸载前的 `backup`。退出 Claude/相关扩展，保留其他开发任务。执行者为 Claude 自身时只检查/预览；执行前的元数据检查不能识别所有 npm/node 包装方式，仍需人工核对。

| 渠道 | 核实后的操作 |
| --- | --- |
| native | 让 helper 的精确清单处理 native 文件与用户数据 |
| Homebrew | `brew list --cask`，仅卸载实际已安装的 `claude-code`/`claude-code@latest`；桌面 cask 单独核实 |
| npm | 核对 `npm root -g` 和包元数据，`npm uninstall -g @anthropic-ai/claude-code`；不删整个 npm/cache |
| 桌面 app | 确认元数据后删除实际 `.app`；`/Applications` 不在 helper 自动范围 |
| VS Code | `code --list-extensions` 核对后 `code --uninstall-extension anthropic.claude-code`；复查注册/目录/缓存 |
| JetBrains/Cursor/其他 IDE | 用插件管理器处理实际精确插件 ID，不删整个 IDE 用户目录 |

## 凭据、状态与受限项

优先 `claude auth logout`（帮助确认支持）或 `/logout`。本机曾遇到 `Claude Code-credentials` 和 `Claude Safe Storage`；其他版本、配置目录可能使用哈希变体。名称必须来自实际可验证来源，不能照搬文章小写名就宣称覆盖全部。

对已核实的精确 service 使用 `security find-generic-password -s <名称>`，程序将 stdout/stderr 丢弃，只记退出码：0 找到，44 未找到，其他值不确定。删除用 `security delete-generic-password -s <名称>`，同样抑制输出。不使用 `-w/-g`，不 dump。未知变体由用户在 Keychain Access 核对，报告未覆盖；不删共享其他 app 的存储。

扩展卸载成功后仍可能留物理目录及 `.obsolete`，后者只移除该扩展 key。关闭 VS Code 再运行 helper `editor-state`，包含 `state.vscdb.backup`；未关闭 IDE 可能重新写回状态。

最近文稿、TCC、诊断日志、废纸篓、安装挂载卷分别核实，不在默认脚本范围。无权限时报告具体缺口，不修改安全设置。

## 验收

uninstall：检查命令/alias、实际应用/包、进程、目录、扩展注册/目录、已确认 service；重新打开终端/IDE 再查是否重建。reset 后不要启动并登录才说“无数据”，启动会生成新状态。history 保留 memory、Skills、登录和设置是预期。
