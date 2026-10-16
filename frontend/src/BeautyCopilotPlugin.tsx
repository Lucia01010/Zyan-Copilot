import React, { useEffect, useRef, useState } from 'react'
import { PluginActions, PluginContext, riskLevelLabel } from './pluginRuntime'
import { MascotIcon } from './components/brand/Brand'

export type PluginRisk = { level: string; findings: Array<{ risk_id?: string | null; reason: string; recommended_action: string; evidence?: Record<string, unknown> }>; requires_human_review: boolean }
export type PluginResult = { suggestion: string; risk: PluginRisk; provider: string; latency_ms: number; risk_id?: string | null; risk_ids?: string[]; model_output?: { intent?: string; intent_major?: string; intent_minor?: string; emotion?: string; summary?: string }; workflow?: { customer_need?: string } }
export type QuickAction = { action_id: string; label: string; reason: string; priority: 'primary'|'secondary'; tool_name: string; available: boolean; source?: string }
type ChatLine = { role: '客服'|'知妍'; text: string; source?: string }
type Props = { context: PluginContext | null; result: PluginResult | null; loading: boolean; actions: PluginActions; onStartAnalysis?: () => void }
const api = import.meta.env.VITE_API_URL || 'http://localhost:9000'

function evidenceSummary(evidence: Record<string, unknown> | undefined): string {
  if (!evidence || !Object.keys(evidence).length) return '已关联业务记录，详情待人工核对。'
  const labels: Record<string, string> = { work_order_numbers: '工单', matched_terms: '命中信号', message_count: '消息数', order_count: '订单数' }
  const termLabels: Record<string, string> = { '12315': '12315（消费者投诉热线）' }
  return Object.entries(evidence).map(([key, value]) => `${labels[key] || key}：${Array.isArray(value) ? value.map(v => termLabels[v] || v).join('、') : String(value)}`).join('；')
}

