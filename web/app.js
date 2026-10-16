const $=id=>document.getElementById(id);
let statusData=null;
let apiReachable=null;
const titles={overview:"Overview",chat:"AI Chat",sessions:"Sessions",models:"Models",diagnostics:"Diagnostics",memory:"Memory",goals:"Goals",self:"Self-awareness",skills:"Skills",tools:"Tools",learning:"Learning",improvements:"Self-improvement",selfx:"Self-X Evolution Engine",settings:"Settings",knowledge:"Knowledge Base",workspace:"Workspace Tools",scheduler:"Task Scheduler","command-control":"Command Control Center"};
function escapeHtml(value){return String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));}
async function api(path,options={}){const res=await fetch(path,{...options,headers:{"Content-Type":"application/json",...(options.headers||{})}});let data={};try{data=await res.json()}catch{}if(!res.ok)throw new Error(data.detail||data.message||("Request failed ("+res.status+")"));return data;}
function showView(name){document.querySelectorAll(".view").forEach(el=>el.classList.toggle("active",el.id==="view-"+name));document.querySelectorAll("#nav button").forEach(el=>el.classList.toggle("active",el.dataset.view===name));$("page-title").textContent=titles[name]||name;if(name==="sessions")loadSessions();if(name==="models")loadModels();if(name==="diagnostics")loadDiagnostics();if(name==="memory")loadMemory();if(name==="goals")loadGoals();if(name==="settings"){loadSettings();loadUpdateStatus();}if(name==="self")loadSelf();if(name==="skills")loadSkills();if(name==="tools")loadTools();if(name==="learning")loadLearning();if(name==="improvements"){loadImprovements();loadSkillEvolution();}if(name==="selfx"){loadSelfX();loadAgenticConsole();loadTaskLifecycle();loadAutonomyStatus();}if(name==="knowledge")loadKnowledge();if(name==="workspace")loadWorkspace();if(name==="scheduler")loadScheduler();if(name==="command-control")loadCommandControl();}
$("nav").addEventListener("click",e=>{const b=e.target.closest("[data-view]");if(b)showView(b.dataset.view);});
if($("overview-refresh"))$("overview-refresh").addEventListener("click",()=>loadStatus());
document.addEventListener("click",e=>{const b=e.target.closest("[data-go]");if(b)showView(b.dataset.go);});
const commandPalette=$("command-palette");
const commandSearch=$("command-search");
const commandResults=$("command-results");
let commandItems=[];
let commandActiveIndex=0;
let commandReturnFocus=null;
function refreshCommandItems(){
 commandItems=Array.from(document.querySelectorAll("#nav [data-view]")).map(button=>({view:button.dataset.view,label:button.querySelector(".nav-text")?.textContent.trim()||button.dataset.view,icon:button.querySelector(".ico")?.textContent.trim()||"◈"}));
}
function renderCommandResults(){
 const query=(commandSearch.value||"").trim().toLowerCase();
 const filtered=commandItems.filter(item=>item.label.toLowerCase().includes(query)||item.view.toLowerCase().includes(query));
 commandActiveIndex=Math.max(0,Math.min(commandActiveIndex,filtered.length-1));
 commandResults.innerHTML=filtered.length?filtered.map((item,index)=>'<button type="button" class="command-result'+(index===commandActiveIndex?' active':'')+'" role="option" aria-selected="'+(index===commandActiveIndex?'true':'false')+'" data-command-view="'+escapeHtml(item.view)+'"><span class="command-result-icon">'+escapeHtml(item.icon)+'</span><span>'+escapeHtml(item.label)+'</span><kbd>↵</kbd></button>').join(""):'<div class="empty command-empty">No pages match “'+escapeHtml(query)+'”. Try another search.</div>';
}
function openCommandPalette(){
 if(!commandPalette)return;
 refreshCommandItems();commandReturnFocus=document.activeElement;commandSearch.value="";commandActiveIndex=0;renderCommandResults();
 commandPalette.classList.add("open");commandPalette.setAttribute("aria-hidden","false");document.body.classList.add("command-open");commandSearch.focus();
}
function closeCommandPalette(){
 if(!commandPalette)return;
 commandPalette.classList.remove("open");commandPalette.setAttribute("aria-hidden","true");document.body.classList.remove("command-open");
 if(commandReturnFocus&&typeof commandReturnFocus.focus==="function")commandReturnFocus.focus();
}
if($("command-open"))$("command-open").addEventListener("click",openCommandPalette);
if($("command-close"))$("command-close").addEventListener("click",closeCommandPalette);
if(commandSearch)commandSearch.addEventListener("input",()=>{commandActiveIndex=0;renderCommandResults();});
if(commandResults)commandResults.addEventListener("click",e=>{const item=e.target.closest("[data-command-view]");if(!item)return;const view=item.dataset.commandView;closeCommandPalette();showView(view);const navButton=Array.from(document.querySelectorAll("#nav [data-view]")).find(button=>button.dataset.view===view);if(navButton)navButton.focus();});
if(commandPalette)commandPalette.addEventListener("click",e=>{if(e.target===commandPalette)closeCommandPalette();});
document.addEventListener("keydown",e=>{
 if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==="k"){e.preventDefault();openCommandPalette();return;}
 if(!commandPalette||!commandPalette.classList.contains("open"))return;
 if(e.key==="Escape"){e.preventDefault();closeCommandPalette();return;}
 if(e.key==="ArrowDown"||e.key==="ArrowUp"){
  e.preventDefault();const buttons=Array.from(commandResults.querySelectorAll("[data-command-view]"));if(!buttons.length)return;
  commandActiveIndex=(commandActiveIndex+(e.key==="ArrowDown"?1:-1)+buttons.length)%buttons.length;renderCommandResults();
  const active=commandResults.querySelectorAll("[data-command-view]")[commandActiveIndex];if(active)active.scrollIntoView({block:"nearest"});
 }else if(e.key==="Enter"){
  const active=commandResults.querySelectorAll("[data-command-view]")[commandActiveIndex];if(active){e.preventDefault();active.click();}
 }
});
async function loadBrowserOverview(){
 const badge=$("overview-browser-badge");
 try{
  const data=await api("/api/browser/status");
  const enabled=Boolean(data.enabled);
  badge.textContent=enabled?"Allowlist ready":"Disabled";
  badge.className="badge "+(enabled?"success":"");
  $("overview-browser-mark").textContent=enabled?"✓":"◈";
  $("overview-browser-state").textContent=enabled?"Browser allowlist configured":"Browser access is disabled";
  $("overview-browser-detail").textContent=enabled?"Domain policy is configured; actions remain gated":"Add trusted DNS names in Settings to enable browser access";
  $("overview-browser-domains").textContent=String(data.allowed_domain_count??0);
  $("overview-browser-playwright").textContent=data.playwright_installed?"Installed":"Not installed";
  $("overview-browser-actions").textContent="Disabled";
 }catch(error){
  badge.textContent="Unavailable";badge.className="badge";
  $("overview-browser-mark").textContent="!";
  $("overview-browser-state").textContent="Could not read browser status";
  $("overview-browser-detail").textContent=error.message;
  $("overview-browser-domains").textContent="—";$("overview-browser-playwright").textContent="—";$("overview-browser-actions").textContent="Disabled";
 }
}
if($("overview-browser-refresh"))$("overview-browser-refresh").addEventListener("click",loadBrowserOverview);

