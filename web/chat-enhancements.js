/* Advanced chat controls for Terminal AI. Loaded after app.js to replace the basic submit handler. */
(()=>{
"use strict";
const $=id=>document.getElementById(id);
const SETTINGS_KEY="terminal-ai-chat-preferences-v1";
const defaults={enter:true,scroll:true,meta:true,compact:false,font:14};
let prefs={...defaults};
let lastPrompt="";
let activeRequest=false;
function safeText(value){return String(value??"");}
function esc(value){return safeText(value).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));}
function notify(message){const el=$("chat-error");if(el)el.textContent=message;}
function readMessages(){return [...document.querySelectorAll("#messages > .message")].map((el,index)=>({index,role:el.classList.contains("user")?"user":"assistant",text:el.querySelector(".message-body")?.textContent??el.children[1]?.textContent??"",timestamp:el.dataset.timestamp||null,feedback:el.dataset.feedback||null}));}
function transcript(){return readMessages().filter(m=>m.text.trim()).map(m=>({role:m.role,content:m.text,timestamp:m.timestamp,feedback:m.feedback}));}
function savePrefs(){try{localStorage.setItem(SETTINGS_KEY,JSON.stringify(prefs));}catch{}}
function applyPrefs(){
 const box=$("messages");if(box){box.classList.toggle("compact",!!prefs.compact);box.style.setProperty("--chat-font-size",String(prefs.font)+"px");}
 const meta=$("chat-setting-meta");if(meta)document.querySelectorAll(".response-meta").forEach(el=>el.hidden=!prefs.meta);
 const controls=[["chat-setting-enter","enter"],["chat-setting-scroll","scroll"],["chat-setting-meta","meta"],["chat-setting-compact","compact"]];
 controls.forEach(([id,key])=>{const el=$(id);if(el)el.checked=!!prefs[key];});
 if($("chat-setting-font"))$("chat-setting-font").value=String(prefs.font);
}
function loadPrefs(){try{const parsed=JSON.parse(localStorage.getItem(SETTINGS_KEY)||"{}");if(parsed&&typeof parsed==="object")prefs={...defaults,...parsed};}catch{}prefs.font=Math.max(12,Math.min(19,Number(prefs.font)||14));applyPrefs();}
function download(name,content,type){const blob=new Blob([content],{type});const url=URL.createObjectURL(blob);const a=document.createElement("a");a.href=url;a.download=name;document.body.append(a);a.click();a.remove();URL.revokeObjectURL(url);}
function timestamp(){return new Date().toISOString();}
function renderAnswer(text){
 let out=esc(text);
 out=out.replace(/```([a-zA-Z0-9_+-]*)\n([\s\S]*?)```/g,(_,lang,code)=>'<pre class="chat-code"><code'+(lang?' data-language="'+esc(lang)+'"':'')+'>'+code+'</code></pre>');
 out=out.replace(/`([^`\n]+)`/g,'<code class="chat-inline-code">$1</code>');
 out=out.replace(/\*\*([^*\n]+)\*\*/g,'<strong>$1</strong>');
 out=out.replace(/(^|\n)\s*[-*] (.+)/g,'$1<span class="chat-list-line">• $2</span>');
 return out.replace(/\n/g,"<br>");
}
function addActions(messageEl,prompt){
 const bar=document.createElement("div");bar.className="message-actions";
 const add=(label,action,title)=>{const b=document.createElement("button");b.type="button";b.className="message-action";b.dataset.chatAction=action;b.title=title||label;b.textContent=label;if(prompt)b.dataset.prompt=prompt;bar.append(b);};
 add("Copy","copy","Copy answer");add("↻ Regenerate","regenerate","Send the same prompt again");add("👍","up","Helpful");add("👎","down","Not helpful");
 messageEl.append(bar);
}
function addTimestamp(el){el.dataset.timestamp=timestamp();const time=document.createElement("small");time.className="message-time";time.textContent=new Date(el.dataset.timestamp).toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"});el.append(time);}
function renderTrace(trace,run){
 const root=$("chat-execution-trace");if(!root)return;
 if(!Array.isArray(trace)||!trace.length){root.innerHTML='<div class="empty">No execution trace is available for this run.</div>';return;}
 const total=Number(run?.elapsed_seconds||0);
 root.innerHTML='<div class="execution-summary"><span class="badge">'+esc(run?.status||"completed")+'</span><span>'+esc(run?.backend||"Backend unknown")+'</span><span>'+total.toFixed(2)+' s total</span><span>Request '+esc(run?.request_id||"")+'</span></div>'+trace.map((step,i)=>'<div class="execution-step"><span class="execution-step-number">'+(i+1)+'</span><div class="execution-step-content"><b>'+esc(step.name.replaceAll("_"," "))+'</b><p>'+esc(step.detail||"")+'</p></div><span class="execution-step-status '+esc(step.status)+'">'+esc(step.status)+'</span><small>'+Number(step.elapsed_ms||0)+' ms</small></div>').join("")+'<p class="muted execution-footnote">Execution traces retain stage metadata only, not the prompt or generated answer.</p>';
}
async function loadRuns(){
 const err=$("chat-run-error");if(err)err.textContent="";
 try{
  const data=await api("/api/chat/runs");
  const runs=data.runs||[];
  if(runs.length)renderTrace(runs[0].execution,runs[0]);
  else if($("chat-execution-trace"))$("chat-execution-trace").innerHTML='<div class="empty">No chat runs recorded in this server process yet.</div>';
 }catch(e){if(err)err.textContent=e.message;}
}
function createAssistant(text,prompt){
 const el=addMessage("assistant",text);
 const body=el.children[1];body.classList.add("message-body");body.innerHTML=renderAnswer(text);
 addTimestamp(el);addActions(el,prompt);
 if(prefs.scroll)$("messages").scrollTop=$("messages").scrollHeight;
 return el;
}
function createUser(text){
 const el=addMessage("user",text);
 el.children[1].classList.add("message-body");addTimestamp(el);
 if(prefs.scroll)$("messages").scrollTop=$("messages").scrollHeight;
 return el;
}
function addMeta(el,data){
 const meta=document.createElement("small");meta.className="response-meta";
 meta.textContent="Generated by "+(data.backend||"unknown backend")+" · "+(Number(data.elapsed_seconds)||0).toFixed(2)+" s · "+(data.history_count??"—")+" history entries · "+(data.persistence||"persistence unknown");
 meta.hidden=!prefs.meta;el.append(meta);
}
async function sendMessage(prompt,{displayUser=true}={}){
 if(activeRequest)return;
 const message=safeText(prompt).trim();if(!message)return;
 activeRequest=true;lastPrompt=message;notify("");
 if(displayUser)createUser(message);
 const input=$("chat-input");if(input)input.value="";
 const send=$("send-btn");if(send){send.disabled=true;send.textContent="Working…";}
 const pending=createAssistant("Request accepted. Waiting for backend…",message);
 pending.classList.add("pending");
 const pendingBody=pending.children[1];
 const phases=["Validating request…","Waiting for conversation lock…","Running model inference…","Saving conversation history…"];
 let phase=0;
 const phaseTimer=setInterval(()=>{if(pending.classList.contains("pending")){pendingBody.textContent=phases[Math.min(phase++,phases.length-1)];}},1800);
 try{
  const data=await api("/api/chat",{method:"POST",body:JSON.stringify({message})});
  clearInterval(phaseTimer);pending.classList.remove("pending");pending.dataset.requestId=data.request_id||"";
  pendingBody.innerHTML=renderAnswer(data.answer||"The selected model returned an empty answer. Check Diagnostics and the active backend.");
  pending.querySelector(".message-actions")?.remove();
  addMeta(pending,data);
  const actions=document.createElement("div");actions.className="message-actions";
  for(const [label,action,title] of [["Copy","copy","Copy answer"],["↻ Regenerate","regenerate","Send the same prompt again"],["👍","up","Helpful"],["👎","down","Not helpful"]]){
   const b=document.createElement("button");b.type="button";b.className="message-action";b.dataset.chatAction=action;b.dataset.prompt=message;b.title=title;b.textContent=label;actions.append(b);
  }
  pending.append(actions);
  await loadRuns();
  if(typeof loadStatus==="function")await loadStatus();
 }catch(err){
  clearInterval(phaseTimer);pending.classList.remove("pending");pendingBody.textContent="Request failed: "+err.message;
  pending.querySelector(".message-actions")?.remove();
  const actions=document.createElement("div");actions.className="message-actions";
  const retry=document.createElement("button");retry.type="button";retry.className="message-action";retry.dataset.chatAction="regenerate";retry.dataset.prompt=message;retry.textContent="Retry request";actions.append(retry);pending.append(actions);
  notify("Chat request failed. Your message remains visible; use Retry request to try again.");
  await loadRuns();
 }finally{
  activeRequest=false;if(send){send.disabled=false;send.textContent="Send message ↗";}
  if(prefs.scroll)$("messages").scrollTop=$("messages").scrollHeight;
 }
}
function applySearch(){
 const q=($("chat-search")?.value||"").trim().toLowerCase();
 document.querySelectorAll("#messages > .message").forEach(el=>{el.hidden=!!q&&!el.textContent.toLowerCase().includes(q);});
}
function exportTranscript(format){
 const rows=transcript();if(!rows.length){notify("There are no messages to export.");return;}
 if(format==="json")download("terminal-ai-chat-"+new Date().toISOString().slice(0,10)+".json",JSON.stringify({exported_at:timestamp(),session:$("messages")?.dataset.session||null,messages:rows},null,2),"application/json");
 else download("terminal-ai-chat-"+new Date().toISOString().slice(0,10)+".md",rows.map(m=>"## "+(m.role==="user"?"You":"Terminal AI")+(m.timestamp?" · "+new Date(m.timestamp).toLocaleString():"")+"\n\n"+m.content).join("\n\n---\n\n"),"text/markdown;charset=utf-8");
}
document.addEventListener("DOMContentLoaded",loadPrefs);
loadPrefs();
const form=$("chat-form");
if(form)form.addEventListener("submit",e=>{e.preventDefault();e.stopImmediatePropagation();sendMessage($("chat-input").value);},true);
const input=$("chat-input");
if(input)input.addEventListener("keydown",e=>{if(e.key==="Enter"&&!e.shiftKey&&!prefs.enter){e.preventDefault();e.stopImmediatePropagation();}},true);
const messages=$("messages");
if(messages)new MutationObserver(()=>{if(prefs.meta)document.querySelectorAll(".response-meta").forEach(el=>el.hidden=false);}).observe(messages,{childList:true,subtree:true});
$("chat-search")?.addEventListener("input",applySearch);
$("chat-export-md")?.addEventListener("click",()=>exportTranscript("md"));
$("chat-export-json")?.addEventListener("click",()=>exportTranscript("json"));
$("chat-copy-transcript")?.addEventListener("click",async()=>{const text=transcript().map(m=>(m.role==="user"?"You":"Terminal AI")+": "+m.text).join("\n\n");try{await navigator.clipboard.writeText(text);notify("Transcript copied.");}catch{download("terminal-ai-transcript.txt",text,"text/plain;charset=utf-8");}});
$("chat-new-session")?.addEventListener("click",async()=>{if(activeRequest){notify("Wait for the active request to finish before opening a new chat.");return;}const name="Chat "+new Date().toLocaleString().replace(/[/:]/g,"-");try{await api("/api/sessions/new",{method:"POST",body:JSON.stringify({name})});$("messages").innerHTML='<div class="welcome" id="welcome"><div class="orb">✧</div><h2>New conversation</h2><p>New local session created. Send a message to begin.</p></div>';lastPrompt="";notify("");await loadRuns();if(typeof loadSessions==="function")await loadSessions();}catch(e){notify(e.message);}});
$("chat-refresh-runs")?.addEventListener("click",loadRuns);
document.addEventListener("click",async e=>{
 const b=e.target.closest("[data-chat-action]");if(!b)return;
 const action=b.dataset.chatAction;const prompt=b.dataset.prompt||lastPrompt;
 if(action==="copy"){const text=b.closest(".message")?.querySelector(".message-body")?.textContent||"";try{await navigator.clipboard.writeText(text);b.textContent="Copied";setTimeout(()=>b.textContent="Copy",1200);}catch{notify("Clipboard access unavailable in this browser.");}}
 else if(action==="regenerate"){if(prompt)sendMessage(prompt);else notify("No previous prompt is available in this view.");}
 else if(action==="up"||action==="down"){const msg=b.closest(".message");if(!msg)return;msg.dataset.feedback=action;try{localStorage.setItem("terminal-ai-feedback-"+(msg.dataset.requestId||msg.dataset.timestamp||Date.now()),action);}catch{}msg.querySelectorAll('[data-chat-action="up"],[data-chat-action="down"]').forEach(x=>x.classList.toggle("selected",x===b));notify(action==="up"?"Feedback saved in this browser.":"Feedback saved in this browser; consider refining your prompt.");}
});
["chat-setting-enter","chat-setting-scroll","chat-setting-meta","chat-setting-compact"].forEach((id)=>$(id)?.addEventListener("change",()=>{const key=id.replace("chat-setting-","");prefs[key]=$(id).checked;savePrefs();applyPrefs();}));
$("chat-setting-font")?.addEventListener("input",()=>{prefs.font=Number($("chat-setting-font").value);savePrefs();applyPrefs();});
const clear=$("clear-chat");
if(clear)clear.addEventListener("click",e=>{if(!confirm("Clear the current conversation history? This cannot be undone.")){e.preventDefault();e.stopImmediatePropagation();}},true);
loadRuns();
})();
