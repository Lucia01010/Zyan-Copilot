# 知妍 AI 产品架构

```text
知妍 AI / Zhiyan Beauty Copilot
├── 知妍·伴答 / Zhiyan Copilot
│   └── 模拟千牛客服工作台右侧智能接待辅助插件
├── 知妍·洞察 / Zhiyan Insight Dashboard
│   └── 客户服务风险预警、详情和状态跟踪
└── 知妍·智核 / Zhiyan Intelligence Core
    ├── Intent Understanding
    ├── Tool Calling
    ├── Evidence Grounding
    ├── Hybrid Risk
    └── Reply Generation
```

## 数据与运行链路

真实赛题数据进入 SQLite，由 FastAPI 业务 Tools 按需查询；知妍·智核编排 Qwen 或明确标识的 mock provider，输出结构化意图、证据、风险和智能回复建议。模拟千牛宿主把当前真实会话转换为 Plugin Context，知妍·伴答展示结果并通过 Plugin Actions 写回回复编辑器或打开知妍·洞察。

## 产品边界

知妍·伴答验证客服工作台中的实时辅助交互，知妍·洞察验证服务风险的发现、解释和跟踪，知妍·智核负责模型、工具、证据和风险融合。真实千牛 API 接入仍是可选增强，不是比赛 Demo 完成条件。