async function loadStatus(){
 try{
  statusData=await api("/api/status");
  if(apiReachable===false)showToast("Terminal AI API is back online.","status");
  apiReachable=true;
  loadBrowserOverview();
  const ready=Boolean(statusData.ready);
  recordHealthSnapshot(true,ready);
  $("status-label").textContent=ready?"System online":"Setup required";
  $("status-dot").style.background=ready?"var(--green)":"var(--red)";
  $("metric-ready").textContent=ready?"Ready":"Setup";
  $("metric-backend").textContent=statusData.backend||"Not loaded";
  $("metric-mode").textContent="Mode: "+(statusData.mode||"auto");
  $("metric-memory").textContent=Number(statusData.memory_facts||0).toLocaleString();
  $("metric-goals").textContent=Number(statusData.active_goals||0).toLocaleString();
  $("side-version").textContent="v"+(statusData.version||"—");
  $("side-state").textContent=ready?"Agent connected":"Backend not ready";
  const localModels=statusData.local_models||[];
  const checks=[
   ["API server","Available","ok"],
   ["Inference backend",statusData.backend||"Not initialized",ready?"ok":"warn"],
   ["Local model files",localModels.length?localModels.length+" model(s) found":"No .litertlm files found",localModels.length?"ok":"warn"],
   ["Saved sessions",String(statusData.session_count??"—"),"neutral"],
   ["Application uptime",formatDuration(statusData.uptime_seconds),"neutral"],
   ["Self-X maintenance",statusData.selfx_enabled?"Enabled":"Configured in Settings",statusData.selfx_enabled?"ok":"neutral"]
  ];
  $("overview-health").innerHTML=checks.map(([k,v,s])=>'<div class="health-item"><span class="health-indicator '+s+'"></span><div><b>'+escapeHtml(k)+'</b><p>'+escapeHtml(v)+'</p></div></div>').join("");
  $("overview-health-badge").textContent=ready?"Runtime reachable":"Action required";
  $("overview-ready-sub").textContent=ready?"Backend initialized · API responding":"Open Settings or Diagnostics to resolve setup";
  $("system-list").innerHTML=[["Application",statusData.interface],["Version","v"+statusData.version],["Active session",statusData.active_session||"web-session"],["Session count",statusData.session_count??"Unknown"],["State directory",statusData.state_dir],["Uptime",formatDuration(statusData.uptime_seconds)]].map(([k,v])=>'<div class="list-item"><b>'+escapeHtml(k)+'</b><p>'+escapeHtml(v??"Unknown")+'</p></div>').join("");
  $("overview-inference").innerHTML=[["Selected mode",statusData.mode||"auto"],["Active backend",statusData.backend||"Not loaded"],["Gemini credentials",statusData.gemini_configured?"Present (not displayed)":"Not configured"],["Local models",localModels.length?localModels.join(", "):"None detected"],["Network dependency",statusData.mode==="local"?"Not required for inference":"Depends on selected provider / fallback"]].map(([k,v])=>'<div class="list-item"><b>'+escapeHtml(k)+'</b><p>'+escapeHtml(v)+'</p></div>').join("");
  const checklist=[
   [ready,"Initialize an inference backend",ready?"Backend is ready":"Check model/provider configuration","settings"],
   [false,"Verify offline model",localModels.length?"Model file detected; run a test with network disabled to confirm inference":"Add a compatible .litertlm model in the models directory","models"],
   [false,"Verify session persistence",statusData.session_count?"Saved session records are discoverable; reopen one to verify messages":"Create a session, send a message, then reopen it to verify persistence","sessions"],
   [!statusData.error,"Review runtime errors",statusData.error||"No current backend initialization error reported","diagnostics"]
  ];
  $("overview-checklist").innerHTML=checklist.map(([ok,title,detail,view])=>'<div class="check-item"><span class="check-mark '+(ok?"done":"pending")+'">'+(ok?"✓":"!")+'</span><div><b>'+escapeHtml(title)+'</b><p>'+escapeHtml(detail)+'</p><button class="btn" data-go="'+view+'">Open</button></div></div>').join("");
  $("system-error").textContent=statusData.error||"";
  $("storage-list").innerHTML=[["State",statusData.state_dir],["Models",localModels.length+" found"],["Interface","Litestar + HTML/CSS/JS"]].map(([k,v])=>'<div class="list-item"><b>'+escapeHtml(k)+'</b><p>'+escapeHtml(v)+'</p></div>').join("");
 }catch(e){
  if(apiReachable===true)showToast("Terminal AI API is unavailable.","error");
  apiReachable=false;
  recordHealthSnapshot(false,false);
  $("status-label").textContent="API unavailable";$("metric-ready").textContent="Offline";$("system-error").textContent=e.message;
  if($("overview-health"))$("overview-health").innerHTML='<div class="error">'+escapeHtml(e.message)+'</div>';
 }
}
function formatDuration(value){let s=Math.max(0,Number(value)||0);const d=Math.floor(s/86400);s%=86400;const h=Math.floor(s/3600);s%=3600;const m=Math.floor(s/60);s=Math.floor(s%60);return [d?d+"d":"",h?h+"h":"",m?m+"m":"",(!d&&!h&&!m)||s?s+"s":""].filter(Boolean).join(" ");}
function addMessage(role,text){const welcome=$("welcome");if(welcome)welcome.remove();const div=document.createElement("div");div.className="message "+role;const who=document.createElement("span");who.className="who";who.textContent=role==="user"?"You":"Terminal AI";const body=document.createElement("div");body.textContent=text;div.append(who,body);$("messages").append(div);$("messages").scrollTop=$("messages").scrollHeight;return div;}
document.querySelectorAll(".suggestions button").forEach(b=>b.addEventListener("click",()=>{$("chat-input").value=b.textContent;showView("chat");$("chat-input").focus();}));
$("chat-form").addEventListener("submit",async e=>{e.preventDefault();const message=$("chat-input").value.trim();if(!message)return;$("chat-error").textContent="";addMessage("user",message);$("chat-input").value="";$("send-btn").disabled=true;$("send-btn").textContent="Thinking…";const pending=addMessage("assistant","Thinking…");try{const data=await api("/api/chat",{method:"POST",body:JSON.stringify({message})});pending.lastChild.textContent=data.answer||"The selected model returned an empty answer. Check Diagnostics and the active backend.";const meta=document.createElement("small");meta.className="response-meta";meta.textContent="Generated by "+(data.backend||"unknown backend")+" · "+(Number(data.elapsed_seconds)||0).toFixed(1)+"s · "+(data.history_count??"—")+" history entries";pending.append(meta);await loadStatus();}catch(err){pending.lastChild.textContent="";$("chat-error").textContent=err.message;pending.remove();}finally{$("send-btn").disabled=false;$("send-btn").textContent="Send message ↗";}});
$("chat-input").addEventListener("keydown",e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();$("chat-form").requestSubmit();}});
$("clear-chat").addEventListener("click",async()=>{try{await api("/api/chat/clear",{method:"POST",body:"{}"});$("messages").innerHTML='<div class="welcome" id="welcome"><div class="orb">✧</div><h2>Fresh conversation</h2><p>Your chat history was cleared from the active session.</p></div>';$("chat-error").textContent="";}catch(e){$("chat-error").textContent=e.message;}});
async function loadMemory(){const list=$("memory-list");list.innerHTML='<div class="empty">Loading…</div>';try{const data=await api("/api/memory");const facts=data.facts||[];list.innerHTML=facts.length?facts.slice().reverse().map(f=>'<div class="list-item"><div class="row" style="justify-content:space-between"><b>'+escapeHtml(f.k)+'</b><button class="btn danger forget-btn" data-key="'+escapeHtml(f.k)+'">Forget</button></div><p>'+escapeHtml(f.v)+'</p><div class="muted" style="font-size:11px;margin-top:8px">Source: '+escapeHtml(f.source||"unknown")+'</div></div>').join(""):'<div class="empty">No saved facts yet. Add a memory using the form.</div>';}catch(e){list.innerHTML='<div class="error">'+escapeHtml(e.message)+'</div>';}}
$("memory-list").addEventListener("click",async e=>{const b=e.target.closest(".forget-btn");if(!b)return;if(!confirm("Forget memory facts matching “"+b.dataset.key+"”?"))return;try{await api("/api/memory/forget",{method:"POST",body:JSON.stringify({key:b.dataset.key})});await loadMemory();await loadStatus();}catch(err){$("memory-error").textContent=err.message;}});
$("refresh-memory").addEventListener("click",loadMemory);
$("memory-form").addEventListener("submit",async e=>{e.preventDefault();$("memory-error").textContent="";try{await api("/api/memory",{method:"POST",body:JSON.stringify({key:$("memory-key").value,value:$("memory-value").value})});$("memory-key").value="";$("memory-value").value="";await loadMemory();await loadStatus();}catch(err){$("memory-error").textContent=err.message;}});
async function loadGoals(){const list=$("goal-list");list.innerHTML='<div class="empty">Loading…</div>';try{const data=await api("/api/goals");const goals=data.goals||[];list.innerHTML=goals.length?goals.slice().reverse().map(g=>'<div class="list-item"><div class="row" style="justify-content:space-between"><b>'+escapeHtml(g.text)+'</b><span class="badge">'+escapeHtml(g.status)+'</span></div><p class="muted">ID: '+escapeHtml(g.id)+'</p>'+(g.status==="active"?'<button class="btn" data-complete="'+escapeHtml(g.id)+'">Mark complete</button>':"")+'</div>').join(""):'<div class="empty">No goals yet. Create your first goal.</div>';}catch(e){list.innerHTML='<div class="error">'+escapeHtml(e.message)+'</div>';}}
$("goal-list").addEventListener("click",async e=>{const b=e.target.closest("[data-complete]");if(!b)return;try{await api("/api/goals/"+encodeURIComponent(b.dataset.complete)+"/complete",{method:"POST",body:"{}"});await loadGoals();await loadStatus();}catch(err){$("goal-error").textContent=err.message;}});
$("refresh-goals").addEventListener("click",loadGoals);
$("goal-form").addEventListener("submit",async e=>{e.preventDefault();$("goal-error").textContent="";try{await api("/api/goals",{method:"POST",body:JSON.stringify({text:$("goal-text").value})});$("goal-text").value="";await loadGoals();await loadStatus();}catch(err){$("goal-error").textContent=err.message;}});
async function loadSessions(){
 const list=$("session-list");list.innerHTML='<div class="empty">Loading saved sessions…</div>';
 try{
  const data=await api("/api/sessions");const sessions=data.sessions||[];
  list.innerHTML=sessions.length?sessions.map(name=>'<div class="list-item"><div class="row" style="justify-content:space-between;gap:8px"><b>'+escapeHtml(name)+'</b><span class="badge">'+(name===data.active_session?'Active':'Saved locally')+'</span></div><div class="row" style="margin-top:10px;gap:8px"><button class="btn primary" data-select-session="'+escapeHtml(name)+'">'+(name===data.active_session?'Reload session':'Open session')+'</button><button class="btn danger" data-delete-session="'+escapeHtml(name)+'">Delete</button></div></div>').join(""):'<div class="empty">No saved sessions yet. Create a session to begin.</div>';
  $("sessions-error").textContent="";
 }catch(e){list.innerHTML='<div class="error">'+escapeHtml(e.message)+'</div>';}
}
$("refresh-sessions").addEventListener("click",loadSessions);
$("session-new-form").addEventListener("submit",async e=>{
 e.preventDefault();$("sessions-error").textContent="";
 try{await api("/api/sessions/new",{method:"POST",body:JSON.stringify({name:$("session-new-name").value})});$("session-new-name").value="";$("messages").innerHTML='<div class="welcome" id="welcome"><div class="orb">✧</div><h2>New conversation</h2><p>New session created. Send a message to begin.</p></div>';await loadSessions();showView("chat");}
 catch(err){$("sessions-error").textContent=err.message;}
});
$("session-list").addEventListener("click",async e=>{
 const open=e.target.closest("[data-select-session]");
 const del=e.target.closest("[data-delete-session]");
 try{
  if(open){const result=await api("/api/sessions/select",{method:"POST",body:JSON.stringify({name:open.dataset.selectSession})});$("messages").innerHTML="";if((result.history||[]).length){for(const m of result.history)addMessage(m.role==="assistant"?"assistant":"user",m.text);}else{$("messages").innerHTML='<div class="welcome" id="welcome"><div class="orb">✧</div><h2>Empty session</h2><p>Send a message to begin this conversation.</p></div>';}await loadSessions();showView("chat");}
  else if(del){if(!confirm("Permanently delete session '"+del.dataset.deleteSession+"'?"))return;await api("/api/sessions/delete",{method:"POST",body:JSON.stringify({name:del.dataset.deleteSession})});await loadSessions();}
 }catch(err){$("sessions-error").textContent=err.message;}
});
async function loadModels(){const list=$("model-list");list.innerHTML='<div class="empty">Loading model inventory…</div>'; $("models-error").textContent="";try{const data=await api("/api/models");$("model-count").textContent=data.installed_count+" local model file(s)";$("model-dir").textContent="Directory: "+data.models_dir;const models=data.models||[];list.innerHTML=models.length?models.map(m=>'<div class="list-item"><div class="row" style="justify-content:space-between"><b>'+escapeHtml(m.display||m.name)+'</b><span class="badge">'+escapeHtml(m.kind)+(m.installed?' · installed':'')+'</span></div><p>'+escapeHtml(m.name)+' · '+escapeHtml(m.tier||'model')+(m.size?' · '+escapeHtml(m.size):'')+'</p><p>Strengths: '+escapeHtml((m.strengths||[]).join(', ')||'not specified')+'</p>'+(m.path?'<p>Path: '+escapeHtml(m.path)+'</p>':'')+(m.hf_repo?'<p>Source: '+escapeHtml(m.hf_repo+'/'+(m.hf_file||''))+'</p>':'')+(!m.installed&&m.kind==="local"&&m.hf_file&&m.hf_file.endsWith(".litertlm")?'<button class="btn primary" data-download-model="'+escapeHtml(m.name)+'">Download model</button>':'')+'</div>').join(""):'<div class="empty">No model entries are registered.</div>';}catch(e){list.innerHTML='<div class="error">'+escapeHtml(e.message)+'</div>';}}
$("refresh-models").addEventListener("click",loadModels);
async function loadProviders(){const list=$("provider-list");try{const data=await api("/api/providers");list.innerHTML=(data.providers||[]).map(p=>'<div class="list-item"><div class="row" style="justify-content:space-between"><b>'+escapeHtml(p.label)+'</b><span class="badge">'+(p.configured?'Configured':'Not configured')+'</span></div><p>'+escapeHtml(p.kind)+' · '+(p.requires_network?'Network required':'Local/offline capable')+'</p>'+(p.token_configured!==undefined?'<p>Hugging Face token: '+(p.token_configured?'configured':'optional / not configured')+'</p>':'')+'</div>').join("");}catch(e){list.innerHTML='<div class="error">'+escapeHtml(e.message)+'</div>';}}
$("refresh-providers").addEventListener("click",loadProviders);
async function loadDownloads(){const list=$("download-list");try{const data=await api("/api/downloads");const jobs=data.downloads||[];list.innerHTML=jobs.length?jobs.map(j=>'<div class="list-item"><div class="row" style="justify-content:space-between"><b>'+escapeHtml(j.display||j.model_id)+'</b><span class="badge">'+escapeHtml(j.status)+'</span></div><p>'+escapeHtml(j.repo_id+'/'+j.filename)+'</p><p>Downloaded: '+(Number(j.bytes_downloaded||0)/1048576).toFixed(2)+' MiB</p>'+(j.path?'<p>Saved: '+escapeHtml(j.path)+'</p>':'')+(j.error?'<p class="error">'+escapeHtml(j.error)+'</p>':'')+'</div>').join(""):'<div class="empty">No downloads started.</div>';}catch(e){$("downloads-error").textContent=e.message;}}
$("refresh-downloads").addEventListener("click",loadDownloads);
$("model-list").addEventListener("click",async e=>{const b=e.target.closest("[data-download-model]");if(!b)return;const id=b.dataset.downloadModel;if(!confirm("Download "+id+" from its registered Hugging Face source? This uses network data and disk space."))return;b.disabled=true;b.textContent="Queueing…";try{await api("/api/models/download",{method:"POST",body:JSON.stringify({model_id:id,confirm:true})});await loadDownloads();startDownloadPolling();}catch(err){$("models-error").textContent=err.message;}finally{b.disabled=false;b.textContent="Download model";}});
let downloadPoll=null;
function startDownloadPolling(){if(downloadPoll)clearInterval(downloadPoll);downloadPoll=setInterval(async()=>{await loadDownloads();try{const d=await api("/api/downloads");if(!(d.downloads||[]).some(j=>["queued","downloading"].includes(j.status))){clearInterval(downloadPoll);downloadPoll=null;await loadModels();}}catch{}},1500);}
loadProviders();loadDownloads();
async function loadDiagnostics(){const list=$("diagnostic-list");list.innerHTML='<div class="empty">Running local checks…</div>';$("diagnostics-error").textContent="";try{const d=await api("/api/diagnostics");const sections=[["Application",d.application],["Backend",d.backend],["Storage",d.storage],["Runtime",d.runtime]];list.innerHTML=sections.map(([name,values])=>'<div class="list-item"><b>'+escapeHtml(name)+'</b>'+Object.entries(values||{}).map(([k,v])=>'<p><span class="muted">'+escapeHtml(k.replace(/_/g," "))+'</span>: '+escapeHtml(typeof v==="object"&&v!==null?JSON.stringify(v):v)+'</p>').join("")+'</div>').join("");}catch(e){list.innerHTML='<div class="error">'+escapeHtml(e.message)+'</div>';}}
$("refresh-diagnostics").addEventListener("click",loadDiagnostics);

async function fetchProviderModels({auto=false}={}) {
 const button=$("fetch-provider-models"),error=$("provider-model-error"),count=$("provider-model-count"),list=$("provider-model-options");
 if(!button||!error||!count||!list)return;
 const provider=$("setting-provider").value;
 button.disabled=true;button.textContent="Fetching…";error.textContent="";count.textContent="Contacting provider API…";
 try{
  const result=await api("/api/providers/models",{method:"POST",body:JSON.stringify({
   provider_id:provider,api_key:$("setting-api-key").value,base_url:$("setting-endpoint").value
  })});
  list.replaceChildren(...(result.models||[]).map(model=>{const option=document.createElement("option");option.value=model.id;option.label=model.label||model.id;return option;}));
  const current=$("setting-model").value.trim();
  if(!current||!(result.models||[]).some(model=>model.id===current))$("setting-model").value=result.default_model||"";
  count.textContent=(result.count||0)+" model ID(s) loaded";
  if(!auto)showToast("Loaded "+(result.count||0)+" model IDs from "+provider+". Choose one and save settings.","status");
 }catch(e){
  count.textContent="Could not load model list";
  error.textContent=e.message+" You can still enter a model ID manually.";
 }finally{button.disabled=false;button.textContent="Fetch model IDs";}
}
$("fetch-provider-models")?.addEventListener("click",()=>fetchProviderModels());
async function loadProviderConfigurationStatus(){
 const target=$("provider-configuration-status");
 if(!target)return;
 try{
  const data=await api("/api/providers");
  const providers=(data.providers||[]).filter(item=>item.kind==="cloud"&&item.id&&item.label);
  const selector=$("setting-provider");
  if(selector&&providers.length){
   const selected=selector.value||data.active_provider||"gemini";
   selector.replaceChildren(...providers.map(item=>{const option=document.createElement("option");option.value=item.id;option.textContent=item.label;return option;}));
   selector.value=providers.some(item=>item.id===selected)?selected:(data.active_provider||providers[0].id);
   $("custom-endpoint-field").hidden=!providers.find(item=>item.id===selector.value)?.endpoint_configurable;
  }
  target.innerHTML=providers.map(item=>'<div class="list-item"><div class="row" style="justify-content:space-between"><b>'+escapeHtml(item.label||item.id)+'</b><span class="badge '+(item.configured?'success':'')+'">'+(item.auth_required===false?'No key required':item.configured?'Configured':'Missing key')+'</span></div><p class="muted">'+escapeHtml(item.protocol||"Gemini API")+' · default '+escapeHtml(item.default_model||"fetch installed models")+(item.requires_network===false?' · local endpoint':'')+'</p></div>').join("")||'<div class="empty">No cloud providers are registered.</div>';
 }catch(error){target.innerHTML='<div class="error">'+escapeHtml(error.message)+'</div>';}
}
$("refresh-provider-status")?.addEventListener("click",loadProviderConfigurationStatus);

let providerProfiles = {};

