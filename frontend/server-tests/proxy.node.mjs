import test from 'node:test'
import assert from 'node:assert/strict'
import handler,{upstreamPath} from '../api/proxy.mjs'

function result(){return {headers:{},code:0,data:null,setHeader(k,v){this.headers[k.toLowerCase()]=v},status(c){this.code=c;return this},json(v){this.data=v;return this},send(v){this.data=v;return this},end(){return this}}}
function request(path,extra={}){return {query:{forwardPath:path},url:'/api/'+path,method:'GET',headers:{host:'example.vercel.app'},...extra}}
test('rejects encoded traversal, slashes, alternate origins and malformed paths',()=>{
 for(const path of ['../policy','bank/%2e%2e/policy','bank/%2Foperator','https://elsewhere','bank//accounts','bank/%5caccounts'])assert.throws(()=>upstreamPath(path))
 assert.equal(upstreamPath('bank/accounts/123456789012'),'/api/bank/accounts/123456789012')
})
test('configuration status reveals only booleans and default operator access fails closed',async()=>{
 const r=result();await handler(request('deployment-status'),r);assert.equal(r.code,200);assert.deepEqual(Object.keys(r.data).sort(),['backendConfigured','operatorAccessConfigured'])
 const denied=result();await handler(request('operator/accounts'),denied);assert.equal(denied.code,401)
 assert.match(denied.headers['www-authenticate'],/Basic/)
})
test('cross-origin requests and unavailable backend are rejected',async()=>{
 const bad=result();await handler(request('bank/accounts',{headers:{host:'example.vercel.app',origin:'https://evil.example'}}),bad);assert.equal(bad.code,403)
 const old=process.env.BACKEND_URL;delete process.env.BACKEND_URL
 const unavailable=result();await handler(request('bank/accounts'),unavailable);assert.equal(unavailable.code,503)
 if(old!==undefined)process.env.BACKEND_URL=old
})
test('proxy preserves bodies/cookies and keeps operator Basic credentials out of backend requests',async()=>{
 const names=['BACKEND_URL','CLOUD_OPERATOR_PASSWORD','CLOUD_OPERATOR_USERNAME','VEILMINT_OPERATOR_TOKEN'];const saved=Object.fromEntries(names.map(n=>[n,process.env[n]]));const originalFetch=globalThis.fetch
 Object.assign(process.env,{BACKEND_URL:'https://backend.example',CLOUD_OPERATOR_PASSWORD:'SYNTHETIC-Operator-Password',CLOUD_OPERATOR_USERNAME:'operator',VEILMINT_OPERATOR_TOKEN:'SYNTHETIC-Backend-Token'})
 const calls=[];globalThis.fetch=async(url,init)=>{calls.push({url:String(url),init});return new Response('{"ok":true}',{headers:{'Content-Type':'application/json','Set-Cookie':'nexus_session=SYNTHETIC; Path=/api/bank; HttpOnly; Secure','X-Privacy-Masked-Fields':'/account_id'}})}
 try{
  const auth='Basic '+Buffer.from('operator:SYNTHETIC-Operator-Password').toString('base64')
  const op=result();await handler(request('operator/accounts',{headers:{host:'example.vercel.app',authorization:auth}}),op)
  assert.equal(op.code,200);assert.equal(calls[0].init.headers['X-VEILMINT-Operator'],'SYNTHETIC-Backend-Token');assert.equal(calls[0].init.headers.authorization,undefined)
  const bank=result();await handler(request('bank/transfers',{method:'POST',body:{amount_minor:123},headers:{host:'example.vercel.app',origin:'https://example.vercel.app',authorization:auth,cookie:'nexus_session=SYNTHETIC','x-nexus-request':'1','content-type':'application/json'}}),bank)
  assert.equal(calls[1].init.headers['X-VEILMINT-Operator'],undefined);assert.equal(calls[1].init.headers.Origin,'https://backend.example');assert.equal(calls[1].init.headers.cookie,'nexus_session=SYNTHETIC')
  assert.equal(calls[1].init.body,'{"amount_minor":123}');assert.ok(bank.headers['set-cookie']);assert.equal(bank.headers['cache-control'],'no-store')
 }finally{globalThis.fetch=originalFetch;for(const n of names){if(saved[n]===undefined)delete process.env[n];else process.env[n]=saved[n]}}
})
