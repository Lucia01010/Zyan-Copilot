import React, { useEffect, useState } from 'react'
import { riskCategoryLabel, riskLevelLabel, riskStatusLabel } from './pluginRuntime'
import { MascotIcon } from './components/brand/Brand'

const api = import.meta.env.VITE_API_URL || 'http://localhost:9000'
type Risk = { id: string; risk_id?: string; level: string; category: string; reason: string; recommended_action: string; evidence?: Record<string, unknown>; status?: string; note?: string; buyer_nickname?: string; session_id?: string; observed_at?: string | null }
type RiskDetail = Risk & { customer?: Record<string, unknown>; session?: Record<string, unknown>; orders?: Array<Record<string, unknown>>; work_orders?: Array<Record<string, unknown>>; risk_reasons?: string[]; service_timeline?: Array<Record<string, string>> }
type RiskFilter = { level?: string; category?: string; status?: string; customer?: string }
const levels = ['critical', 'high', 'medium', 'low']
const levelColors: Record<string, string> = { critical: '#bb3e4b', high: '#d47a35', medium: '#c5a247', low: '#578b76' }
const statusColors: Record<string, string> = { pending: '#d47a35', processing: '#8064aa', resolved: '#578b76', ignored: '#98a2b3' }
const normalizedStatus = (status?: string) => !status || status === 'open' ? 'pending' : status

function countBy(items: Risk[], key: (risk: Risk) => string): Array<[string, number]> {
  const counts = new Map<string, number>()
  items.forEach(risk => { const value = key(risk); counts.set(value, (counts.get(value) || 0) + 1) })
  return [...counts].sort((a, b) => b[1] - a[1])
}

function ChartCard({ title, subtitle, children, wide = false }: { title: string; subtitle?: string; children: React.ReactNode; wide?: boolean }) {
  return <section className={`insight-chart panel ${wide ? 'wide-chart' : ''}`}><div className="chart-heading"><h3>{title}</h3>{subtitle && <p>{subtitle}</p>}</div>{children}</section>
}

function BarChart({ rows, total, label, color, onSelect, selected }: { rows: Array<[string, number]>; total: number; label: (key: string) => string; color: (key: string) => string; onSelect: (key: string) => void; selected?: string }) {
  if (!rows.length) return <div className="chart-empty">暂无足够数据</div>
  return <div className="chart-bars">{rows.map(([key, count]) => <button type="button" key={key} className={`chart-bar-row ${selected === key ? 'active' : ''}`} onClick={() => onSelect(key)} aria-label={`${label(key)} ${count} 条，点击筛选`}><span className="chart-bar-label">{label(key)}</span><span className="chart-bar-track"><span style={{ width: `${Math.max(3, count / Math.max(total, 1) * 100)}%`, background: color(key) }} /></span><strong>{count}</strong></button>)}</div>
}

function TrendChart({ risks }: { risks: Risk[] }) {
  const counts = new Map<string, number>()
  risks.forEach(risk => { const date = risk.observed_at?.slice(0, 10); if (date) counts.set(date, (counts.get(date) || 0) + 1) })
  const dates = [...counts.keys()].sort().slice(-14)
  if (dates.length < 2) return <div className="chart-empty">当前暂无足够时间序列数据</div>
  const values = dates.map(date => counts.get(date) || 0)
  const max = Math.max(...values, 1)
  const width = 720; const height = 150; const padX = 36; const padY = 20
  const points = values.map((value, index) => `${padX + index * ((width - padX * 2) / (values.length - 1))},${height - padY - (value / max) * (height - padY * 2)}`).join(' ')
  const tickValue = (index: number) => Math.round(max * index / 4 * 10) / 10
  const tickLabel = (value: number) => Number.isInteger(value) ? String(value) : value.toFixed(1)
  return <div className="trend-wrap"><svg className="trend-svg" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="风险趋势图">{[0, 1, 2, 3, 4].map(index => { const y = height - padY - (tickValue(index) / max) * (height - padY * 2); return <g key={index}><line x1={padX} y1={y} x2={width - padX} y2={y} stroke="#eee5f2" /><text x={padX - 6} y={y + 3} textAnchor="end" className="trend-axis">{tickLabel(tickValue(index))}</text></g> })}<line x1={padX} y1={padY} x2={padX} y2={height - padY} stroke="#dec5e8" /><polyline points={points} fill="none" stroke="#8064aa" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />{values.map((value, index) => { const x = padX + index * ((width - padX * 2) / (values.length - 1)); const y = height - padY - (value / max) * (height - padY * 2); return <g key={dates[index]}><circle cx={x} cy={y} r="4" fill="#8064aa" /><text x={x} y={height - 3} textAnchor="middle" className="trend-label">{dates[index].slice(5)}</text><title>{dates[index]}：{value} 条风险</title></g> })}</svg></div>
}

