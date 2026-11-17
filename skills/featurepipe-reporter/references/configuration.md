# 输入与外部接口配置

## 输入

程序使用以下 JSON；每份来源 id 应唯一：

```json
{"title":"选题","materials":[{"id":"S1","label":"采访对象甲","text":"采访原文"}]}
```

`import` 可重复指定 `--file`；`--alias-map /work/化名.json` 接受明确的字符串替换，例如 `{"真名":"化名"}`，同时替换正文与标签。这不是自动识别全部隐私。导入器另写仅供本地追溯的来源清单，含原文件路径与哈希；不要随源码或技能分享该清单。

DOCX 读取正文段落和表格内文字，排除删除修订；内嵌图片未导入，页眉、脚注等不能据此声称已核查。原文件不修改。`assets/interview-example.json` 全为虚构，仅供试用；`assets/mock-case.json` 用于固定响应的离线演示。

## API

仅在用户授权的任务范围内使用接口；沿用仍有效的服务、材料和费用授权，不重复询问。未指定本任务费用范围时先明确预算。凭证放在技能目录以外的本地文件，不能复制进技能、日志或分享包：

```dotenv
FEATUREPIPE_API_KEY=在本地填写
FEATUREPIPE_BASE_URL=https://api.siliconflow.cn/v1
FEATUREPIPE_MODEL=deepseek-ai/DeepSeek-V4-Pro
```

实际支持的变量以附带 runtime/featurepipe/config.py 与 client.py 为准。`paper` 默认写作模型为 DeepSeek-V4-Pro，复核模型为 GLM-5.3；两者都会收到采访内容，使用前须处于用户授权的发送范围。

运行器价格表是 2026-11-16 的快照，人民币计价，适用于表中接口配置。未来收费调用前查阅供应商当前模型、接口和价格（[硅基流动官方文档](https://docs.siliconflow.cn/)），有变化则在工作副本更新价格表，不把旧估算当作现价。预算数值必须有限且为正。未知用量按保留额度处理；请求前持久保存保留额度，续跑时计入未结请求。此机制仍不等于供应商账单硬限制。

完整实验需要 macOS、Linux 或 WSL 的文件锁支持。输出与输入均使用明确路径；运行结果、来源清单和 .env 留在用户工作目录。`--resume` 只续跑同配置的已有输出。禁止为演示主动发起收费请求。