function populateProviderProfileChoices(){
 const select=$("profile-provider"),source=$("setting-provider");
 if(!select||!source)return;
 const previous=select.value;
 select.replaceChildren(...Array.from(source.options).map(option=>{
  const copy=document.createElement("option");copy.value=option.value;copy.textContent=option.textContent;return copy;
 }));
 if(Array.from(select.options).some(option=>option.value===previous))select.value=previous;
 else select.value=source.value||select.options[0]?.value||"";
}
function renderProviderProfiles(){
 const target=$("provider-profile-list");if(!target)return;
 const entries=Object.entries(providerProfiles||{});
 if(!entries.length){target.innerHTML='<div class="empty">No custom profiles saved yet. Default settings remain in effect.</div>';return;}
 target.innerHTML=entries.map(([id,p])=>'<div class="list-item"><b>'+escapeHtml(id)+'</b><p>Model: '+escapeHtml(p.model||"provider default")+' · Priority: '+escapeHtml(p.failover_priority??100)+' · Temperature: '+escapeHtml(p.temperature??0.7)+' · Top-p: '+escapeHtml(p.top_p??0.95)+' · Tokens: '+escapeHtml(p.max_tokens??2048)+' · Timeout: '+escapeHtml(p.timeout_seconds??60)+'</p>'+(p.base_url?'<p>Endpoint: '+escapeHtml(p.base_url)+'</p>':'')+'</div>').join("");
}
function loadProviderProfileIntoEditor(){
 const id=$("profile-provider")?.value;if(!id)return;
 const p=providerProfiles[id]&&typeof providerProfiles[id]==="object"?providerProfiles[id]:{};
 $("profile-model").value=p.model||"";
 $("profile-base-url").value=p.base_url||"";
 $("profile-temperature").value=p.temperature??0.7;
 $("profile-top-p").value=p.top_p??0.95;
 $("profile-max-tokens").value=p.max_tokens??2048;
 $("profile-timeout").value=p.timeout_seconds??60;
 $("profile-priority").value=p.failover_priority??100;
 $("provider-profile-status").textContent=providerProfiles[id]?"Editing saved profile for "+id+".":"No profile saved for "+id+"; default values shown.";
}
async function saveProviderProfile(){
 const id=$("profile-provider").value;
 const profile={
  model:$("profile-model").value.trim(),
  base_url:$("profile-base-url").value.trim(),
  temperature:Number($("profile-temperature").value),
  top_p:Number($("profile-top-p").value),
  max_tokens:Number($("profile-max-tokens").value),
  timeout_seconds:Number($("profile-timeout").value),
  failover_priority:Number($("profile-priority").value)
 };
 if(!id){throw new Error("Choose a provider first.");}
 if(!Number.isFinite(profile.temperature)||profile.temperature<0||profile.temperature>2)throw new Error("Temperature must be between 0 and 2.");
 if(!Number.isFinite(profile.top_p)||profile.top_p<0||profile.top_p>1)throw new Error("Top-p must be between 0 and 1.");
 if(!Number.isInteger(profile.max_tokens)||profile.max_tokens<64||profile.max_tokens>32768)throw new Error("Maximum tokens must be an integer from 64 to 32768.");
 if(!Number.isInteger(profile.timeout_seconds)||profile.timeout_seconds<5||profile.timeout_seconds>180)throw new Error("Timeout must be an integer from 5 to 180 seconds.");
 if(!Number.isInteger(profile.failover_priority)||profile.failover_priority<1||profile.failover_priority>1000)throw new Error("Failover priority must be an integer from 1 to 1000.");
 if(profile.base_url){const url=new URL(profile.base_url);if(!["http:","https:"].includes(url.protocol)||url.username||url.password)throw new Error("Endpoint must be HTTP(S) and must not contain credentials.");}
 const button=$("save-provider-profile");button.disabled=true;
 $("provider-profile-status").textContent="Saving profile…";
 try{
  const next={...providerProfiles,[id]:profile};
  const response=await api("/api/settings",{method:"PATCH",body:JSON.stringify({provider_profiles:next})});
  providerProfiles=response.provider_profiles&&typeof response.provider_profiles==="object"?response.provider_profiles:next;
  renderProviderProfiles();loadProviderProfileIntoEditor();
  $("provider-profile-status").textContent="Saved profile for "+id+". It will be used when the agent is next initialized.";
  showToast("Provider profile saved for "+id+".","status");
 }catch(error){$("provider-profile-status").textContent="Could not save profile: "+error.message;throw error;}
 finally{button.disabled=false;}
}
$("profile-provider")?.addEventListener("change",loadProviderProfileIntoEditor);
$("save-provider-profile")?.addEventListener("click",async()=>{
 try{await saveProviderProfile();}catch(error){showToast(error.message,"error");}
});
$("reset-provider-profile")?.addEventListener("click",loadProviderProfileIntoEditor);

async function loadSettings(){
 try{
  const data=await api("/api/settings");
  $("setting-mode").value=data.mode||"auto";
  $("setting-provider").value=data.active_provider||"gemini";
  $("setting-model").value=data.provider_model||"";
  $("setting-temperature").value=data.provider_temperature??0.7;
  $("setting-top-p").value=data.provider_top_p??0.95;
  $("setting-max-tokens").value=data.provider_max_tokens??2048;
  $("setting-timeout").value=data.provider_timeout_seconds??60;
  $("setting-endpoint").value=data.custom_base_url||"";
  providerProfiles=data.provider_profiles&&typeof data.provider_profiles==="object"?data.provider_profiles:{};
  populateProviderProfileChoices();renderProviderProfiles();loadProviderProfileIntoEditor();
  await loadProviderConfigurationStatus();
  $("setting-browser-domains").value=(data.browser_allowed_domains||[]).join("\n");
  try{const browser=await api("/api/browser/status");$("browser-config-status").textContent=browser.enabled?("Allowlist configured: "+browser.allowed_domain_count+" domain(s) · Playwright "+(browser.playwright_installed?"installed":"not installed")+" · actions disabled pending secure dispatch"):"Browser disabled · no domains configured";}catch(e){$("browser-config-status").textContent="Browser status unavailable: "+e.message;}
  $("custom-endpoint-field").hidden=!["custom-openai","ollama","lm-studio","vllm"].includes($("setting-provider").value);
  $("setting-critique").checked=!!data.self_critique;
  $("setting-agentic-persona").value=data.agentic_persona||"helpful";
  $("setting-agentic-planning").checked=data.agentic_planning_enabled!==false;
  $("setting-agentic-recovery").checked=data.agentic_recovery_enabled!==false;
  $("setting-proactive").checked=!!data.proactive;
  $("setting-context").value=data.max_ctx_chars||12000;
  $("setting-learning").checked=data.learning_enabled!==false;
  $("setting-auto-skills").checked=!!data.auto_extract_skills;
  $("setting-self-improve").checked=data.self_improvement_enabled!==false;
  $("setting-self-diagnostics").checked=data.self_diagnostics_enabled!==false;
  $("setting-self-repair").checked=data.self_repair_enabled!==false;
  $("setting-self-research").checked=!!data.self_research_enabled;
  $("setting-self-evaluation").checked=data.self_evaluation_enabled!==false;
  $("setting-self-goals").checked=data.self_goals_enabled!==false;
  $("setting-self-skills").checked=data.self_skills_enabled!==false;
  $("setting-self-recovery").checked=data.self_recovery_enabled!==false;
  $("setting-self-maintenance").checked=data.self_maintenance_enabled!==false;
  $("setting-self-autonomous").checked=!!data.self_autonomous_enabled;
  $("setting-self-checkpoint").checked=data.self_auto_checkpoint!==false;
  $("setting-checkpoint-retention").value=data.self_checkpoint_retention||10;
  $("setting-evaluation-interval").value=data.self_evaluation_interval_hours||24;
  $("setting-autonomy-profile").value=data.self_autonomy_profile||"maintain";
  $("setting-checkpoint-interval").value=data.self_checkpoint_interval_hours||24;
  $("setting-goal-generation").checked=data.self_goal_generation_enabled!==false;
  $("setting-max-goals").value=data.self_max_goals_per_cycle||3;
  // This guard is intentionally hard-locked in both UI and API.
  $("setting-tool-approval").checked=true;
  $("setting-long-memory").checked=data.long_term_memory_enabled!==false;
  $("setting-conversation-archive").checked=data.conversation_archive_enabled!==false;
  $("setting-workspace-tools").checked=data.workspace_tools_enabled!==false;
  $("setting-scheduler").checked=data.scheduled_tasks_enabled!==false;
  $("hf-token-state").textContent=data.hf_token_configured?"Hugging Face token configured locally.":"No Hugging Face token saved (some models may require access approval/token).";
  $("updates-enabled").checked=!!data.updates_enabled;
  $("update-interval").value=data.update_check_interval_hours||24;
  const configured=data.provider_configured||{};
  const rows=[["State directory",data.state_dir],["Models directory",data.models_dir],...Object.entries(configured).map(([k,v])=>[k,v?"API key configured":"API key missing"])];
  $("storage-list").innerHTML=rows.map(([k,v])=>'<div class="list-item"><b>'+escapeHtml(k)+'</b><p>'+escapeHtml(v)+'</p></div>').join("");
  if(configured[data.active_provider])await fetchProviderModels({auto:true});
 }catch(e){$("settings-error").textContent=e.message;}
}
$("setting-provider").addEventListener("change",()=>{$("custom-endpoint-field").hidden=!["custom-openai","ollama","lm-studio","vllm"].includes($("setting-provider").value);$("provider-model-options")?.replaceChildren();$("provider-model-count").textContent="Provider changed · model list not loaded";$("provider-model-error").textContent="";fetchProviderModels({auto:true});});

let latestUpdateInfo=null;
async function loadUpdateStatus(){
 try{
  const data=await api("/api/updates/status");
  $("updates-enabled").checked=!!data.enabled;
  $("update-interval").value=data.interval_hours||24;
  $("update-status").textContent="Channel: "+data.channel+" · "+(data.last_result||"Not checked yet")+" · install: "+data.install_method;
 }catch(e){$("update-error").textContent=e.message;}
}
$("check-updates").addEventListener("click",async()=>{
 const b=$("check-updates");b.disabled=true;b.textContent="Checking…";$("update-error").textContent="";
 try{
  latestUpdateInfo=await api("/api/updates/check",{method:"POST",body:"{}"});
  $("update-status").textContent=latestUpdateInfo.update_available
   ?"Update available: "+(latestUpdateInfo.commit_message||latestUpdateInfo.latest_sha.slice(0,12))+" · "+latestUpdateInfo.latest_sha.slice(0,12)
   :"No update detected. Latest checked commit: "+(latestUpdateInfo.latest_sha||"unknown").slice(0,12);
  $("apply-update").disabled=!latestUpdateInfo.update_available;
  if(latestUpdateInfo.commit_url){$("update-status").innerHTML=escapeHtml($("update-status").textContent)+' · <a href="'+escapeHtml(latestUpdateInfo.commit_url)+'" target="_blank" rel="noopener">View commit</a>';}
 }catch(e){$("update-error").textContent=e.message;}
 finally{b.disabled=false;b.textContent="Check for updates now";}
});
$("apply-update").addEventListener("click",async()=>{
 if(!latestUpdateInfo?.update_available)return;
 if(!confirm("Apply this update now? A state backup will be created first. Your Git working tree must be clean. You will need to restart Terminal AI after the update."))return;
 const b=$("apply-update");b.disabled=true;b.textContent="Updating…";$("update-error").textContent="";
 try{
  const result=await api("/api/updates/apply",{method:"POST",body:JSON.stringify({confirm:true})});
  $("update-status").textContent=result.message+(result.backup?" Backup: "+result.backup:"");
  latestUpdateInfo=null;
 }catch(e){$("update-error").textContent=e.message;}
 finally{b.disabled=true;b.textContent="Apply available update";}
});

$("run-maintenance-now").addEventListener("click",async()=>{
 const button=$("run-maintenance-now"),result=$("maintenance-run-result");
 if(!confirm("Run one local Self-X maintenance cycle now? It may create a checkpoint and diagnostic goals according to your current profile."))return;
 button.disabled=true;button.textContent="Running local checks…";result.textContent="Working…";$("settings-error").textContent="";
 try{
  const data=await api("/api/selfx/maintenance/run",{method:"POST"});
  result.textContent=data.summary+(data.checkpoint_id?" · checkpoint "+data.checkpoint_id:"")+
   ((data.created_goals||[]).length?" · goals: "+data.created_goals.join(", "):"");
  await loadSelfX();await loadStatus();await loadSettings();
 }catch(err){result.textContent="Maintenance failed."; $("settings-error").textContent=err.message;}
 finally{button.disabled=false;button.textContent="Run safe maintenance cycle now";}
});

$("reset-autonomy-settings").addEventListener("click",async()=>{
 if(!confirm("Reset autonomy to safe defaults? This disables autonomous maintenance and goal generation. Other model and provider settings will remain unchanged."))return;
 const button=$("reset-autonomy-settings");button.disabled=true;$("settings-error").textContent="";
 try{
  await api("/api/settings",{method:"PATCH",body:JSON.stringify({
   self_autonomous_enabled:false,self_autonomy_profile:"observe",
   self_maintenance_enabled:true,self_diagnostics_enabled:true,self_evaluation_enabled:true,
   self_recovery_enabled:true,self_auto_checkpoint:true,self_goal_generation_enabled:false,
   self_max_goals_per_cycle:3,self_evaluation_interval_hours:24,
   self_checkpoint_interval_hours:24,self_checkpoint_retention:10,
   tool_approval_required:true
  })});
  $("settings-saved").textContent="Autonomy reset to safe defaults";await loadSettings();await loadStatus();
 }catch(err){$("settings-error").textContent=err.message;}
 finally{button.disabled=false;}
});