async function getJson<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${api}${path}`, options)
  if (!response.ok) throw new Error(`API ${response.status}`)
  return response.json() as Promise<T>
}

type DetailProps = { selected: RiskDetail; status: string; note: string; saving: boolean; setStatus: (value: string) => void; setNote: (value: string) => void; save: () => void }

const EVIDENCE_LABELS: Record<string, string> = {
  work_order_numbers: '工单号',
  order_numbers: '订单号',
  matched_terms: '命中信号',
  message_count: '消息数',
  order_count: '订单数',
  work_order_count: '工单数',
  risk_keywords: '风险信号',
  recent_topics: '近期话题',
  time_range: '时间范围',
  buyer_nickname: '客户昵称',
}
const EVIDENCE_VALUE_LABELS: Record<string, string> = { '12315': '12315（消费者投诉热线）' }
const evidenceLabel = (key: string) => EVIDENCE_LABELS[key] || key
const evidenceValue = (value: unknown) => {
  if (typeof value === 'string') return EVIDENCE_VALUE_LABELS[value] || value
  if (typeof value === 'number') return String(value)
  if (Array.isArray(value)) return value.map(item => EVIDENCE_VALUE_LABELS[item] || item).join('、')
  return JSON.stringify(value)
}

function RiskDetailModal({ selected, status, note, saving, setStatus, setNote, save, onClose }: DetailProps & { onClose: () => void }) {
  return <div className="modal-overlay" onClick={onClose}><div className="modal-content risk-detail-modal" onClick={event => event.stopPropagation()}>
    <div className="risk-detail-header"><div className="risk-detail-brand"><MascotIcon size={32}/><div><span className="eyebrow">知妍·洞察</span><h2>风险详情</h2></div></div><span className={`badge ${selected.level}`}>{riskLevelLabel(selected.level)}</span></div>
    <div className="risk-detail-meta"><div><span>客户</span><strong>{selected.buyer_nickname || '客户信息缺失'}</strong></div><div><span>会话</span><strong>{selected.session_id || '未关联'}</strong></div><div><span>风险类型</span><strong>{riskCategoryLabel(selected.category)}</strong></div></div>
    <div className="risk-detail-section risk-reason-section"><div className="detail-section-heading"><h3>风险原因</h3></div><ul>{(selected.risk_reasons || [selected.reason]).map((reason, index) => <li key={index}>{reason}</li>)}</ul></div>
    <div className="risk-detail-section"><div className="detail-section-heading"><h3>关键依据</h3><span>{Object.keys(selected.evidence || {}).length} 项</span></div><div className="evidence-list">{Object.entries(selected.evidence || {}).map(([key, value]) => <div className="evidence-row" key={key}><b>{evidenceLabel(key)}</b><span>{evidenceValue(value)}</span></div>)}{!Object.keys(selected.evidence || {}).length && <p className="detail-empty">暂无结构化依据。</p>}</div></div>
    <div className="risk-detail-section"><div className="detail-section-heading"><h3>订单 / 工单</h3><span>{(selected.orders?.length || 0) + (selected.work_orders?.length || 0)} 条关联记录</span></div><div className="facts"><span>订单 <b>{selected.orders?.length || 0}</b></span><span>工单 <b>{selected.work_orders?.length || 0}</b></span></div><div className="detail-context">{(selected.orders || []).slice(0, 3).map((order, index) => <div key={`order-${index}`}><b>订单 {String(order.order_number || order.id || '未知')}</b><span>{String(order.status || order.order_status || '状态未知')}，{String(order.product_name || order.product || '商品信息未返回')}</span></div>)}{(selected.work_orders || []).slice(0, 3).map((ticket, index) => <div key={`ticket-${index}`}><b>工单 {String(ticket.work_order_number || ticket.ticket_number || ticket.id || '未知')}</b><span>{String(ticket.type || ticket.reason || ticket.status || '工单信息已关联')}</span></div>)}{!selected.orders?.length && !selected.work_orders?.length && <p className="detail-empty">暂无关联订单或工单。</p>}</div></div>
    <div className="risk-detail-section"><div className="detail-section-heading"><h3>服务轨迹</h3><span>{(selected.service_timeline || []).length} 条记录</span></div><div className="timeline detail-timeline">{(selected.service_timeline || []).map((message, index) => <div key={index}><b>{message.sent_at || `步骤 ${index + 1}`} {message.role || '记录'}</b><span>{message.message_text || message.chat_content || ''}</span></div>)}{!selected.service_timeline?.length && <span className="detail-empty">暂无服务轨迹。</span>}</div></div>
    <div className="risk-detail-action"><div className="detail-section-heading"><h3>处理动作</h3><span>保存后同步风险看板</span></div><p className="detail-copy">{selected.recommended_action || '请结合风险依据确认后续处理方式。'}</p><label>当前状态<select value={status} onChange={event => setStatus(event.target.value)}><option value="pending">待跟进</option><option value="processing">处理中</option><option value="resolved">已解决</option></select></label><label>处理备注<textarea value={note} onChange={event => setNote(event.target.value)} placeholder="记录本次处理结果或待跟进事项" /></label><div className="detail-actions"><button onClick={save} disabled={saving}>{saving ? '保存中…' : '保存状态'}</button>{selected.session_id && <a className="secondary" href={`/workbench?session_id=${encodeURIComponent(selected.session_id)}`}>返回原始会话</a>}</div></div>
    <button className="modal-close" onClick={onClose} aria-label="关闭">×</button>
  </div></div>
}

export function RiskDashboard() {
  const [risks, setRisks] = useState<Risk[]>([])
  const [filter, setFilter] = useState<RiskFilter>({})
  const [selected, setSelected] = useState<RiskDetail | null>(null)
  const [status, setStatus] = useState('pending')
  const [note, setNote] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [saving, setSaving] = useState(false)
  const load = () => getJson<{ items?: Risk[] }>('/api/risks').then(data => { setRisks(data.items || []); setError('') }).catch(() => { setRisks([]); setError('后端暂不可用，未展示风险事件。') }).finally(() => setLoading(false))
  const chooseById = async (riskId: string) => { setLoadingDetail(true); setError(''); try { const detail = await getJson<RiskDetail>(`/api/risks/${encodeURIComponent(riskId)}`); setSelected(detail); setStatus(detail.status || 'pending'); setNote(detail.note || '') } catch { setSelected(null); setError('未找到该风险事件。') } finally { setLoadingDetail(false) } }
  const choose = (risk: Risk) => chooseById(risk.id)
  useEffect(() => {
    load()
    const queryRiskId = new URLSearchParams(window.location.search).get('risk_id')
    if (!queryRiskId) return
    chooseById(queryRiskId)
  }, [])
  const save = async () => { if (!selected) return; setSaving(true); setError(''); try { const updated = await getJson<RiskDetail>(`/api/risks/${encodeURIComponent(selected.id)}`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ status, note }) }); setSelected(updated); setRisks(items => items.map(item => item.id === updated.id ? { ...item, ...updated } : item)); await load() } catch { setError('状态更新失败，请重试。') } finally { setSaving(false) } }
  const shown = risks.filter(risk => (!filter.level || risk.level === filter.level) && (!filter.category || risk.category === filter.category) && (!filter.status || normalizedStatus(risk.status) === filter.status) && (!filter.customer || risk.buyer_nickname === filter.customer)).sort((a, b) => { const ta = a.observed_at || ''; const tb = b.observed_at || ''; if (!ta && !tb) return 0; if (!ta) return 1; if (!tb) return -1; return ta.localeCompare(tb) })
  const levelCounts = levels.map(level => [level, risks.filter(risk => risk.level === level).length] as [string, number]).filter(([, count]) => count > 0)
  const categoryCounts = countBy(risks, risk => risk.category || 'other')
  const statusCounts = countBy(risks, risk => normalizedStatus(risk.status))
  const topCustomers = countBy(risks.filter(risk => ['high', 'critical'].includes(risk.level) && risk.buyer_nickname), risk => risk.buyer_nickname || '').slice(0, 5)
  const pending = risks.filter(risk => normalizedStatus(risk.status) === 'pending').length
  const resolved = risks.filter(risk => normalizedStatus(risk.status) === 'resolved').length
  const toggleFilter = (name: keyof RiskFilter, value: string) => setFilter(current => ({ ...current, [name]: current[name] === value ? undefined : value }))
  const closeModal = () => { setSelected(null); setError('') }
  let offset = 0

  return <main className="dashboard"><section className="panel">
    <div className="panel-title"><div><span className="eyebrow">知妍·洞察</span><h2>客户服务风险预警与跟踪中心</h2></div></div>
    {error && <p className="notice">{error}</p>}
    <div className="risk-metrics"><div><strong>{loading ? '—' : risks.length}</strong><span>风险总数</span></div><div><strong>{loading ? '—' : risks.filter(risk => ['high', 'critical'].includes(risk.level)).length}</strong><span>高风险（含紧急）</span></div><div><strong>{loading ? '—' : pending}</strong><span>待跟进</span></div><div><strong>{loading ? '—' : risks.length ? `${Math.round(resolved / risks.length * 100)}%` : '—'}</strong><span>已解决率 · {resolved} 条</span></div></div>
    <div className="insight-charts">
      <ChartCard title="风险等级分布" subtitle="点击环形区或图例筛选列表">{loading ? <div className="chart-empty">正在加载…</div> : !risks.length ? <div className="chart-empty">暂无足够数据</div> : <div className="donut-layout"><svg className="risk-donut" viewBox="0 0 120 120" role="img" aria-label="风险等级分布图"><circle cx="60" cy="60" r="43" fill="none" stroke="#f0edf3" strokeWidth="18" />{levelCounts.map(([level, count]) => { const length = count / risks.length * 270.18; const start = offset; offset += length; return <circle key={level} cx="60" cy="60" r="43" fill="none" stroke={levelColors[level]} strokeWidth="18" strokeDasharray={`${length} ${270.18 - length}`} strokeDashoffset={-start} transform="rotate(-90 60 60)" className={`donut-segment ${filter.level === level ? 'active' : ''}`} onClick={() => toggleFilter('level', level)} aria-label={`${riskLevelLabel(level)} ${count} 条`} /> })}<text x="60" y="58" textAnchor="middle" className="donut-number">{risks.length}</text><text x="60" y="75" textAnchor="middle" className="donut-caption">风险事件</text></svg><div className="donut-legend">{levelCounts.map(([level, count]) => <button key={level} type="button" className={filter.level === level ? 'active' : ''} onClick={() => toggleFilter('level', level)}><i style={{ background: levelColors[level] }} />{riskLevelLabel(level)} <strong>{count}</strong></button>)}</div></div>}</ChartCard>
      <ChartCard title="主要风险来源">{loading ? <div className="chart-empty">正在加载…</div> : <BarChart rows={categoryCounts} total={risks.length} label={riskCategoryLabel} color={() => '#8064aa'} onSelect={value => toggleFilter('category', value)} selected={filter.category} />}</ChartCard>
      <ChartCard title="风险趋势" subtitle="近 14 个有记录日期" wide>{loading ? <div className="chart-empty">正在加载…</div> : <TrendChart risks={risks} />}</ChartCard>
      <ChartCard title="风险处理进度" subtitle="点击状态筛选待办">{loading ? <div className="chart-empty">正在加载…</div> : <BarChart rows={statusCounts} total={risks.length} label={riskStatusLabel} color={value => statusColors[value] || '#98a2b3'} onSelect={value => toggleFilter('status', value)} selected={filter.status} />}</ChartCard>
      <ChartCard title="重点风险客户 Top 5" subtitle="按高危及紧急风险事件数排序">{loading ? <div className="chart-empty">正在加载…</div> : <BarChart rows={topCustomers} total={topCustomers[0]?.[1] || 0} label={value => value} color={() => '#bb3e4b'} onSelect={value => toggleFilter('customer', value)} selected={filter.customer} />}</ChartCard>
    </div>
    <div className="filters">{[['', '全部'], ['pending', '待跟进'], ['processing', '处理中'], ['resolved', '已解决'], ['ignored', '已忽略']].map(([value, label]) => <button type="button" key={value || 'all'} className={(filter.status || '') === value ? 'selected' : ''} onClick={() => value ? toggleFilter('status', value) : setFilter(current => ({ ...current, status: undefined }))}>{label}</button>)}</div>
    <div className="risk-list-header"><h3>风险事件列表</h3><span className="list-count">共 {risks.length} 条 · 当前显示 {shown.length} 条</span>{Object.values(filter).some(Boolean) && <button type="button" className="secondary" style={{ marginLeft: 'auto' }} onClick={() => setFilter({})}>清除筛选</button>}</div>
    <div className="active-filters">{filter.level && <span>等级：{riskLevelLabel(filter.level)}</span>}{filter.category && <span>类型：{riskCategoryLabel(filter.category)}</span>}{filter.customer && <span>客户：{filter.customer}</span>}</div>
    <div className="risk-list">{shown.map(risk => <article className="risk-row" key={risk.id} onClick={() => choose(risk)}><span className={`badge ${risk.level}`}>{riskLevelLabel(risk.level)}</span><div><strong>{risk.reason}</strong><p>{risk.buyer_nickname || '客户信息缺失'} {riskStatusLabel(risk.status || 'pending')}{risk.observed_at ? ` 最后聊天 ${String(risk.observed_at).replace('T', ' ').slice(0, 19)}` : ''}</p></div><button className="secondary" onClick={event => { event.stopPropagation(); choose(risk) }}>查看详情</button></article>)}</div>
    {!loading && !shown.length && <div className="empty">{risks.length ? '当前筛选条件下没有风险事件。' : '当前没有可展示的真实风险事件。'}</div>}
    {selected && (loadingDetail ? <div className="modal-overlay"><div className="modal-loading">正在加载风险详情…</div></div> : <RiskDetailModal selected={selected} status={status} note={note} saving={saving} setStatus={setStatus} setNote={setNote} save={save} onClose={closeModal} />)}
  </section></main>
}
