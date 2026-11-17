# FeaturePipe：中文采访写作流水线与 Codex Skill

把已有采访材料组织成中文深度报道，保留来源编号、过程稿与修订记录，支持论文方法复现和提示词对照实验。

**当前状态：可运行的研究原型。** 已有离线测试、在线接口实测与独立 Skill；尚未完成完整五轮论文实验和人工盲评，不能保证生成稿达到发表标准。本仓库是依据研究手稿独立实现的工程版本，不是原论文的原始实验代码。

## 可以做什么

- 整理人物关系、时间线、核心矛盾和信息缺口，生成策略、大纲与初稿。
- 逐句审阅、汇总编辑建议、顺序修订全文，并做五项清理。
- 对照旧版与论文版初稿提示词，记录版本、字数、调用用量和估算费用。
- 导入明确选择的 DOCX 采访，进行显式化名替换，检查直接引语的字面出处。
- 作为 Codex Skill 使用：默认由当前助手写作，也可连接外部模型执行实验。

只依赖 Python 3.10+ 标准库。完整论文实验使用文件锁，支持 macOS、Linux；Windows 请使用 WSL。当前提供命令行和 Skill 入口，尚无网页界面。

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

将 [`skills/featurepipe-reporter`](skills/featurepipe-reporter) 整个目录复制到个人技能目录 `~/.codex/skills/`；已有同名技能时先比较版本，避免覆盖自己的修改。Skill 自带所需程序与资源，不依赖本仓库的固定路径。

调用示例：

> $featurepipe-reporter 用这份采访写一篇中文特稿，先给大纲，再写正文，保留来源、修订记录和待核实问题。

默认使用当前助手，消耗当前会话额度，不额外调用外部模型接口。外部实验需明确本次材料发送范围、服务和预算；历史任务预算不自动沿用。详见 [Skill 指引](skills/featurepipe-reporter/SKILL.md)。

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

[`examples/borrow-room.json`](examples/borrow-room.json) 包含八组虚构来源，不能作为真实新闻发布。独立生成实验中，已发表文章或参考成稿应留作评测，不进入生成输入。

导入自己有权处理的 DOCX：

```bash
python3 skills/featurepipe-reporter/scripts/run.py import \
  --file /path/to/interview1.docx \
  --file /path/to/interview2.docx \
  --title "报道选题" \
  --output runs/private-inputs/case.json
```

可加 `--alias-map /path/to/aliases.json`，内容如 `{"原姓名":"化名"}`。替换作用于正文和标签，不修改原文件；这是显式字符串替换，**不是全面自动脱敏**。只导入 DOCX 正文文字，内嵌图片不作为证据。另写的本地来源清单含原文件路径和哈希，不应公开。

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

完整协议使用 `--rounds 5`：采访摘要 → 元提示词 → 大纲检查及局部修订/重建 → 初稿与长度检查 → 五轮逐句检查、资深编辑汇总、顺序修订和每轮五项清理 → 第六次只读审阅。工程适配与早期简版差异见 [复现说明](docs/REPRODUCTION.md)。

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

## 评价与已知局限

- 截至 2026-11-17，36 项本地测试通过，覆盖预算、恢复、引语检查、导入与 Skill 搬迁运行；它们不是文章质量评分。
- 虚构材料在线试跑已完成，但终稿超出目标篇幅，并有核查误报、无依据性别等问题。
- 一个真实案例完成初稿提示词对照、部分审查、已有意见修订、五项清理和模型评价；**没有完成完整论文五轮，也没有人工盲评**。私有输入、正文及评分原件不公开，不能作为公开可复验基准。
- 独立 Skill 离线试用产出 443 个汉字的虚构短稿，保留来源与缺口，未调用外部 API；只验证操作流程，不建立模型排名。

引语字面匹配不能证明说话人、语境或间接陈述正确。审阅模型也会误读来源，修订可能引入新错误。多模型一致、检查数量减少或轮次增加，都不能单独证明事实质量提高。详见 [评估记录与后续设计](docs/EVALUATION.md)。

[中文提示词](prompt_sets/论文提示词中文执行版.txt)依据英文附录回译，不是找回的原始中文运行字符串。[论文访谈指南](evaluation/论文访谈评价指南中文版.txt)与[本项目新增量表](evaluation/评价标准.json)分别维护。

## 隐私与公开范围

本仓库只发布程序、中文模板、评价说明、测试和虚构示例。真实采访、真实生成稿、私有运行结果、来源清单、个人路径和密钥不包含在发布内容中；研究作者署名有意保留。`.gitignore` 仅作辅助，发布前仍需检查实际文件。

外部实验会把采访发送至配置的服务。化名替换后，身份组合、地点和经历仍可能识别人；公开前需核对事实、引语、归属和受访者公开意愿。详见 [数据与安全](SECURITY.md)。

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

## 研究归属与许可

方法依据提供的 FeaturePipe 研究手稿。研究署名顺序为 **Ruowan Zhu（一作）、Jiani Liu（二作）**。本仓库作为独立工程复现与使用封装发布，不代表其他作者或受访者对私有材料的公开授权。代码采用 [MIT License](LICENSE)，论文、采访和第三方材料的权利不因代码许可证转让。

欢迎贡献来源证据定位、核查精确率/召回率评测、人工盲评工具及同预算协作实验。提交前运行测试，使用虚构或获授权的公开示例；见 [贡献指南](CONTRIBUTING.md)。