$("settings-form").addEventListener("submit",async e=>{
 e.preventDefault();$("settings-error").textContent="";$("settings-saved").textContent="Saving…";
 try{
  await api("/api/settings",{method:"PATCH",body:JSON.stringify({
   mode:$("setting-mode").value,active_provider:$("setting-provider").value,
   provider_model:$("setting-model").value,
   provider_temperature:Number($("setting-temperature").value),
   provider_top_p:Number($("setting-top-p").value),
   provider_max_tokens:Number($("setting-max-tokens").value),
   provider_timeout_seconds:Number($("setting-timeout").value),
   custom_base_url:$("setting-endpoint").value,
   browser_allowed_domains:$("setting-browser-domains").value.split(String.fromCharCode(10)).flatMap(x=>x.split(",")).map(x=>x.trim()).filter(Boolean),
   api_key:$("setting-api-key").value,hf_token:$("setting-hf-token").value,
   self_critique:$("setting-critique").checked,
   agentic_persona:$("setting-agentic-persona").value,
   agentic_planning_enabled:$("setting-agentic-planning").checked,
   agentic_recovery_enabled:$("setting-agentic-recovery").checked,
   proactive:$("setting-proactive").checked,max_ctx_chars:Number($("setting-context").value),
   updates_enabled:$("updates-enabled").checked,
   update_check_interval_hours:Number($("update-interval").value),
   learning_enabled:$("setting-learning").checked,
   auto_extract_skills:$("setting-auto-skills").checked,
   self_improvement_enabled:$("setting-self-improve").checked,
   self_diagnostics_enabled:$("setting-self-diagnostics").checked,
   self_repair_enabled:$("setting-self-repair").checked,
   self_research_enabled:$("setting-self-research").checked,
   self_evaluation_enabled:$("setting-self-evaluation").checked,
   self_goals_enabled:$("setting-self-goals").checked,
   self_skills_enabled:$("setting-self-skills").checked,
   self_recovery_enabled:$("setting-self-recovery").checked,
   self_maintenance_enabled:$("setting-self-maintenance").checked,
   self_autonomous_enabled:$("setting-self-autonomous").checked,
   self_auto_checkpoint:$("setting-self-checkpoint").checked,
   self_checkpoint_retention:Number($("setting-checkpoint-retention").value),
   self_evaluation_interval_hours:Number($("setting-evaluation-interval").value),
   self_autonomy_profile:$("setting-autonomy-profile").value,
   self_checkpoint_interval_hours:Number($("setting-checkpoint-interval").value),
   self_goal_generation_enabled:$("setting-goal-generation").checked,
   self_max_goals_per_cycle:Number($("setting-max-goals").value),
   tool_approval_required:$("setting-tool-approval").checked,
   long_term_memory_enabled:$("setting-long-memory").checked,
   conversation_archive_enabled:$("setting-conversation-archive").checked,
   workspace_tools_enabled:$("setting-workspace-tools").checked,
   scheduled_tasks_enabled:$("setting-scheduler").checked
  })});
  $("setting-hf-token").value="";
  $("settings-saved").textContent="Saved";$("setting-api-key").value="";
  await loadSettings();await loadProviderConfigurationStatus();await loadStatus();
 }catch(err){$("settings-saved").textContent="";$("settings-error").textContent=err.message;}
});
async function loadSelfX(){
 try{
  const data=await api("/api/selfx/status");
  const latest=data.latest_diagnostic;
  $("selfx-health").textContent=latest?latest.status:"Not checked";
  $("selfx-score").textContent=data.latest_evaluation?data.latest_evaluation.score+"/100":"Not evaluated";
  $("selfx-research-count").textContent=(data.research||[]).length;
  $("selfx-checkpoint-count").textContent=(data.checkpoints||[]).length;
  $("selfx-capabilities").innerHTML=(data.capabilities||[]).map(x=>'<div class="list-item"><div class="row" style="justify-content:space-between"><b>'+escapeHtml(x.name)+'</b><span class="badge">'+escapeHtml(x.status)+'</span></div><p>'+escapeHtml(x.mode)+'</p></div>').join("");
  $("selfx-events").innerHTML=(data.events||[]).length?(data.events||[]).map(x=>'<div class="list-item"><b>'+escapeHtml(x.kind)+'</b><p>'+escapeHtml(x.summary)+'</p><p class="muted">'+new Date(x.created_at*1000).toLocaleString()+'</p></div>').join(""):'<div class="empty">No Self-X activity recorded yet.</div>';
  $("selfx-research-list").innerHTML=(data.research||[]).length?(data.research||[]).map(x=>'<div class="list-item"><div class="row" style="justify-content:space-between"><b>'+escapeHtml(x.title)+'</b><span class="badge">'+escapeHtml(x.status)+'</span></div>'+(x.source_url?'<p><a href="'+escapeHtml(x.source_url)+'" target="_blank" rel="noopener noreferrer">'+escapeHtml(x.source_url)+'</a></p>':'')+'<p>'+escapeHtml(x.notes||"No notes")+'</p><p class="muted">'+new Date(x.created_at*1000).toLocaleString()+'</p></div>').join(""):'<div class="empty">No research notes saved.</div>';
  $("selfx-checkpoint-list").innerHTML=(data.checkpoints||[]).length?(data.checkpoints||[]).map(x=>'<div class="list-item"><div class="row" style="justify-content:space-between"><b>'+escapeHtml(x.id)+'</b><span class="badge">'+escapeHtml(x.file_count)+' files</span></div><p class="muted">'+new Date(x.created_at*1000).toLocaleString()+'</p><button class="btn danger" data-selfx-restore="'+escapeHtml(x.id)+'">Restore checkpoint</button></div>').join(""):'<div class="empty">No recovery checkpoints yet.</div>';
  if(latest){$("selfx-diagnostic-list").innerHTML=(latest.checks||[]).map(x=>'<div class="list-item"><div class="row" style="justify-content:space-between"><b>'+escapeHtml(x.name)+'</b><span class="badge">'+(x.ok?"PASS":"CHECK")+'</span></div><p>'+escapeHtml(x.detail)+'</p></div>').join("");}
  const ev=data.latest_evaluation;
  if(ev){$("selfx-evaluation-list").innerHTML='<div class="list-item"><b>Score: '+escapeHtml(ev.score)+'/100</b><p>'+escapeHtml(ev.scope)+'</p></div>'+(ev.checks||[]).map(x=>'<div class="list-item"><b>'+escapeHtml(x.name)+'</b><p>'+(x.passed?"Passed":"Needs attention")+'</p></div>').join("");}
  $("selfx-recovery-error").textContent="";
 }catch(e){$("selfx-recovery-error").textContent=e.message;}
}
async function loadTaskLifecycle(){
 const host=$("task-lifecycle-list"),err=$("task-lifecycle-error");
 try{
  const data=await api("/api/agentic/tasks?limit=50");
  const tasks=data.tasks||[];
  host.innerHTML=tasks.length?tasks.map(t=>{
   const status=escapeHtml(t.status),id=escapeHtml(t.id);
   let actions='<button class="btn" data-task-refresh="'+id+'">Sync status</button>';
   if(t.status==="planned")actions+='<button class="btn primary" data-task-prepare="'+id+'">Prepare terminal operation</button><button class="btn" data-task-link="'+id+'">Link existing operation</button>';
   if(t.status==="awaiting_approval"||t.status==="pending")actions+='<button class="btn primary" data-go="command-control">Review in Command Control</button>';
   if(t.status==="approved"&&t.operation_tool==="terminal"&&t.operation_name==="execute")actions+='<button class="btn primary" data-task-execute="'+id+'" data-operation-id="'+escapeHtml(t.operation_id)+'">Execute approved command</button>';
   if(t.status==="executed")actions+='<button class="btn primary" data-task-verify="'+id+'">Verify result</button>';
   if(t.status==="verified")actions+='<button class="btn primary" data-task-review="'+id+'">Review outcome</button>';
   if(t.operation_id&&["failed","expired"].includes(t.execution_status))actions+='<button class="btn" data-task-recovery="'+id+'">Draft recovery proposal</button>';
   const recovery=(t.recovery_proposals||[]).map(p=>'<div class="list-item"><b>Recovery proposal '+escapeHtml(p.attempt)+' · '+escapeHtml(p.failure_category)+'</b><p>'+escapeHtml(p.error_summary)+'</p><p class="muted">Policy: '+escapeHtml(p.retry_policy)+' · Status: '+escapeHtml(p.status)+'</p><ol>'+((p.recovery_steps||[]).map(s=>'<li>'+escapeHtml(s)+'</li>').join(""))+'</ol>'+(p.status==="proposed"?'<button class="btn" data-recovery-review="'+id+'" data-recovery-proposal="'+escapeHtml(p.id)+'">Review proposal</button>':'')+(p.status==="verified"?'<button class="btn primary" data-recovery-outcome-review="'+id+'" data-recovery-proposal="'+escapeHtml(p.id)+'">Review verified outcome</button>':'')+(p.outcome_review?'<p><b>Reviewed outcome:</b> '+escapeHtml(p.outcome_review.outcome)+' · rating '+escapeHtml(p.outcome_review.rating)+'/5 · reviewer '+escapeHtml(p.outcome_review.reviewer)+'</p>':'')+(p.status==="approved_for_replanning"?'<button class="btn primary" data-recovery-queue="'+id+'" data-recovery-proposal="'+escapeHtml(p.id)+'">Create fresh approved operation</button>':'')+(p.new_operation_id?'<p>New Command Control operation: <code>'+escapeHtml(p.new_operation_id)+'</code> · status: '+escapeHtml(p.new_operation_status||"unknown")+'</p>':'')+(p.verification?'<p><b>Recovery verification:</b> '+(p.verification.passed?"Passed":"Failed")+' · '+escapeHtml(p.verification.evidence)+'</p>':"")+(p.new_operation_id&&p.new_operation_status==="executed"&&!p.verification?'<button class="btn primary" data-recovery-verify="'+id+'" data-recovery-proposal="'+escapeHtml(p.id)+'">Verify recovery result</button>':"")+'</div>').join("");
   const steps=(t.steps||[]).map(s=>'<li>'+escapeHtml(s)+'</li>').join("");
   const verify=t.verification?'<p><b>Verification:</b> '+(t.verification.passed?"Passed":"Failed")+' · '+escapeHtml(t.verification.evidence)+'</p>':"";
   const review=t.review?'<p><b>Reviewed:</b> '+escapeHtml(t.review.outcome)+' · rating '+escapeHtml(t.review.rating)+'/5</p>':"";
   return '<div class="list-item"><div class="row" style="justify-content:space-between"><b>'+id.slice(0,12)+' · '+escapeHtml(t.goal)+'</b><span class="badge">'+status+'</span></div><p class="muted">Risk: '+escapeHtml(t.risk)+' · Type: '+escapeHtml(t.task_type)+' · Algorithm: '+escapeHtml(t.algorithm)+' · Updated: '+escapeHtml(new Date(t.updated_at*1000).toLocaleString())+'</p>'+(t.operation_id?'<p>Linked operation: <code>'+escapeHtml(t.operation_id)+'</code> · status: '+escapeHtml(t.execution_status||"unknown")+'</p>':'<p class="muted">No Command Control operation linked.</p>')+'<details><summary>Planned steps</summary><ol>'+steps+'</ol></details>'+verify+review+(recovery?'<details><summary>Recovery proposals ('+(t.recovery_proposals||[]).length+')</summary>'+recovery+'</details>':'')+'<div class="row" style="margin-top:10px">'+actions+'</div></div>';
  }).join(""):'<div class="empty">No tracked tasks yet. Create a plan to start a lifecycle record.</div>';
 }catch(e){err.textContent=e.message;}
}
$("task-lifecycle-refresh").addEventListener("click",loadTaskLifecycle);
$("task-lifecycle-form").addEventListener("submit",async e=>{
 e.preventDefault();const b=$("task-lifecycle-create");b.disabled=true;b.textContent="Creating…";$("task-lifecycle-error").textContent="";
 try{
  const result=await api("/api/agentic/tasks",{method:"POST",body:JSON.stringify({goal:$("task-lifecycle-goal").value,risk:$("task-lifecycle-risk").value,complexity:Number($("task-lifecycle-complexity").value),has_external_side_effects:false,evidence_available:false})});
  $("task-lifecycle-goal").value="";
  $("task-lifecycle-error").textContent="Tracked plan created. No tools were executed.";
  await loadTaskLifecycle();
 }catch(err){$("task-lifecycle-error").textContent=err.message;}
 finally{b.disabled=false;b.textContent="Create tracked plan";}
});
$("task-lifecycle-list").addEventListener("click",async e=>{
 const b=e.target.closest("button");if(!b)return;
 const run=async(path,body)=>api(path,{method:"POST",body:JSON.stringify(body)});
 try{
  if(b.dataset.taskRefresh){b.disabled=true;await api("/api/agentic/tasks/"+encodeURIComponent(b.dataset.taskRefresh));await loadTaskLifecycle();return;}
  if(b.dataset.taskPrepare){
   const raw=prompt('Enter the exact argv as a JSON array (no shell strings), e.g. ["pytest","-q"]:','["pytest","-q"]');
   if(raw===null)return;
   let argv;try{argv=JSON.parse(raw);}catch(_){$("task-lifecycle-error").textContent="argv must be valid JSON.";return;}
   if(!Array.isArray(argv)||!argv.length||argv.some(x=>typeof x!=="string")){$("task-lifecycle-error").textContent="argv must be a non-empty array of strings.";return;}
   const cwd=prompt("Workspace-relative working directory",".");if(cwd===null)return;
   const timeoutText=prompt("Timeout in seconds (1–120)","30");if(timeoutText===null)return;
   const timeout=Number(timeoutText);if(!Number.isInteger(timeout)||timeout<1||timeout>120){$("task-lifecycle-error").textContent="Timeout must be an integer from 1 to 120.";return;}
   if(!confirm("Queue this exact command for approval? It will NOT execute until you approve it in Command Control and then click Execute approved command."))return;
   const result=await run("/api/agentic/tasks/"+encodeURIComponent(b.dataset.taskPrepare)+"/terminal-operation",{argv,cwd,timeout});
   $("task-lifecycle-result").textContent=JSON.stringify(result,null,2);
   $("task-lifecycle-error").textContent="Operation queued. Open Command Control Center, approve the exact operation, then return and sync task status.";
  }else if(b.dataset.taskExecute){
   if(!confirm("Execute the exact command you previously approved? This consumes that approval. No shell is used."))return;
   b.disabled=true;b.textContent="Executing…";
   const result=await api("/api/terminal/execute/"+encodeURIComponent(b.dataset.operationId),{method:"POST",body:"{}"});
   $("task-lifecycle-result").textContent=JSON.stringify(result,null,2);
   $("task-lifecycle-error").textContent=result.returncode===0?"Command returned exit code 0. Sync task status, independently verify the result, then review the outcome.":"Command failed with exit code "+result.returncode+". Sync task status; do not mark it successful. Use the recovery proposal workflow if needed.";
  }else if(b.dataset.taskLink){
   const id=prompt("Paste the existing Command Control operation ID. This only links it; it does not approve or execute it.");
   if(!id)return;
   await run("/api/agentic/tasks/"+encodeURIComponent(b.dataset.taskLink)+"/operation",{operation_id:id.trim()});
  }else if(b.dataset.taskVerify){
   const evidence=prompt("Describe the independent verification evidence (do not include secrets):");
   if(!evidence||!evidence.trim())return;
   const passed=confirm("Did the independent check pass? Choose Cancel to stop; OK means passed.");
   await run("/api/agentic/tasks/"+encodeURIComponent(b.dataset.taskVerify)+"/verify",{passed,evidence:evidence.trim(),verifier:"operator"});
  }else if(b.dataset.taskReview){
   const outcome=prompt("Reviewed outcome: success, partial, or failure","success");
   if(!["success","partial","failure"].includes(outcome))return;
   const ratingText=prompt("Reviewer rating from 1 to 5","4"),rating=Number(ratingText);
   if(!Number.isInteger(rating)||rating<1||rating>5)return;
   await run("/api/agentic/tasks/"+encodeURIComponent(b.dataset.taskReview)+"/review",{outcome,rating,reviewer:"operator"});
  }else if(b.dataset.recoveryReview){
   const decision=prompt("Review proposal: type approve to approve replanning only, or reject to reject.","reject");
   if(decision!=="approve"&&decision!=="reject")return;
   await run("/api/agentic/tasks/"+encodeURIComponent(b.dataset.recoveryReview)+"/recovery-proposals/"+encodeURIComponent(b.dataset.recoveryProposal)+"/review",{decision,reviewer:"operator",note:"Reviewed in Self-X task lifecycle UI"});
  }else if(b.dataset.recoveryOutcomeReview){
   const outcome=prompt("Reviewed recovery outcome: success, partial, or failure","success");
   if(!["success","partial","failure"].includes(outcome))return;
   const ratingText=prompt("Reviewer rating from 1 to 5","4"),rating=Number(ratingText);
   if(!Number.isInteger(rating)||rating<1||rating>5)return;
   const note=prompt("Short review note (optional, max 500 characters; no secrets)","")||"";
   await run("/api/agentic/tasks/"+encodeURIComponent(b.dataset.recoveryOutcomeReview)+"/recovery-proposals/"+encodeURIComponent(b.dataset.recoveryProposal)+"/review-outcome",{outcome,rating,reviewer:"operator",note});
  }else if(b.dataset.recoveryVerify){
   const evidence=prompt("Describe independent verification evidence (max 4,000 chars; no secrets):");
   if(!evidence||!evidence.trim())return;
   const passed=confirm("Did the independent verification pass? OK = passed; Cancel = failed.");
   await run("/api/agentic/tasks/"+encodeURIComponent(b.dataset.recoveryVerify)+"/recovery-proposals/"+encodeURIComponent(b.dataset.recoveryProposal)+"/verify",{passed,evidence:evidence.trim(),verifier:"operator"});
  }else if(b.dataset.recoveryQueue){
   const tool=prompt("Enter the exact registered tool name for the new operation (tool and operation must match):");
   if(!tool||!tool.trim())return;
   const raw=prompt("Enter the exact JSON arguments for the new operation.");
   if(raw===null)return;
   let args;try{args=JSON.parse(raw||"{}");}catch(_){$("task-lifecycle-error").textContent="Arguments must be valid JSON.";return;}
   if(!args||Array.isArray(args)||typeof args!=="object"){$("task-lifecycle-error").textContent="Arguments must be a JSON object.";return;}
   if(!confirm("Queue a NEW Command Control operation for human approval? This will not execute it."))return;
   const taskId=encodeURIComponent(b.dataset.recoveryQueue),proposalId=encodeURIComponent(b.dataset.recoveryProposal);
   const result=await run("/api/agentic/tasks/"+taskId+"/recovery-proposals/"+proposalId+"/operation",{tool:tool.trim(),operation:tool.trim(),arguments:args});
   alert("New operation queued for separate approval. Execution started: "+result.execution_started);
  }else if(b.dataset.taskRecovery){
   const category=prompt("Failure category: timeout, transient_network, rate_limit, missing_dependency, validation, permission, destructive, unknown","timeout");
   if(!["timeout","transient_network","rate_limit","missing_dependency","validation","permission","destructive","unknown"].includes(category))return;
   const summary=prompt("Short error summary (max 500 chars; do not include secrets):");
   if(!summary||!summary.trim())return;
   const taskId=encodeURIComponent(b.dataset.taskRecovery);
   const result=await run("/api/agentic/tasks/"+taskId+"/recovery-proposals",{failure_category:category,error_summary:summary.trim()});
   const proposal=result.proposal;
   alert("Recovery proposal (not executed):\n"+proposal.recovery_steps.join("\n"));
   const decision=prompt("Review proposal: type approve to approve replanning only, or reject to reject. Leave blank to keep it pending.","");
   if(decision==="approve"||decision==="reject"){
    await run("/api/agentic/tasks/"+taskId+"/recovery-proposals/"+encodeURIComponent(proposal.id)+"/review",{decision,reviewer:"operator",note:"Reviewed in Self-X task lifecycle UI"});
   }
  }else return;
  await loadTaskLifecycle();await loadAgenticConsole();
 }catch(err){$("task-lifecycle-error").textContent=err.message;}
});
async function loadAutonomyJobs(){
 const host=$("autonomy-jobs");if(!host)return;
 try{
  const data=await api("/api/agentic/autonomy/jobs");
  const counts=data.queue?.by_status||{};
  const summary=Object.entries(counts).map(([key,value])=>escapeHtml(key)+": "+escapeHtml(value)).join(" · ")||"No jobs yet";
  host.innerHTML='<div class="list-item"><p>'+summary+' · Max attempts: '+escapeHtml(data.queue?.max_attempts??2)+'</p></div>'+
   ((data.jobs||[]).length?data.jobs.map(job=>'<div class="list-item"><b>'+escapeHtml(job.status)+' · '+escapeHtml(job.progress||"")+'</b><p>'+escapeHtml(job.payload?.goal||"")+'</p><p class="muted">Attempts: '+escapeHtml(job.attempts)+'/'+escapeHtml(job.max_attempts)+' · Updated: '+escapeHtml(new Date(job.updated_at*1000).toLocaleString())+'</p>'+(["queued","running"].includes(job.status)?'<button class="btn" type="button" data-autonomy-cancel="'+escapeHtml(job.id)+'">Cancel job</button>':'')+(job.error?'<p class="error">'+escapeHtml(job.error)+'</p>':'')+'</div>').join(""):'<div class="empty">No queued autonomy jobs.</div>');
 }catch(error){host.innerHTML='<div class="error">'+escapeHtml(error.message)+'</div>';}
}
async function loadAutonomyStatus(){
 const host=$("autonomy-status");if(!host)return;
 try{
  const data=await api("/api/agentic/autonomy/status");
  const counts=data.history?.by_status||{};
  host.innerHTML='<div class="list-item"><b>Mode: '+escapeHtml(data.mode||"unknown")+'</b><p>Autonomous runs: '+escapeHtml(data.history?.count??0)+' · Completed read-only actions: '+escapeHtml(counts.completed||0)+' · Plans awaiting approval: '+escapeHtml(counts.awaiting_approval||0)+'</p><p>Automatic actions: '+escapeHtml((data.automatic_actions||[]).join(", "))+'</p><p>External side effects: '+escapeHtml(data.external_side_effects||"approval required")+'</p></div>'+
   ((data.history?.recent||[]).length?data.history.recent.map(item=>'<div class="list-item"><b>'+escapeHtml(item.action)+' · '+escapeHtml(item.status)+'</b><p>'+escapeHtml(item.goal)+'</p><p class="muted">'+escapeHtml(item.decision)+'</p></div>').join(""):'<div class="empty">No autonomous runs recorded yet.</div>');
 }catch(error){host.innerHTML='<div class="error">'+escapeHtml(error.message)+'</div>';}
 await loadAutonomyJobs();
}
$("autonomy-refresh")?.addEventListener("click",loadAutonomyStatus);
$("autonomy-queue-button")?.addEventListener("click",async()=>{
 const button=$("autonomy-queue-button"),error=$("autonomy-error");
 button.disabled=true;error.textContent="";
 try{
  const payload={goal:$("autonomy-goal").value.trim(),complexity:Number($("autonomy-complexity").value)};
  const action=$("autonomy-action").value;if(action)payload.action=action;
  const data=await api("/api/agentic/autonomy/jobs",{method:"POST",body:JSON.stringify(payload)});
  $("autonomy-result").textContent=JSON.stringify(data,null,2);
  error.textContent="Queued. The background worker only performs registered read-only actions or creates plans.";
  await loadAutonomyJobs();
 }catch(err){error.textContent=err.message;}
 finally{button.disabled=false;}
});
$("autonomy-jobs")?.addEventListener("click",async event=>{
 const button=event.target.closest("[data-autonomy-cancel]");if(!button)return;
 button.disabled=true;
 try{await api("/api/agentic/autonomy/jobs/"+encodeURIComponent(button.dataset.autonomyCancel)+"/cancel",{method:"POST",body:"{}"});await loadAutonomyJobs();}
 catch(err){$("autonomy-error").textContent=err.message;button.disabled=false;}
});
$("autonomy-run-form")?.addEventListener("submit",async event=>{
 event.preventDefault();
 const button=$("autonomy-run-button"),error=$("autonomy-error"),result=$("autonomy-result");
 button.disabled=true;button.textContent="Running…";error.textContent="";result.textContent="Decision cycle running…";
 try{
  const payload={goal:$("autonomy-goal").value.trim(),complexity:Number($("autonomy-complexity").value)};
  const action=$("autonomy-action").value;if(action)payload.action=action;
  const data=await api("/api/agentic/autonomy/run",{method:"POST",body:JSON.stringify(payload)});
  result.textContent=JSON.stringify(data,null,2);
  error.textContent=data.run?.status==="completed"?"Completed a registered read-only action automatically.": "Plan recorded. Any side effects remain approval-gated.";
  await loadAutonomyStatus();await loadTaskLifecycle();
 }catch(err){error.textContent=err.message;result.textContent="The autonomous run did not complete.";}
 finally{button.disabled=false;button.textContent="Run autonomous decision cycle";}
});
async function loadAgenticConsole(){
 const showError=(id,error)=>{const node=$(id);if(node)node.textContent=error?error.message:"";};
 showError("agentic-console-error",null);
 const results=await Promise.allSettled([
  api("/api/agentic/status"),
  api("/api/agentic/learning/summary"),
  api("/api/agentic/world-model"),
  api("/api/control/pending?status=pending&limit=100")
 ]);
 const [status,learning,world,pending]=results;
 if(status.status==="fulfilled"){
  $("agentic-world-count").textContent=String(status.value.world_facts??(world.status==="fulfilled"?world.value.count:"—"));
  $("agentic-learning-count").textContent=String(status.value.learning_records??(learning.status==="fulfilled"?learning.value.count:"—"));
 }else showError("agentic-console-error",status.reason);
 if(pending.status==="fulfilled")$("agentic-pending-count").textContent=String((pending.value.operations||[]).length);
 else $("agentic-pending-count").textContent="Unavailable";
 if(learning.status==="fulfilled"){
  const groups=learning.value.groups||[];
  $("agentic-learning-summary").innerHTML='<div class="list-item"><b>Verified outcomes: '+escapeHtml(learning.value.count??0)+'</b><p>Retained records: '+escapeHtml(learning.value.retained??learning.value.count??0)+'. Learning changes recommendations only; it cannot grant permissions.</p></div>'+
   (groups.length?groups.slice(0,8).map(g=>'<div class="list-item"><div class="row" style="justify-content:space-between"><b>'+escapeHtml(g.task_type)+' · '+escapeHtml(g.algorithm)+'</b><span class="badge">'+escapeHtml(g.samples)+' reviewed</span></div><p>Success score: '+escapeHtml(Number(g.success_score||0).toFixed(2))+' · Average rating: '+escapeHtml(Number(g.average_rating||0).toFixed(1))+'/5</p></div>').join(""):'<div class="empty">No reviewed outcome groups yet. Only explicitly verified outcomes are eligible for learning.</div>');
 }else $("agentic-learning-summary").innerHTML='<div class="error">'+escapeHtml(learning.reason.message)+'</div>';
 if(world.status==="fulfilled"){
  const facts=world.value.facts||[];$("agentic-world-count").textContent=String(world.value.count??facts.length);
  $("agentic-world-list").innerHTML=facts.length?facts.slice(0,100).map(f=>'<div class="list-item"><div class="row" style="justify-content:space-between"><b>'+escapeHtml(f.subject)+' · '+escapeHtml(f.predicate)+'</b><span class="badge">'+escapeHtml(Number(f.confidence||0).toFixed(2))+' confidence</span></div><p>'+escapeHtml(JSON.stringify(f.value))+'</p><p class="muted">Source: '+escapeHtml(f.source||"unknown")+' · Observed: '+escapeHtml(new Date(f.observed_at*1000).toLocaleString())+(f.expires_at?' · Expires: '+escapeHtml(new Date(f.expires_at*1000).toLocaleString()):' · No expiry')+'</p></div>').join(""):'<div class="empty">No observations recorded. Add evidence with the form above.</div>';
 }else $("agentic-world-list").innerHTML='<div class="error">'+escapeHtml(world.reason.message)+'</div>';
}
$("agentic-console-refresh").addEventListener("click",loadAgenticConsole);
$("agentic-world-refresh").addEventListener("click",loadAgenticConsole);
$("agentic-plan-form").addEventListener("submit",async e=>{
 e.preventDefault();const b=$("agentic-plan-submit");b.disabled=true;b.textContent="Planning…";$("agentic-plan-error").textContent="";
 try{
  const result=await api("/api/agentic/plan",{method:"POST",body:JSON.stringify({goal:$("agentic-plan-goal").value,risk:$("agentic-plan-risk").value,complexity:Number($("agentic-plan-complexity").value),has_external_side_effects:false,evidence_available:false})});
  const p=result.plan,signals=p.adaptive_signals||{};
  $("agentic-plan-result").innerHTML='<div class="list-item"><div class="row" style="justify-content:space-between"><b>'+escapeHtml(p.strategy)+' · '+escapeHtml(p.risk)+' risk</b><span class="badge">'+(p.needs_approval?"Approval required":"Review before action")+'</span></div><p>'+escapeHtml(p.rationale)+'</p><p class="muted">Task family: '+escapeHtml(signals.task_type||"unknown")+' · Algorithm: '+escapeHtml(signals.algorithm||"default")+' · Execution started: No</p><ol>'+(p.steps||[]).map(step=>'<li>'+escapeHtml(step)+'</li>').join("")+'</ol></div>';
 }catch(err){$("agentic-plan-error").textContent=err.message;}
 finally{b.disabled=false;b.textContent="Preview adaptive plan";}
});
$("agentic-world-form").addEventListener("submit",async e=>{
 e.preventDefault();$("agentic-world-error").textContent="";
 let value;try{value=JSON.parse($("agentic-world-value").value);}catch(_){$("agentic-world-error").textContent="Observation value must be valid JSON.";return;}
 const ttlText=$("agentic-world-ttl").value;
 const payload={subject:$("agentic-world-subject").value,predicate:$("agentic-world-predicate").value,value,source:$("agentic-world-source").value,confidence:Number($("agentic-world-confidence").value)};
 if(ttlText!=="")payload.ttl_seconds=Number(ttlText);
 try{await api("/api/agentic/world-model/observe",{method:"POST",body:JSON.stringify(payload)});$("agentic-world-value").value="";await loadAgenticConsole();}
 catch(err){$("agentic-world-error").textContent=err.message;}
});
$("selfx-refresh").addEventListener("click",loadSelfX);
$("selfx-diagnose").addEventListener("click",async()=>{
 const b=$("selfx-diagnose");b.disabled=true;b.textContent="Checking…";
 try{const r=await api("/api/selfx/diagnose",{method:"POST",body:"{}"});const d=r.diagnostic;$("selfx-health").textContent=d.status;$("selfx-diagnostic-list").innerHTML=(d.checks||[]).map(x=>'<div class="list-item"><div class="row" style="justify-content:space-between"><b>'+escapeHtml(x.name)+'</b><span class="badge">'+(x.ok?"PASS":"CHECK")+'</span></div><p>'+escapeHtml(x.detail)+'</p></div>').join("");await loadSelfX();}
 catch(e){$("selfx-recovery-error").textContent=e.message;}finally{b.disabled=false;b.textContent="Run checks";}
});
$("selfx-evaluate").addEventListener("click",async()=>{
 const b=$("selfx-evaluate");b.disabled=true;b.textContent="Evaluating…";
 try{const r=await api("/api/selfx/evaluate",{method:"POST",body:"{}"});const ev=r.evaluation;$("selfx-score").textContent=ev.score+"/100";$("selfx-evaluation-list").innerHTML='<div class="list-item"><b>Score: '+escapeHtml(ev.score)+'/100</b><p>'+escapeHtml(ev.scope)+'</p></div>'+(ev.checks||[]).map(x=>'<div class="list-item"><b>'+escapeHtml(x.name)+'</b><p>'+(x.passed?"Passed":"Needs attention")+'</p></div>').join("");await loadSelfX();}
 catch(e){$("selfx-recovery-error").textContent=e.message;}finally{b.disabled=false;b.textContent="Evaluate readiness";}
});
$("selfx-research-form").addEventListener("submit",async e=>{
 e.preventDefault();$("selfx-research-error").textContent="";
 try{await api("/api/selfx/research",{method:"POST",body:JSON.stringify({title:$("selfx-research-title").value,source_url:$("selfx-research-url").value,notes:$("selfx-research-notes").value})});$("selfx-research-title").value="";$("selfx-research-url").value="";$("selfx-research-notes").value="";await loadSelfX();}
 catch(err){$("selfx-research-error").textContent=err.message;}
});
$("selfx-checkpoint").addEventListener("click",async()=>{
 const b=$("selfx-checkpoint");b.disabled=true;b.textContent="Creating…";
 try{const r=await api("/api/selfx/checkpoints",{method:"POST",body:"{}"});$("selfx-recovery-error").textContent="Checkpoint created: "+r.checkpoint.id;await loadSelfX();}
 catch(e){$("selfx-recovery-error").textContent=e.message;}finally{b.disabled=false;b.textContent="Create checkpoint";}
});
$("selfx-checkpoint-list").addEventListener("click",async e=>{
 const b=e.target.closest("[data-selfx-restore]");if(!b)return;
 const id=b.dataset.selfxRestore;
 if(!confirm("Restore checkpoint "+id+"? Current state will first be saved to a safety checkpoint. The active agent will be reset."))return;
 b.disabled=true;
 try{const r=await api("/api/selfx/restore",{method:"POST",body:JSON.stringify({checkpoint_id:id,confirm:true})});$("selfx-recovery-error").textContent="Restored. Safety checkpoint: "+r.safety_checkpoint+". Reopen chat to reinitialize the agent.";await loadSelfX();}
 catch(err){$("selfx-recovery-error").textContent=err.message;b.disabled=false;}
});

