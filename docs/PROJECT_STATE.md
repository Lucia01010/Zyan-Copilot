# 知妍 AI（Zhiyan Beauty Copilot）项目状态

## 当前阶段

M5 PASS（MANUAL_BROWSER_ACCEPTANCE）；M6 PASS；M7 PARTIAL — live Agent pipeline verified, one risk-consistency issue remains；M8 小规模 Hybrid live evaluation 已完成；M9 Product / Demo Polish PASS；M10 Competition Demo Packaging PASS。真实千牛接入改为 M11 Optional，不是比赛完成前提。

## 故障修复记录

- 插件标题精简 + 看板图表联动滚动（2026-10-20）：按用户要求两项调整。①`frontend/src/BeautyCopilotPlugin.tsx` 删除右侧插件标题区中「智能接待辅助插件」这行文字（去掉 `<p className="subhead">`，保留 eyebrow「ZHIYAN COPILOT」与 h2「知妍·伴答」）。②`frontend/src/RiskDashboard.tsx` 让「风险等级分布 / 主要风险来源 / 风险处理进度 / 重点风险客户 Top 5」四个可视化面板点击时，在筛选下方风险事件列表的同时把页面平滑滚动到列表：新增 `riskListRef` 挂到 `.risk-list-header`，`toggleFilter(name, value, scroll=false)` 追加第三参数，命中时 `requestAnimationFrame` 内调用 `riskListRef.current?.scrollIntoView({behavior:'smooth', block:'start'})`；环形区、环形图例、三个柱状图的 onSelect 全部改为传入 `scroll=true`；底部「全部/待跟进」等状态筛选按钮与「清除筛选」保持原行为（不滚动）。验证：`npm.cmd run build` 通过（tsc -b + vite build，index-DYOa5Qz1.css / index-CF2ZmaJi.js）；`python -m pytest -q` 173/173 PASS；浏览器实测 /workbench 标题区文字为「ZHIYAN COPILOT」「知妍·伴答」，已无「智能接待辅助插件」；/risk-dashboard（须用 `http://localhost:9000`，用 127.0.0.1 会因前端 JS 固定请求 `http://localhost:9000` 而跨域被 CORS 拦截、图表空数据）风险总数 52，点击「主要风险来源」条形后列表由 52 条筛选为 9 条、出现「类型：售后异常」标签且列表标题滚到视口顶部；点击「风险处理进度」「重点风险客户 Top 5」同样触发筛选并滚动到列表。已知限制：CORS 白名单仍只有 5173/5174，通过 127.0.0.1:9000 直接访问看板时 API 调用会失败（属既有问题，本次未改动）。

- 图片识别（多模态）能力修复（2026-10-20）：端到端冒烟测试发现带图请求全程 fallback、未调用视觉模型。**根因是视觉模型名 `qwen-vl-max` 在 DashScope 兼容模式已废弃**，返回 HTTP 404。代码链路本身完整（`api.py` → `attachment_image_part` base64 转 data URL → `agent_brain.process_message` 透传 images → `response_generator.build_chat_messages` 组装多模态 content array → `provider._request` 传 `model=vision_model`），问题仅在模型名。修复：`.env` 新增 `QWEN_VISION_MODEL=qwen3-vl-plus`（之前代码用默认值 `qwen-vl-max`），`.env.example` 同步改。验证：`python -m unittest discover -s tests -q` 173/173 PASS；端到端冒烟（Logo.png 1.1MB）→ attachment upload 200 → chat POST 带 `attachment_ids` → live_debug 确认 `model=qwen3-vl-plus` / status=200 / finish_reason=stop / 内容准确识别"白色半透明白团子、紫眼睛、蓝触角、蓝紫渐变背景"、回复判断为视觉设计素材"无需跟进"。`app/agent_brain.py` 的 `intent=unknown` 分支经确认 `_free_reply()` 已透传 images 参数到 LLM，**无需额外代码修改**——分类成 unknown 的带图自由问答（"看看这张图片"）本来就是 LLM 自由回答的场景，`response_generator.py` 的 `_IMAGE_INSTRUCTION` 会引导模型先描述图片再回答。

- 模型切换 + 产品知识图谱直达修复（2026-10-20）：原模型 `qwen3.7-plus` 额度耗尽，切换为 `qwen-max`（.env / .env.example 同步改 `QWEN_MODEL`，API 端点不变）。修复成分查询未命中知识图谱的根因链路——问题表现：客服问"这款精华的主要成分和可能导致过敏的成分？"，知妍未直接答成分数据而是说"我去帮您核实"。**三层修复**：① 意图分类（`app/action_registry.py`）：ADVERSE_EVENT_TERMS 里的"过敏"在有"成分/配方/致敏"等产品知识信号时，归为 knowledge_query 而非 business_query；只有纯不良反应事件描述（"客户用后过敏了"）才走业务工单查询。② 产品图谱检索（`app/product_knowledge.py`）：原 `search()` 仅在 exact（产品名匹配）/ brands / recommendation 时才进图谱，现追加 categories（精华/面膜等品类词命中）作为触发条件。③ 回复语气（`app/response_generator.py` SYSTEM_PROMPT）：明确知妍的对话对象是**人工客服**而非消费者，知识资料里有的直接给，不说"我去帮你查一下"。**DashScope 兼容层适配**：切换 qwen-max 后发现两处 400 Bad Request——`enable_thinking: false` 键即使值为 false 某些模型也不接受（改为 True 时才传）、以及 `tools: []` 空数组不被接受（改为 tools 为空时完全省略 tools 和 tool_choice 键）。同步更新 `tests/test_qwen_agent.py` 的 final_synthesis 阶段 payload 断言。验证：`python -m unittest discover -s tests -q` 173/173 PASS；冒烟 TEST1 `这款精华的主要成分和可能导致过敏的成分？` → intent=knowledge_query、tools_used=search_knowledge、命中 product_catalog（欧莱雅青春密语精华肌底液）、LLM 自然语言回复"可能引起过敏的成分有香精（含苧烯）、乙醇以及防腐剂如苯氧乙醇"、grounding=True；TEST2 纯不良反应事件仍正确走 business_query + check_adverse_reaction；TEST3 无过敏词的成分查询同样命中知识图谱。服务当前运行于 `127.0.0.1:9000`，provider=qwen / model=qwen-max。

- 演示视频制作支持（2026-10-20）：为比赛演示产出三类交付物。① 文字稿 `docs/demo_video_script.md`：八幕分镜（片头/工作台总览/客户洞察/Agent分析/交互与附件/回复闭环/风险看板/风险详情）+ 逐镜头操作清单，口播总时长约 4 分 40 秒。② AI 片头动画 `output/video/`：zhiyan_intro.mp4（首版，Copilot 拼写错误）、zhiyan_intro_v2.mp4（逐字母锁定重试版）、zhiyan_intro_notext.mp4（无字版，推荐，中央留白供剪映后加字）；AI 生成英文字样不稳定，最终建议用无字版+剪映叠字。③ 自动录制脚本 `scripts/record_demo.py`：Playwright 驱动真实页面按八幕节奏连续录像（viewport 1920x1080，录像 1280x720 webm），幕3 等分析完成（最长 150s）、幕4 含快捷行动/自由提问（护发精油孕妇能用吗）/set_input_files 真实上传附件、幕7 含弹窗滚动/改状态/备注/保存；单幕失败截图 step_fail_*.png 不中断整段；运行前提 pip install playwright && playwright install chromium、服务 9000 在线。已知限制：幕8 架构图卡需另行制作；录制时长受 live LLM 分析耗时影响（约 2-4 分钟）。

- 对话框附件真实上传（2026-10-19）：问题为 agent 对话框「+」按钮已有隐藏 file input 但未绑定 onChange，选中文件后无任何反应（假上传）。用户选定方案为"后端上传 + 对话框展示"（不接入多模态识别）。后端 `app/api.py`：新增 `ATTACHMENT_DIR`（默认 data/generated/attachments，env `BEAUTY_ATTACHMENT_DIR`）与 `ATTACHMENT_MAX_BYTES`（默认 10MB）；`POST /api/workbench/attachments`（空文件 400、超限 413、uuid 命名落盘、返回 id/name/size/content_type/kind/url）；`GET /api/workbench/attachments/{id}`（Path(name) 约束 + 根目录校验防目录穿越，不存在/越界 404）。新增依赖 python-multipart（requirements.txt 已登记，venv 已安装）。前端 `frontend/src/pluginRuntime.ts` 新增 Attachment 类型、attachmentUrl()、uploadAttachment()（multipart POST）；`frontend/src/BeautyCopilotPlugin.tsx` 的 ChatLine 增 attachment 字段、新增 uploading 状态与 handleAttachment()（成功追加"客服"附件气泡、失败追加知妍错误气泡、清空 input 值）、隐藏 file input 绑定 onChange、「+」按钮上传中禁用、气泡内渲染图片缩略图或文件链接；`frontend/src/styles.css` 新增 .chat-attachment-img/.chat-attachment-file 样式；`.gitignore` 新增 data/generated/attachments/（上传文件不入库）。验证：typecheck 0、py_compile 0、build 通过（index-DYOa5Qz1.css / index-vhnfHf9R.js）；后端 curl 冒烟：上传 200（正确返回 id/name/size/kind/url）、下载 200、路径穿越 ..%2F..%2Fconfig.py 404、不存在 id 404、文件确认落盘；浏览器实测（v=11，DataTransfer 注入 PNG）：imgCount=1、图片 src 指向 /api/workbench/attachments/xxx.png、气泡文案"已上传附件：测试图片.png"、POST /api/workbench/attachments 200；pytest 173 passed。已知限制：附件仅上传与展示，未接入 LLM 图片识别；上传文件保存在本地 data/generated/attachments，暂无清理策略；控制台页面跳转相关的 ERR_ABORTED 报错与功能无关。

- 全屏对话框标题与间距优化（2026-10-19）：用户要求全屏后删除对话框上方"知妍 Agent"小标题、并去掉对话框顶部与"智能接待辅助插件"这行字之间的空白。改动仅 `.frontend/src/styles.css`：全屏时 `.panel.plugin.plugin-fullscreen` 加 position:relative、`.panel-title{margin-bottom:0}`（消除标题下 24px 间距）、`.agent-heading` 改为绝对定位（position:absolute;top:14px;right:20px）从文档流移除且不占位、`.agent-heading h3{display:none}` 隐藏小标题、`.agent-chat{margin-top:0}`；右上角全屏按钮保留可点击（仍能退出全屏）。验证：build 通过（index-5ou9gixT.css/index-FavNwmzr.js）；浏览器实测（v=10 强刷）：全屏 class 含 plugin-fullscreen、h3 display=none 且不可见、退出按钮可见、subhead 底到对话框顶间距=0px、panel-title margin-bottom=0px；退出后标题恢复可见、title 回"进入全屏"，无控制台错误。

- 洞察看板通栏铺满（2026-10-19）：用户再次反馈"知妍·洞察看板缩在中间"。诊断（浏览器实测）：.dashboard 技术上已全宽（max-width:none，宽=视口 100%），视觉收缩感来自面板卡片式留白（dashboard padding 0 24px、panel 圆角 24px/边框/悬浮阴影）与内部图表宽度限制（trend-wrap 820px、donut-layout 310px、chart-bars 520px）。修复（styles.css 末尾追加）：.dashboard{margin:0;padding:0}、.dashboard .panel{border-radius:0;border:0;box-shadow:none;padding:20px 24px}（通栏白底）、.trend-wrap/.donut-layout/.chart-bars{max-width:none}（donut-layout 同时 margin:0）。验证：build 通过（index-BDuCgyjJ.js）；浏览器实测（v=9 强刷）：dashboard margin/padding 0、panel left:0 宽约满视口、borderRadius 0px、boxShadow none、三个图表容器 max-width 均 none、截图确认内容区占满视口无留白居中。

- 风险原因圆点移除（2026-10-19）：风险详情弹窗"风险原因"li 前的默认列表圆点删除（styles.css 追加 `.risk-reason-section ul{list-style:none;padding-left:0;margin:0}`）。验证：build 通过（index-CZUR84vB.js/index-CDgzpF1n.css）；浏览器实测 ul/li listStyleType 均 none、padding-left 0px、原因文本以汉字开头无异常符号。

- Agent 对话框全屏切换（2026-10-19）：用户要求在 agent 对话框界面右上角加"进入全屏"灰色图标按钮，点击后右侧插件全屏为 agent 对话框，客户洞察与订单商品隐藏。改动：`frontend/src/BeautyCopilotPlugin.tsx` 新增 chatFullscreen state、IconMaximize/IconMinimize 图标常量、"知妍 Agent" h3 改为 .agent-heading 行内右侧 .fs-toggle 按钮（灰色 #98a2b3、26px、透明底、hover 浅紫，图标随状态切换）、section className 条件附加 plugin-fullscreen、"客户洞察"/"订单商品" h3 加 insight-title/order-title class；`frontend/src/styles.css` 新增 .agent-heading/.fs-toggle 样式与全屏规则（.panel.plugin.plugin-fullscreen min-height:calc(100vh - 150px) flex column，.insight-title/.order-title/.insight-grid/.plugin-order-product/.risk-compact display:none，agent-chat flex:1 1 auto min-height:0 填满剩余空间）。全屏范围修正：初版用 position:fixed inset:0 覆盖整个视口，用户反馈"只在右侧插件部分进入全屏，不要进入模拟工作台"，改为去掉 fixed/z-index，插件保持三栏布局原位、min-height 拉伸到工作台全高（左栏与中间对话框始终可见）。验证：typecheck+build 通过（index-56geTH9k.js/index-CEKsmvEs.css）；浏览器实测（v=6 强刷）：新 CSS 加载、fullscreenRule minHeight=calc(100vh-150px) 且无 fixed、全屏时插件 position static、左栏 session-list 可见（left:24 width:210）、洞察与订单 display=none、插件面板高度 188.5→399 拉伸、agent-chat 填满（214.5px）、再次点击完整恢复（static/区块可见/title 复原），无控制台错误。