export function BeautyCopilotPlugin({ context, result, loading, actions, onStartAnalysis }: Props) {
  const [quickActions, setQuickActions] = useState<QuickAction[]>([])
  const [chat, setChat] = useState<ChatLine[]>([])
  const [input, setInput] = useState('')
  const [actionLoading, setActionLoading] = useState('')
  const [chatLoading, setChatLoading] = useState(false)
  const [actionReply, setActionReply] = useState('')
  const requestIdRef = useRef('')
  const sendingRef = useRef(false)
  const [listening, setListening] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const recognitionRef = useRef<any>(null)
  const toggleVoice = () => {
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    if (!SR) { setChat(lines => [...lines, { role: '知妍', text: '当前浏览器不支持语音输入，请使用 Chrome 或 Edge。' }]); return }
    if (listening) { recognitionRef.current?.stop(); return }
    const rec = new SR()
    rec.lang = 'zh-CN'; rec.interimResults = true; rec.continuous = false
    rec.onresult = (e: any) => { const t = Array.from(e.results as any[]).map((r: any) => r[0].transcript).join(''); setInput(t) }
    rec.onend = () => setListening(false)
    rec.onerror = () => setListening(false)
    recognitionRef.current = rec; rec.start(); setListening(true)
  }
  useEffect(() => {
    setChat([]); setInput(''); setQuickActions([]); setActionReply(''); sendingRef.current = false
    if (!context) return
    fetch(`${api}/api/workbench/${encodeURIComponent(context.sessionId)}/actions`).then(r => r.ok ? r.json() : Promise.reject(r)).then(data => setQuickActions(data.items || [])).catch(() => setQuickActions([]))
  }, [context?.sessionId])
  const runAction = async (item: QuickAction) => {
    if (!context || actionLoading) return
    setActionLoading(item.action_id); setChat(lines => [...lines, { role: '客服', text: item.label }])
    try { const response = await actions.executeQuickAction(item.action_id, context.sessionId); setActionReply(response.message); setChat(lines => [...lines, { role: '知妍', text: response.message, source: response.source }]) }
    catch { setChat(lines => [...lines, { role: '知妍', text: '当前业务查询暂不可用，我会帮您进一步核实。' }]) }
    finally { setActionLoading('') }
  }
  const ask = async () => {
    const text = input.trim(); if (!text || !context || chatLoading || sendingRef.current) return
    sendingRef.current = true
    setInput(''); setChat(lines => [...lines, { role: '客服', text }]); setChatLoading(true)
    requestIdRef.current = typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : `chat_${Date.now()}_${Math.random().toString(16).slice(2)}`
    try { const response = await actions.askAgent(text, context.sessionId, requestIdRef.current); setChat(lines => [...lines, { role: '知妍', text: response.message, source: response.source }]) }
    catch { setChat(lines => [...lines, { role: '知妍', text: '当前业务查询暂不可用，我会帮您进一步核实。' }]) }
    finally { sendingRef.current = false; setChatLoading(false) }
  }
  const output = result?.model_output || {}
  return <section className="panel plugin">
    <div className="panel-title plugin-identity"><div className="plugin-brand-lockup"><MascotIcon size={40}/><div><span className="eyebrow">ZHIYAN COPILOT</span><h2>知妍·伴答</h2><p className="subhead">智能接待辅助插件</p></div></div></div>
    {!context ? <div className="plugin-empty"><strong>知妍已准备好</strong><span>请选择一个客户会话，我将帮助你分析需求。</span><ul><li>理解客户需求</li><li>查询订单与服务记录</li><li>判断风险并生成回复建议</li></ul><button onClick={onStartAnalysis} disabled={!onStartAnalysis}>开始分析</button></div> : <>
      <h3>客户洞察</h3><div className="insight-grid"><div><label>当前诉求</label><strong>{output.intent || '待确认'}</strong></div><div><label>情绪</label><strong>{output.emotion || (result?.risk.requires_human_review ? '需关注' : '待分析')}</strong></div><div><label>风险</label><strong>{result?.risk?.level ? riskLevelLabel(result.risk.level) : '待分析'}</strong></div></div>{output.summary && output.summary !== '已基于现有业务记录生成建议。' && <p className="detail-copy">{output.summary}</p>}
      <h3>订单商品</h3><div className="plugin-order-product">{context.currentOrder || context.currentProduct ? <><strong>{String(context.currentProduct?.product_name || context.currentProduct?.product || context.currentOrder?.product_name || '关联商品')}</strong><span>{String(context.currentOrder?.order_number || context.currentOrder?.order_id || '订单信息已关联')} · {String(context.currentOrder?.status || context.currentOrder?.order_status || '状态待核对')}</span></> : <span className="detail-copy">暂无关联订单商品，插件将按需核查。</span>}</div>
      {result?.risk?.findings?.length ? <div className="risk-compact">{result.risk.findings.slice(0, 2).map((finding, i) => <div className="finding risk-card" key={finding.risk_id || i}><div><strong>{finding.reason}</strong><span>{evidenceSummary(finding.evidence)}</span></div></div>)}{(() => { const target = result.risk_id || result.risk.findings.find(f => f.risk_id)?.risk_id; return target ? <button className="secondary risk-card-action" onClick={() => actions.openRiskDetail(target)}>查看风险详情</button> : null })()}</div> : null}
      <h3>知妍 Agent</h3><div className="agent-chat" aria-label="知妍 Agent 对话框"><div className="agent-chat-messages">{chat.length ? chat.map((line, i) => <div className={`agent-chat-line ${line.role === '客服' ? 'operator' : 'copilot'}`} key={i}>{line.role === '客服' ? null : <span className="bubble-role">{line.role}</span>}<div className="agent-chat-bubble"><span>{line.text}</span></div></div>) : <div className="detail-copy">可以向知妍询问物流、退款、历史沟通或售后工单。</div>}</div><div className="agent-chat-input trae-input"><button type="button" className="trae-icon-btn" title="上传附件" aria-label="上传附件" onClick={() => fileInputRef.current?.click()}><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg></button><input ref={fileInputRef} type="file" style={{display:'none'}} aria-hidden="true" tabIndex={-1}/><input value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') ask() }} placeholder="向知妍发送消息"/><button type="button" className={`trae-icon-btn ${listening ? 'listening' : ''}`} onClick={toggleVoice} title="语音输入" aria-label="语音输入"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg></button><button type="button" className="trae-send-btn" onClick={ask} disabled={!input.trim() || chatLoading} title="发送" aria-label="发送">{chatLoading ? <span className="send-dots">…</span> : <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/></svg>}</button></div></div>
      <h3>建议行动</h3><div className="quick-actions">{quickActions.map(item => <button key={item.action_id} className={item.priority === 'primary' ? 'quick-action primary' : 'quick-action'} disabled={!!actionLoading || !item.available} onClick={() => runAction(item)}>{actionLoading === item.action_id ? '查询中…' : item.label}</button>)}{!quickActions.length && <span className="detail-copy">暂无可执行的业务行动。</span>}</div>
      <h3>建议回复 <span className="ai-generated-badge">AI生成</span></h3><div className="suggestion">{loading ? '知妍正在分析当前会话…' : actionReply || result?.suggestion || '完成一项建议行动后，知妍会用查询结果更新回复建议。'}</div>{(actionReply || result?.suggestion) && <button className="secondary copy-btn" onClick={() => actions.insertSuggestedReply(actionReply || result!.suggestion)}>复制到回复框</button>}
    </>}
  </section>
}