async function loadSelf(){
 try{
  const state=await api("/api/self/status");
  $("self-identity").value=state.identity||"Terminal AI";
  $("self-mission").value=state.mission||"";
  $("self-reflection-enabled").checked=!!state.reflection_enabled;
  $("self-stats").innerHTML=[["Backend",state.backend||"Not initialized"],["Mode",state.mode],["Initialized",state.agent_initialized?"Yes":"No"]].map(([k,v])=>'<div class="stat"><small>'+escapeHtml(k)+'</small><strong>'+escapeHtml(v)+'</strong></div>').join("");
  $("self-capabilities").innerHTML=["Reports configured backend and mode","Reviews current limitations and risks","Stores latest review locally","Cannot grant itself permissions"].map(x=>'<div class="list-item">'+escapeHtml(x)+'</div>').join("");
  if(state.last_reflection){$("self-reflection-text").textContent=state.last_reflection.text||"";$("self-reflection-time").textContent=new Date(state.last_reflection.created_at*1000).toLocaleString();}
  else{$("self-reflection-text").textContent="Run a self-review to inspect capabilities, limitations, risks and possible improvements.";$("self-reflection-time").textContent="No review yet";}
 }catch(e){$("self-error").textContent=e.message;}
}
$("self-save").addEventListener("click",async()=>{
 try{$("self-error").textContent="";await api("/api/settings",{method:"PATCH",body:JSON.stringify({self_identity:$("self-identity").value,self_mission:$("self-mission").value,self_reflection_enabled:$("self-reflection-enabled").checked})});await loadSelf();}
 catch(e){$("self-error").textContent=e.message;}
});
$("self-reflect").addEventListener("click",async()=>{
 const b=$("self-reflect");b.disabled=true;b.textContent="Reviewing…";$("self-error").textContent="";
 try{const data=await api("/api/self/reflect",{method:"POST",body:"{}"});$("self-reflection-text").textContent=data.reflection.text;$("self-reflection-time").textContent=new Date(data.reflection.created_at*1000).toLocaleString();}
 catch(e){$("self-error").textContent=e.message;}
 finally{b.disabled=false;b.textContent="Run self-review";}
});


