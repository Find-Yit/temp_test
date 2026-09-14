# CLAUDE.md — zju_test_test 项目

本文件为 Claude Code 在本项目目录下工作时的项目级指引。
上级目录 `/scratch/e1351071/CLAUDE.md` 中的用户偏好（中文回答、删文件前须同意、
发现 bug 先说明再修、plan 存 plans/ 等）同样适用，本文件只补充本项目特有信息。

## GitHub 远程仓库

- **仓库地址（HTTPS）**：https://github.com/Find-Yit/temp_test.git
- **仓库地址（SSH，推荐日常使用）**：git@github.com:Find-Yit/temp_test.git
- **GitHub 账号**：Find-Yit
- **本地推送方式**：使用 SSH 密钥 `~/.ssh/id_ed25519_github`
  （`~/.ssh/config` 中已配置 `Host github.com` 走 `ssh.github.com:443`，
  因为本机 22 端口被防火墙拦截，必须走 443）
- **认证状态**：已验证可用，`ssh -T git@github.com` 返回 `Hi Find-Yit!`
  → 推送时**无需再输入用户名/密码，也无需 Personal Access Token**

### 推送约定

- 远程名统一用 `origin`，主分支用 `main`
- 首次推送：`git push -u origin main`
- **不要把以下内容提交进仓库**（体积过大或属于第三方代码 / 可重新生成的产物）：
  - `data/`（约 1.4 GB，含 682 MB 的 `tandt_db.zip` 数据集，远超 GitHub 100 MB 单文件上限）
  - `repo/`（第三方代码 SuGaR，约 216 MB，且自带独立 `.git`）
  - `venv/`（Python 虚拟环境，约 19 MB）
  - `cache/`、`outputs/`、`logs/`（运行时产物）
  - 这些排除规则写在本目录的 `.gitignore` 中
- 需要提交的主要是：`scripts/`、`notes/`、`plans/`、`CLAUDE.md`、`README.md`

## 项目结构

```
zju_test_test/
├── repo/SuGaR/     # 第三方代码（SuGaR: 3DGS → Mesh），独立 git 仓库，不纳入本仓库
├── data/           # 数据集 tandt_db（Tanks&Temples + DeepBlending），不纳入本仓库
├── venv/           # Python 虚拟环境，不纳入本仓库
├── scripts/        # 自己写的脚本（提交）
├── notes/          # 实验记录（提交）
├── plans/          # 计划文件，按用户偏好规则 4 保存于此（提交）
├── outputs/        # 实验产出（不提交）
├── logs/           # 运行日志（不提交）
└── cache/          # 缓存（不提交）
```

## 任务背景

李俊成老师组 6 小时考核：3DGS → Mesh（基于 SuGaR），
任务说明见本目录下的 `李俊成老师组_6小时考核_3DGS到Mesh_v2.pdf`，
总计划见 `plans/SuGaR考核总计划.txt`。
