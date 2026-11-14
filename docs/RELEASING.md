# 自动发版

版本以 `module/module.prop` 的 `version`（`vMAJOR.MINOR.PATCH[-PRERELEASE]`）和
`versionCode` 为准。准备新版本时更新这两个字段；`versionCode` 必须递增，Tag 必须未使用。
无需提前修改 `update/update.json` 或 `update/CHANGELOG.md`。

推送到 `main` 且修改 `module/module.prop`，或在 `main` 手动运行 Release 工作流，即可发版。
工作流使用 `cliff.toml` 和 git-cliff 生成上一个版本 Tag 之后的 Release Notes，
首次发版没有 Tag 时使用全部提交历史。

工作流沿用 KernelSU module-release Action 打包、预检，在触发工作流的源码提交上创建 Tag，
上传 Draft Release，核对 Tag、Release Notes、ZIP 名称、上传状态和 SHA-256 后发布。
预发布版本保留 GitHub prerelease 标记，且不设为 Latest。

正式发布后，工作流将同一份 Notes 放入 `update/CHANGELOG.md` 顶部，保留既有历史，
并同步 `update/update.json`。这两个文件以独立的
`chore(release): sync version <tag> [skip ci]` 提交写回 `main`；
`cliff.toml` 过滤该提交，Tag 始终保留在源码提交上。
同步提交通过普通 rebase 接到最新 `main`，随后正常推送，不执行强推。

GitHub Actions 需要 `contents: write`，仓库分支规则需要允许工作流提交到 `main`。
工作流只对运行它的仓库操作；本地默认推送目标仍为 `dev`，公开仓库 `origin` 仅在明确授权后推送。
上传或校验失败时不会发布；发布后若同步提交失败，需修复同步，不要重发或移动已有 Tag。