$("test-provider").addEventListener("click",async()=>{
 const b=$("test-provider");b.disabled=true;b.textContent="Testing…";$("provider-test-result").textContent="Contacting provider…";$("settings-error").textContent="";
 try{
  const result=await api("/api/providers/test",{method:"POST",body:JSON.stringify({provider_id:$("setting-provider").value,model:$("setting-model").value,base_url:$("setting-endpoint").value,api_key:$("setting-api-key").value})});
  $("provider-test-result").textContent="Connected · "+result.elapsed_ms+" ms";
 }catch(e){$("provider-test-result").textContent="Connection failed";$("settings-error").textContent=e.message;}
 finally{b.disabled=false;b.textContent="Test provider";}
});

loadStatus();
loadUpdateStatus();
setInterval(async()=>{
 try{
  const data=await api("/api/updates/status");
  if(data.enabled && data.interval_hours){await api("/api/updates/check",{method:"POST",body:"{}"});}
 }catch{}
}, 60*60*1000);



async function loadSkills(){
 const list=$("skill-list");list.innerHTML='<div class="empty">Loading local skills…</div>'; $("skill-error").textContent="";
 try{
  const data=await api("/api/skills");const skills=data.skills||[];
  list.innerHTML=skills.length?skills.slice().reverse().map(s=>'<div class="list-item"><div class="row" style="justify-content:space-between"><b>'+escapeHtml(s.name)+'</b><button class="btn danger" data-delete-skill="'+escapeHtml(s.name)+'">Delete</button></div>'+(s.context?'<p>'+escapeHtml(s.context)+'</p>':'')+'<ol>'+((s.steps||[]).map(step=>'<li>'+escapeHtml(step)+'</li>').join(''))+'</ol><p class="muted">Saved locally'+(s.t?' · '+escapeHtml(new Date(s.t*1000).toLocaleString()):'')+'</p></div>').join(''):'<div class="empty">No skills yet. Save a tested procedure using the form.</div>';
 }catch(e){list.innerHTML='<div class="error">'+escapeHtml(e.message)+'</div>';}
}
$("refresh-skills").addEventListener("click",loadSkills);
$("skill-generate-form").addEventListener("submit",async e=>{
 e.preventDefault();const button=$("skill-generate-btn");button.disabled=true;button.textContent="Generating draft…";$("skill-error").textContent="";$("skill-draft-notice").textContent="";
 try{
  const result=await api("/api/skills/generate",{method:"POST",body:JSON.stringify({task:$("skill-generate-task").value,context:$("skill-generate-context").value})});
  const d=result.draft||{};$("skill-name").value=d.name||"";$("skill-context").value=d.context||"";$("skill-steps").value=(d.steps||[]).join("\n");
  $("skill-draft-notice").textContent=result.notice||"Review and edit the draft, then press Save skill.";
 }catch(err){$("skill-error").textContent=err.message;}
 finally{button.disabled=false;button.textContent="Generate skill draft with AI";}
});
$("skill-form").addEventListener("submit",async e=>{
 e.preventDefault();$("skill-error").textContent="";
 const steps=$("skill-steps").value.split(/\r?\n/).map(x=>x.trim()).filter(Boolean);
 try{await api("/api/skills",{method:"POST",body:JSON.stringify({name:$("skill-name").value,context:$("skill-context").value,steps})});$("skill-name").value="";$("skill-context").value="";$("skill-steps").value="";await loadSkills();await loadLearning();}
 catch(err){$("skill-error").textContent=err.message;}
});
$("skill-list").addEventListener("click",async e=>{
 const b=e.target.closest("[data-delete-skill]");if(!b)return;
 if(!confirm("Delete saved skill '"+b.dataset.deleteSkill+"'?"))return;
 try{await api("/api/skills/delete",{method:"POST",body:JSON.stringify({name:b.dataset.deleteSkill})});await loadSkills();await loadLearning();}
 catch(err){$("skill-error").textContent=err.message;}
});

async function loadTools(){
 const list=$("tool-list");list.innerHTML='<div class="empty">Loading tool registry…</div>'; $("tools-error").textContent="";
 try{
  const data=await api("/api/tools");$("tool-builtins").textContent=data.built_in_count;$("tool-forged").textContent=data.forged_count;$("tool-approval").textContent=data.approval_required?"Required":"Disabled";
  list.innerHTML=(data.tools||[]).map(t=>'<div class="list-item"><div class="row" style="justify-content:space-between"><b>'+escapeHtml(t.name)+'</b><span class="badge">'+escapeHtml(t.kind)+(t.approval_required?' · approval required':'')+'</span></div><p>'+escapeHtml(t.description)+'</p><p class="muted">Arguments: '+escapeHtml(JSON.stringify(t.arguments||{}))+'</p>'+(t.kind==="forged"?'<p class="muted">Stored custom tool metadata only. Web execution is disabled.</p>':'')+'</div>').join('')||'<div class="empty">No tools registered.</div>';
 }catch(e){list.innerHTML='<div class="error">'+escapeHtml(e.message)+'</div>';}
}
$("refresh-tools").addEventListener("click",loadTools);

async function loadLearning(){
 const list=$("learning-strategies");list.innerHTML='<div class="empty">Reading local learning records…</div>'; $("learning-error").textContent="";
 try{
  const data=await api("/api/learning");
  $("learning-facts").textContent=data.memory_facts;$("learning-episodes").textContent=data.episodes;$("learning-skills").textContent=data.skills_count;$("learning-records").textContent=data.meta_strategy_count;
  $("learning-enabled").textContent=data.enabled?"Learning enabled":"Learning disabled";
  $("learning-patterns").textContent=(data.pattern_count||0)+" pattern group(s) · automatic extraction "+(data.auto_extract_skills?"preferred":"off");
  const groups=data.strategy_groups||[];
  list.innerHTML=groups.length?groups.map(g=>'<div class="list-item"><b>'+escapeHtml(g.problem_type)+'</b><p>'+escapeHtml(g.records)+' recorded outcomes · '+escapeHtml(g.successes)+' successful</p></div>').join(''):'<div class="empty">No strategy outcomes recorded yet. Save verified skills and use the agent over time to build useful local records.</div>';
  $("learning-notice").textContent=data.notice||"";
 }catch(e){list.innerHTML='<div class="error">'+escapeHtml(e.message)+'</div>';}
}
$("refresh-learning").addEventListener("click",loadLearning);

async function loadImprovements(){
 const list=$("improvement-list");list.innerHTML='<div class="empty">Reviewing local configuration…</div>'; $("improvements-error").textContent="";
 try{
  const data=await api("/api/self/improvements");
  list.innerHTML=(data.proposals||[]).length?data.proposals.map(p=>'<div class="list-item"><div class="row" style="justify-content:space-between"><b>'+escapeHtml(p.title)+'</b><span class="badge">'+escapeHtml(p.risk)+' risk</span></div><p>'+escapeHtml(p.reason)+'</p><p><b>Suggested next step:</b> '+escapeHtml(p.action)+'</p><button class="btn" data-improvement-goal="'+escapeHtml(p.title+'. '+p.action)+'">Add to goals</button></div>').join(''):'<div class="empty">'+escapeHtml(data.notice||"No proposals currently available.")+'</div>';
 }catch(e){list.innerHTML='<div class="error">'+escapeHtml(e.message)+'</div>';}
}
$("refresh-improvements").addEventListener("click",loadImprovements);
$("improvement-list").addEventListener("click",async e=>{
 const b=e.target.closest("[data-improvement-goal]");if(!b)return;
 try{await api("/api/goals",{method:"POST",body:JSON.stringify({text:b.dataset.improvementGoal})});b.textContent="Added to goals";b.disabled=true;await loadStatus();}
 catch(err){$("improvements-error").textContent=err.message;}
});

async function loadSkillEvolution(){
 const list=$("skill-evolution-list");if(!list)return;
 list.innerHTML='<div class="empty">Loading reviewed proposals…</div>';
 try{
  const data=await api("/api/agentic/skills/proposals?limit=100");
  const items=data.proposals||[];
  list.innerHTML=items.length?items.map(p=>{
   const actions=[];
   if(p.status==="proposed")actions.push('<button class="btn" data-evolution-action="validate" data-id="'+escapeHtml(p.id)+'">Static validate</button>','<button class="btn danger" data-evolution-action="reject" data-id="'+escapeHtml(p.id)+'">Reject</button>');
   if(p.status==="validated")actions.push('<button class="btn primary" data-evolution-action="approve" data-id="'+escapeHtml(p.id)+'">Human approve</button>','<button class="btn danger" data-evolution-action="reject" data-id="'+escapeHtml(p.id)+'">Reject</button>');
   if(p.status==="approved")actions.push('<button class="btn primary" data-evolution-action="promote" data-id="'+escapeHtml(p.id)+'">Promote to reviewed catalog</button>','<button class="btn danger" data-evolution-action="reject" data-id="'+escapeHtml(p.id)+'">Revoke / reject</button>');
   return '<div class="list-item"><div class="row" style="justify-content:space-between;gap:8px"><b>'+escapeHtml(p.name)+'</b><span class="badge">'+escapeHtml(p.status)+'</span></div><p class="muted">Family: '+escapeHtml(p.task_type)+' · '+escapeHtml(new Date(p.updated_at*1000).toLocaleString())+'</p><p>'+escapeHtml(p.rationale)+'</p><p><b>Evidence:</b> '+escapeHtml(p.evidence_summary)+'</p><ol>'+p.steps.map(step=>'<li>'+escapeHtml(step)+'</li>').join('')+'</ol>'+(p.review_note?'<p class="muted">Review note: '+escapeHtml(p.review_note)+'</p>':'')+'<p class="muted">Executable: no · Permissions changed: no</p><div class="row">'+actions.join(' ')+'</div></div>';
  }).join(""):'<div class="empty">No skill proposals yet. Submit a draft above or create one after reviewing repeated task outcomes.</div>';
 }catch(e){list.innerHTML='<div class="error">'+escapeHtml(e.message)+'</div>';}
}
if($("skill-evolution-refresh"))$("skill-evolution-refresh").addEventListener("click",loadSkillEvolution);
if($("skill-evolution-from-learning"))$("skill-evolution-from-learning").addEventListener("click",async()=>{
 const button=$("skill-evolution-from-learning");const error=$("skill-evolution-error");error.textContent="";
 if(!confirm("Create a non-executable skill draft from repeated, explicitly verified outcomes? It will remain unapproved and cannot execute tools or change permissions."))return;
 button.disabled=true;button.textContent="Preparing draft…";
 try{
  const result=await api("/api/agentic/skills/proposals/from-learning",{method:"POST",body:"{}"});
  error.textContent=result.notice||"Draft created; human review is still required.";
  await loadSkillEvolution();await loadControlAudit();
 }catch(err){error.textContent=err.message;}
 finally{button.disabled=false;button.textContent="Draft from reviewed learning";}
});
if($("skill-evolution-form"))$("skill-evolution-form").addEventListener("submit",async e=>{
 e.preventDefault();$("skill-evolution-error").textContent="";
 const steps=$("evolution-steps").value.split("\n").map(x=>x.trim()).filter(Boolean);
 try{
  const result=await api("/api/agentic/skills/proposals",{method:"POST",body:JSON.stringify({
   name:$("evolution-name").value.trim(),task_type:$("evolution-task-type").value,
   rationale:$("evolution-rationale").value.trim(),steps,evidence_summary:$("evolution-evidence").value.trim()
  })});
  if(!confirm("Proposal created. Review it in the queue; it is not approved or executable. Clear the form?")){await loadSkillEvolution();return;}
  e.target.reset();$("skill-evolution-error").textContent="Proposal created as proposed; it has not been approved or executed.";
  await loadSkillEvolution();await loadControlAudit();
 }catch(err){$("skill-evolution-error").textContent=err.message;}
});
if($("skill-evolution-list"))$("skill-evolution-list").addEventListener("click",async e=>{
 const b=e.target.closest("[data-evolution-action]");if(!b)return;
 const action=b.dataset.evolutionAction,id=b.dataset.id,note=($("skill-evolution-note").value||"").trim();
 const labels={validate:"Run static validation",approve:"Approve this skill proposal",reject:"Reject this skill proposal",promote:"Promote this approved proposal to the reviewed catalog"};
 if(!confirm(labels[action]+"?\nThis action will not execute code or change permissions."))return;
 try{
  const body=action==="validate"?undefined:{note};
  await api("/api/agentic/skills/proposals/"+encodeURIComponent(id)+"/"+action,{method:"POST",...(body?{body:JSON.stringify(body)}:{})});
  await loadSkillEvolution();await loadControlAudit();
 }catch(err){$("skill-evolution-error").textContent=err.message;}
});

