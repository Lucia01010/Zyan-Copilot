import React from 'react'
import { PluginActions, PluginContext, riskLevelLabel } from './pluginRuntime'
import { AgentStatusMascot, MascotIcon, ZhiyanMascot } from './components/brand/Brand'

export type PluginRisk = { level: string; findings: Array<{ reason: string; recommended_action: string; evidence?: Record<string, unknown> }>; requires_human_review: boolean }
export type PluginWorkflow = { customer_need?: string; latest_message?: string; tool_checks?: Array<{ tool: string; label: string; reason: string; status: string }>; evidence_summary?: string[]; risk_summary?: { level: string; reasons?: string[] }; reply_basis?: string }
export type PluginResult = { suggestion: string; risk: PluginRisk; provider: string; latency_ms: number; model_output?: { intent?: string; intent_major?: string; intent_minor?: string; emotion?: string; summary?: string }; workflow?: PluginWorkflow }
type Props = { context: PluginContext | null; result: PluginResult | null; loading: boolean; actions: PluginActions; onStartAnalysis?: () => void }

function evidenceSummary(evidence: Record<string, unknown> | undefined): string {
  if (!evidence || !Object.keys(evidence).length) return '已关联业务记录，详情待人工核对。'
  const labels: Record<string, string> = { work_order_numbers: '工单', matched_terms: '命中信号', message_count: '消息数', order_count: '订单数' }
  return Object.entries(evidence).map(([key, value]) => {
    const rendered = Array.isArray(value) ? value.join('、') : String(value)
    return `${labels[key] || key}：${rendered}`
  }).join('；')
}

export function BeautyCopilotPlugin({ context, result, loading, actions, onStartAnalysis }: Props) {
  const messages = context?.currentMessages || []
  const output = result?.model_output || {}
  const workflow = result?.workflow
  const workflowSteps = [
    { label: '理解需求', state: result ? 'completed' : loading ? 'running' : 'waiting' },
    { label: '查询信息', state: loading ? 'running' : result ? 'completed' : 'waiting' },
    { label: '分析风险', state: result ? 'completed' : 'waiting' },
    { label: '生成回复', state: result ? 'completed' : 'waiting' },
  ]
  return <section className="panel plugin">
    <div className="panel-title plugin-identity"><div className="plugin-brand-lockup"><MascotIcon size={40}/><div><span className="eyebrow">ZHIYAN COPILOT</span><h2>知妍·伴答</h2><p className="subhead">智能接待辅助插件</p></div></div>{result && <span className={`badge ${result.risk.level}`}>{riskLevelLabel(result.risk.level)}</span>}</div>
    {!context ? <div className="plugin-empty"><strong>知妍已准备好</strong><span>请选择一个客户会话，我将帮助你分析需求。</span><ul><li>理解客户需求</li><li>查询订单与服务记录</li><li>判断风险并生成回复建议</li></ul><button onClick={onStartAnalysis} disabled={!onStartAnalysis}>开始分析</button></div> : loading ? <><div className="analysis-status"><AgentStatusMascot state="running"/><div><strong>知妍正在分析</strong><span>正在理解当前会话并核查相关业务信息…</span></div></div><h3>信息核查</h3><div className="tool-checks">{['理解当前消费者需求', '查询订单与售后记录', '核对历史服务与风险'].map((label, index) => <div className="tool-check" key={label}><span className="tool-check-icon">{index === 0 ? '◌' : '✓'}</span><span>{label}</span></div>)}</div></> : result ? <>
      <h3>知妍工作流</h3><div className="workflow-card"><div className="workflow-steps">{workflowSteps.map((step, index) => <div className={`workflow-step ${step.state}`} key={step.label}><span className="step-index">{index + 1}</span><strong>{step.label}</strong><small>{step.state === 'completed' ? '已完成' : step.state === 'running' ? '进行中' : '等待'}</small></div>)}</div></div>
      <h3>客户洞察</h3><div className="insight-grid"><div><label>意图</label><strong>{output.intent || '待确认'}</strong></div><div><label>情绪</label><strong>{output.emotion || (result.risk.requires_human_review ? '需人工关注' : '平稳')}</strong></div><div><label>客户状态</label><strong>{result.risk.requires_human_review ? '需要人工跟进' : '当前可继续服务'}</strong></div></div>
      <p className="detail-copy">{workflow?.customer_need || output.summary || '已结合当前会话理解消费者需求。'}</p>
      <h3>信息核查</h3><div className="tool-checks">{(workflow?.tool_checks || []).map(step => <div className="tool-check" key={step.tool}><span className="tool-check-icon">✓</span><div><strong>{step.label}</strong><small>{step.reason}</small></div></div>)}{!workflow?.tool_checks?.length && <div className="detail-copy">未调用额外业务工具，将在回复中明确需要进一步核实的信息。</div>}</div>
      <h3>关键依据</h3><div className="evidence">{result.risk.findings.map((finding, i) => <div className="finding" key={i}><strong>{finding.reason}</strong><span>{evidenceSummary(finding.evidence)}</span></div>)}</div>
      <h3>订单 / 工单洞察</h3><div className="facts"><span>{context.currentOrder ? '当前订单已关联' : '订单信息待核对'}</span><span>{context.currentProduct ? '商品上下文已关联' : '商品信息待核对'}</span></div>
      <h3>服务时间线</h3><div className="timeline">{messages.slice(-4).map((message, i) => <div key={i}><b>{message.sent_at || `步骤 ${i + 1}`}</b><span>{message.message_text || message.chat_content || ''}</span></div>)}</div>
      <h3>风险 / 处理建议</h3><ul>{result.risk.findings.map((finding, i) => <li key={i}>{finding.recommended_action}</li>)}</ul>
      <h3><MascotIcon size={24} className="inline-brand-icon"/>知妍生成建议回复 <span className="ai-generated-badge">AI生成</span></h3><div className="suggestion">{result.suggestion}</div><div className="detail-copy">生成依据：{workflow?.reply_basis || result.risk.findings[0]?.reason || '当前会话与可用业务记录；未找到的事实会继续核实'}</div>
      <button className="secondary" onClick={() => actions.insertSuggestedReply(result.suggestion)}>复制到回复框</button><button className="secondary" onClick={actions.requestHumanTakeover}>人工接管</button><button className="secondary" onClick={() => actions.openRiskDetail()}>打开风险详情</button>
    </> : <div className="empty">知妍·伴答会在这里展示意图、情绪、关键依据、服务轨迹、风险和智能回复建议。</div>}
  </section>
}