- 工作台布局与洞察看板调整（2026-10-19）：按用户要求 3 项调整，均只改 `frontend/src/styles.css`。①客户洞察三格（当前诉求/情绪/风险）文字框内居中（`.insight-grid>div{text-align:center}`，label 与 strong 同步居中）；②知妍·洞察看板全宽铺满页面（`.dashboard{max-width:none}` 覆盖基础规则 max-width:1400px）；③知妍 Agent 对话框底线固定到右侧插件底部（`@media(min-width:1001px)` 下 `.panel.plugin` 改 flex column、`.agent-chat{flex:1 1 auto;min-height:280px;max-height:none}`，移除原 max-height:300px 上限，插件被三栏 stretch 拉高时对话框延伸至面板底部）。迭代过程：第一版用 `flex:1 1 0%` 在窄屏（<1000px 插件独占一行、app 锁 100vh）下导致对话框塌缩为 26px；第二版 min-height:280 修复塌缩但窄屏溢出插件面板 437px；最终限定 >=1001px 生效、窄屏回退原规则（max-height:300px），窄屏行为与改前一致（插件面板内部滚动为既有行为，非本次回归）。验证：build 通过（bundle index-BAn_4eWG.css/index-DvOMNz14.js）；浏览器实测 810px 窄屏：三格 label/strong 均 center、agent-chat maxHeight 回退 300px 无页面级溢出、dashboard maxWidth=none；宽屏规则（flex/none/280px）经 CSSOM 检查确认注入，对齐数值因浏览器工具窗口固定 810px 未实测，用户以本机宽屏浏览器查看为准。

- 风险详情面板与按钮排版优化（2026-10-18）：按用户要求多项调整。风险详情弹窗（RiskDashboard.tsx RiskDetailModal）：①删除 meta 第一格"风险事件 {id}"，meta 三列（客户/会话/风险类型）；②"风险原因"标题旁删除"识别依据"；③弹窗内订单行与轨迹行的"·"分隔符删除；④风险原因框去橙色填充（#fffaf5/#f7e5cc → #faf7fc/#eee5f2）；⑤关键依据 key 英文转中文（EVIDENCE_LABELS：work_order_numbers→工单号等，12315→中文全称），evidence-row b 加 white-space:nowrap 消除号码与文字重合；⑥弹窗内除 h2/h3 小标题外 b/strong 全部 font-weight:400（含 facts/detail-context/timeline/evidence 内更具体的 b 规则覆盖）；⑦服务轨迹去掉 slice(-8) 截断改为全量显示 + "N 条记录"计数 + max-height 280px 内部滚动（修复外层 .timeline overflow:hidden 覆盖问题）；⑧"返回原始会话"链接改为与"保存状态"按钮一致的深紫底白字圆角样式。列表页：`清除筛选`/`查看详情` 按钮字号 13px、padding 6px 10px。工作台：`.chat-inline-actions .quick-action` padding 5px 10px，与"复制到回复框"按钮等高（实测均 29px）。验证：typecheck+build 通过（index-CWuTxgEZ.js）；浏览器实测 metaLabels=["客户","会话","风险类型"]、reasonBg=rgb(250,247,252)、evidenceKeys=["工单号"]、b/strong 全 400、timeline overflow auto 可滚动、无" · "残留、双按钮样式一致、按钮字号 13px、行动/复制按钮等高，全部通过。

- 工作台/风险面板 UI 细节调整（2026-10-18）：按用户要求 5 项调整。①千牛对话区买家气泡去掉 1px 边框（styles.css `.customer` 移除 border）；②回复编辑器"发送"键移入编辑框内右下角（main_m11.tsx 用 `.reply-editor` 包裹 textarea+`.reply-send` absolute 定位，文案由"发送给消费者"改为"发送"，删除框外独立按钮）；③风险面板"主要风险来源"删除副标题"按现有规则类别聚合"（ChartCard 的 subtitle 改为可选）；④风险趋势图删除说明文字"趋势基于风险识别时间或关联服务记录时间统计"，新增纵坐标（Y 轴线 + 5 档刻度数字 `.trend-axis` + 横向网格线）；⑤知妍 Agent 对话框消息区滚动条弱化（5px 宽浅紫色 webkit/firefox 样式）。修复过程中发现并纠正一次回归：修改 ChartCard subtitle 可选化时误删 `{children}`，导致风险页所有图表容器不渲染（趋势/饼图/柱状图全部消失），已补回并重建。验证：typecheck+build 通过（bundle index-DkFBhR_Z.js）；浏览器实测 workbench（气泡无边框、发送键框内右下角 12px、滚动条规则生效、对话框 3 条消息与复制到回复框正常）与 risk-dashboard（趋势 SVG 渲染、纵坐标 0/2.8/5.5/8.3/11 可见、12 个日期标签、饼图柱状图恢复、两处旧文案均已消失）全部通过。

- 对话框整合建议行动/建议回复 + 气泡操作图标（2026-10-18）：用户要求"建议行动/建议回复（含复制到回复框）"移入知妍 Agent 对话框，并参考 Trae 为客服侧气泡加复制/编辑图标、知妍侧气泡加复制/重试/喜欢/不喜欢图标。改动：`frontend/src/BeautyCopilotPlugin.tsx` 重构 ChatLine（id/kind: chat|summary|actions|suggestion|action-result|error），分析完成后在对话框依次追加会话小结、快捷行动按钮组、建议回复气泡（带"复制到回复框"按钮与 AI生成 标签）；删除底部"建议行动/建议回复"独立区块；气泡下 msg-actions 图标行 hover 显示，客服侧复制/编辑（编辑回填输入框），知妍侧复制（点击后短暂变勾）/重试（小结与建议回复→重跑分析，问答→重发原话，行动结果→重执行该行动）/喜欢/不喜欢（互斥高亮，前端视觉状态）；`frontend/src/styles.css` 新增 msg-actions/msg-action-btn/chat-inline-actions/chat-insert-btn/chat-loading 样式。修复伴随发现的后端缺陷：`app/qwen_agent.py` run() 中 `suggested_reply` 为空字符串时（LLM 偶发返回空值，`dict.get` 默认值仅对键缺失生效）静默透传，导致前端建议回复气泡随机缺失；现加诚实兜底文案并记录 `empty_suggested_reply_fallback`。验证：typecheck+build 通过；173 项测试通过；服务重启（provider=qwen）；浏览器实测 3 条消息齐全、复制到回复框写入编辑器、赞踩互斥高亮、编辑回填输入框、hover 图标可见。已知限制：喜欢/不喜欢为前端视觉状态未持久化（现有 /api/copilot/feedback 是"修改建议"语义，不适用）。

- 客户洞察中文化 + 状况总结迁移（2026-10-18）：用户要求"当前诉求/情绪/风险"统一中文表述，且"历史对话与状况总结"不在客户洞察板块显示、改为在知妍 Agent 对话框输出。改动：`app/qwen_agent.py` AgentOutput 为 intent/intent_major/intent_minor/emotion/summary 增加中文 description（随 strict json_schema 下发，约束 live LLM 输出中文）；`frontend/src/pluginRuntime.ts` 新增 EMOTION_LABELS/INTENT_LABELS 及 emotionLabel/intentLabel 兜底映射（常见英文值转中文）；`frontend/src/BeautyCopilotPlugin.tsx` 洞察三项套用映射、移除 summary 段落，新增 effect 在分析完成后向知妍对话框追加"会话小结：{summary}"气泡（按 session+summary 去重）。验证：`npm run typecheck` + `vite build` 通过；`python -m pytest tests -q` 173 项通过；live smoke（S00082）返回 intent="不良反应咨询与退货确认"、emotion="平稳"、中文 summary，live_debug 确认 schema 描述已下发；浏览器实测洞察三字段全中文、洞察区无总结段落、对话框出现"会话小结"气泡。服务经 `scripts/run_service.cmd` 重启于 9000（provider=qwen）。

- 修复闲聊/自由问答退化（2026-10-18）：用户实测 "hello" 只得到 UNKNOWN_REPLY 兜底。根因是 `scripts/run_service.cmd` 硬编码 `AGENT_PROVIDER=mock`，启动时覆盖 `.env` 的 `qwen` 配置（config.load_env 只注入环境中不存在的键），导致 LLM 永不参与 copilot chat。修复：run_service.cmd 移除硬编码，运行模式完全由 `.env` 决定（未配置时 Python 侧 QwenProvider 默认回退 mock）；`response_generator.py` LLM 调用失败由静默吞异常改为 logging.warning；`agent_brain.py` 工具/RAG 无结果的两处兜底改为先尝试 `_free_reply`（LLM 人性化引导，grounding_check 仍拦截无依据业务事实；mock 模式行为不变）。验证：9000 服务 health 显示 provider=qwen；hello 返回自然问候；通用技术问题（构建 agent 知识图谱）得到诚实说明+场景引导；业务订单查询正常。173 项测试全部通过。

## 已完成

- 创建仓库级 `AGENTS.md`。
- 创建 `.codex/skills/beauty-cs-agent-builder/` 及其产品规格、验收标准。
- 初始化 Git 仓库并添加根目录 `.gitignore`。
- 完成 M0 源文件盘点，建立 `docs/SOURCE_INVENTORY.md`。
- 完成 M1 SQLite schema，建立 `docs/DATA_SCHEMA.md`。
- 创建 `scripts/import_excel_to_sqlite.py` 和 `tests/test_import_excel_to_sqlite.py`。
- 已生成 `data/beauty_cs_agent.sqlite3` 与导入摘要 `data/import_summary.json`。
- 建立 `app/business_tools.py`、`app/risk_engine.py` 和 `docs/BUSINESS_TOOLS.md`。
- 业务 Tools 采用白名单和参数绑定，风险规则保留证据与建议动作。
- 建立 `app/qwen_agent.py`、`app/api.py`、`requirements.txt` 和 `docs/AGENT_API.md`。
- Agent 支持 `QWEN_MOCK` 离线模式与 OpenAI-compatible Qwen endpoint，并记录 `agent_runs` 成本元数据。
- 建立 `frontend/` Vite + React + TypeScript 应用和 `docs/FRONTEND.md`。
- 完成 `/workbench` 智能接待辅助和 `/risk-dashboard` 风险筛选界面，API 不可用时提供 mock fallback。
- 创建项目 `.venv`，安装后端依赖并生成 `frontend/package-lock.json`。
- 完成真实后端 API、前端 typecheck、Vite production build 和开发服务器 smoke test。
- 建立 `docs/ENVIRONMENT_REPORT.md`、`.env.example`、`README.md`、`scripts/setup.ps1` 和 `scripts/dev.ps1`。
- M5 补齐 `/api/workbench/sessions`、会话详情和 CORS；工作台展示会话列表、聊天、intent、emotion、evidence、订单/工单、timeline、risk、recommended actions 和 suggested reply。
- 用户人工完成 M5 浏览器验收：`/workbench` 打开、会话加载/切换、聊天显示、AI 分析、插件字段展示和运行稳定性均通过。
- M6 已建立风险详情、证据、筛选和状态跟踪 API/UI，状态持久化到 SQLite `risk_tracking`。
- M6 建立 `scripts/smoke_risk_api.py`，验证风险列表、详情字段和状态持久化恢复。
- M7 扩展 `scripts/evaluate_mvp.py`，完成 112 个客户样例的 mock Agent、Tools、风险和 Token 评估，报告见 `docs/EVALUATION_REPORT.md`。
- 完善 `QwenProvider` 的 `AGENT_PROVIDER=mock|qwen` 切换、OpenAI-compatible bounded tool-calling、结构化 JSON 校验和证据 grounding 检查；新增 `scripts/evaluate_qwen_live.py` 与 `docs/QWEN_LIVE_VERIFICATION.md`。
- 新增 `QWEN_FREE_ONLY=true`、`QWEN_EVAL_TOKEN_BUDGET=50000`、`QWEN_MAX_TOKENS` 和 `QWEN_MAX_TOOL_ROUNDS` 保护；live evaluation 串行执行、限制调用轮数和结果大小，记录逐次 usage 与总 token，额度/计费错误立即停止且不切换模型。
- M8.0 建立 `TokenBudgetGuard`，在启动下一 live case 前按保守估计检查剩余预算；新增 M8 dataset/evaluator、指标 provenance 与 `docs/EVALUATION_PLAN.md`、`docs/EVALUATION_REPORT.md`。

## 当前假设

- `data/raw/` 中的比赛源文件保留并纳入版本控制；当前未发现需要因体积排除的文件。
- 本地数据库、环境文件、缓存、虚拟环境和前端依赖不纳入版本控制。

## 待办

- M9：Product / Demo Polish。
- M10：Competition Demo Packaging，默认比赛交付终点。
- M11：Optional Real Qianniu Integration，仅在用户明确要求且具备真实店铺、商家账号和开放平台权限时启动。
- 不因缺少真实店铺、商家账号或开放平台权限阻塞比赛项目完成。

## 官方答疑路线调整（2026-09-29）

- 赛题 1 插件无需强制部署到千牛生产环境。
- 允许使用 React/Vibe Coding 模拟客服工作台，或使用场景数据模拟 + Agent 计算结果展示 + 插件 Demo 产品交互逻辑。
- 默认交付路线为：真实赛题数据、React 模拟千牛工作台、真实 Qwen Agent、风险预警看板和完整端到端风险闭环。
- M10 完成标准包括模拟消费者咨询、模拟人工客服工作台、右侧 Agent 插件、风险事件写入看板、风险状态跟踪、稳定演示场景、一键启动和演示说明。
- 真实千牛接入仅为 M11 可选增强；除非用户明确要求并提供真实资质/权限，否则不进入 M11。

