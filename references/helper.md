# 跨平台助手

依赖 Python 3.9+ 标准库，不联网、不安装依赖、不执行卸载器。命令在 Skill 目录执行；macOS 用 `python3`，Windows 用已确认存在的 `py -3`（或实际 Python 命令）。路径均可加引号。

## 先预览与备份

输出位置选在待删目录之外的本机私密工作目录。以下 `review/` 为相对当前 Skill 目录的示例；不可把正在运行的 Skill 安装在待删除的 `~/.claude/skills` 内。若 Skill 来源正位于待删范围，先复制到范围外并从副本运行。实际使用可替换为用户指定的绝对输出目录。

```sh
python3 scripts/claude_cleanup.py plan --mode uninstall --product both --out review/plan.json
python3 scripts/claude_cleanup.py backup --out review/pre-uninstall-assets
```

Windows 对应：

```powershell
py -3 scripts/claude_cleanup.py plan --mode uninstall --product both --out review/plan.json
py -3 scripts/claude_cleanup.py backup --out review/pre-uninstall-assets
```

四模式：cache/history/reset 的 product 必须是 code（省略时自动 code）；uninstall 省略 product 为 both，可指定 desktop。cache 只纳入 Code 的 cache、telemetry、statsig、stats-cache.json，以及 macOS 的 claude-cli-nodejs 缓存；不扩展到 usage、会话、debug 或桌面版持久数据。只清桌面版不需要 Code 资产备份，但需另行核对桌面内有无未保存工作。备份不能代替完整恢复：不含会话、登录、原始配置的 env/MCP/hooks。hook 文件目录会保留，内嵌 hook 配置不复制。链接不跟随，备份 manifest 明确记录跳过项；仍有消费者的共享链接由 Agent 迁移/保留，不自动改链接。

先审查 plan，核对未知 fork 与用户选择；正常退出相关工作会话后做备份，再完成原生登出/卸载。之后重新 plan（使用新的文件名），避免原生卸载改变文件身份。不要手工伪造 path/identity 来绕过检查。plan 可删减条目实现更小范围，不可扩大到任意目录。

## 执行与复查

```sh
# 默认 apply 仍只预览，且不会生成 out 目录
python3 scripts/claude_cleanup.py apply --plan review/plan-after-native.json --out review/cleanup
# 已有用户授权，且 Agent 实际核实应用/扩展已停止后
python3 scripts/claude_cleanup.py apply --plan review/plan-after-native.json --out review/cleanup --execute --apps-stopped
```

`--apps-stopped` 仍是 Agent 完成检查的声明。助手在执行前及资产备份后读取进程元数据，发现已知 Claude 名称、native versions 路径或 app 路径就拒绝；无法读取时也停止。它不读取完整命令行、不终止进程，不能识别所有以 node 启动的旧 npm CLI、fork 和 IDE 内存状态，Agent 仍需核对。独立 `backup` 命令也先检查进程。`--execute` 是显式执行开关，不要求用户在明确授权后重复确认。

- 清单核对 OS/home/config/scope、精确候选及 lstat 身份；原生卸载已移除项记录 absent。出错停止，记录已完成项/剩余项，不盲重试。
- 所有输出必须是新路径，不覆盖旧审计。apply 执行时创建 `reviewed-plan.json`、`reusable-assets/`、`cleanup-report.json`；cache/history 不创建资产备份。记录按计划目标文件/目录，不是目录内每个文件的完整审计。
- 对已有真实目录，POSIX 删除内部 symlink 仅移除链接；Windows 嵌套 reparse point 会阻断该目录自动删除，交给人工核实。父路径链接和 config 根链接均拒绝。
- 只支持默认 Code 根或 home 直属 `.claude-*` 自定义根。其他 `CLAUDE_CONFIG_DIR` 拒绝自动处理，需 Agent 单独核实，不能为了通过脚本临时 unset 变量。
- 备份路径检查、复制校验或设置 JSON 解析失败时不删除；若原生卸载已先发生，依卸载前备份恢复，不能声称自动回滚。
- JSON 只含路径、身份、错误、计数和哈希，不含设置/凭据值。自定义资产备份可能含敏感内容；POSIX 目录 0700/文件 0600。Windows 继承输出目录 ACL，应选当前用户私有目录，不用共享网盘；脚本不宣称重设过 ACL。
- 没有执行包管理器、凭据删除、扩展注册、shell/环境清理、受保护系统记录；这些必须按系统说明完成并单独记录。脚本成功只证明计划内文件处理完成。

## 可恢复文件隔离（显式选择）

生成清单时使用 `--disposition quarantine`；缺省和旧版清单仍为 `delete`，永久删除行为保持不变。执行方式已写入清单，须在执行前审查，不通过 apply 临时改动。

```sh
python3 scripts/claude_cleanup.py plan --mode cache --disposition quarantine --out review/cache-plan.json
python3 scripts/claude_cleanup.py apply --plan review/cache-plan.json --out review/cache-result
```

授权执行后，助手以同文件系统 rename 将目标移入输出目录的 `quarantine/`，先写 `quarantine-map.json`，再逐项记录 source/destination。跨卷拒绝，不回退到复制后删除。`cleanup-report.json` 用 `quarantined` 与 `removed` 区分隔离和永久删除；失败时报告已处理目标与剩余目标。原路径消失不等于数据被擦除，也不表示释放空间。

隔离目录可能包含原始会话、配置或凭据，和资产备份的排除规则不同；只在用户理解差异的私有位置使用，不同步分享、不自动清空。POSIX 目录权限 0700；Windows 需确认继承的私有 ACL。恢复前逐项核对映射、目标完整性与原路径不存在，停止相关应用后由 Agent 单独处理，不覆盖新生成的数据。没有自动 restore 子命令，文件恢复不会撤销原生卸载、登出、凭据删除或 SQLite 状态清理。

## VS Code 专属状态

仅 uninstall 且用户选择清理 Code/扩展时使用，不用于 history/reset。其他 IDE 需其原生接口。

```sh
python3 scripts/claude_cleanup.py editor-state --out review/editor-preview.json
# 关闭 VS Code 后
python3 scripts/claude_cleanup.py editor-state --execute --apps-stopped --out review/editor-result.json
```

只处理稳定版 `Code/User` 下 `state.vscdb` 及 `.backup`：精确 `Anthropic.claude-code`、该 extension 的 `secret://` 命名空间（含 JSON extensionId 形式），不读 value；前后 `quick_check`。其他扩展不变。不遍历所有 DB 后按模糊字符串删 value，不删共享 `Code Safe Storage`。VS Code 不同版本的持久化形式可能变化，报告边界；无匹配不等于不存在其他形式。

## 安全测试

```sh
python3 scripts/test_cleanup.py
```

测试只在临时目录构造数据，含中文/空格、Windows 规则模拟、路径伪造、链接/共享文件、memory、凭据排除、失败日志、SQLite 精确删除与幂等性。不检查真实用户文件，也不等价于 Windows 实机/凭据验证。
