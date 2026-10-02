import React, { useEffect, useState } from 'react'
import { riskCategoryLabel, riskLevelLabel, riskStatusLabel } from './pluginRuntime'
import { BrandIcon } from './components/brand/Brand'

const api = import.meta.env.VITE_API_URL || 'http://localhost:8000'
type Risk = { id: string; level: string; category: string; reason: string; recommended_action: string; evidence?: Record<string, unknown>; status?: string; note?: string; buyer_nickname?: string; session_id?: string }
type RiskDetail = Risk & { customer?: Record<string, unknown>; session?: Record<string, unknown>; orders?: Array<Record<string, unknown>>; work_orders?: Array<Record<string, unknown>>; risk_reasons?: string[]; service_timeline?: Array<Record<string, string>> }

async function getJson<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${api}${path}`, options)
  if (!response.ok) throw new Error(`API ${response.status}`)
  return response.json() as Promise<T>
}

type DetailProps = { selected: RiskDetail; status: string; note: string; saving: boolean; setStatus: (value: string) => void; setNote: (value: string) => void; save: () => void }

function RiskDetailInline({ selected, status, note, saving, setStatus, setNote, save }: DetailProps) {
  return <aside className="panel risk-detail inline-risk-detail">
    <div className="panel-title"><div className="risk-detail-brand"><BrandIcon size={32}/><div><span className="eyebrow">知妍风险分析</span><h2>风险详情</h2></div></div><span className={`badge ${selected.level}`}>{riskLevelLabel(selected.level)}</span></div>
    <p className="detail-copy">客户：{selected.buyer_nickname || '客户信息缺失'}<br />会话：{selected.session_id || '未关联'}<br />类别：{riskCategoryLabel(selected.category)}</p>
    <h3>风险原因</h3><ul>{(selected.risk_reasons || [selected.reason]).map((reason, index) => <li key={index}>{reason}</li>)}</ul>
    <h3>关键依据</h3><pre>{JSON.stringify(selected.evidence || {}, null, 2)}</pre>
    <h3>订单 / 工单上下文</h3><div className="facts"><span>订单 {selected.orders?.length || 0} 条</span><span>工单 {selected.work_orders?.length || 0} 条</span></div>
    <div className="detail-context">{(selected.orders || []).slice(0, 3).map((order, index) => <div key={`order-${index}`}><b>订单 {String(order.order_number || order.id || '未知')}</b><span>{String(order.status || order.order_status || '状态未知')} · {String(order.product_name || order.product || '商品信息未返回')}</span></div>)}{(selected.work_orders || []).slice(0, 3).map((ticket, index) => <div key={`ticket-${index}`}><b>工单 {String(ticket.work_order_number || ticket.ticket_number || ticket.id || '未知')}</b><span>{String(ticket.type || ticket.reason || ticket.status || '工单信息已关联')}</span></div>)}</div>
    <h3>服务轨迹</h3><div className="timeline detail-timeline">{(selected.service_timeline || []).slice(-8).map((message, index) => <div key={index}><b>{message.sent_at || `步骤 ${index + 1}`} · {message.role || '记录'}</b><span>{message.message_text || message.chat_content || ''}</span></div>)}{!selected.service_timeline?.length && <span className="detail-copy">暂无服务轨迹。</span>}</div>
    <h3>处理建议</h3><p className="detail-copy">{selected.recommended_action}</p>
    <h3>当前状态</h3><select value={status} onChange={event => setStatus(event.target.value)}><option value="pending">待处理</option><option value="processing">处理中</option><option value="resolved">已解决</option></select>
    <textarea value={note} onChange={event => setNote(event.target.value)} placeholder="记录处理备注" /><button onClick={save} disabled={saving}>{saving ? '保存中…' : '保存状态'}</button>
    {selected.session_id && <a className="secondary" href={`/workbench?session_id=${encodeURIComponent(selected.session_id)}`}>查看原始会话</a>}
  </aside>
}

export function RiskDashboard() {
  const [risks, setRisks] = useState<Risk[]>([])
  const [filter, setFilter] = useState('all')
  const [selected, setSelected] = useState<RiskDetail | null>(null)
  const [status, setStatus] = useState('pending')
  const [note, setNote] = useState('')
  const [error, setError] = useState('')
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [saving, setSaving] = useState(false)

  const load = () => getJson<{ items?: Risk[] }>('/api/risks').then(data => setRisks(data.items || [])).catch(() => { setRisks([]); setError('后端暂不可用，未展示风险事件。') })
  useEffect(() => { load() }, [])
  const choose = async (risk: Risk) => { setLoadingDetail(true); setError(''); try { const detail = await getJson<RiskDetail>(`/api/risks/${encodeURIComponent(risk.id)}`); setSelected(detail); setStatus(detail.status || 'pending'); setNote(detail.note || '') } catch { setError('风险详情加载失败，请重试。') } finally { setLoadingDetail(false) } }
  const save = async () => { if (!selected) return; setSaving(true); setError(''); try { const updated = await getJson<RiskDetail>(`/api/risks/${encodeURIComponent(selected.id)}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status, note }) }); setSelected(updated); setRisks(items => items.map(item => item.id === updated.id ? { ...item, ...updated } : item)); await load() } catch { setError('状态更新失败，请重试。') } finally { setSaving(false) } }
  const shown = filter === 'all' ? risks : risks.filter(risk => risk.level === filter)
  const counts = { critical: risks.filter(r => r.level === 'critical').length, high: risks.filter(r => r.level === 'high').length, open: risks.filter(r => ['pending', 'open'].includes(r.status || 'pending')).length }

  return <main className="dashboard"><section className="panel">
    <div className="panel-title"><div><span className="eyebrow">知妍·洞察</span><h2>风险预警与跟踪中心</h2><p className="subhead">客户服务风险预警与跟踪</p></div><span className="status-dot">真实风险事件</span></div>
    {error && <p className="notice">{error}</p>}
    <div className="risk-metrics"><div><strong>{risks.length}</strong><span>全部事件</span></div><div><strong>{counts.critical}</strong><span>紧急</span></div><div><strong>{counts.high}</strong><span>高危</span></div><div><strong>{counts.open}</strong><span>待跟进</span></div></div>
    <div className="filters">{['all', 'critical', 'high', 'medium', 'low'].map(level => <button className={filter === level ? 'selected' : ''} onClick={() => setFilter(level)} key={level}>{level === 'all' ? '全部' : riskLevelLabel(level)}</button>)}</div>
    <div className="risk-list">{shown.map(risk => <React.Fragment key={risk.id}><article className={`risk-row ${selected?.id === risk.id ? 'selected-row' : ''}`} onClick={() => choose(risk)}><span className={`badge ${risk.level}`}>{riskLevelLabel(risk.level)}</span><div><strong>{risk.reason}</strong><p>{risk.buyer_nickname || '客户信息缺失'} · {riskStatusLabel(risk.status || 'pending')} · {risk.recommended_action}</p></div><button className="secondary" onClick={event => { event.stopPropagation(); choose(risk) }}>查看详情</button></article>{selected?.id === risk.id && (loadingDetail ? <div className="inline-detail-loading">正在加载风险详情…</div> : <RiskDetailInline selected={selected} status={status} note={note} saving={saving} setStatus={setStatus} setNote={setNote} save={save} />)}</React.Fragment>)}</div>
    {!shown.length && <div className="empty">当前没有可展示的真实风险事件。</div>}
  </section></main>
}
