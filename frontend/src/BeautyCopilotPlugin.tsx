import React, { useEffect, useRef, useState } from 'react'
import { PluginActions, PluginContext, emotionLabel, intentLabel, riskLevelLabel } from './pluginRuntime'
import { MascotIcon } from './components/brand/Brand'

export type PluginRisk = { level: string; findings: Array<{ risk_id?: string | null; reason: string; recommended_action: string; evidence?: Record<string, unknown> }>; requires_human_review: boolean }
export type PluginResult = { suggestion: string; risk: PluginRisk; provider: string; latency_ms: number; risk_id?: string | null; risk_ids?: string[]; model_output?: { intent?: string; intent_major?: string; intent_minor?: string; emotion?: string; summary?: string }; workflow?: { customer_need?: string } }
export type QuickAction = { action_id: string; label: string; reason: string; priority: 'primary'|'secondary'; tool_name: string; available: boolean; source?: string }
type ChatKind = 'chat' | 'summary' | 'actions' | 'suggestion' | 'action-result' | 'error'
type ChatLine = { id: string; role: '客服'|'知妍'; text: string; source?: string; kind: ChatKind; actionId?: string; prompt?: string }
type Props = { context: PluginContext | null; result: PluginResult | null; loading: boolean; actions: PluginActions; onStartAnalysis?: () => void }
const api = import.meta.env.VITE_API_URL || 'http://localhost:9000'

const uid = () => typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : `m_${Date.now()}_${Math.random().toString(16).slice(2)}`
const copyText = (text: string) => { try { navigator.clipboard?.writeText(text) } catch { /* 剪贴板不可用时静默 */ } }

