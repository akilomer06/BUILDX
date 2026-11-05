import { createContext, useContext, useMemo, useState, useId } from 'react'
import type { ReactNode } from 'react'

export type DashboardMode='standard'|'veilmint'
const ModeContext=createContext<{mode:DashboardMode;setMode:(mode:DashboardMode)=>void}|null>(null)

export function DashboardModeProvider({children}:{children:ReactNode}){
  const [mode,setMode]=useState<DashboardMode>('standard')
  const value=useMemo(()=>({mode,setMode}),[mode])
  return <ModeContext.Provider value={value}>{children}</ModeContext.Provider>
}
export function useDashboardMode(){
  const context=useContext(ModeContext)
  if(!context)throw new Error('Dashboard mode requires its provider.')
  return context
}
export function DashboardModeToggle(){
  const {mode,setMode}=useDashboardMode()
  const groupName=useId()
  return <section className="dashboard-mode-bar" data-mode={mode} aria-label="Global dashboard mode">
    <div className="mode-bar-copy"><span className="mode-signal" aria-hidden="true"/><div><span className="eyebrow">DASHBOARD MODE</span><p>{mode==='standard'?'Standard API response':'VEILMINT API protection'}<small>Selects baseline or protected preview; actual enforcement is shown per trace</small></p></div></div>
    <fieldset className="dashboard-mode-control" aria-label="Dashboard mode"><legend className="sr-only">Dashboard mode</legend>
      <span className="mode-thumb" aria-hidden="true"/>
      {(['standard','veilmint'] as const).map(value=><label key={value}><input className="sr-only" type="radio" name={groupName} value={value} checked={mode===value} onChange={()=>setMode(value)}/><span>{value==='standard'?'Standard':'VEILMINT'}</span></label>)}
    </fieldset>
  </section>
}
