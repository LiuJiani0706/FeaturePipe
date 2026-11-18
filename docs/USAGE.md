# 使用指南

[返回项目首页](../README.md)

除克隆步骤外，以下命令均在仓库根目录执行。Python 3.10+，只使用标准库；完整论文实验的文件锁支持 macOS、Linux，Windows 请使用 WSL。

## 三种入口

| 入口 | 用途 | 调用方式 |
| --- | --- | --- |
| Codex Skill | 日常采访写作，按用户目标调整篇幅与流程 | 当前助手写作，外部 API 为可选项 |
| `featurepipe.paper_experiment` | 论文协议与提示词对照研究 | 外部 API，保存阶段产物和预算预留 |
| `python3 -m featurepipe` | 早期简版、离线演示与回归比较 | `--mock` 为固定虚构响应；未指定时会调用 API |

日常写作无需自动增加对照稿或完整五轮实验。三种入口的结果与成本应分别报告。

## 快速开始：离线验证

```bash
git clone https://github.com/LiuJiani0706/FeaturePipe.git
cd FeaturePipe
python3 -m unittest discover -s tests -v
python3 skills/featurepipe-reporter/scripts/run.py demo --output runs/demo
```

首次运行的输出目录必须尚不存在。演示结果包括 `article.md`、`report.json`、`usage.json` 和过程文件。`demo` 强制使用固定虚构响应，不发送采访、不需要密钥；只能验证流程，不能展示在线模型写作能力。

## 使用 Codex Skill

将 [`skills/featurepipe-reporter`](../skills/featurepipe-reporter) 整个目录复制到个人技能目录 `~/.codex/skills/`；已有同名技能时先比较版本，避免覆盖自己的修改。Skill 自带所需程序与资源，不依赖本仓库的固定路径。

调用示例：

> $featurepipe-reporter 用这份采访写一篇中文特稿，先给大纲，再写正文，保留来源、修订记录和待核实问题。

默认使用当前助手，消耗当前会话额度，不额外调用外部模型接口。外部实验需明确本次材料发送范围、服务和预算；历史任务预算不自动沿用。详见 [Skill 指引](../skills/featurepipe-reporter/SKILL.md)。

## 准备采访材料

输入 JSON 使用稳定、唯一的来源编号：

```json
{
  "title": "报道选题",
  "materials": [
    {"id": "S1", "label": "受访者甲", "text": "采访原文"},
    {"id": "S2", "label": "登记表", "text": "有明确统计时点的记录"}
  ]
}
```

[`examples/borrow-room.json`](../examples/borrow-room.json) 包含八组虚构来源，不能作为真实新闻发布。独立生成实验中，已发表文章或参考成稿应留作评测，不进入生成输入。

导入自己有权处理的 DOCX：

```bash
python3 skills/featurepipe-reporter/scripts/run.py import \
  --file /path/to/interview1.docx \
  --file /path/to/interview2.docx \
  --title "报道选题" \
  --output runs/private-inputs/case.json
```

可加 `--alias-map /path/to/aliases.json`，内容如 `{"原姓名":"化名"}`。替换作用于正文和标签，不修改原文件；这是显式字符串替换，**不是全面自动脱敏**。只导入 DOCX 正文文字，内嵌图片不作为证据。另写的本地来源清单含原文件路径和哈希，不应公开。

### 离线检查直接引语

演示运行后，可以对同一组虚构来源做字面匹配，不发送材料、不调用 API：

```bash
python3 skills/featurepipe-reporter/scripts/run.py inspect \
  --input examples/case.json \
  --article runs/demo/article.md \
  --output runs/demo/literal-evidence.json
```

检查输出文件也必须尚不存在。引语文字匹配不能验证说话人、语境或间接陈述的真实性。

## 外部模型实验

通用客户端支持 DeepSeek 官方及硅基流动的 Chat Completions 兼容接口。论文实验器的模型 ID 与人民币价格表是 **2026-11-16 快照**；运行前核对供应商当前模型、价格及数据处理政策。模型可用性以服务账户为准。

把配置保存在仓库根目录的本地 `.env`，或通过 `--env-file` 指定；不要把真实密钥写进命令、代码或提交记录：