## 验证记录

- `python scripts/import_excel_to_sqlite.py --db data/beauty_cs_agent.sqlite3`：通过。
- `python -m unittest discover -s tests -v`：1 个测试通过。
- 重复导入后业务表行数保持稳定，`import_runs` 正确累计运行记录。
- 已抽查 `orders.order_number`，值为 Python/SQLite 字符串且未出现科学计数法。
- `python -m unittest discover -s tests -v`：5 个测试通过。
- 已对真实数据库客户样例执行 Tools 聚合与风险评估 smoke test，返回结构化 context/risk 结果。
- `python -m unittest discover -s tests -v`：6 个测试通过，包含 mock Agent 与成本记录验证。
- Python/FastAPI/uvicorn 和前端依赖已恢复并完成真实验证，详细结果见 `docs/ENVIRONMENT_REPORT.md`。
- 环境恢复后已重新执行相关检查；完整结果见 `docs/ENVIRONMENT_REPORT.md`。
- `MANUAL_BROWSER_ACCEPTANCE`：用户人工验证 `/workbench` 全流程通过；未执行自动化 CUA，也未执行自动化 console 检查。
- M5 使用 mock provider 完成 UI 验收；真实 Qwen 验证尚未完成，但不作为 M5 UI 验收 blocker。
- M6：`scripts/smoke_risk_api.py` 返回 `status_persistence: ok`；前端 `npm run typecheck` 与 `npm run build` 通过。未声称本轮执行风险看板浏览器 click-through。
- M7：`scripts/evaluate_mvp.py` 评估 112 个客户，42 个风险发现，Tool 成功率 100%，mock 输入/输出 token 为 705,633/2,760；`python -m unittest discover -s tests -v` 修复后通过 7 个测试。
- 真实 Qwen 回归命令在无凭据时明确返回阻塞信息（退出码 2，未发起网络请求）；未执行四场景 live test。离线编译与 `python -m unittest discover -s tests -v`：9 个测试通过。

## 2026-10-18 产品知识图谱接入

- 新增 `app/product_knowledge.py`：将只读 `data/raw/产品功能详情.jsonl` 解析为产品实体和关系（功效、适用部位、适用人群、功效宣称），写入独立 `product_knowledge` / `product_relations` 表；整文件 SHA-256 校验后原子替换，重复导入幂等。
- 产品查询已接入现有知识工具：支持指定产品/品牌及“推荐/选品”请求，返回使用方法、注意事项、成分、保存/保质期和可追溯来源（源文件、行号、哈希）。缺少明确依据时返回待确认，不编造替代产品。通用使用方法仍走原有 Markdown RAG。
- 肤质适配仅采信备案资料明确的适用人群/宣称；功效测试受试者肤质不等于适用肤质；存在注销日期的记录不用于推荐。
- 验证：`python -m unittest discover -s tests -q`，171/171 PASS；新增 `tests/test_product_knowledge.py` 覆盖幂等、来源追溯和未知品牌不推荐。
- 已知限制：JSONL 是备案/功效资料，不等于实时在售库存、价格或完整商品目录；推荐前仍需核对店铺当前在售版本。

## 2026-10-18 建议回复语气优化

- `app/prompts/final_synthesis.txt` 明确区分消费者可直接发送的 `suggested_reply` 与内部字段/知妍-客服对话：先回应最新关切，再引用真实上下文和工具证据，按日常咨询、物流、退款、投诉、不良反应区分语气。
- 增加少量合成测试示例并标明“合成测试数据”；禁止宝宝/宝子、表情符号、无证据承诺和机械堆砌语气词。退款纠纷与不良反应保持克制，产品资料不足时说明边界。
- 离线 mock 回复同步调整为消费者可发送话术，保留事实 grounding；内部 `response_generator.py` 的 Agent 对话提示未套用该消费者语气。
- 真实源会话对照命令：`python scripts/evaluate_suggested_reply_tone.py`，覆盖 5 类会话，输出 `data/generated/evaluation/suggested_reply_tone.json`；本轮 5/5 场景检查通过（无宝宝/宝子、无虚假承诺、≤300 字）。
- 验证：`python -m unittest tests.test_qwen_agent -q`，20/20 PASS；完整测试需与产品知识接入回归一起执行。

## 2026-10-18 风险详情界面视觉优化

- `frontend/src/RiskDashboard.tsx` 将风险详情弹窗重排为状态头部、事件信息、风险原因、关键依据、订单/工单、服务轨迹和处理动作六个区块；保留风险状态更新、备注保存和返回原始会话功能。
- `frontend/src/styles.css` 为详情页建立独立紧凑字号体系：除“风险详情”主标题外，正文、字段、按钮和辅助信息统一 13px/12px；采用低饱和灰白表面、细边框、轻分隔线和移动端两列适配，降低视觉噪声并便于快速扫描。
- 验证：`cd frontend && npm run typecheck` 通过；`cd frontend && npm run build` 通过。未改变后端接口或风险数据逻辑。

## 已知限制

- 当前数据库是 M1 原始业务层，尚未建立后续 service 层的规范化客户、商品和风险事件实体。
- 原始 DOCX 的文本已读取；case 图片已人工盘点要点，尚未做 OCR。
- 当前 PowerShell PATH 尚未刷新 npm，需使用 `C:\Program Files\nodejs\npm.cmd` 或重开终端。
- CUA 曾返回 `Transport closed`；该浏览器自动化基础设施限制不代表当前代码失败。
- 真实 Qwen 回归凭证已通过环境配置提供，但 M3/M7 live-model verification 尚未通过，不把 mock 结果计为真实模型通过。
- 免费额度保护已默认开启；只有显式 `AGENT_PROVIDER=qwen` 且运行 live evaluation/smoke 才会调用真实 Qwen。
- 真实 Qwen 回归已执行第二轮：provider/model 为 `qwen/qwen3.7-plus`，四个 case 均发生真实多轮 Tool calling；每个 case 最多执行一次 bounded JSON repair，但仍出现 `invalid_json`/`json_repair_failed`/`structured_output_invalid`，本轮累计 `62,718` tokens，未标记 PASS。已通过 Pydantic schema、JSON-only prompt、`response_format=json_object`、结果截断和 repair 单元测试；当前不再追加 live 请求，M7 live verification 保持未完成。
- JSON Schema transport smoke 曾仅执行 Case A 并发现长度截断；随后已通过压缩修复。安全诊断写入 `data/generated/live_debug/`（gitignored）。
- 输出长度压缩后 Case A smoke PASS：`max_tokens=1024`、`output_tokens=964`、`finish_reason=stop`、未 repair，Pydantic validation、Tool calling 与 evidence grounding 均通过，total `12,711` tokens。
- 随后仅执行 B/C/D：B 与 D 的真实 Tool calling、strict schema、Pydantic、grounding 和 finish_reason 均通过；C 虽 schema/grounding 通过，但模型 risk_level=low 与 medium 规则基线不一致。三 case 合计 `43,172` tokens，超过 `40,000` 预算后停止，M7 四场景 live verification 未标记 PASS，未进入 M8。
- M7 状态修正为 `PARTIAL — live Agent pipeline verified, one risk-consistency issue remains`；A/B/C/D 均真实 qwen/tool calling/structured output/grounding，通过但 Case C 风险分歧保留。
- M8 离线阶段：已生成可追溯 source-derived dataset、Rules baseline 报告和三系统评估框架；人工风险/意图标签不可用，未伪造 accuracy/F1。
- M8.0–M8.7 离线准备验证：dataset 138 条会话、source label coverage 138/138；修正业务 Tools 的工单来源标记后 Rules distribution 为 low=102/medium=3/high=22/critical=11；`TokenBudgetGuard` 与 dataset provenance 测试通过；未发起新的 Qwen 请求。
- 人工 gold 阶段：生成 24 条分层候选 CSV，覆盖 LOW/MEDIUM/HIGH/CRITICAL、A/B/C/D 关键会话；当时提供 `docs/MANUAL_EVALUATION_GUIDE.md` 与 `scripts/review_manual_gold.py`，人工未完成前不计算正式 accuracy 或 Agent improvement。随后人工完成 intent/risk/status 字段，生成 Gold v1；required_tools/notes 仍为空。
- 修复人工候选会话顺序：`message_sequence` 按整数并结合 `_row_number` 升序，excerpt 保留时间、角色和内容。旧 CSV 因检测到 3 个非空人工字段已备份为 `manual_gold_candidates.pre_order_fix.csv`，修正版重新生成并随机抽查 5/5 通过。
- M8.8 Gold v1：24/24 条人工标注为 DONE，生成 `manual_gold_v1.jsonl`；未填充 required_tools/notes。
- M8.11–M8.16 小规模 live 对照：仅执行 2 条（含 Case C），LLM-only 与 Agent 均使用真实 qwen3.7-plus；总 41,117 tokens，第三条由 predictive guard 阻止。结果见 `data/generated/evaluation/live_results.jsonl`、`metrics.json` 和 `docs/EVALUATION_REPORT.md`。

## M8 当前修订（离线优化，2026-09-29）

- Gold Set v1 已固化：24/24 条 `human_review_status=DONE` 纳入正式 Gold；Case C 的正式人工标签为 `HIGH`，不再标记为未知或待审核。`human_required_tools` 与 `human_review_notes` 仍按人工决定保持为空。
- 已建立统一 IntentTaxonomy：来自 Gold v1/source 标签，支持 major/minor 合法组合、别名归一化和非法组合测试，见 `docs/INTENT_TAXONOMY.md`。
- 已实现离线 Hybrid Risk policy：保留 `model_risk`、`rule_risk`、`rule_floor`、`final_risk`，只对有证据支持的明确不良反应、投诉/监管升级、历史承诺线索应用可解释风险下限；不针对 Case C 硬编码结果。
- 已完成 Agent token cost audit、业务 Tool projection/context compaction 方案和 Tool catalog，见 `docs/TOKEN_COST_AUDIT.md`、`docs/TOOL_CATALOG.md`。
- 历史 N=2 live 结果生成于 hybrid policy 实现前，未重新调用 Qwen；因此 hybrid 与人工 Gold 的正式 live 指标仍为未测量，而非通过或失败。
- 本轮离线验证：`python -m unittest discover -s tests -q`，24/24 PASS；未发起新的 live Qwen 请求。
- M8 Hybrid live evaluation 尝试：按 90,000 token 硬预算、30,000 token/样本保守估算启动前检查；因仓库根目录没有 `.env` 且进程未提供 `QWEN_API_KEY`，在发起 HTTP 请求前安全停止。未使用 `.env.example` 占位符，未覆盖既有 live 结果。
- 随后凭证恢复后的重试：发现本机 `HTTP(S)_PROXY=127.0.0.1:9` 导致连接拒绝；仅在当前进程清除代理后直连，endpoint 返回 HTTP 401 Unauthorized。未产生 token、未追加 live 结果、未 fallback mock 或其他模型；需核对 Qwen API key 与 endpoint/region 匹配后再重试。
- 更新 `QWEN_BASE_URL/region` 后再次重试仍在首个 LLM-only 请求返回 HTTP 401（model=`qwen3.7-plus`）；未产生 token、未追加结果，按失败策略停止。
- 再次更新凭证与 endpoint 后，首个请求返回 HTTP 404 Not Found（model=`qwen3.7-plus`）；未产生 token、未追加结果，需核对兼容 API 路径与模型区域，不再扩大重试。
- M8 Hybrid live evaluation 成功：使用更新后的 endpoint/key，按 `QWEN_FREE_ONLY=true`、90,000 token 硬预算和 30,000 token/样本预测估算执行 3 条（Case C、LOW、CRITICAL），实测总 42,183 tokens，未启动第 4 条；结果追加至 `live_results.jsonl`，未覆盖既有记录、未 fallback。
- 最新 3 条 Agent：structured output 3/3、grounding 3/3、unsupported fact 0、repair 0、finish_reason 全为 stop；平均 13,013 tokens、20,892ms。相对历史 19,585 tokens/case，下降约 33.6%。Hybrid risk 3/3 有 final risk，Risk accuracy=1.00（N=3）；Rules=0.67，LLM-only=1.00，Agent model=1.00。Case C 最新结果 Human HIGH / Rules CRITICAL / rule floor HIGH / model HIGH / hybrid HIGH。
- `metrics.json` 与 `docs/EVALUATION_REPORT.md` 已更新；planning/tool-loop/final 分阶段 token 未由本次 evaluator 持久化，明确标为 NOT MEASURED。

## M9 Product / Demo Polish（PASS）

- 模拟工作台顶部增加演示/在线模式标识和产品说明，明确当前交付是 React 模拟千牛工作台。
- 工作台补充会话加载态、无会话态、无消息态、角色标签、分析结果空态和人工接管/复制反馈，降低演示时的状态歧义。
- Agent 建议回复支持浏览器复制反馈；人工接管动作给出明确 toast，不改变后端业务状态。
- 前端验证：`C:\Program Files\nodejs\npm.cmd run typecheck` 通过；`C:\Program Files\nodejs\npm.cmd run build` 通过（Vite production build）。
- 后端离线验证：`python -m unittest discover -s tests -q`，25/25 PASS。
- M9 浏览器验收已完成：使用 mock/demo 模式实际打开 `/workbench` 与 `/risk-dashboard`；会话切换、角色/消息展示、AI 分析、插件字段、复制反馈、人工接管反馈、风险指标卡、筛选、详情证据/服务轨迹和状态持久化均通过。完成同一 `郭a**` 会话 → Agent 分析 → 对应风险事件 → 看板详情 → `processing` 状态保存/刷新闭环。
- 浏览器 fresh tab console error=0；未发现用户可见 runtime error 或阻塞性 network failure。此前发现并修复 5174 开发端口未在 FastAPI CORS allowlist 的问题。
- M9 验证命令：frontend typecheck PASS；Vite production build PASS；`python -m unittest discover -s tests -q` 25/25 PASS。未发起 live Qwen evaluation。

