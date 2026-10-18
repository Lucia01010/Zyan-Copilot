export type HostEventName = 'SESSION_CHANGED' | 'MESSAGE_RECEIVED' | 'AGENT_ANALYSIS_STARTED' | 'AGENT_ANALYSIS_COMPLETED' | 'RISK_EVENT_CREATED'
export type PluginMessage = Record<string, string>
export type PluginContext = { sessionId: string; customer: string; currentMessages: PluginMessage[]; currentOrder?: Record<string, string>; currentProduct?: Record<string, string> }
export type PluginActions = {
  insertSuggestedReply(text: string): void
  requestHumanTakeover(): void
  openRiskDetail(riskId?: string): void
  executeQuickAction(actionId: string, sessionId: string): Promise<{ message: string; source?: string }>
  askAgent(message: string, sessionId: string, requestId?: string): Promise<{ message: string; source?: string }>
}
export type QianniuHostAdapter = { getPluginContext(): PluginContext | null; emit(event: HostEventName): void; onEvent(listener: (event: HostEventName) => void): () => void }
export class SimulatedQianniuAdapter implements QianniuHostAdapter {
  private context: PluginContext | null = null
  private listeners = new Set<(event: HostEventName) => void>()
  setContext(context: PluginContext | null) { this.context = context }
  getPluginContext() { return this.context }
  emit(event: HostEventName) { this.listeners.forEach(listener => listener(event)) }
  onEvent(listener: (event: HostEventName) => void) { this.listeners.add(listener); return () => this.listeners.delete(listener) }
}
// Future production integration implements this contract; no real Qianniu API is called here.
export type RealQianniuAdapter = QianniuHostAdapter

// 界面统一中文标签映射（原始枚举值仍用于数据与接口）
export const HOST_EVENT_LABELS: Record<HostEventName, string> = {
  SESSION_CHANGED: '会话已切换',
  MESSAGE_RECEIVED: '收到新消息',
  AGENT_ANALYSIS_STARTED: 'AI 分析开始',
  AGENT_ANALYSIS_COMPLETED: 'AI 分析完成',
  RISK_EVENT_CREATED: '已生成风险事件',
}
export const RISK_LEVEL_LABELS: Record<string, string> = {
  critical: '紧急',
  high: '高危',
  medium: '中风险',
  low: '低风险',
}
export const RISK_STATUS_LABELS: Record<string, string> = {
  pending: '待跟进',
  open: '待跟进',
  processing: '处理中',
  resolved: '已解决',
  ignored: '已忽略',
}
export const RISK_CATEGORY_LABELS: Record<string, string> = {
  safety: '安全',
  complaint: '投诉升级',
  after_sales: '售后异常',
  sentiment: '情绪',
  service: '服务',
  context: '订单关联',
  other: '其他',
}
export const riskLevelLabel = (level: string) => RISK_LEVEL_LABELS[level] || level
export const riskStatusLabel = (status: string) => RISK_STATUS_LABELS[status] || status
export const riskCategoryLabel = (category: string) => RISK_CATEGORY_LABELS[(category || '').toLowerCase()] || category

export const EMOTION_LABELS: Record<string, string> = {
  angry: '生气',
  upset: '生气',
  frustrated: '不满',
  anxious: '焦虑',
  nervous: '焦虑',
  worried: '担忧',
  urgent: '急切',
  impatient: '不耐烦',
  disappointed: '失望',
  confused: '困惑',
  calm: '平稳',
  neutral: '平稳',
  satisfied: '满意',
  positive: '积极',
  negative: '负面',
}
export const emotionLabel = (value: string) => EMOTION_LABELS[value.trim().toLowerCase()] || value

export const INTENT_LABELS: Record<string, string> = {
  refund: '退款售后',
  logistics: '物流查询',
  shipping: '物流查询',
  delivery: '物流查询',
  complaint: '投诉',
  inquiry: '产品咨询',
  consultation: '产品咨询',
  after_sales: '售后咨询',
  aftersales: '售后咨询',
  after_sale: '售后咨询',
  order: '订单查询',
  usage: '产品使用',
  praise: '表扬',
  other: '其他咨询',
}
export const intentLabel = (value: string) => INTENT_LABELS[value.trim().toLowerCase()] || value
