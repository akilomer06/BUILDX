import type { DashboardMode } from './DashboardMode'

export interface InspectedResponse {
  mode:DashboardMode;correlationId:string;endpoint:string;method:string;data:unknown;
  status:number;reason:string;httpVersion:string;capturedAt:string;headers:Record<string,string>;
  masked:string[];removed:string[];exposed:string[];
  standardBytes:number;responseBytes:number;reductionBytes:number;reductionPercent:number
}
export const responseEndpoint=(correlationId:string,mode:DashboardMode)=>`/api/operator/responses/${encodeURIComponent(correlationId)}/${mode}`

export async function fetchInspectedResponse(correlationId:string,mode:DashboardMode,signal:AbortSignal):Promise<InspectedResponse>{
  const response=await fetch(responseEndpoint(correlationId,mode),{signal,cache:'no-store'})
  if(response.headers.get('X-Captured-Correlation-ID')!==correlationId)throw new Error('Response body unavailable.')
  const raw=await response.text()
  const data:unknown=JSON.parse(raw)
  const number=(key:string)=>{
    const header=response.headers.get('X-Privacy-'+key)
    if(!header||!/^\d+(\.\d+)?$/.test(header))throw new Error('Response measurements are unavailable.')
    return Number(header)
  }
  const list=(key:string)=>{
    const header=response.headers.get('X-Privacy-'+key)
    if(header===null)throw new Error('Response field decisions are unavailable.')
    return header.split(',').filter(Boolean)
  }
  const responseBytes=number('Response-Bytes'),standardBytes=number('Standard-Bytes')
  const reductionBytes=number('Reduction-Bytes'),reductionPercent=number('Reduction-Percent')
  if(response.headers.get('X-Privacy-Mode')!==mode||new TextEncoder().encode(raw).byteLength!==responseBytes||
     reductionBytes!==standardBytes-responseBytes||Math.abs(reductionPercent-100*reductionBytes/standardBytes)>.011)throw new Error('Response measurements did not match.')
  const headers:Record<string,string>={}
  for(const name of ['Content-Type','X-Content-Type-Options','Cache-Control','X-Request-ID']){
    const value=response.headers.get(name);if(value)headers[name]=value
  }
  return {mode,correlationId,endpoint:response.headers.get('X-Captured-Endpoint')||'',method:response.headers.get('X-Captured-Method')||'',
    data,status:response.status,reason:response.headers.get('X-Captured-Status-Text')||response.statusText,
    httpVersion:response.headers.get('X-Captured-HTTP-Version')||'1.1',capturedAt:response.headers.get('X-Captured-At')||'',headers,
    masked:list('Masked-Fields'),removed:list('Removed-Fields'),exposed:list('Exposed-Fields'),
    responseBytes,standardBytes,reductionBytes,reductionPercent}
}