## M10 Competition Demo Packaging（PASS）

- 固化 3 个真实赛题数据演示场景：`docs/DEMO_SCENARIOS.md`，覆盖不良反应/历史服务风险、普通套装赠品咨询、物流/重复服务闭环。
- 增加明确的 `DEMO CACHED MODE` / `LIVE QWEN MODE` UI 标识；Demo Mode 使用 mock/固定 SQLite 数据和离线 fallback，不冒充实时 Qwen。
- 新增 `scripts/reset_demo.py`，只清理 `risk_tracking` 覆盖状态，已验证源数据不变。
- 新增 `scripts/demo_preflight.py`，检查 Python、FastAPI/app import、SQLite、前端依赖/build artifact 和 live 配置存在性，不打印 API Key。
- 新增 Windows `scripts/start_demo.ps1`，自动执行 preflight 并启动 mock backend/frontend，输出访问地址。
- 完成 `docs/DEMO_METRICS.md`、`docs/DEMO_SCRIPT.md`、`docs/DELIVERY_CHECKLIST.md`，README 已补充架构、Demo/Live 模式、启动、reset、测试、评估和 FAQ。
- M10 回归：backend tests 25/25 PASS；frontend typecheck PASS；Vite production build PASS；demo preflight READY；demo reset PASS；risk API smoke PASS（risk_total=52、status persistence ok）；workbench sessions/health/risk API HTTP smoke PASS；start_demo.ps1 parse PASS。
- 未发起新的 live Qwen 请求；未进入 M11。

## M11 Simulated Qianniu Plugin Runtime（PASS）

- 本阶段不实现真实千牛 API；目标是满足比赛要求的“模拟千牛客服工作台环境中的插件形态运行”。
- 新增 `frontend/src/pluginRuntime.ts`：定义 `PluginContext`、`PluginActions`、`QianniuHostAdapter`、`SimulatedQianniuAdapter` 和五类宿主事件。
- 新增 `frontend/src/BeautyCopilotPlugin.tsx`：右侧知妍·伴答插件组件，不直接依赖宿主内部 React state。
- `/workbench` 已加入 Host/Plugin 分区、Scenario Controller、消费者下一条消息、Reset Scenario、Host Reply Composer 和插件动作闭环。
- 文档见 `docs/PLUGIN_RUNTIME.md`；真实千牛接入仍为后续可选增强，不因账号或权限缺失阻塞比赛 Demo。
- 回归验证：frontend `npm run typecheck` PASS；Vite production build PASS；backend `python -m unittest discover -s tests -q` 25/25 PASS；`scripts/demo_preflight.py` READY；`scripts/reset_demo.py` PASS。
- 浏览器 click-through（demo cached/mock）：Scenario Controller 发送消息后，消息进入 Host chat 并触发 `MESSAGE_RECEIVED`；AI 分析显示插件身份、intent/emotion/evidence/timeline/risk/actions/suggested reply；Risk Dashboard 详情展示客户、证据、服务轨迹和状态控件。未发起 live Qwen 请求。
- M11 PASS：Host/Plugin 边界、Context/Action 合约、事件生命周期、固定 A/B/C 场景、插件动作到 Reply Composer、风险看板闭环均已具备。真实 Qianniu API 仍为 OPTIONAL M12。

## M11 真实性修订（2026-09-30）

- M11 改为 `Real Scenario Driven Simulated Qianniu Plugin Runtime`：模拟千牛交互环境，不模拟或替换业务数据。
- `/workbench` 的会话列表继续来自现有真实赛题 session API；A/B/C 快捷入口分别加载 `S00082`、`S00002`、`S00075`，而不是创建新客户或替换会话。
- 删除前端加载失败时的“演示客户”与预设消息 fallback，以及风险看板的 mock 风险初始列表；API 不可用时显示明确错误/空态，不伪造业务事实。
- 场景入口只重新加载真实会话，原始订单、工单、风险事件和 Gold evaluation 数据保持不变。Agent、Risk Engine、Evaluation 未修改。
- `docs/PLUGIN_RUNTIME.md` 已补充 Real Scenario Driven Architecture、数据层/适配层/宿主层/插件层/Agent 层边界及未来 Host Adapter 替换方式。
- 离线回归：`npm.cmd run typecheck` PASS；Vite production build PASS；`python -m unittest discover -s tests -q` 25/25 PASS；`python scripts/reset_demo.py` PASS；未发起 live Qwen 请求。
- 本次真实性修订未改变已有浏览器闭环代码路径；本轮重点为移除虚构 fallback，完成 typecheck/build/backend regression，未发起新的 live Qwen evaluation。
- 2026-09-30 启动修复：发现本地 backend/frontend 进程均未监听端口，导致 `http://localhost:5173/` 无法打开；使用 `scripts/start_demo.ps1` 启动 backend，并以受限外部权限运行 `npm.cmd run dev -- --host 127.0.0.1 --port 5173`。验证 `GET /`=200、`GET http://localhost:8000/health`=200，当前为 mock/demo 模式。

## Context-grounded Agent Reply Generation（2026-09-30）

- 修复 mock provider 的固定 suggested reply：现在基于当前会话消息、关联订单、物流/退款/不良反应工单和 risk findings 生成确定性、可解释的客服回复；无事实时明确请求进一步核实，不编造订单或状态。
- `conversation_id` 入口现在会先读取真实会话，再通过关联 buyer context 获取真实订单和工单证据；未改变 Qwen provider、Tool calling、Hybrid Risk 或 Evaluation。
- 插件智能回复建议卡片新增“知妍生成”标识和简短“生成依据”，复制后可在宿主回复编辑器继续修改。
- 离线 API smoke：S00011 回复包含真实物流单号/状态；S00038 回复包含真实退款金额/状态；S00082 回复包含真实不良反应工单号并建议暂停使用与人工升级。
- 测试：backend `python -m unittest discover -s tests -q` 29/29 PASS；frontend typecheck PASS；production build PASS；未发起 live Qwen evaluation。

## Workbench 会话栏展示调整（2026-09-30）

- 左侧标题由“真实赛题会话”调整为“真实会话”。
- 真实会话列表默认显示 8 个；超过 8 个时提供“展开更多/收起”按钮，数据仍来自真实 session API。
- 移除宿主事件摘要文字，事件合约和内部生命周期不变。
- 前端 `npm.cmd run typecheck` PASS；未修改业务数据、Agent、风险引擎或评估流程。

## 前端界面中文化（2026-09-29）

- 为提升插件易操作性，将实际显示页面（`frontend/src/main_m11.tsx`、`frontend/src/BeautyCopilotPlugin.tsx`）中的英文界面文案统一改为中文：顶部品牌/模式标识（演示缓存模式/实时 Qwen 模式）、各分区 eyebrow 标题、按钮（演示场景/发送下一条消费者消息/重置场景/宿主回复编辑器）、宿主事件名、插件分区标题（意图/情绪/证据/订单工单洞察/服务时间线/风险建议动作/建议回复）等。
- 在 `frontend/src/pluginRuntime.ts` 新增统一中文标签映射：风险等级（critical/high/medium/low → 紧急/高危/中风险/低风险）、跟踪状态（open/processing/resolved/ignored → 待跟进/处理中/已解决/已忽略）、风险类别（safety/sentiment/service → 安全/情绪/服务）、五类宿主事件；原始枚举值仍用于接口与数据，未知值回退显示原值。
- 未改动的英文：JSON 证据块的 key、会话编号（如 S00082）、provider 数据值（如 mock-ui）等机器数据；旧入口 `frontend/src/main.tsx` 未被 `index.html` 引用，本轮保持不变。
- 验证：`npm.cmd run typecheck`（tsc --noEmit）PASS；浏览器实测 `/`、`/workbench`、`/risk-dashboard` 三页渲染正常，点击 AI 分析后插件面板各中文分区正确显示，无前端控制台报错（仅有后端 8000 端口未启动的预期网络失败，UI 正常降级 mock）。

## Risk Dashboard 风险详情闭环（2026-09-30）

- 修复 `GET /api/risks/{risk_id}` 与状态更新接口的详情构造调用，返回真实客户、session、订单、工单、风险原因、证据、服务时间线、建议动作和当前状态；未修改 Agent、Hybrid Risk 或 Evaluation。
- 新增 `frontend/src/RiskDashboard.tsx` 风险详情抽屉：风险列表点击“查看详情”后加载详情；支持状态 `pending/processing/resolved`、处理备注保存、列表刷新，以及“查看原始会话”跳转 `/workbench?session_id=...`。
- 后端 HTTP smoke：风险详情返回 `session=S00277`、订单 2 条、工单 1 条、时间线 8 条；状态 `processing` 保存后恢复为原状态，持久化正常。
- 浏览器 click-through（mock/demo）：点击详情展示完整字段；状态切换为处理中并保存，再恢复为待处理；详情抽屉可见“查看原始会话”；浏览器 error logs=0。
- 验证命令：`python -m unittest discover -s tests -q`（30/30 PASS）；`frontend/npm.cmd run typecheck` PASS；`frontend/npm.cmd run build` PASS。
- 本次未发起 live Qwen 请求，`data/raw` 未修改。

### 风险详情布局调整（2026-09-30）

- 风险详情不再作为风险列表之后的独立底部面板；点击“查看详情”后，完整详情直接插入到对应风险条目下方。
- 切换其他风险条目时，旧详情收起，详情随当前选中条目移动，避免列表与详情上下文错位。
- 保留订单/工单上下文、证据、服务时间线、状态持久化和原始会话链接。
- 验证：frontend typecheck PASS；Vite production build PASS；浏览器实际点击首条及其他风险，详情均显示在对应条目之后。

## 产品品牌体系升级（2026-09-30）

- 产品统一命名为 `知妍 AI / Zhiyan AI`，英文产品描述为 `Zhiyan Beauty Copilot`。
- 模块命名统一为：知妍·伴答（Zhiyan Copilot，智能接待辅助插件）、知妍·洞察（Zhiyan Insight Dashboard，风险预警与跟踪中心）、知妍·智核（Zhiyan Intelligence Core，Agent/Tools/Hybrid Risk）。
- 前端用户可见品牌、宿主/插件边界、风险看板标题和智能回复建议文案已完成统一；代码变量、API 字段、数据结构保持不变。
- 新增 `docs/BRAND_GUIDE.md` 与 `docs/PRODUCT_ARCHITECTURE.md`，并更新 README、Demo Script、Plugin Runtime 和 Skill references。
- 本轮未修改 Agent、Qwen 调用、Tools、Hybrid Risk、Evaluation 或原始比赛数据。
- 验证：`frontend/npm.cmd run typecheck` PASS；`frontend/npm.cmd run build` PASS；`python -m unittest discover -s tests -q` 30/30 PASS；浏览器 `/workbench` 与 `/risk-dashboard` 已显示知妍 AI、知妍·伴答、知妍·洞察品牌体系。

## M12-P0 知妍·伴答核心 Copilot 能力升级（2026-10-01）

- 保留现有 Qwen provider、业务 Tools、Hybrid Risk、Evaluation、Demo cached mode 和 Live Qwen mode；未改变品牌、风险算法、数据结构或评估数据。
- `BeautyAgent` 现在返回 UI-safe workflow trace：客户需求、工具核查步骤、已获得事实摘要、风险摘要和回复依据；不返回 raw tool payload。
- 会话入口会显式核查历史会话、客户/订单上下文和相关服务工单，回复生成继续使用真实物流、退款、不良反应和工单事实；缺少事实时明确要求进一步核实。
- 知妍·伴答新增“客户洞察 / 信息核查 / 关键依据 / 风险判断 / 智能回复建议”展示；分析中显示“知妍正在分析”和简洁核查步骤。
- 关键依据已从 raw JSON 改为中文摘要（订单数、工单号、命中信号等），插件不展示原始 Tool payload。
- 新增离线测试覆盖：workflow trace、物流事实回复、退款事实回复、不良反应安抚与人工升级回复；未发起大规模 Qwen evaluation。
- 验证：`python -m unittest discover -s tests -q` 33/33 PASS；frontend `npm.cmd run typecheck` PASS；Vite production build PASS；mock API S00011 返回真实物流单号与状态；浏览器 smoke 显示信息核查步骤和智能回复建议。

## M13-P1 企业级工作台体验升级（2026-10-01）

- 保留模拟千牛 Host + 知妍·伴答 Plugin 边界、真实赛题会话、Agent、Hybrid Risk、Dashboard 和 Demo cached/live 模式；未修改数据结构、风险算法或 Evaluation。
- `/workbench` 左侧真实会话列表继续显示 8 条并支持展开，新增服务状态与风险等级标识；中间 Host 新增客户洞察卡（客户、消费等级、历史订单/服务、情绪、风险）及订单/商品上下文卡。
- 知妍·伴答新增“知妍工作流”四步可视化：理解需求、查询信息、分析风险、生成回复，明确 waiting/running/completed 状态；整体 UI 收敛为企业 SaaS 卡片层级，减少渐变和调试感。
- `/risk-dashboard` 真实风险列表、详情与 Workbench 原始会话闭环保持可用；未发起新的 live Qwen 请求。
- 验证：backend `python -m unittest discover -s tests -q` 33/33 PASS；frontend `npm.cmd run typecheck` PASS；frontend `npm.cmd run build` PASS（Vite 生产构建成功）；浏览器 mock click-through 验证 `/workbench` 客户洞察、订单上下文、插件工作流和真实工具核查展示，`/risk-dashboard` 风险列表与详情加载正常。
- API smoke：更新后的 `/api/workbench/sessions` 在 mock backend 返回真实会话的 `status` 与 `risk_level`（例如 S00362=medium），未读取或输出任何密钥。