const IconCopy = <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
const IconCheck = <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
const IconEdit = <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>
const IconRetry = <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>
const IconLike = <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/></svg>
const IconDislike = <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zM17 2h3a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-3"/></svg>
const IconSend = <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/></svg>

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
  const [feedback, setFeedback] = useState<Record<string, 'like'|'dislike'|undefined>>({})
  const [copiedId, setCopiedId] = useState('')
  const requestIdRef = useRef('')
  const emittedSummaryRef = useRef('')
  const sendingRef = useRef(false)
  const chatInputRef = useRef<HTMLInputElement>(null)
  const [listening, setListening] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const recognitionRef = useRef<any>(null)
  const toggleVoice = () => {
    const SR = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
    if (!SR) { setChat(lines => [...lines, { id: uid(), role: '知妍', kind: 'error', text: '当前浏览器不支持语音输入，请使用 Chrome 或 Edge。' }]); return }
    if (listening) { recognitionRef.current?.stop(); return }
    const rec = new SR()
    rec.lang = 'zh-CN'; rec.interimResults = true; rec.continuous = false
    rec.onresult = (e: any) => { const t = Array.from(e.results as any[]).map((r: any) => r[0].transcript).join(''); setInput(t) }
    rec.onend = () => setListening(false)
    rec.onerror = () => setListening(false)
    recognitionRef.current = rec; rec.start(); setListening(true)
  }
  useEffect(() => {
    setChat([]); setInput(''); setQuickActions([]); setFeedback({}); sendingRef.current = false
    if (!context) return
    fetch(`${api}/api/workbench/${encodeURIComponent(context.sessionId)}/actions`).then(r => r.ok ? r.json() : Promise.reject(r)).then(data => setQuickActions(data.items || [])).catch(() => setQuickActions([]))
  }, [context?.sessionId])
  useEffect(() => {
    const summary = result?.model_output?.summary || ''
    if (!summary || summary === '已基于现有业务记录生成建议。') return
    const stamp = `${context?.sessionId || ''}|${summary}`
    if (emittedSummaryRef.current === stamp) return
    emittedSummaryRef.current = stamp
    const lines: ChatLine[] = [{ id: uid(), role: '知妍', kind: 'summary', text: `会话小结：${summary}` }]
    lines.push({ id: uid(), role: '知妍', kind: 'actions', text: '为了更快核实情况，你可以直接执行下面的快捷行动：' })
    if (result?.suggestion) lines.push({ id: uid(), role: '知妍', kind: 'suggestion', text: result.suggestion })
    setChat(lines2 => [...lines2, ...lines])
  }, [result?.model_output?.summary, result?.suggestion, context?.sessionId])
  const retryAnalysis = () => {
    if (!onStartAnalysis || loading) return
    emittedSummaryRef.current = ''
    setChat(lines => lines.filter(line => line.kind !== 'summary' && line.kind !== 'actions' && line.kind !== 'suggestion'))
    onStartAnalysis()
  }
  const retry = (line: ChatLine) => {
    if (line.kind === 'chat' && line.prompt) { askText(line.prompt); return }
    if (line.kind === 'action-result' && line.actionId) { const item = quickActions.find(a => a.action_id === line.actionId); if (item) { setChat(lines => lines.filter(l => l.id !== line.id)); runActionCore(item) } return }
    retryAnalysis()
  }
  const runActionCore = async (item: QuickAction) => {
    if (!context || actionLoading) return
    setActionLoading(item.action_id); setChat(lines => [...lines, { id: uid(), role: '客服', kind: 'chat', text: item.label }])
    try { const response = await actions.executeQuickAction(item.action_id, context.sessionId); setChat(lines => [...lines, { id: uid(), role: '知妍', kind: 'action-result', actionId: item.action_id, text: response.message, source: response.source }]) }
    catch { setChat(lines => [...lines, { id: uid(), role: '知妍', kind: 'error', text: '当前业务查询暂不可用，我会帮您进一步核实。' }]) }
    finally { setActionLoading('') }
  }
  const askText = async (text: string) => {
    if (!text || !context || chatLoading || sendingRef.current) return
    sendingRef.current = true
    setInput(''); setChat(lines => [...lines, { id: uid(), role: '客服', kind: 'chat', text }]); setChatLoading(true)
    requestIdRef.current = uid()
    try { const response = await actions.askAgent(text, context.sessionId, requestIdRef.current); setChat(lines => [...lines, { id: uid(), role: '知妍', kind: 'chat', prompt: text, text: response.message, source: response.source }]) }
    catch { setChat(lines => [...lines, { id: uid(), role: '知妍', kind: 'error', text: '当前业务查询暂不可用，我会帮您进一步核实。' }]) }
    finally { sendingRef.current = false; setChatLoading(false) }
  }
  const ask = () => askText(input.trim())
  const output = result?.model_output || {}
  return <section className="panel plugin">
    <div className="panel-title plugin-identity"><div className="plugin-brand-lockup"><MascotIcon size={40}/><div><span className="eyebrow">ZHIYAN COPILOT</span><h2>知妍·伴答</h2><p className="subhead">智能接待辅助插件</p></div></div></div>
    {!context ? <div className="plugin-empty"><strong>知妍已准备好</strong><span>请选择一个客户会话，我将帮助你分析需求。</span><ul><li>理解客户需求</li><li>查询订单与服务记录</li><li>判断风险并生成回复建议</li></ul><button onClick={onStartAnalysis} disabled={!onStartAnalysis}>开始分析</button></div> : <>
      <h3>客户洞察</h3><div className="insight-grid"><div><label>当前诉求</label><strong>{output.intent ? intentLabel(output.intent) : '待确认'}</strong></div><div><label>情绪</label><strong>{output.emotion ? emotionLabel(output.emotion) : (result?.risk.requires_human_review ? '需关注' : '待分析')}</strong></div><div><label>风险</label><strong>{result?.risk?.level ? riskLevelLabel(result.risk.level) : '待分析'}</strong></div></div>
      <h3>订单商品</h3><div className="plugin-order-product">{context.currentOrder || context.currentProduct ? <><strong>{String(context.currentProduct?.product_name || context.currentProduct?.product || context.currentOrder?.product_name || '关联商品')}</strong><span>{String(context.currentOrder?.order_number || context.currentOrder?.order_id || '订单信息已关联')} · {String(context.currentOrder?.status || context.currentOrder?.order_status || '状态待核对')}</span></> : <span className="detail-copy">暂无关联订单商品，插件将按需核查。</span>}</div>
      {result?.risk?.findings?.length ? <div className="risk-compact">{result.risk.findings.slice(0, 2).map((finding, i) => <div className="finding risk-card" key={finding.risk_id || i}><div><strong>{finding.reason}</strong><span>{evidenceSummary(finding.evidence)}</span></div></div>)}{(() => { const target = result.risk_id || result.risk.findings.find(f => f.risk_id)?.risk_id; return target ? <button className="secondary risk-card-action" onClick={() => actions.openRiskDetail(target)}>查看风险详情</button> : null })()}</div> : null}
      <h3>知妍 Agent</h3><div className="agent-chat" aria-label="知妍 Agent 对话框"><div className="agent-chat-messages">{chat.length ? chat.map(line => {
        const fb = feedback[line.id]
        const isOperator = line.role === '客服'
        return <div className={`agent-chat-line ${isOperator ? 'operator' : 'copilot'}`} key={line.id}>
          {isOperator ? null : <span className="bubble-role">{line.role}{line.kind === 'suggestion' ? ' · AI生成' : ''}</span>}
          <div className="agent-chat-bubble"><span>{line.text}</span></div>
          {!isOperator && line.kind === 'actions' && <div className="chat-inline-actions">{quickActions.map(item => <button key={item.action_id} className={item.priority === 'primary' ? 'quick-action primary' : 'quick-action'} disabled={!!actionLoading || !item.available} onClick={() => runActionCore(item)}>{actionLoading === item.action_id ? '查询中…' : item.label}</button>)}{!quickActions.length && <span className="detail-copy">暂无可执行的业务行动。</span>}</div>}
          {!isOperator && line.kind === 'suggestion' && <button className="chat-insert-btn" onClick={() => actions.insertSuggestedReply(line.text)}>{IconSend}复制到回复框</button>}
          <div className="msg-actions">
            <button type="button" className="msg-action-btn" title="复制" onClick={() => { copyText(line.text); setCopiedId(line.id); setTimeout(() => setCopiedId(cur => cur === line.id ? '' : cur), 800) }}>{copiedId === line.id ? IconCheck : IconCopy}</button>
            {isOperator ? <button type="button" className="msg-action-btn" title="编辑" onClick={() => { setInput(line.text); chatInputRef.current?.focus() }}>{IconEdit}</button> : <>
              {line.kind !== 'error' && <button type="button" className="msg-action-btn" title="重试" onClick={() => retry(line)}>{IconRetry}</button>}
              <button type="button" className={`msg-action-btn ${fb === 'like' ? 'active-like' : ''}`} title="喜欢" onClick={() => setFeedback(s => ({ ...s, [line.id]: s[line.id] === 'like' ? undefined : 'like' }))}>{IconLike}</button>
              <button type="button" className={`msg-action-btn ${fb === 'dislike' ? 'active-dislike' : ''}`} title="不喜欢" onClick={() => setFeedback(s => ({ ...s, [line.id]: s[line.id] === 'dislike' ? undefined : 'dislike' }))}>{IconDislike}</button>
            </>}
          </div>
        </div>
      }) : <div className="detail-copy">可以向知妍询问物流、退款、历史沟通或售后工单。</div>}{loading && <div className="chat-loading">知妍正在分析当前会话<span className="send-dots">…</span></div>}</div><div className="agent-chat-input trae-input"><button type="button" className="trae-icon-btn" title="上传附件" aria-label="上传附件" onClick={() => fileInputRef.current?.click()}><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg></button><input ref={fileInputRef} type="file" style={{display:'none'}} aria-hidden="true" tabIndex={-1}/><input ref={chatInputRef} value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') ask() }} placeholder="向知妍发送消息"/><button type="button" className={`trae-icon-btn ${listening ? 'listening' : ''}`} onClick={toggleVoice} title="语音输入" aria-label="语音输入"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg></button><button type="button" className="trae-send-btn" onClick={ask} disabled={!input.trim() || chatLoading} title="发送" aria-label="发送">{chatLoading ? <span className="send-dots">…</span> : <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="19" x2="12" y2="5"/><polyline points="5 12 12 5 19 12"/></svg>}</button></div></div>
    </>}
  </section>
}
