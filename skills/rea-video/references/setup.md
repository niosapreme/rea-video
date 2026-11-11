# 安装与 VLM 配置

## 托管安装

需要 ffmpeg、ffprobe、Python ≥ 3.10。在源码仓库中运行：

```bash
bash scripts/install_skill.sh --dry-run
bash scripts/install_skill.sh install
~/.local/bin/rea-video --version
bash scripts/install_skill.sh update
bash scripts/install_skill.sh rollback
bash scripts/install_skill.sh uninstall
```

`PYTHON_BIN=python3.12` 可选指定解释器。`--dry-run` 可与各动作组合。安装器先检查冲突，再把源码快照复制到 `~/.local/share/rea-video/versions/<version>-<commit>-<architecture>/`，在其中创建独立 Python 环境并验证，最后切换 `current`。命令入口是 `~/.local/bin/rea-video`；请确保 `~/.local/bin` 在 PATH 中。

唯一的 skill 正文在 `~/.local/share/rea-video/current/skill/`。安装器为 Claude Code、Codex、通用 agent 分别建立 `~/.claude/skills/rea-video`、`~/.codex/skills/rea-video`、`~/.agents/skills/rea-video` 链接，均指向该正文；不会改 agent 设置文件。已有非安装器拥有的同名文件、目录或链接会导致安装拒绝，请自行检查后处理。

更新失败时旧版继续可用；回滚切换到之前的版本。卸载只删除清单证明由安装器拥有的链接和版本，保留 `~/.rea-video` 中的用户数据。Intel 与 Apple Silicon 各自建立原生环境，不复制虚拟环境；Apple Silicon 尚未在真实机器上验证。

安装器使用 macOS/Linux 的 `fcntl.flock` 非阻塞独占锁；另一个安装操作正在运行时会立即报错。锁文件位于 `~/.local/share/rea-video/.installer.lock`，卸载后也可保留，空闲的旧锁文件不会阻止重新安装。更新时 CLI 和 skill 链接保持不变，只原子切换 `current` 指针。

## VLM 配置（建议，不强制）


外部 VLM 只在本次明确传入 `--vlm` 时启用；保存的 `prefs vlm=on` 不再自动上传媒体。默认仅本地分析，`--no-vlm` 可明确关闭。VLM 会向配置的端点发送每镜头最多 12 秒的缩小片段、关键帧及分析提示词；默认还发送整片 480p 片段（可能带音轨），可用 `--no-whole` 关闭。第三方服务的隐私政策适用。分析结果会保存在输出目录的 `vlm_cache/`，删除该目录即可清除；不要将其公开分享。

端点必须是 HTTPS；仅本机 loopback 开发服务可用 `--vlm-allow-local-http`（或 `REA_VLM_ALLOW_LOCAL_HTTP=1`）明确允许 HTTP。局域网 HTTP 和其他协议不可用。`--vlm-max-requests N` / `REA_VLM_MAX_REQUESTS` 限制包括重试、备用模型和帧回退在内的实际请求次数（默认 60）。`REA_VLM_MAX_RETRIES` 默认 1（最多 3），`REA_VLM_TIMEOUT` 默认 180 秒，`REA_VLM_MAX_REQUEST_BYTES` 默认 20000000 字节。超过预算时本地分析继续，VLM 结果标为部分成功或失败。

**VLM（建议配置，不强制）**：VLM 是能看图/看视频的多模态大模型（Gemini、GPT-4o、豆包、Qwen-VL 等）。不开 VLM，工具只靠像素统计、帧率、OCR、元数据判断，照样能跑完、出报告，但**实拍 / AI / 3D 的区分明显变弱**，音效清单也只有信号层的低置信候选。开了 VLM，工具会把每个镜头的短片段和关键帧发给它，再和确定性结果融合。

配置走 OpenAI 兼容接口，按以下顺序读取：

1. `REA_VLM_BASE_URL` / `REA_VLM_API_KEY` / `REA_VLM_MODEL`（`REA_VLM_MODEL` 可写多个模型、逗号分隔，前一个失败自动换下一个）
2. 如果没有，回落到 capsule-cinema 的 `VIDEO_ANALYSIS_*` 或 `GEMINI3_*`

用 `--env-file <某个 .env>` 读取配置（例如复用 capsule-cinema 的）。**不要把密钥写进对话、仓库或报告，也不要打开 .env 看内容。**

用户没配 VLM 时：照常不加 `--vlm` 跑，不要因此中止任务。

- **你自己能看图（多模态 agent）**：你就是这次的"VLM"，不需要建议用户另配。按 SKILL.md 第 1 节的「看图复核并入」做：`rea-video review` → 逐镜看图填答案 → `rea-video apply-review`，你的判断会并入工具结论和报告。结论里写"未开 VLM，由 agent 看图复核"。
- **你看不了图**：遵守 `review.md` 的「看不了图时的规则」，并在回复末尾用一句话建议配置 VLM（说明能提升实拍/AI/3D 的区分和音效识别）。
- 实测（2026-10-30，仓库 eval/RESULTS.md）：agent 看图复核并入比单开 Gemini VLM 更准；Gemini 容易把卡通 3D 风格的 AI 视频判成 3D 渲染、把画进画面的游戏界面判成录屏。所以能看图时**一定要做看图复核**，开了 VLM 也要做，并且独立判断，不要照抄 VLM。
- 外部 VLM 仍有你替代不了的部分：它能直接看视频片段的运动、听音轨。你只能看静帧、听不了声音时，音效和人声来源照样标"待确认"。

**VLM 是否真的生效，以 `rea-video summary` 的 `VLM:` 一行为准**（也在 `breakdown.json` 的 `analysis.vlm.status`）：`ok` 已生效、`partial` 部分镜头有结果、`failed` 请求了但全部调用失败（例如服务端 503）、`not_configured` 请求了但没找到配置、`off` 没请求。`failed` / `not_configured` 等同没开 VLM，报告里要如实写，不能写"已开 VLM"。

启动时会核对 `current`、清单与版本目录的所有权标记。已验证的活动版本可修复旧清单；清单有效而 `current` 缺失时可恢复指针。无法证明所有权时停止并报告恢复原因，`--dry-run` 不执行恢复。首次安装中断且尚未建立清单时需人工检查，安装器不会认领已有链接。