## M15 知妍 AI 品牌形象与 Mascot UI Integration（2026-10-02）

- 新增统一品牌资产 `Logo.png`，复制至 `frontend/public/Logo.png`，并新增可复用 `frontend/src/components/brand/Brand.tsx`：`BrandIcon`、`ZhiyanMascot`、`AgentStatusMascot`。
- `/workbench` Header、知妍·伴答插件标题、空状态、分析状态和智能回复建议均使用知妍 Mascot；空状态提供“知妍已准备好”与开始分析引导，分析中使用真实 loading 生命周期，保留 LIVE/DEMO 模式标识。
- `/risk-dashboard` 风险详情增加知妍风险分析与品牌关键依据标识；Host + Plugin 边界保持不变，mascot 未覆盖客户消息区域。
- 新增 `docs/BRAND_UI_GUIDE.md`，定义品牌色、Icon/Mascot 尺寸、状态动画与使用边界。
- 未修改 Qwen provider、Tool calling、Hybrid Risk、数据集或评估流程；未发起新的 Agent evaluation。
- 验证：backend `python -m unittest discover -s tests -q` 33/33 PASS；frontend `npm.cmd run typecheck` PASS；Vite production build PASS；浏览器 smoke 验证 `/workbench` Header/插件/空状态/工作流/回复品牌和 `/risk-dashboard` 风险详情品牌一致，未见页面级运行错误。

## M15-P1 品牌 UI 微调（2026-10-02）

- 替换无背景图标：用 `Logo（无背景）.png` 覆盖 `frontend/public/LogoMascot.png`（透明背景、白团子主体），删除 `make_logo_mascot.py` 与临时探针脚本。
- 移除 `/workbench` Header 副标题"面向美妆客服场景的智能接待与风险洞察 Copilot"（仅保留中英文标题）。
- 移除知妍·伴答空状态大图标（`ZhiyanMascot` 96px），仅保留标题与操作列表。
- 移除风险详情"关键依据"前的 Logo 图标，修正 `ZHiyan COPILOT` 为 `ZHIYAN COPILOT`。
- 删除建议回复卡片底部的"服务提供方 / 耗时"元信息行。
- 验证：frontend `npm.cmd run build` PASS（TypeScript 编译 + Vite 生产构建均通过）；未修改后端、Agent 或评估逻辑。

## Recovery / Integrity Check（2026-10-02）

- 按只读模式检查 SQLite、原始 Excel、generated data、配置、Git 和备份线索；未执行 reset_demo、seed、import 或任何数据库写入。
- `data/beauty_cs_agent.sqlite3` 存在，`PRAGMA integrity_check=ok`；核心记录与导入摘要一致：chat_messages 998、orders 113、工单表合计 80。
- 原始 Excel SHA-256 与 `data/import_summary.json` 一致；未发现可恢复的数据库 backup/previous/WAL 副本。数据库未纳入 Git，无法从 Git 直接恢复 SQLite 版本。
- 检查时本地 API 端口不可连接，且数据库路径为相对路径 `data/beauty_cs_agent.sqlite3`；当前最可能是服务未启动或启动工作目录不正确，而不是数据删除。
- 诊断报告见 `docs/DATA_RECOVERY_REPORT.md`。未自动恢复，等待确认。
- 后续验证已从仓库根目录使用 `.venv\Scripts\python.exe -m uvicorn app.api:app --host 127.0.0.1 --port 8000` 恢复服务；实际解析数据库为 `E:\beauty-cs-agent\data\beauty_cs_agent.sqlite3`。`/health`=200、工作台会话 total=100、风险 total=52；S00082 返回 10 条消息/1 订单/1 工单，客户摘要与风险详情均可读取真实数据。结论：无需修改路径或数据库，原问题是 API 未监听或启动工作目录不正确。

## Risk Detail Context Navigation（2026-10-02）

- 知妍·伴答的“打开风险详情”现在携带 `risk_id`、`session_id` 和可用 `order_id`，优先跳转 `/risk-dashboard?risk_id=...`；无 risk_id 时按当前客户关联风险查找，找不到则显示“当前会话暂无已生成风险事件”，不跳转总览。
- `/risk-dashboard` 读取 query 参数后自动加载并展开对应风险详情；详情保留客户、会话、订单/工单、风险原因、关键依据、服务轨迹、处理建议和状态，并提供“返回原始会话”。独立“打开知妍·洞察”入口仍跳转总览。
- 后端建议结果增加导航元数据 `risk_id/risk_ids`，不改变 Agent、Hybrid Risk 或 Evaluation；多风险按当前模型风险等级及风险等级排序选择优先事件。
- 浏览器 click-through：S00082 → 分析 → 打开风险详情，URL 包含 `risk_id=方b**:adverse_reaction`、`session_id=S00082`、订单号；风险详情自动展开并显示真实订单/工单/轨迹；点击“返回原始会话”回到 `/workbench?session_id=S00082`。
- 验证：backend 33/33 PASS；frontend typecheck PASS；Vite build PASS；未发起 live Qwen evaluation。

## M16 知妍·伴答 Quick Action Agent 重构（2026-10-02）

- 从当前 998 条聊天及关联订单/工单字段提炼客服行动类型，新增 `docs/CUSTOMER_SERVICE_ACTION_CATALOG.md` 和 `docs/ZHIYAN_COPILOT_INTERACTION.md`。当前实现 10 个可执行 Action，均绑定真实 SQLite 来源；不存在生产 API、直播后台、批次追溯或预计送达时间时不展示伪按钮。
- 新增 `app/action_registry.py` 作为 Action/Tool allowlist；`BusinessTools` 增加订单、物流、退款、打款、退货、换货、售后工单、不良反应、历史沟通和历史承诺的最小结构化查询投影。所有执行请求绑定 `session_id`，NOT_FOUND 明确返回进一步核实。
- 新增 `/api/workbench/{session_id}/actions`、`POST /api/copilot/actions/{action_id}`、`POST /api/copilot/chat`。快捷按钮直接执行真实业务 Tool，Agent Chat 只展示简洁结果和数据来源，不展示 raw payload。
- 右侧知妍·伴答已改为“客户洞察 → 知妍建议行动 → 知妍 Agent → 知妍生成建议回复”；删除“知妍工作流”“信息核查”独立大卡片和中央聊天区“知妍分析当前会话”按钮。会话切换后插件清空短对话并重新加载 Action。
- 浏览器 mock click-through：真实会话 S00362 点击“查看退款状态”返回待审核退款记录 HV8045912170；真实会话 S00082 点击“查看不良反应记录”返回待处理工单 BLFY70604980；两条结果的 `session_id` 和数据来源分别隔离，无串线。
- 新增 `tests/test_action_registry.py`；backend `37/37 PASS`，frontend typecheck PASS，Vite production build PASS；未发起新的 live Qwen evaluation，未修改原始数据、Hybrid Risk 或 Evaluation。

### Workbench Host 边界微调（2026-10-04）

- 移除中部模拟千牛 Host 聊天区上方的“客户洞察”和“订单与商品上下文”卡片；中部现在只保留会话抬头、消费者/客服消息和回复编辑器。
- 客户洞察与建议行动继续只在右侧知妍·伴答插件提供，避免 Host 与 Plugin 的信息职责混淆。
- 验证：frontend `npm.cmd run typecheck` PASS；Vite production build PASS；浏览器 `/workbench?session_id=S00362` smoke 确认中部无上述卡片，右侧插件仍展示客户洞察与建议行动。
- 订单商品信息已移入右侧知妍·伴答，并统一命名为“订单商品”；浏览器验证右侧展示真实商品“【预售】测试修护精华双支装30ml*2”和订单状态，中部仍不显示该卡片。

### 知妍·伴答 UI 微调（2026-10-04）

- 删除建议行动下方与客户洞察重复的“风险：xx”标签；同步移除 `.risk-compact` 顶部分隔横线及配套 padding。
- 修复客户洞察三个方框内因 `.panel label` 全局 margin 导致的顶部空行（`.insight-grid label{margin:0}`）。
- 知妍 Agent 对话改为左右气泡布局：客服靠右深紫气泡、知妍靠左浅紫气泡，消息不再上下整行堆叠。
- 移除 Agent 回复末尾的“以上信息来自当前比赛实例数据。/来自 chat_messages”等来源声明（`app/action_registry.py`），并删除前端气泡中的“数据来源：{source}”行；接口字段保留不变。
- 验证：`python -m pytest tests/test_action_registry.py -q` 4 passed；frontend TS diagnostics 无错误。

### 访问方式永久修复：单进程托管 + 一键启动（2026-10-05）

- 根因：前端 Vite（5173）是独立手工进程，重启/进程回收后不自启（后端 8000 常在跑），导致反复出现 5173 打不开。
- `app/api.py` 新增 SPA 托管：`frontend/dist` 存在时，FastAPI 在所有 API 路由之后注册 `/{full_path:path}` 兜底——静态文件直接返回，其余路径回退 `index.html`，`api/*` 未命中返回 404（不回退页面）。
- `frontend/vite.config.ts` 固定 `host=127.0.0.1`、`port=5173`、`strictPort`，杜绝端口静默漂移到 5174。
- 新增双击启动脚本 `scripts/start_zhiyan.cmd`：检测 8000 未监听时以 mock 模式启动 uvicorn，等待 `/health` 后自动打开 `http://localhost:8000/workbench`；无需 Node/Vite 常驻。
- 统一访问入口为 **http://localhost:8000/workbench**（5173 仅开发时使用，`npm run dev`）；前端改动后需重新 `npm run build` 才会在 8000 生效。
- 验证：frontend build PASS；backend `python -m unittest discover -s tests -q` 37/37 PASS；HTTP smoke：`/workbench` 200、`/risk-dashboard` SPA 200、assets 200、`/api/workbench/sessions` total=100、未知 api 404；浏览器实测页面/会话切换/插件加载正常，console error=0。

## 12-Factor Agent 差距评估（2026-10-09）

依据仓库根目录 `12-factors-agent.docx`（Dex Horthy《12-Factor Agents》中文演绎版，共 12 条原则）对当前架构逐条对照。注意：原文交叉引用编号在文档中存在错位，以原则内容为准。

### 已符合项

- **原则 1/2（组织规划与工具调用、工具执行器）**：`BusinessTools` 提供工具定义，`action_registry` 承担注册表 + `execute_action` 执行器，Agent 输出结构化动作意图——"思考/行动分离"模式已落地。
- **原则 12（无状态归约器，部分）**：FastAPI 无状态服务，业务状态统一外部化到 SQLite（`data/beauty_cs_agent.sqlite3`）。
- **原则 11（从任何地方触发，部分）**：知妍·伴答以插件形式嵌入千牛工作台面板（宿主触发）；HTTP API 可独立调用。

### 差距项（候选 backlog）

| # | 原则 | 差距 | 建议动作 | 优先级 |
|---|------|------|---------|--------|
| G1 | 原则 4 拥有提示词 | ~~系统提示词硬编码在 `app/qwen_agent.py`~~ **已落地（2026-10-09）**，见下方 G1 落地记录 | 已完成 | ✅ |
| G2 | 原则 5 上下文评估与仲裁 | ~~长会话仅按轮次拼接历史，无重要性分级~~ **已落地（2026-10-09）**，见下方 G2 落地记录 | 已完成 | ✅ |
| G3 | 原则 6 错误压缩入上下文 | ~~工具执行失败时错误未结构化回馈给 Agent 自纠~~ **已落地（2026-10-09）**，见下方 G3 落地记录 | 已完成 | ✅ |
| G4 | 原则 7 统一执行/业务状态 | ~~多步执行步骤状态未统一持久化~~ **已落地（2026-10-09）**，见下方 G4 落地记录 | 已完成 | ✅ |
| G5 | 配置外置化（原则 3 相关基础设施） | ~~配置散落在代码 env 读取与启动脚本注入，无统一 .env 加载；`.env.example` 曾混入真实密钥~~ **已落地（2026-10-09）**，见下方 G5 落地记录 | 已完成 | ✅ |
| G5b | 原则 3 人机协同工具化（原 G5） | ~~人工介入（客服编辑回复）是前端自由文本，未建模为结构化"人类工具调用"，审计链不完整~~ **已落地（2026-10-09）**，见下方 G5b 落地记录 | 已完成 | ✅ |
| G6 | 原则 8 任务生命周期 API | 无任务级 pause/resume/cancel 端点（当前均为同步短请求） | 比赛演示无需长任务，可暂缓；仅在做异步长任务时补 | 低 |
| G7 | 原则 9 显式状态机 | 控制流由 mock 分支与 LLM 隐式决策混合，未用显式 FSM 描述 | 可为 Quick Action 流程补充显式状态文档（不必引入框架） | 低 |
| G8 | 原则 10 小而专注 Agent | 单体 `BeautyAgent` 承担意图/回复/风险多职责，比赛规模可接受 | 保持现状；扩展新业务域时再按 DDD 拆分 | 低（暂不动） |

### G1 落地记录（2026-10-09）