$("ai-settings-form").addEventListener("submit",async e=>{
 e.preventDefault();const button=$("ai-settings-propose");button.disabled=true;button.textContent="Preparing proposal…";$("ai-settings-error").textContent="";$("ai-settings-preview").textContent="";$("ai-settings-apply").disabled=true;window.__aiSettingsProposal=null;
 try{
  const proposal=await api("/api/ai/settings/propose",{method:"POST",body:JSON.stringify({request:$("ai-settings-request").value})});
  window.__aiSettingsProposal=proposal.changes||{};
  $("ai-settings-preview").textContent=JSON.stringify({explanation:proposal.explanation,changes:proposal.changes,notice:proposal.notice},null,2);
  $("ai-settings-apply").disabled=!Object.keys(window.__aiSettingsProposal).length;
 }catch(err){$("ai-settings-error").textContent=err.message;}
 finally{button.disabled=false;button.textContent="Ask AI to propose settings";}
});
$("ai-settings-apply").addEventListener("click",async()=>{
 const changes=window.__aiSettingsProposal;if(!changes||!Object.keys(changes).length)return;
 if(!confirm("Apply these reviewed settings changes? Backend changes may reset the active agent."))return;
 $("ai-settings-error").textContent="";$("ai-settings-apply").disabled=true;
 try{await api("/api/settings",{method:"PATCH",body:JSON.stringify(changes)});$("ai-settings-preview").textContent="Settings applied. Review the current values below.";window.__aiSettingsProposal=null;await loadSettings();await loadStatus();}
 catch(err){$("ai-settings-error").textContent=err.message;$("ai-settings-apply").disabled=false;}
});

async function loadKnowledge(query=""){
 const list=$("knowledge-results"); if(!list)return; list.innerHTML='<div class="empty">Loading local knowledge…</div>';
 try{const data=await api("/api/knowledge"+(query?"?q="+encodeURIComponent(query):""));const items=data.items||[];
 list.innerHTML=items.length?items.map(i=>'<div class="list-item"><div class="row" style="justify-content:space-between;gap:8px"><b>'+escapeHtml(i.title)+'</b><button class="btn" data-knowledge-delete="'+escapeHtml(i.id)+'">Delete</button></div><p>'+escapeHtml(i.content)+'</p><p class="muted">'+escapeHtml((i.tags||[]).join(", "))+' · '+escapeHtml(i.kind)+' · '+new Date(i.updated_at*1000).toLocaleString()+'</p></div>').join(''):'<div class="empty">No matching knowledge yet. Add a project note or tested procedure.</div>';
 }catch(e){list.innerHTML='<div class="error">'+escapeHtml(e.message)+'</div>';}
}
$("knowledge-refresh")?.addEventListener("click",()=>loadKnowledge());
$("knowledge-form")?.addEventListener("submit",async e=>{e.preventDefault();$("knowledge-error").textContent="";
 try{await api("/api/knowledge",{method:"POST",body:JSON.stringify({title:$("knowledge-title").value,content:$("knowledge-content").value,tags:$("knowledge-tags").value.split(",").map(s=>s.trim()).filter(Boolean)})});$("knowledge-form").reset();await loadKnowledge();}
 catch(err){$("knowledge-error").textContent=err.message;}});
$("knowledge-search-form")?.addEventListener("submit",e=>{e.preventDefault();loadKnowledge($("knowledge-query").value.trim());});
$("knowledge-clear-search")?.addEventListener("click",()=>{$("knowledge-query").value="";loadKnowledge();});
$("knowledge-results")?.addEventListener("click",async e=>{const b=e.target.closest("[data-knowledge-delete]");if(!b)return;if(!confirm("Delete this saved knowledge item?"))return;
 try{await api("/api/knowledge/"+encodeURIComponent(b.dataset.knowledgeDelete)+"/delete",{method:"POST",body:"{}"});await loadKnowledge($("knowledge-query").value.trim());}catch(err){alert(err.message);}});
async function loadWorkspace(){
 try{const data=await api("/api/workspace");$("workspace-output").textContent="Workspace: "+data.workspace+"\n"+JSON.stringify(data.items,null,2);}
 catch(e){$("workspace-output").textContent=e.message;}
}
$("workspace-refresh")?.addEventListener("click",loadWorkspace);
$("workspace-list")?.addEventListener("click",async()=>{try{const p=$("workspace-path").value||".";const d=await api("/api/workspace?path="+encodeURIComponent(p));$("workspace-output").textContent=JSON.stringify(d,null,2);}catch(e){$("workspace-output").textContent=e.message;}});
$("workspace-read")?.addEventListener("click",async()=>{try{const d=await api("/api/workspace/read",{method:"POST",body:JSON.stringify({path:$("workspace-path").value})});$("workspace-output").textContent=d.content;}catch(e){$("workspace-output").textContent=e.message;}});
$("workspace-write")?.addEventListener("click",async()=>{const path=$("workspace-write-path").value,content=$("workspace-write-content").value;
 if(!$("workspace-write-approved").checked){$("workspace-error").textContent="Check the explicit approval box first.";return;}
 if(!confirm("Write "+path+" with the exact content shown?"))return;
 try{const d=await api("/api/workspace/write",{method:"POST",body:JSON.stringify({path,content,approved:true})});$("workspace-error").textContent="Saved "+d.path+" ("+d.bytes+" bytes).";$("workspace-write-approved").checked=false;await loadWorkspace();}
 catch(e){$("workspace-error").textContent=e.message;}});
$("workspace-execute")?.addEventListener("click",async()=>{if(!$("workspace-command-approved").checked){$("workspace-error").textContent="Approve the exact command first.";return;}
 const argv=$("workspace-command").value.split("\n").map(s=>s.trim()).filter(Boolean);
 if(!argv.length){$("workspace-error").textContent="Enter command arguments, one per line.";return;}
 if(!confirm("Execute this exact argument list in the project workspace?\n"+JSON.stringify(argv)))return;
 try{const d=await api("/api/workspace/execute",{method:"POST",body:JSON.stringify({argv,approved:true,timeout:30})});$("workspace-output").textContent=JSON.stringify(d,null,2);$("workspace-error").textContent="Command finished with exit code "+d.returncode;$("workspace-command-approved").checked=false;}
 catch(e){$("workspace-error").textContent=e.message;}});
async function loadScheduler(){
 const list=$("scheduler-list");if(!list)return;list.innerHTML='<div class="empty">Loading scheduled jobs…</div>';
 try{const data=await api("/api/scheduled-tasks");list.innerHTML=(data.tasks||[]).length?data.tasks.map(t=>'<div class="list-item"><div class="row" style="justify-content:space-between;gap:8px"><b>'+escapeHtml(t.name)+'</b><span class="badge">'+(t.enabled?"Enabled":"Paused")+'</span></div><p>'+escapeHtml(t.kind)+' · every '+escapeHtml(t.interval_minutes)+' min</p><p class="muted">Next: '+new Date(t.next_run*1000).toLocaleString()+' · Last result: '+escapeHtml(t.last_status||"Not run yet")+'</p><div class="row"><button class="btn" data-task-toggle="'+escapeHtml(t.id)+'" data-enabled="'+(!t.enabled)+'">'+(t.enabled?"Pause":"Enable")+'</button><button class="btn" data-task-delete="'+escapeHtml(t.id)+'">Delete</button></div></div>').join(''):'<div class="empty">No scheduled jobs yet.</div>';}
 catch(e){list.innerHTML='<div class="error">'+escapeHtml(e.message)+'</div>';}
}
$("scheduler-refresh")?.addEventListener("click",loadScheduler);
$("scheduler-form")?.addEventListener("submit",async e=>{e.preventDefault();$("scheduler-error").textContent="";
 try{await api("/api/scheduled-tasks",{method:"POST",body:JSON.stringify({name:$("scheduler-name").value,kind:$("scheduler-kind").value,interval_minutes:Number($("scheduler-interval").value)})});$("scheduler-form").reset();await loadScheduler();}
 catch(err){$("scheduler-error").textContent=err.message;}});
$("scheduler-list")?.addEventListener("click",async e=>{const toggle=e.target.closest("[data-task-toggle]"),del=e.target.closest("[data-task-delete]");
 try{if(toggle){await api("/api/scheduled-tasks/"+encodeURIComponent(toggle.dataset.taskToggle),{method:"PATCH",body:JSON.stringify({enabled:toggle.dataset.enabled==="true"})});await loadScheduler();}
 else if(del&&confirm("Delete this scheduled task?")){await api("/api/scheduled-tasks/"+encodeURIComponent(del.dataset.taskDelete)+"/delete",{method:"POST",body:"{}"});await loadScheduler();}}
 catch(err){$("scheduler-error").textContent=err.message;}});

const routeViews={"/":"overview","/overview":"overview","/chat":"chat","/sessions":"sessions","/models":"models","/diagnostics":"diagnostics","/memory":"memory","/knowledge":"knowledge","/workspace":"workspace","/scheduler":"scheduler","/goals":"goals","/self":"self","/skills":"skills","/tools":"tools","/learning":"learning","/improvements":"improvements","/selfx":"selfx","/settings":"settings"};
const initialView=routeViews[location.pathname]||new URLSearchParams(location.search).get("view");
if(titles[initialView])showView(initialView);


// Command Control Center: human review, policy controls, skill packages and live audit events.
let controlSocket=null;
let controlSocketRetry=null;
function controlApi(path,options={}){return api(path,options);}
function controlList(text){return [...new Set(String(text||"").split(",").map(x=>x.trim()).filter(Boolean))];}
async function loadControlPolicy(){
 const [data,toolData]=await Promise.all([controlApi("/api/control/policy"),controlApi("/api/tools")]);const p=data.policy||{};
 $("control-global-auto").checked=false;
 $("control-allowlist").value=(p.allowlist||[]).join(", ");
 $("control-blocklist").value=(p.blocklist||[]).join(", ");
 const rules=p.tool_auto_execute||{};$("control-tool-rules").value=JSON.stringify(rules,null,2);
 const names=[...new Set((toolData.tools||[]).map(t=>t.name).filter(Boolean))].sort();
 $("control-tool-toggles").innerHTML=names.map(name=>'<label class="list-item"><input type="checkbox" data-tool-rule="'+escapeHtml(name)+'" '+(rules[name]===true?'checked':'')+' style="width:auto;margin-right:8px"> '+escapeHtml(name)+' <span class="muted">— metadata only</span></label>').join("")||'<div class="empty">No tool metadata available.</div>';
}
async function saveControlPolicy(){
 $("control-policy-error").textContent="";
 try{
  let rules=JSON.parse($("control-tool-rules").value||"{}");
  if(!rules||Array.isArray(rules)||typeof rules!=="object")throw new Error("Per-tool rules must be a JSON object.");
  const data=await controlApi("/api/control/policy",{method:"PATCH",body:JSON.stringify({
   auto_execute:false,allowlist:controlList($("control-allowlist").value),
   blocklist:controlList($("control-blocklist").value),tool_auto_execute:rules
  })});
  await loadControlPolicy();$("control-policy-error").textContent=data.notice||"Policy saved; global auto-execution remains disabled.";
  await loadControlAudit();
 }catch(e){$("control-policy-error").textContent=e.message;}
}
async function loadControlPending(){
 const list=$("control-pending-list");list.innerHTML='<div class="empty">Loading operations…</div>';
 const status=$("control-status-filter")?.value||"pending";
 try{
  const data=await controlApi("/api/control/pending?status="+encodeURIComponent(status));
  const ops=data.operations||[];
  const label=status.charAt(0).toUpperCase()+status.slice(1);
  list.innerHTML=ops.length?ops.map(o=>{
   const canReview=o.status==="pending";
   const args=JSON.stringify(o.arguments,null,2);
   return '<div class="list-item"><div class="row" style="justify-content:space-between;gap:8px"><b>'+escapeHtml(o.tool+'.'+o.operation)+'</b><span class="badge">'+escapeHtml(o.status||label)+'</span></div><p class="muted">ID: '+escapeHtml(o.id)+' · Created '+escapeHtml(new Date(o.created_at*1000).toLocaleString())+(o.reviewed_at?' · Reviewed '+escapeHtml(new Date(o.reviewed_at*1000).toLocaleString()):'')+'</p><pre class="reflection" style="white-space:pre-wrap;max-height:140px;overflow:auto">'+escapeHtml(args)+'</pre>'+(o.note?'<p class="muted">Review note: '+escapeHtml(o.note)+'</p>':'')+(canReview?'<div class="row" style="gap:8px"><button class="btn primary" data-control-review="approve" data-id="'+escapeHtml(o.id)+'">Approve</button><button class="btn danger" data-control-review="reject" data-id="'+escapeHtml(o.id)+'">Reject</button></div>':'')+'</div>';
  }).join(""):'<div class="empty">No '+escapeHtml(status)+' operations found.</div>';
  $("control-pending-error").textContent="";
 }catch(e){list.innerHTML='<div class="error">'+escapeHtml(e.message)+'</div>';}
}
async function loadControlAudit(){
 try{
  const data=await controlApi("/api/control/audit?limit=100");const integrity=data.integrity||{};
  $("control-audit-integrity").textContent=(integrity.valid?"Integrity verified":"INTEGRITY WARNING")+" · "+(integrity.checked||0)+" entries checked"+(integrity.reason?" · "+integrity.reason:"");
  $("control-audit-list").innerHTML=(data.entries||[]).map(e=>'<div class="list-item"><div class="row" style="justify-content:space-between;gap:8px"><b>'+escapeHtml(e.action)+'</b><span class="muted">'+escapeHtml(new Date(e.timestamp*1000).toLocaleString())+'</span></div><p>'+escapeHtml(e.actor)+' → '+escapeHtml(e.target)+'</p><p class="muted">'+escapeHtml(JSON.stringify(e.details||{}))+'</p><small class="muted">SHA-256: '+escapeHtml(e.entry_hash)+'</small></div>').join("")||'<div class="empty">No audit entries yet.</div>';
 }catch(e){$("control-audit-integrity").textContent=e.message;}
}
function connectControlEvents(){
 if(controlSocket||!$("control-live-status"))return;
 const scheme=location.protocol==="https:"?"wss:":"ws:";
 try{controlSocket=new WebSocket(scheme+"//"+location.host+"/api/control/events");}catch(e){$("control-live-status").textContent="Unavailable";return;}
 controlSocket.onopen=()=>{$("control-live-status").textContent="Live";};
 controlSocket.onmessage=event=>{
  try{
   const item=JSON.parse(event.data);if(item.type!=="action_event")return;
   const feed=$("control-live-feed");const row=document.createElement("div");row.className="list-item";
   const head=document.createElement("b");head.textContent=item.action||"action";
   const detail=document.createElement("p");detail.textContent=(item.actor||"system")+" · "+(item.target||"")+" · "+new Date(item.timestamp*1000).toLocaleTimeString();
   const summary=document.createElement("p");summary.className="muted";summary.textContent=JSON.stringify(item.details||{});
   row.append(head,detail,summary);feed.prepend(row);while(feed.children.length>40)feed.lastElementChild.remove();
   loadControlAudit();
  }catch(_){}
 };
 controlSocket.onclose=()=>{controlSocket=null;$("control-live-status").textContent="Reconnecting";if(!controlSocketRetry)controlSocketRetry=setTimeout(()=>{controlSocketRetry=null;connectControlEvents();},3000);};
 controlSocket.onerror=()=>{$("control-live-status").textContent="Retrying";};
}
async function loadCommandControl(){
 try{await Promise.all([loadControlPolicy(),loadControlPending(),loadControlAudit()]);connectControlEvents();}
 catch(e){$("control-policy-error").textContent=e.message;}
}
if($("control-refresh"))$("control-refresh").addEventListener("click",loadCommandControl);
if($("control-tool-toggles"))$("control-tool-toggles").addEventListener("change",e=>{
 const input=e.target.closest("[data-tool-rule]");if(!input)return;
 try{const rules=JSON.parse($("control-tool-rules").value||"{}");rules[input.dataset.toolRule]=input.checked;$("control-tool-rules").value=JSON.stringify(rules,null,2);}
 catch(err){$("control-policy-error").textContent="Fix the per-tool JSON before changing toggles.";}
});