```dotenv
FEATUREPIPE_API_KEY=在本地填写
FEATUREPIPE_BASE_URL=https://api.siliconflow.cn/v1
FEATUREPIPE_MODEL=deepseek-ai/DeepSeek-V4-Pro
```

环境变量优先，`.env` 不执行 shell 表达式。通用客户端也接受 `DEEPSEEK_API_KEY`；论文实验器仅允许显式价格表中的模型，更换地址不会自动更新单价。

设置本次预算后试跑一轮（示例 10 元累计估算上限，可能不足以完成长篇审查）：

```bash
python3 skills/featurepipe-reporter/scripts/run.py paper \
  --input runs/private-inputs/case.json \
  --output runs/paper-trial \
  --env-file .env \
  --max-rmb 10 --rounds 1 --workers 4
```

该入口包括旧版与论文版初稿对照。默认写作模型 `deepseek-ai/DeepSeek-V4-Pro`，评价模型 `zai-org/GLM-5.3`；两者都会收到采访内容。示例预算不是完整实验费用承诺。

完整协议使用 `--rounds 5`：采访摘要 → 元提示词 → 大纲检查及局部修订/重建 → 初稿与长度检查 → 五轮逐句检查、资深编辑汇总、顺序修订和每轮五项清理 → 第六次只读审阅。工程适配与早期简版差异见 [复现说明](REPRODUCTION.md)。

同配置中断后加 `--resume` 继续；输入、模型、提示词或轮数变化时使用新目录。不要同时向同一输出目录启动多个进程。主要产物：

| 文件 | 内容 |
| --- | --- |
| `A-legacy-drafting-prompt.txt` | 旧提示词首次生成稿 |
| `B-paper-D0-first.txt`、`B-paper-D0.txt` | 论文版首次初稿及长度补救后的初稿 |
| `r*-*`、`article.txt` | 逐轮过程与最后保存的正文 |
| `report.json`、`metrics.json` | 完成情况、篇幅及引语匹配信号 |
| `usage.json`、`budget-config.json` | 调用、供应商用量和估算费用 |

### 费用与停止机制

`--max-rmb` 是两模型共享的累计本地估算上限。请求前预留输入和最大输出费用并落盘，返回后按供应商 usage 核算，未知计费用满预留额；恢复时把未结请求计为已占用。接近保护线会停止新增写作请求，保存已有产物，并尝试用预留额度评价；完成状态以报告为准。

估算上限不等于供应商账单硬限制。早期简版的 `--max-tokens` 只是字符和输出预留的工程预算，不是人民币限制、准确分词计数或当前助手的额度。恢复不保证接口调用恰好一次，未知计费请求不能视作免费。

## 目录与构建

```text
featurepipe/                    核心程序与实验器
skills/featurepipe-reporter/     自包含 Codex Skill
prompt_sets/                    中文提示词与来源记录
evaluation/                     原访谈指南回译与新增量表
examples/                       虚构输入
tests/                          不调用付费接口的测试
scripts/                        导入、检查和发布工具
docs/                           复现边界、评估与后续工作
```

修改核心程序后重新生成 Skill 内嵌模块，再打包源码：

```bash
python3 scripts/build_skill.py
python3 scripts/package_source.py
```

输出 `release/featurepipe-reporter.zip` 与 `release/featurepipe-source.zip`，按公开文件清单构建，排除私有运行目录和本地凭证。Skill 的 `runtime-manifest.json` 保存源文件及内嵌模块哈希，避免维护两个分叉。

## 提示词与评价资源

中文提示词依据英文附录回译，不是恢复的原始中文运行字符串。论文原访谈指南和本项目新增量表分别维护；模型审阅与字面匹配不能代替来源核实。

- [中文提示词](../prompt_sets/论文提示词中文执行版.txt)
- [论文访谈指南中文回译](../evaluation/论文访谈评价指南中文版.txt)
- [本项目新增评价标准](../evaluation/评价标准.json)
- [评估记录与已知局限](EVALUATION.md)
- [隐私与数据安全](../SECURITY.md)
