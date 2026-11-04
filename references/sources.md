# 来源与验证边界

编写核验日期：2026-11-03；软件/文档可能更新，发生差异时复查入口与本机帮助。

- [Claude Code 安装与卸载](https://code.claude.com/docs/en/setup)：native/Homebrew/npm/WinGet；删除用户配置的影响、IDE/桌面仍安装时目录重建。
- [身份验证](https://code.claude.com/docs/en/authentication)：官方登出、macOS Keychain/文件回退、Windows 文件凭据及 `CLAUDE_CONFIG_DIR`。
- [会话](https://code.claude.com/docs/en/sessions)：transcript、保留策略、`claude purge`；history 优先核对当前官方命令的实际选项/影响。
- [桌面版](https://support.claude.com/en/articles/10065433-install-claude-desktop)：系统/安装入口；不能据此推断所有版本的残留路径和 fork ID。
- [Microsoft winget uninstall](https://learn.microsoft.com/en-us/windows/package-manager/winget/uninstall)：精确应用选择/卸载参数。
- [Microsoft cmdkey](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/cmdkey)：精确 target 删除；未提供 Claude 通用 target 名。

macOS 实践覆盖：native、Claude-3p 数据/虚拟机、VS Code 注册/目录/专属 SQLite 状态、alias、确认的 Keychain service。最近文稿受权限限制。两个名为 Claude 的 ZIP 实为业务 Skills 包，保留。

案例只证明当时本机行为。Skill 不携带用户绝对路径、账号、聊天和凭据。Windows 规则/安全逻辑有隔离测试；原生卸载、凭据、文件锁、权限和真实 reparse point 待 Windows 实机验收。

## 外部 Skill 对照（2026-11-04）

静态审阅 [suyuan2022/suyuan-skill 的 claude-cleanup](https://github.com/suyuan2022/suyuan-skill/tree/8babd4557a4774ca8e3d5b784d82f0ee5a4565e5/claude-cleanup)，固定提交 `8babd4557a4774ca8e3d5b784d82f0ee5a4565e5`；未运行其脚本，以下只评价该版本实现。

| 对方设计 | 本 Skill 的处理 |
| --- | --- |
| 独立可再生缓存清理，保护会话与资产 | 新增窄范围 cache 模式，与删除会话的 history 分开 |
| Claude 自身执行时只审计、检测运行状态 | 增加执行前及备份后进程保护；只读元数据，避免完整命令行可能含敏感参数 |
| 全量复制用户目录，按文件数/总字节数校验 | 保留有限资产备份与逐文件 SHA-256，不默认另存全部会话和凭据，不宣称全量回滚 |
| 移至 macOS 废纸篓 | 提供显式 quarantine，同卷 rename、预写映射和目标级结果记录；不冒充 Windows 回收站，不自动清空 |
| 保持已有遥测设置 | cache/history 保持设置原文，回归测试覆盖含 env、hooks、权限的完整设置 |
| 本地 ID 轮换、精简模式、系统时区修改 | 不纳入清理范围；继续以重置/卸载的用户目标为准 |
| 面向 macOS，固定默认配置根 | 保留 Windows 原生路径和既有自定义根保护；WSL 仍需独立审查 |

改进为独立实现，没有复制外部脚本。隔离测试验证了设置保留、隔离移动失败不丢数据、native 版本路径识别及备份后重启保护；不等价于 Windows 实机验收或对外部项目的完整安全认证。