- 新增 `app/prompts/` 目录，三个提示词模板外置（内容与原硬编码逐字一致，行为零变化）：
  - `stage_a_tools.txt`：阶段 A 工具调用系统提示词；
  - `final_synthesis.txt`：最终合成阶段提示词（含 `{schema_contract}` 占位符）；
  - `json_repair.txt`：JSON 修复提示词（含 `{schema_contract}` 占位符）。
- `app/qwen_agent.py` 新增 `load_prompt(name, **values)`：读取模板并替换 `{placeholder}`，首次读取后缓存；占位符替换用 `str.replace` 而非 `str.format`，避免模板中字面花括号冲突。
- 三处调用点（`run()` 内 system / synthesis_system / repair_system）改为 `load_prompt(...)`。mock 模式不经过提示词路径，演示行为不受影响；仅 Live Qwen 模式生效。
- 新增守护测试 `test_prompts_are_externalized_and_placeholder_replaced`（tests/test_qwen_agent.py）：校验模板存在、非空、占位符被替换、关键措辞保留。
- 验证：`python -m unittest discover -s tests -q` 38/38 PASS。
- 后续迭代提示词时直接改 `app/prompts/*.txt` 并提交，代码零改动；如需回滚 `git revert` 对应提交即可。

### G3 落地记录（2026-10-09）

- 新增 `app/error_compactor.py`（无内部依赖，供 qwen_agent 与 action_registry 共用）：`compact_tool_error(tool_name, exc)` 把异常提炼为紧凑 JSON `{error_summary, error_type, message, offending_parameter?, suggestion}`——message 取首行并截断 200 字符，None 字段省略以省 token；规则化 suggestion：意外参数→改用 schema 参数名、缺参→补齐、KeyError→数据缺失不要编造、JSONDecodeError→按 schema 重试、兜底→如实告知会进一步核实。
- `app/qwen_agent.py` 工具循环失败分支：原先回注无信息量的 `{"error": "tool failed"}`，现改为回注压缩错误 JSON，LLM 可据此改参自纠；`args` 初始化移入 try 前，修复解析失败时未绑定问题；`errors` 审计列表保留 `tool_error:<name>:<Type>`。
- `app/action_registry.py`：`execute_action` 工具异常时不再向上抛裸异常（原会 500），返回 `status="ERROR"` + 压缩错误载荷的完整结果；`format_action_result` 新增 ERROR 分支，用户侧文案诚实为"业务查询服务暂时异常…"（区别于 NOT_FOUND 的"未找到相关记录"）。API 契约不变（仍 200 + status 字段），KeyError 未知 action 仍按原样 404。
- 新增 `tests/test_error_compactor.py`（6 例：意外参数/缺参/KeyError/JSON 解析/兜底压缩/长消息截断）；`tests/test_action_registry.py` 补 2 例（ERROR 载荷结构、ERROR 文案）。
- 验证：`python -m unittest discover -s tests -q` 46/46 PASS。
- 生效范围：Live Qwen 模式的工具自纠链路与 Quick Action 执行兜底；mock 演示路径不受影响。

### 启动脚本修复：双击 start_zhiyan.cmd 无效（2026-10-09）

- 症状：双击 `scripts/start_zhiyan.cmd` 不打开网页，`http://localhost:8000/workbench` 不可达。
- 根因（字节级证据）：脚本文件为 **LF（Unix）换行**（start_zhiyan.cmd 44 处 bare-LF、CRLF=0）+ UTF-8 中文 + `chcp 65001` + `goto` 标签 + `if (...)` 多行块。cmd.exe 对 LF-only 批处理的标签定位与块解析不可靠，双击后脚本解析错乱提前终止——服务未启动、浏览器未打开。后端本身无问题（直接以 venv python 启动 uvicorn 后 health/workbench 均 200）。
- 修复：`scripts/start_zhiyan.cmd` 与新增 `scripts/run_service.cmd` 以 **CRLF + 纯 ASCII** 重写（移除 chcp 与中文输出，消除编码/码页隐患）：
  - 启动器：netstat 探测端口（不依赖 curl）→ 未监听则 `start /MIN` 最小化窗口运行 run_service.cmd → 轮询就绪后 `start` 打开浏览器；超时（约 60s）时自动打印服务日志并 pause。
  - run_service.cmd：设置 mock 环境变量，uvicorn 输出重定向到 `logs/zhiyan_service.log`——服务崩溃不再随窗口消失，失败可查。
- 限制：本开发沙箱会拦截所有 Start-Process 生成的窗口进程（连最小 ASCII 测试 cmd 都不执行），无法在沙箱内端到端验证双击路径；已验证字节格式（CRLF=43/9、bare-LF=0、non-ASCII=0）、脚本结构与后端服务可用性，最终以用户双击实测为准。若再失败，窗口会直接显示错误日志。
- 修复后服务已由会话后台进程拉起，health 200 / workbench 200。

### G2 落地记录（2026-10-09）

- 新增 `app/context_arbiter.py`（规则版仲裁器，无内部依赖），替代 `suggest()` 中 `[-6:]`/`[:3]` 的 FIFO 一刀切：
  - **消息分级** `_score`：最新消息=5；核心诉求关键词（退款/退货/过敏/赔偿/发货等 24 项）=5；业务实体（订单号/单号/金额正则）或关联记录=4；寒暄短消息（≤12 字且命中寒暄词）=1；其余=3。
  - **两阶段预算**：阶段 A 完整窗口 ≤ max_messages(6)，最新消息 + 必须保留项优先、背景消息按新旧补位；阶段 B 压缩区 ≤ max_entries(12)，未进窗口的必须保留项做规则摘要（截断 80 字 + 附加"关键实体：…"，标记 `text_truncated`），其余丢弃。原始核心诉求永不因窗口不足被挤出。
  - **订单排序** `arbitrate_orders`：入参指定订单 > 会话内被提及订单 > 其余，超出 3 条丢弃低相关项。
  - 仲裁统计 `context_arbitration: {messages: {total/kept/compressed/dropped}, orders: {…}}` 随 request_context 进入 workflow trace，可观测。
- `app/qwen_agent.py` `suggest()` 接线：`recent_messages`/`orders` 改由仲裁器产出；风险引擎 `assess_context` 仍吃全量 context 不受影响；mock 模式兼容（recent_messages 结构不变）。
- 新增 `tests/test_context_arbiter.py` 8 例：短会话直通、最新消息必留、核心诉求不被挤出（关键回归）、寒暄先丢、实体溢出压缩不丢弃、顺序保持、订单排序与直通。
- 验证：`python -m unittest discover -s tests -q` 54/54 PASS。
- 已知限制：摘要压缩为规则版（截断 + 实体保留），未用 LLM 摘要；`max_messages=6` 与原 token 预算持平，压缩区最多 12 条有硬顶。

### G4 落地记录（2026-10-09）

- 新增 `app/task_state.py`（原则 7）：`agent_tasks` 表（task_id 主键 + execution_state + business_state_json + error + run_id + 时间戳），与业务数据同库持久化；连接用显式关闭的 contextmanager（`with conn:` 只管事务不释放 Windows 文件锁）。
- 执行状态机：`started → context_ready → synthesis_done → completed / failed`。business_state 增量合并——started 记录入参、context_ready 记录上下文规模/风险等级/仲裁统计、synthesis_done 记录 provider/用量/工具调用、completed 记录结果摘要，failed 记录错误（截断 300 字符）并继续向上抛出（API 行为不变）。
- `qwen_agent.suggest()` 拆为包装层（task 生命周期管理）+ `_suggest_inner`（原执行体，内嵌 2 处状态推进）；`AgentResult` 新增 `task_id` 字段（带默认值，不破坏既有位置参数构造），经 `dict(result.__dict__)` 自动透出给前端。
- 新增观测端点：`GET /api/agent/tasks`（列表，最新在前，limit 上限 100）、`GET /api/agent/tasks/{task_id}`（单任务详情，404 兜底）。
- 新增 `tests/test_task_state.py` 6 例：状态合并回读、failed 落库、非法状态拒绝、缺失任务 None、列表排序限数、suggest 全生命周期集成断言（mock 路径四个阶段业务状态齐全）。
- 验证：`python -m unittest discover -s tests -q` 60/60 PASS；重启服务后实测 `GET /api/agent/tasks?limit=2` 返回 completed 任务（risk_level/provider 字段齐全）。
- 已知限制：同步短请求场景，暂不做断点续传执行（重启后轨迹可查但不自动恢复）；状态推进点在 suggest 单入口内，Quick Action 路径未纳入（其为确定性单步调用，agent_runs 已覆盖）。

### G5 落地记录：配置外置化（2026-10-09）

- 新增 `app/config.py`（无第三方依赖的微型 .env 加载器）：`parse_env` 解析 KEY=VALUE（忽略空行/# 注释、剥离首尾空白与成对引号）；`load_env` 把仓库根目录 `.env` 中进程环境尚不存在的键注入 `os.environ`，**已存在的真实环境变量优先**（启动脚本注入的 `AGENT_PROVIDER=mock` 不被覆盖）。
- `app/qwen_agent.py` 与 `app/api.py` 在模块导入时先 `load_env()`，再读取任何配置（api.py 的 `DB_PATH` 与 QwenProvider 的 12 项 env 读取全部经由 .env 可配置）。
- `.env.example` 修复安全问题并补全：此前该文件混入了真实 QWEN_API_KEY（违反占位符规则），已替换为 `sk-your-key-here`；补全 QWEN_MOCK、QWEN_ENABLE_THINKING、QWEN_DEBUG_DIR 等全部键并附中文注释。`.env` 真实值未改动。
- 优先级语义：真实环境变量 > .env > 代码默认值。`scripts/run_service.cmd` 注入的 mock 强制继续生效；手动裸启 uvicorn 时将采用 .env 的 `AGENT_PROVIDER=qwen`（.env 即唯一配置源）。
- 新增 `tests/test_config.py` 4 例：解析（引号/注释/空白）、真实 env 优先不被覆盖、缺失文件 no-op、.env.example 占位符与键全覆盖守护。
- 验证：`python -m unittest discover -s tests -q` 68/68 PASS；重启后 `/health` provider=mock（脚本注入优先级正确）。

### G5b 落地记录：原则 3 人机协同工具化（2026-10-09）

- 新增 `app/human_feedback.py`：`human_feedback` 表（feedback_id 主键、conversation_id、original_reply、edited_reply、created_at）与业务数据同库持久化，连接用显式关闭的 contextmanager（Windows 文件锁随关闭释放）；`record_feedback` 校验非空并生成 `fb_` 前缀 ID，`list_feedback` 支持按会话过滤/限量（供审计查询）。
- 新增 `POST /api/copilot/feedback`：校验会话存在（404）与回复非空（400），落库后返回 `{feedback_id, conversation_id, recorded}`。
- 前端接线（`frontend/src/main_m11.tsx`）：插件「复制到回复框」时记录本次插入的建议文本（lastInserted，切换会话时清空）；点击「发送给消费者」时，若本次会话插入过 AI 建议，自动以 `{conversation_id, original_reply: 插入的建议, edited_reply: 最终文本}` 调用反馈端点（失败静默，不阻断模拟发送）；未采纳建议的普通发送不产生记录。
- 审计链闭合：AI 建议（agent_runs/agent_tasks 已有）→ 人工修订（human_feedback）→ 发送；未经编辑直接采纳也会留痕（可计算采纳率）。
- 新增 `tests/test_human_feedback.py` 4 例：落库回读、按会话过滤与限量、空回复拒绝、跨连接持久化。
- 验证：unittest 68/68 PASS；frontend typecheck + Vite production build PASS；重启服务后实测 POST /api/copilot/feedback 返回 feedback_id（S00082，内容带 [smoke] 标记，保留作功能演示数据）。
- 已知限制：反馈为 best-effort 上报（网络失败静默，不做重试）；快捷行动结果经复制后同样被记录为"原始建议"；暂无读取端点（`list_feedback` 模块级可用，UI 展示按需再加）。

### Git 历史安全重写（2026-10-10）

- 背景：`.env.example` 曾在历史提交（已推送到 GitHub）中混入真实 QWEN_API_KEY，违反占位符规则；G5 落地时工作区文件已改回占位符，本轮继续清除历史。
- 操作：`git stash` 暂存未提交工作 → `git bundle` 备份至 Temp → `git filter-repo --replace-text` 将历史中的真实 Key 替换为 `sk-your-key-here` → `git stash pop` 恢复工作区（改动完整保留）。
- 额外发现：Trae/Codex 编辑器快照引用 `refs/codex/turn-diffs/checkpoints/...` 持有含 Key 的旧 `.env.example` blob，filter-repo 不会重写此类工具快照；已删除该引用并 `repack -a -d -f` + `prune --expire=now`，旧 blob 确认从对象库消失（122→120 对象）。
- 远端：force push 覆盖 `origin/master`（d923243 → 8af1484），GitHub 上的旧历史已被替换。提交信息、作者、日期保留，工作区 33 项改动不变。
- 建议：尽管历史已清除，GitHub 可能缓存旧提交视图（fork/PR 引用不可控），**仍建议到阿里云控制台轮换该 Key**；新 Key 只放 `.env`。Temp 中的重写前备份 bundle 含旧 Key，确认无误后应删除。

### Copilot Chat 意图路由修复（2026-10-10）

