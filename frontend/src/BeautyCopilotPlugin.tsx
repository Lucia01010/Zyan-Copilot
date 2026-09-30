import React from 'react'
import { PluginActions, PluginContext, riskLevelLabel } from './pluginRuntime'

export type PluginRisk = { level: string; findings: Array<{ reason: string; recommended_action: string; evidence?: Record<string, unknown> }>; requires_human_review: boolean }
export type PluginResult = { suggestion: string; risk: PluginRisk; provider: string; latency_ms: number }
type Props = { context: PluginContext | null; result: PluginResult | null; loading: boolean; actions: PluginActions }

export function BeautyCopilotPlugin({ context, result, loading, actions }: Props) {
  const messages = context?.currentMessages || []
  return <section className="panel plugin">
    <div className="panel-title"><div><span className="eyebrow">ZYAN COPILOT</span><h2>知妍·伴答</h2><p className="subhead">智能接待辅助插件</p></div>{result && <span className={`badge ${result.risk.level}`}>{riskLevelLabel(result.risk.level)}</span>}</div>
    {!context ? <div className="empty">选择宿主会话后，插件将加载对应上下文。</div> : loading ? <div className="empty compact-empty">插件正在分析当前会话…</div> : result ? <>
      <div className="insight-grid"><div><label>意图</label><strong>售后与敏感肌咨询</strong></div><div><label>情绪</label><strong>{result.risk.requires_human_review ? '需人工关注' : '平稳'}</strong></div></div>
      <h3>客户 / 服务摘要</h3><p className="detail-copy">插件仅接收当前宿主会话上下文，并通过业务工具补充必要证据。</p>
      <h3>关键依据</h3><div className="evidence">{result.risk.findings.map((finding, i) => <div className="finding" key={i}><strong>{finding.reason}</strong><span>{JSON.stringify(finding.evidence || {})}</span></div>)}</div>
      <h3>订单 / 工单洞察</h3><div className="facts"><span>{context.currentOrder ? '当前订单已关联' : '订单信息待核对'}</span><span>{context.currentProduct ? '商品上下文已关联' : '商品信息待核对'}</span></div>
      <h3>服务时间线</h3><div className="timeline">{messages.slice(-4).map((message, i) => <div key={i}><b>{message.sent_at || `步骤 ${i + 1}`}</b><span>{message.message_text || message.chat_content || ''}</span></div>)}</div>
      <h3>风险 / 处理建议</h3><ul>{result.risk.findings.map((finding, i) => <li key={i}>{finding.recommended_action}</li>)}</ul>
      <h3>智能回复建议 <span className="ai-generated-badge">知妍生成</span></h3><div className="suggestion">{result.suggestion}</div><div className="detail-copy">生成依据：{result.risk.findings[0]?.reason || '当前会话与可用业务记录；未找到的事实会继续核实'}</div><div className="meta">服务提供方：{result.provider} · 耗时 {result.latency_ms} 毫秒 · 可复制后在宿主回复框编辑</div>
      <button className="secondary" onClick={() => actions.insertSuggestedReply(result.suggestion)}>复制到回复框</button><button className="secondary" onClick={actions.requestHumanTakeover}>人工接管</button><button className="secondary" onClick={() => actions.openRiskDetail()}>打开风险详情</button>
    </> : <div className="empty">知妍·伴答会在这里展示意图、情绪、关键依据、服务轨迹、风险和智能回复建议。</div>}
  </section>
}