if($("control-save-policy"))$("control-save-policy").addEventListener("click",saveControlPolicy);
if($("control-refresh-pending"))$("control-refresh-pending").addEventListener("click",loadControlPending);
if($("control-status-filter"))$("control-status-filter").addEventListener("change",loadControlPending);
if($("control-audit-refresh"))$("control-audit-refresh").addEventListener("click",loadControlAudit);
if($("control-queue-form"))$("control-queue-form").addEventListener("submit",async e=>{
 e.preventDefault();$("control-queue-error").textContent="";
 try{let args=JSON.parse($("control-arguments").value||"{}");if(!args||Array.isArray(args)||typeof args!=="object")throw new Error("Arguments must be a JSON object.");
  await controlApi("/api/control/pending",{method:"POST",body:JSON.stringify({tool:$("control-tool").value,operation:$("control-operation").value,arguments:args})});
  $("control-queue-error").textContent="Added to queue; no command was executed.";await loadControlPending();await loadControlAudit();
 }catch(err){$("control-queue-error").textContent=err.message;}
});
if($("control-pending-list"))$("control-pending-list").addEventListener("click",async e=>{
 const b=e.target.closest("[data-control-review]");if(!b)return;
 const approve=b.dataset.controlReview==="approve";
 const note=($("control-review-note")?.value||"").trim();
 if(!confirm((approve?"Approve":"Reject")+" this operation?"+(note?"\nReviewer note: "+note:"")+"\nThis records a decision only and will not execute it."))return;
 try{await controlApi("/api/control/pending/"+encodeURIComponent(b.dataset.id)+"/review",{method:"POST",body:JSON.stringify({approve,note})});$("control-review-note").value="";await loadControlPending();await loadControlAudit();}
 catch(err){$("control-pending-error").textContent=err.message;}
});
if($("control-skills-export"))$("control-skills-export").addEventListener("click",async()=>{
 try{const data=await controlApi("/api/control/skills/export");$("control-skills-json").value=JSON.stringify(data,null,2);$("control-skills-result").textContent="Package exported into the editor. Copy/save it as a JSON file if needed.";}
 catch(e){$("control-skills-error").textContent=e.message;}
});
if($("control-skills-export-yaml"))$("control-skills-export-yaml").addEventListener("click",async()=>{
 $("control-skills-error").textContent="";
 try{const res=await fetch("/api/control/skills/export.yaml");if(!res.ok)throw new Error("YAML export failed ("+res.status+")");$("control-skills-json").value=await res.text();$("control-skills-format").value="yaml";$("control-skills-result").textContent="YAML package exported into the editor.";}
 catch(e){$("control-skills-error").textContent=e.message;}
});
if($("control-skills-import"))$("control-skills-import").addEventListener("click",async()=>{
 $("control-skills-error").textContent="";
 try{
  const format=$("control-skills-format").value;const raw=$("control-skills-json").value;
  const result=format==="yaml"
   ? await controlApi("/api/control/skills/import.yaml",{method:"POST",body:JSON.stringify({content:raw})})
   : await controlApi("/api/control/skills/import",{method:"POST",body:JSON.stringify(JSON.parse(raw))});
  $("control-skills-result").textContent=JSON.stringify(result,null,2);await loadControlAudit();
 }catch(e){$("control-skills-error").textContent=e.message;}
});

// Browser-local presentation preferences; these never affect backend settings or permissions.
const uiPreferenceDefaults={compact:false,largeText:false,reducedMotion:false};
function readUiPreferences(){
 try{return {...uiPreferenceDefaults,...JSON.parse(localStorage.getItem("terminal-ai-ui-preferences")||"{}")};}
 catch(_){return {...uiPreferenceDefaults};}
}
function applyUiPreferences(preferences,save=true){
 const value={...uiPreferenceDefaults,...preferences};
 document.documentElement.classList.toggle("ui-compact",!!value.compact);
 document.documentElement.classList.toggle("ui-large-text",!!value.largeText);
 document.documentElement.classList.toggle("ui-reduced-motion",!!value.reducedMotion);
 const mapping=[["ui-pref-compact","compact"],["ui-pref-large-text","largeText"],["ui-pref-reduced-motion","reducedMotion"]];
 mapping.forEach(([id,key])=>{const input=$(id);if(input)input.checked=!!value[key];});
 if(save){try{localStorage.setItem("terminal-ai-ui-preferences",JSON.stringify(value));}catch(_){}}
 const status=$("ui-pref-status");if(status)status.textContent=save?"Preferences applied to this browser.":"Current browser preferences loaded."; 
}
applyUiPreferences(readUiPreferences(),false);
["ui-pref-compact","ui-pref-large-text","ui-pref-reduced-motion"].forEach(id=>{
 const input=$(id);if(input)input.addEventListener("change",()=>applyUiPreferences({compact:$("ui-pref-compact").checked,largeText:$("ui-pref-large-text").checked,reducedMotion:$("ui-pref-reduced-motion").checked}));
});
if($("ui-pref-reset"))$("ui-pref-reset").addEventListener("click",()=>applyUiPreferences(uiPreferenceDefaults));


// Theme and transient status notifications are presentation-only browser features.
const themeStorageKey="terminal-ai-theme";
function readTheme(){
 try{return localStorage.getItem(themeStorageKey)==="light"?"light":"dark";}catch(_){return "dark";}
}
function applyTheme(theme,save=true){
 const light=theme==="light";
 document.documentElement.classList.toggle("theme-light",light);
 document.documentElement.style.colorScheme=light?"light":"dark";
 const button=$("theme-toggle");
 if(button){
  button.setAttribute("aria-pressed",String(light));
  button.setAttribute("aria-label",light?"Switch to dark theme":"Switch to light theme");
  button.title=light?"Switch to dark theme":"Switch to light theme";
 }
 const icon=$("theme-toggle-icon");
 if(icon)icon.textContent=light?"☾":"☼";
 try{if(save)localStorage.setItem(themeStorageKey,light?"light":"dark");}catch(_){}
}
applyTheme(readTheme(),false);
if($("theme-toggle"))$("theme-toggle").addEventListener("click",()=>{
 const next=document.documentElement.classList.contains("theme-light")?"dark":"light";
 applyTheme(next);
});
let toastSequence=0;
function showToast(message,kind="info"){
 const region=$("toast-region");
 if(!region||!message)return;
 const toast=document.createElement("div");
 const sequence=++toastSequence;
 toast.className="toast toast-"+(["success","status","error"].includes(kind)?kind:"info");
 toast.setAttribute("role",kind==="error"?"alert":"status");
 const text=document.createElement("span");
 text.textContent=String(message).slice(0,240);
 const close=document.createElement("button");
 close.type="button";close.className="toast-close";close.setAttribute("aria-label","Dismiss notification");close.textContent="×";
 close.addEventListener("click",()=>toast.remove());
 toast.append(text,close);region.append(toast);
 while(region.children.length>4)region.firstElementChild.remove();
 window.setTimeout(()=>{const current=region.querySelectorAll(".toast");for(const item of current){if(item===toast)item.remove();}},5000);
 return sequence;
}


// Poll the lightweight status endpoint while the dashboard is visible.
setInterval(()=>{if(!document.hidden)loadStatus();},30000);
document.addEventListener("visibilitychange",()=>{if(!document.hidden)loadStatus();});


const healthHistoryKey="terminal-ai-health-history-v1";
function readHealthHistory(){
 try{const v=JSON.parse(localStorage.getItem(healthHistoryKey)||"[]");return Array.isArray(v)?v.filter(x=>x&&Number.isFinite(x.t)&&typeof x.api==="boolean"&&typeof x.ready==="boolean").slice(-48):[];}catch(_){return [];}
}
function recordHealthSnapshot(api,ready){
 const now=Date.now(),samples=readHealthHistory();
 if(samples.length&&now-samples[samples.length-1].t<20000&&samples[samples.length-1].api===!!api&&samples[samples.length-1].ready===!!ready){renderHealthTimeline(samples);return;}
 samples.push({t:now,api:!!api,ready:!!ready});
 const bounded=samples.slice(-48);
 try{localStorage.setItem(healthHistoryKey,JSON.stringify(bounded));}catch(_){}
 renderHealthTimeline(bounded);
}
function renderHealthTimeline(samples=readHealthHistory()){
 const svg=$("health-timeline-svg");if(!svg)return;
 const ns="http://www.w3.org/2000/svg";
 const add=(tag,attrs,text)=>{const e=document.createElementNS(ns,tag);Object.entries(attrs).forEach(([k,v])=>e.setAttribute(k,String(v)));if(text!==undefined)e.textContent=text;svg.appendChild(e);return e;};
 while(svg.firstChild)svg.removeChild(svg.firstChild);
 [22,52,82].forEach(y=>add("line",{x1:18,y1:y,x2:582,y2:y,class:"health-gridline"}));
 if(!samples.length){add("text",{x:20,y:15,class:"health-axis-label"},"Waiting for status samples…");if($("health-timeline-count"))$("health-timeline-count").textContent="Collecting samples";if($("health-timeline-summary"))$("health-timeline-summary").textContent="Samples are collected while this page is open.";return;}
 const width=560;
 for(const spec of [{key:"api",up:22,down:42,cls:"health-api-line"},{key:"ready",up:62,down:82,cls:"health-ready-line"}]){
  const points=samples.map((s,i)=>({x:samples.length===1?20:20+i*width/(samples.length-1),y:s[spec.key]?spec.up:spec.down}));
  add("path",{d:points.map((p,i)=>(i?"L":"M")+p.x.toFixed(1)+" "+p.y.toFixed(1)).join(" "),class:spec.cls,fill:"none","stroke-width":2.5,"stroke-linecap":"round","stroke-linejoin":"round"});
  points.forEach((p,i)=>add("circle",{cx:p.x,cy:p.y,r:i===points.length-1?4:2.2,class:spec.cls+"-point"}));
 }
 add("text",{x:20,y:105,class:"health-axis-label"},new Date(samples[0].t).toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"}));
 add("text",{x:580,y:105,class:"health-axis-label","text-anchor":"end"},new Date(samples[samples.length-1].t).toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"}));
 const latest=samples[samples.length-1];
 if($("health-timeline-count"))$("health-timeline-count").textContent=samples.length+" sample"+(samples.length===1?"":"s");
 if($("health-timeline-summary"))$("health-timeline-summary").textContent=(latest.api?"API reachable":"API unavailable")+" · "+(latest.ready?"inference ready":"inference not ready")+" · latest sample "+new Date(latest.t).toLocaleTimeString();
}
renderHealthTimeline();


const collectionSearchTargets=[
 ["memory-list","Search saved memories"],["workspace-list","Search workspace files"],["scheduler-list","Search scheduled jobs"],
 ["goal-list","Search goals"],["session-list","Search sessions"],["model-list","Search models"],["provider-list","Search providers"],
 ["download-list","Search downloads"],["diagnostic-list","Search diagnostics"],["skill-list","Search skills"],["tool-list","Search tools"],
 ["skill-evolution-list","Search skill proposals"],["improvement-list","Search improvements"],["selfx-diagnostic-list","Search diagnostics"],
 ["selfx-evaluation-list","Search evaluations"],["selfx-research-list","Search research"],["selfx-checkpoint-list","Search checkpoints"],
 ["agentic-world-list","Search world model"],["task-lifecycle-list","Search tasks"],["control-pending-list","Search operations"],["control-audit-list","Search audit events"]
];
function setupCollectionSearch(){
 for(const [id,placeholder] of collectionSearchTargets){
  const container=$(id);if(!container||container.dataset.searchReady==="true")continue;
  container.dataset.searchReady="true";
  const bar=document.createElement("div");bar.className="collection-search";
  const label=document.createElement("label");label.className="sr-only";label.htmlFor=id+"-search";label.textContent=placeholder;
  const input=document.createElement("input");input.type="search";input.id=id+"-search";input.maxLength=120;input.placeholder=placeholder+"…";input.autocomplete="off";
  const count=document.createElement("span");count.className="collection-search-count";count.setAttribute("aria-live","polite");
  bar.append(label,input,count);container.parentNode.insertBefore(bar,container);
  const apply=()=>{
   const query=input.value.trim().toLocaleLowerCase();
   const items=Array.from(container.children).filter(el=>!el.classList.contains("empty")&&!el.classList.contains("error"));
   let shown=0;
   for(const item of items){const match=!query||item.textContent.toLocaleLowerCase().includes(query);item.hidden=!match;if(match)shown++;}
   const empty=Array.from(container.children).find(el=>el.classList.contains("empty"));
   if(empty)empty.hidden=Boolean(query);
   count.textContent=query?(shown?shown+" matching":"No matching items"):items.length+" item"+(items.length===1?"":"s");
  };
  input.addEventListener("input",apply);
  new MutationObserver(apply).observe(container,{childList:true});
  apply();
 }
}
setupCollectionSearch();