- 问题：Agent Chat 对"你能做什么"等能力咨询误入业务兜底（执行 actions[0]）并返回"未找到相关记录"，且消息重复出现两次。
- 修复：意图分类新增 capability_question/risk_query/unknown；路由改为"先分类再路由"，仅 business_query 允许调用 business tool；能力咨询返回固定介绍（CAPABILITY_RESPONSE，多行经 white-space:pre-line 渲染）；删除 actions[0] 盲兜底，未知意图诚实回复 UNKNOWN_REPLY，"未找到相关业务记录"仅在真实业务查询无结果时出现（format_action_result NOT_FOUND 分支）。
- 防重：前端 sendingRef 同步锁 + request_id（crypto.randomUUID）随请求发送；后端 copilot_request_cache 幂等缓存（先查后路由，上限 256 条 LRU 淘汰）。
- 分类与路由逻辑位于 app/action_registry.py（classify_copilot_intent / handle_copilot_chat / BUSINESS_ROUTES 关键词→动作映射），api.py 端点为薄委托；业务查询按关键词直达动作（过敏→check_adverse_reaction、物流→check_logistics、退款→check_refund 等 8 条），不再依赖 recommend_actions 排序。
- 验证：75/75 测试通过（新增 CopilotChatRoutingTests：Case1 能力介绍零工具调用 / Case2 物流问题调用 get_logistics_info / Case3 风险问题调用 get_customer_context / 未知意图诚实回复）；HTTP 冒烟四用例 intent 与 tools_used 符合预期，同 request_id 二次请求返回缓存响应；前端 typecheck + build 通过（bundle index-C0lqSEmm.js），服务已重启。
- 已知限制：意图分类为规则词表（BUSINESS_ROUTES/CAPABILITY_TERMS/RISK_TERMS），覆盖演示场景；接 qwen live 后可由 LLM 分类替换，词表保留为兜底。测试注意：PowerShell Invoke-RestMethod 发中文 body 必须 UTF-8 字节，否则服务端收乱码全部判 unknown。

### 结论

G1–G5（含 G5b 人机协同）已完成，剩余 G6–G8 优先级均为低（演示阶段不动）；若后续迭代，建议顺序 G7。

## M17.1 知妍·洞察 Dashboard 视觉优化（2026-10-11）

- 风险事件 API 增加只读 `risk_id`、`risk_type` 和 `observed_at` 字段；`observed_at` 取关联客户最新客服聊天 `sent_at`，用于趋势统计并明确标注为关联服务记录时间。
- 看板增加紧凑两列图表卡：风险等级分布、主要风险来源、风险处理进度、重点风险客户 Top 5；趋势图占满一行并按最近 14 个有记录日期绘制。
- 图表与列表联动筛选、清除筛选和风险详情链路保持不变；无时间序列或无风险事件时显示业务空态。
- 文档：`docs/ZHIYAN_INSIGHT_DASHBOARD.md`。
- 待验证：frontend typecheck、production build、backend tests、浏览器图表联动 smoke。

### M17.1 验证结果（2026-10-11）

- `python -m unittest discover -s tests -q`：77/77 PASS。
- `npm run typecheck`：PASS；`npm run build`：PASS。
- 风险趋势已使用 `/api/risks` 的 `observed_at`：取关联客户最新聊天 `sent_at`，按最近 14 个有记录日期绘制；页面文案说明这是风险识别/关联服务记录时间。
- 图表布局改为紧凑两列卡片，趋势图占满一行；环形图图例固定紧凑宽度，避免大面积横向空白。
- 浏览器自动化尝试访问本地 Vite 地址时出现 `ERR_CONNECTION_TIMED_OUT`，因此本轮未将浏览器 click-through 记为通过；需在可访问本地服务的浏览器环境复验筛选、清除筛选和详情打开。

## M12 Context Engine（2026-10-13）

- 目标：知妍从单轮问答升级为理解当前客服环境的 Agent——模型在回答"这个客户为什么投诉？"时能知道客户是谁、买了什么、历史发生了什么、当前订单状态、可调用什么工具。
- 数据扫描文档：`docs/DATA_CONTEXT_MAP.md`，逐表列出客户维度（无独立 customers 表，buyer_nickname 承载）、chat_messages（998 行 17 字段）、orders（113 行）、五类工单表（公共字段 + 特有字段 + 行数）、风险派生实体与运行态辅助表，并明确隔离与防串线约束。
- 新增 `app/context_engine.py`：
  - 统一 `AgentContext` 六段：customer / session / order / service_history / risk / available_tools；`raw_context`（repr=False，不序列化）供风险引擎与 workflow 内部使用未修剪数据。
  - 三入口构建 `ContextEngine.build(session_id/conversation_id/buyer_nickname/order_number)`：会话入口从首条消息锚定 buyer → `get_customer_context(buyer, limit=200)` → 关联会话工单优先（与既有 suggest 行为一致）→ 只读调用 `assess_context`。
  - 防串线：一切聚合以 buyer_nickname 为锚；白名单字段投影（`_prune_messages` 限 8 条、`_prune_orders` 限 3 条、`_prune_work_orders` 限 6 条），`_compact` 递归剔除 None/空串/空列表，杜绝不存在字段与虚假业务事实进入 payload。
  - `_PROMISE_TERMS` 关键词提取历史承诺消息；`available_tool_names()` 返回 14 个工具名。
- `app/qwen_agent.py` 接入：`BeautyAgent.__init__` 持有 `ContextEngine`；`_suggest_inner` 上下文装配段重写——任一入口（conversation_id / buyer_nickname / order_number）自动推导完整业务上下文，不要求前端手动传大量信息；request_context 保留全部旧键（mock provider 依赖 recent_messages/orders/work_orders），追加 customer/session/service_history/risk_context/available_tools 五段。
- 新增 `tests/test_context_engine.py` 12 例：`_compact` 空值剔除；S00082 构建六段齐全、未知会话安全降级、payload 无 None/空串、字段白名单校验；客户 A/B 隔离（S00082=方b** vs S00002=冯h**——买家不同、消息/订单/工单不串买家、订单号集合无交集、锚定会话不在 other_sessions、risk level 各自独立）。
- 验证：`python -m unittest discover -s tests -q` 89/89 PASS；重启 9000 端口服务（mock）冒烟：/health ok，POST /api/workbench/suggest（S00082）返回 risk_level=critical、tool_calls=[get_conversation, get_customer_context, get_work_orders]，S00002 对照返回不同建议（上下文隔离生效）。
- 未改动：UI、Risk 算法、Qwen provider。
- 已知限制：mock 模式下 request_context 不直接暴露在 HTTP 响应中（内部对象，经 workflow trace 可观测）；字段白名单为手工维护，schema 变更时需同步。

## M14 Planner & Action Router（2026-10-13）

- 目标：知妍从"按钮驱动工具"升级为"Agent 根据问题自主决定行动"——输入用户消息，先由 Planner 输出 plan，再由 Action Router 执行。
- Action Registry 升级（`app/action_registry.py`）：`ActionDefinition` 新增 `description` / `trigger_examples` / `required_context` 自描述元数据；新增第 11 个行动 `assess_customer_risk`（分析客户风险，tool 映射 `get_customer_context` + 风险引擎，由会话锚定买家）；新增 `registry_catalog()` 输出完整目录（未来可直接注入 LLM Planner 提示词）。
- 新增 `app/planner.py`：
  - **Planner** `build_plan(message, intent=None, context=None, memory=None)`：输出 `{"mode": "none|direct|planned", "steps": [{"action", "reason", "tool"}]}`。路由规则——明确查询单步直达（direct）；投诉/升级信号（投诉/举报/12315/差评/曝光等）固定规划"历史服务摘要 + 风险评估"两步（planned）；多意图消息为每个诉求各规划一步（上限 3）；闲聊/能力咨询/无法识别不调用任何工具（none）。memory 生效：本轮会话已执行过的行动不重复规划。
  - **Action Router** `run_plan(tools, session_id, plan)`：Planner ↓ Tool，逐步经 Registry 执行（错误压缩兜底不变），聚合 tools_used / results / evidence，多步回复按行拼接。
- `handle_copilot_chat` 重接：capability/unknown 直接返回（不调 tool）；business_query/risk_query 交由 Planner 规划、Router 执行，响应新增 `plan_mode` 与 `plan` 字段（可审计规划依据）；`execute_action` 内部分派 `assess_customer_risk`（`_execute_risk_action`），`format_action_result` 新增风险评估渲染与无客户诚实回复分支。API 契约向后兼容（仅新增字段）。
- 新增 `tests/test_planner.py` 10 例：plan 步骤结构（action/reason/tool）、Registry 目录完整性、多意图多步规划、memory 去重、闲聊/空消息零工具；四个核心 case——物流→get_logistics_info、退款→get_refund_status、投诉→summarize_customer_history + get_customer_context（回复含历史服务摘要与风险等级）、能力询问→零工具。
- 验证：`python -m unittest discover -s tests -q` 99/99 PASS；重启 9000 端口服务（mock）冒烟四 case：物流 direct/get_logistics_info、退款 direct/get_refund_status、投诉 planned/[summarize_customer_history, assess_customer_risk]、能力 none/零工具，全部符合预期。
- 已知限制：Planner 为规则版（词表路由），接口已对齐 LLM Planner（registry_catalog + build_plan 签名），接入 qwen live 后可替换为模型规划；context 参数当前预留给风险倾向提示，规则版暂未深度使用。

## M15 RAG Knowledge Brain（2026-10-13）

- 目标：知妍不仅知道业务数据，还知道业务知识；事实类业务优先 Business Tool，知识类问题走 RAG，禁止 RAG 覆盖真实订单数据。
- 知识库内容（`knowledge/`，纳入版本控制，只含通用政策不含客户数据）：
  - `product_knowledge.md`（9 切片）：产品线与真实在售商品（含 SKU）、护肤顺序、修护精华液/面霜/洁面/彩妆/洗护用法、适用肤质、保质期与保存、赠品与预售说明；
  - `after_sales_rules.md`（7 切片）：七天无理由退货条件、退货退款流程、退款与线下打款、物流异常、补换货、不良反应特殊通道、时效与承诺规则；
  - `service_standards.md`（7 切片）：响应规范、禁用话术、情绪安抚、投诉处理、承诺管理、隐私安全、AI 助手使用规范。
- 新增 `app/knowledge_base.py`（纯标准库，无网络/无新增依赖）：
  - **Document ingestion**：markdown 按 H2 切片（过长段落按段落打包，上限 360 字），`knowledge_meta` 清单按内容 hash 增量同步，新增/变更/删除文件自动处理；
  - **Embedding**：确定性中文字符 unigram+bigram（含 ASCII 词）md5 哈希向量，512 维 L2 归一化，跨进程一致、可持久化；接口对齐未来远程/本地模型（ingest/search 签名不变）；
  - **Vector retrieval**：SQLite `knowledge_chunks` 持久化切片与向量，余弦相似度 + 0.8 权重的标题命中加权，阈值 0.12，无命中返回空列表。
- 路由接入（`app/action_registry.py` + `app/planner.py`）：新增 `knowledge_query` 意图与 `search_knowledge_base` 行动（tool=`search_knowledge`）；分类优先级为 能力咨询 → 具体业务事实（不良反应事件/订单号/状态查询）→ 通用知识 → 一般业务 → 风险 → 未知；疑似不良反应事件按业务事件处理（安全优先）；具体状态查询即使提到产品名也强制走业务工具；Planner 多意图去重（命中具体动作后不再追加泛化 check_order）；Router 的知识步骤携带问题原文走 RAG。
- 回答渲染：命中时输出最优切片全文 + 《文档·小节》参考来源；无命中诚实回复"知识库中暂未找到…"，不编造；检索异常走 G3 错误压缩。
- API：`GET /api/knowledge/search?q=&top_k=` 只读检索；`POST /api/copilot/chat` 自动注入 KnowledgeStore（启动时建索引）。
- 新增 `tests/test_knowledge_base.py` 19 例：embedding 确定性/归一化、临时库摄入/持久化/幂等/变更与删除同步/无命中、真实库检索（精华用法/退货条件/保质期）、意图边界（产品+订单混合问走 tool、不良反应走业务、能力零工具）、端到端 chat（产品问→search_knowledge 含用法与来源、政策问→含"7 天"、订单问→get_refund_status 无 RAG 来源、空库诚实拒答）、**全量切片不得出现任何真实订单号**（RAG 不覆盖订单事实的守护断言）。
- 验证：`python -m unittest discover -s tests -q` 118/118 PASS；重启 9000 端口（mock）冒烟：精华使用→RAG 用法答案、退货条件→7 天政策、退款到账→get_refund_status（NOT_FOUND 诚实回复，未被 RAG 覆盖）、物流→真实运单、knowledge/search 3 命中。
- 已知限制：embedding 为离线确定性哈希向量（演示与无网环境可用），语义召回弱于神经模型，后续可在 embed() 后接 DashScope embedding；未改动 UI 与 Qwen provider。

## M16 Zhiyan Agent Brain Integration（2026-10-13）

- 目标：整合 Context / Memory / Planner / Action Router / RAG 成完整 Agent，流程为 Input → Context Assembly → Memory Retrieval → Planning → Action Selection → Tool/RAG → Response Generation，并新增 Response Grounding Check（回答必须有依据，禁止无证据业务事实）。
- 新增 `app/agent_brain.py`（唯一编排入口，不改各模块内部实现）：
  - `process_message(tools, session_id, message, knowledge_store, context_engine, memory)`：按阶段执行完整管线，响应暴露全部阶段信息——`intent` / `context_used`（M12 统一上下文）/ `memory_used`（服务历史摘要 + 本会话历史 Agent 轮次）/ `plan_mode` + `plan`（M14 Planner）/ `tools_used` + `results` + `evidence`（M14 Router 执行 / M15 RAG）/ `message`（Response Generation）/ `grounding`（Grounding Check）。能力咨询/无法识别按 M14 规则不进入工具链路，直接返回能力介绍或诚实说明。
  - `SessionMemory`：进程级会话记忆，按 session_id 保留最近 10 轮记录（intent / plan steps / tools_used），回传给 Planner 实现同会话不重复规划已执行行动；服务记忆从装配上下文提取（客户历史会话数/订单/工单/承诺），无数据则不产出记忆条目。
  - `grounding_check(message, results)`：事实信号 = 运单/订单/工单号类 token（字母前缀+6 位以上数字或 8 位以上连续数字）与金额；证据 = status=OK 结果的 data JSON（RAG 命中切片文本同属证据，引用来源即依据）。出现事实但无任何 OK 证据、或事实无法在证据中定位即判定无依据；管线在判定失败时用诚实兜底回复替换原答复（原答复保留在 `grounding.original_reply` 供审计），不编造任何业务事实。
