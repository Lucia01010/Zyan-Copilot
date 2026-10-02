import React from 'react'

type BrandIconProps = { size?: 24 | 32 | 40 | 48; className?: string }

// 带渐变底板的方形 Logo（应用头部、风险详情头部使用）
export function BrandIcon({ size = 32, className = '' }: BrandIconProps) {
  return <img className={`brand-icon ${className}`} src="/Logo.png" alt="知妍 AI" width={size} height={size} />
}

// 去底板白团子：透明背景，仅保留团子主体（右侧插件面板使用）
export function MascotIcon({ size = 32, className = '' }: { size?: number; className?: string }) {
  return <img className={`mascot-icon ${className}`} src="/LogoMascot.png" alt="知妍白团子" width={size} height={size} />
}

export function ZhiyanMascot({ size = 96 }: { size?: 72 | 96 | 120 }) {
  return <img className="zhiyan-mascot" src="/LogoMascot.png" alt="知妍 AI 助手" width={size} height={size} />
}

export function AgentStatusMascot({ state }: { state: 'ready' | 'running' | 'completed' }) {
  return <MascotIcon size={32} className={`agent-status-mascot ${state}`} />
}