- API：`POST /api/copilot/chat` 改接 `process_message`，`create_app` 增加 `ContextEngine` 实例复用；响应新增 `context_used` / `memory_used` / `results` / `grounding` 字段，`message` / `intent` / `tools_used` / `plan` 契约不变，前端零改动兼容。
- 新增 `tests/test_agent_brain.py` 11 例：四个验收场景——物流咨询（context 装配 + get_logistics_info + grounding 通过）、历史投诉（service_history 记忆检索；第二轮 past_turns 记忆生效，plan 去重为仅风险更新）、产品使用（search_knowledge 命中 RAG，含用法与参考来源）、复杂投诉（planned 两步：历史摘要 + 风险评估）；能力询问零工具、未知会话诚实拒答且无记忆、grounding 失败注入测试（mock run_plan 返回编造运单号 → 答复被兜底替换并保留原答复审计）；GroundingCheck 单元测试（无证据事实拒绝 / 有证据通过 / 空事实 vacuous 通过）。
- 验证：`python -m unittest discover -s tests -q` 129/129 PASS（118 + 11）；重启 9000 端口（mock）HTTP 冒烟——物流：context:Y get_logistics_info:Y grounding=True；产品使用：search_knowledge:Y 参考来源:Y grounding=True；复杂投诉：plan_mode=planned 两步含历史服务摘要 grounding=True；能力询问：plan_mode=none 零工具；memory 跨轮：第二轮 plan=[assess_customer_risk]、memory_types=[past_turns, service_history]。
- 已知限制：SessionMemory 为进程级（服务重启即清空，跨进程持久化留待后续）；grounding 为规则化事实核对（单号/金额级），语义级事实核对待接入 qwen live 后可由模型复核；未改动 UI、Risk 算法、Qwen provider。

## M17 Knowledge Pipeline 工程化升级 + M18 Retrieval Intelligence Layer（2026-10-13）

- 目标：把 M15 RAG 从"文件→向量→查询"升级为标准知识管道（Loader → Document → Chunk → Embedding → VectorStore → Retriever → Generation），并补检索智能（改写/混合/精排），解决"知识进不来、找错资料"。
- 新增 `app/knowledge_loader.py`（M17.1 统一知识接入层）：`Document`（page_content + metadata）为标准单元；`KnowledgeLoader` 按来源分发——MarkdownLoader（支持 front-matter 声明 metadata）、ExcelLoader（openpyxl，表头含 text 列、其余列进 metadata，用于成分表/活动规则等表格知识）、DatabaseLoader（只读 SQL，仅政策配置类表，禁止客户/订单数据）、ApiLoader（注入式 fetch 回调，无网络演示环境默认返回空）。`load_path()` 按扩展名（.md/.xlsx/.xlsm）分发；文档级 metadata 自动继承到切片。
- M17.2 Document metadata：三份 md 知识文件头部补 front-matter（category/source/update_time/confidence）；`knowledge_chunks` 表新增 `metadata` 列（启动时检测缺列自动 ALTER 迁移，旧切片置空对象）；检索结果与 `/api/knowledge/search` 响应随切片返回 metadata，回答可追溯"结论来自哪里"。
- 重构 `app/knowledge_base.py`：`ingest_documents()` 为统一摄入入口（文件/数据库/API 共用），`ensure_index` 同步扫描 md+xlsx；`KnowledgeRetriever` 独立封装——不绑定具体 VectorStore，候选由注入的 `candidate_fn` 提供（换存储/远程 embedding 只换候选函数）。
- 新增 `app/query_rewriter.py`（M18.1）：规则版同义词改写（"脸疼"→刺痛/过敏/不良反应等 15 组映射），标准词附加原查询后进入检索；接口预留 LLM 改写替换。
- M18.2 Hybrid Retrieval + M18.3 Rerank：粗排宽阈值召回池（top 20，0.5× 阈值）→ 精排多信号重排（语义分 + 0.8×标题分 + 0.5×关键词覆盖率）→ 阈值过滤 top_k；semantic 与 keyword 双通道显式融合。
- 安全优先补丁：chat 意图层把口语不良反应词（脸疼/脸痛/红肿/辣眼睛等 7 个）纳入 ADVERSE_EVENT_TERMS 与 BUSINESS_ROUTES——"这个用了脸疼怎么办"判业务事件走 `get_adverse_reaction_record`（真实工单），不走 RAG。
- 新增 `tests/test_knowledge_pipeline.py` 16 例：front-matter 解析、Markdown/Excel/Database/Api 四类 Loader、空行跳过、改写命中与不命中、口语查询经改写命中不良反应章节且 metadata 随结果返回、混合精排标题双命中排第一、Excel+Database 双源进同一库可检索、Retriever 注入式独立组装、口语不良反应路由业务工具；现有 19 例知识库测试零修改全部通过。
- 验证：`python -m unittest discover -s tests -q` 145/145 PASS（129 + 16）；重启 9000 端口（mock）HTTP 冒烟——产品问题 chat：knowledge_query + search_knowledge + 参考来源 + grounded；knowledge/search：metadata（产品知识/产品说明书/2026-10/0.95）完整返回；chat"这个用了脸疼怎么办"：business_query + get_adverse_reaction_record + 真实工单编号；search"脸疼"：《不良反应特殊处理通道》首位。
- 已知限制：PDFLoader 暂缓（无真实 PDF 知识源前不引入 pypdf，Loader 架构已预留扩展点）；Query Rewrite 为规则版（接 qwen live 后可换 LLM 改写）；Rerank 权重（0.8 标题/0.5 关键词覆盖）为样例调优值，待真实评估集校准；未改动 UI、Risk 算法、Qwen provider。

## M19 Tool Governance 增量 + M20 Conversation State Machine + M21 Agent Evaluation System（2026-10-13）

- M19 工具治理增量：`ActionDefinition` 新增 `input_schema` 属性（由 required_context 推导 JSON Schema 风格输入契约，免逐条维护），`registry_catalog()` 输出 inputs 供 Planner/审计使用；顺手修复 `search_knowledge_base` 的 required_context 缺逗号笔误（字符串误作 tuple，由 input_schema 校验暴露）。
- M20 会话状态机（新增 `app/conversation_state.py`）：`conversation_state` 表（session_id PK / stage / last_intent / last_actions / updated_at）落业务库，跨重启存活；阶段集 new→confirmed→classified→querying→processing→awaiting_feedback→resolved，规则版推导 `derive_stage`（能力/闲聊=new；结果含 NOT_FOUND=awaiting_feedback；其余=processing）；指代消解 `follow_up_action`——无法识别的短消息（≤12 字）或命中追问标记（还是/还没/怎么样了/然后呢等）时，继承上一轮业务行动重新执行，解决"还是没有到账/怎么样了"类追问重新开始的问题。已接入 `process_message`：每轮结束状态迁移落库，响应新增 `state: {stage, follow_up}` 字段。
- M21 评估系统（新增 `app/agent_evaluation.py` + `tests/gold/agent_eval_cases.json`）：四指标离线基线——Tool Accuracy（7 例：物流/退款/快递/产品/能力/投诉/口语不良反应，expected 全命中且 forbidden 零命中）、Retrieval Accuracy（4 例首位切片命中期望文档/小节，含"脸疼"改写用例）、Hallucination Rate（全量回复 grounding 无依据占比）、Memory Accuracy（投诉两轮 plan 去重验证）；`python -m app.agent_evaluation` 输出 JSON 报告；阈值 tool≥0.8 / retrieval≥0.8 / hallucination=0 / memory=1.0，低于阈值视为回归。当前实测全部 1.0/1.0/0.0/1.0，all_passed=true。评估会话状态写入自有 `conversation_state` 表，不动业务数据。
- 新增 `tests/test_agent_evaluation.py` 12 例：input_schema 完整性与 catalog 暴露、状态迁移往返/非法阶段拒绝/指代消解触发与不触发/derive_stage 规则、端到端追问继承（退款→"怎么样了"复用 check_refund）、状态跨实例持久（新实例读同库）、gold 用例格式校验、四指标阈值断言。
- 验证：`python -m unittest discover -s tests -q` 155/155 PASS（145 + 10，评估与治理合入 12 例含修复后重跑）；评估报告四指标 1.0/1.0/0.0/1.0；重启 9000 端口（mock）HTTP 冒烟——S00362"退款到账了吗"→get_refund_status（stage=processing），追问"怎么样了"→follow_up=True、继承 check_refund 重新执行；S00082 物流查询 grounding evidence=1、grounded=True。
- 已知限制：状态推导与指代消解为规则版（接 qwen live 后可换模型消解长指代）；评估 gold 集规模小（12 例），需随真实客服语料扩充；前端未展示 state 字段（契约已备好，UI 接入留待后续）；未改动 UI、Risk 算法、Qwen provider。

## 2026-10-14 UI 微调：聊天身份标签样式统一（样式层，无逻辑变更）

- 需求：对话框中"知妍/客服/买家"身份标签移到气泡外上方、统一灰色，删除"客服"标签。
- 改动（仅前端）：`main_m11.tsx` 主对话区与 `BeautyCopilotPlugin.tsx` 知妍 Agent 对话框——气泡行改为列布局，客服/assistant 角色不渲染标签，其余角色（买家/知妍/用户）在气泡外上方渲染 `<span class="bubble-role">`；`styles.css` 新增 `.bubble-role`（#98a2b3 灰、10px）与 `.bubble-row` 列布局，`.agent-chat-line` 由行布局改列布局，删除气泡内 `<b>` 角色名的死样式。
- 验证：`vite build` 成功；浏览器实测（localhost:9000）——中间聊天区买家标签灰色位于气泡外上方、客服消息无标签；Agent 对话框知妍有灰色标签、客服无标签。
- 注意：前端 API 写死 `http://localhost:9000`，须以 localhost（而非 127.0.0.1）打开页面，否则跨源导致数据加载失败。

## 2026-10-14 UI 微调 2：删按钮 + 千牛式三栏等高（样式层）

- 需求：删除"加载真实场景""重新加载原始会话"按钮；左/中/右三栏像千牛工作台一样同高、填满视口、各自内部滚动。
- 改动（仅前端）：`main_m11.tsx` 删两个按钮及死代码 `reset`（"真实案例快捷入口"下拉保留）；`styles.css` 追加布局块——`.app` 改为 `height:100vh` flex 列 + `overflow:hidden`，`.app>main` `flex:1;min-height:0;overflow:auto`，`.workbench-layout` `align-items:stretch`，左栏与右插件整栏 `overflow:auto`，中间 `.conversation` flex 列 + `.chat` 内部滚动（回复编辑器固定底部）；≤800px 移动端回退为普通文档流。
- 验证：`vite build` 成功；浏览器实测按钮已消失；三栏等高因测试浏览器视口 669px 触发移动端断点无法实测，宽屏（≥1000px）下为用户本地可验证的标准满高 grid 模式。

## 2026-10-14 M22 Conversational Response Generation（LLM 人性化对话）

- 问题：chat 链路此前无论 mock/live 都是规则模板拼回复，"你好"只得僵硬兜底话术，做不到自由问答、人性化、上下文记忆对答。
- 新增 `app/response_generator.py`：qwen live 模式下由 LLM 生成回复——系统提示固化知妍人设/能力边界/事实纪律（业务事实只能来自工具证据、知识只来自 RAG、≤120 字口语化）；消息组装 = 系统提示 + 服务上下文摘要 + 本轮业务核查结果 + 最近 6 轮对话历史 + 用户问题；mock/异常/空内容一律返回 None 回退规则模板。
- `agent_brain.py`：`process_message` 新增 `llm_provider` 参数；能力咨询/闲聊分支 live 时 LLM 自由回应（grounding 复核，含编造事实则回退兜底）；业务/知识分支优先采用 LLM 基于证据的人性化表述，grounding 不通过则保留规则模板；`SessionMemory` 记录升级为 user/reply 原文（供多轮对答）+ plan steps（供去重）。
- `conversation_state.py` 修复：`follow_up_action` 新增 `_is_chitchat` 整句归一化判定——"你好/谢谢/在吗"等闲聊不再误继承上一轮业务行动（"怎么样了"等追问不受影响）。
- `api.py` chat 端点传入 `agent.provider`。
- 新增 `tests/test_response_generator.py` 13 例：mock 不变、live 问候人性化、编造事实拦截、异常静默回退、历史进消息、NOT_FOUND 标注、记忆写回、闲聊/追问边界回归；测试用独立临时状态机库隔离。
- 验证：全量 169/169 PASS；qwen live 冒烟（真实 Qwen）——"你好"自然问候、"你能做什么"自然介绍、"物流到哪了"带真实顺丰单号（grounded）、"怎么样了"正确继承追问、"修护精华液怎么使用"RAG 作答、"我刚才问你什么了"正确回忆上文；S00474 无物流记录时诚实拒答并引导提供订单号。
- 运行方式：启动脚本不再注入 `AGENT_PROVIDER=mock` 即走 qwen live（.env 已配 AGENT_PROVIDER=qwen）；当前服务以 live 模式运行，每次对话产生真实 token 消耗（free_only 限额 1024 tokens/轮）。
