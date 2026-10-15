const $=id=>document.getElementById(id);
let statusData=null;
const titles={overview:"Overview",chat:"AI Chat",sessions:"Sessions",models:"Models",diagnostics:"Diagnostics",memory:"Memory",goals:"Goals",self:"Self-awareness",skills:"Skills",tools:"Tools",learning:"Learning",improvements:"Self-improvement",selfx:"Self-X Evolution Engine",settings:"Settings"};
function escapeHtml(value){return String(value??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));}
async function api(path,options={}){const res=await fetch(path,{...options,headers:{"Content-Type":"application/json",...(options.headers||{})}});let data={};try{data=await res.json()}catch{}if(!res.ok)throw new Error(data.detail||data.message||("Request failed ("+res.status+")"));return data;}
function showView(name){document.querySelectorAll(".view").forEach(el=>el.classList.toggle("active",el.id==="view-"+name));document.querySelectorAll("#nav button").forEach(el=>el.classList.toggle("active",el.dataset.view===name));$("page-title").textContent=titles[name]||name;if(name==="sessions")loadSessions();if(name==="models")loadModels();if(name==="diagnostics")loadDiagnostics();if(name==="memory")loadMemory();if(name==="goals")loadGoals();if(name==="settings"){loadSettings();loadUpdateStatus();}if(name==="self")loadSelf();if(name==="skills")loadSkills();if(name==="tools")loadTools();if(name==="learning")loadLearning();if(name==="improvements")loadImprovements();if(name==="selfx")loadSelfX();}
$("nav").addEventListener("click",e=>{const b=e.target.closest("[data-view]");if(b)showView(b.dataset.view);});
if($("overview-refresh"))$("overview-refresh").addEventListener("click",()=>loadStatus());
document.querySelectorAll("[data-go]").forEach(b=>b.addEventListener("click",()=>showView(b.dataset.go)));
async function loadStatus(){
 try{
  statusData=await api("/api/status");
  const ready=Boolean(statusData.ready);
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
   [localModels.length>0,"Verify offline model",localModels.length?"Local model file detected; test it with internet disabled":"Add a compatible .litertlm model in the models directory","models"],
   [Boolean(statusData.session_count),"Check session persistence",statusData.session_count?"Saved session storage is discoverable":"Create a session and send a test message","sessions"],
   [!statusData.error,"Review runtime errors",statusData.error||"No current backend initialization error reported","diagnostics"]
  ];
  $("overview-checklist").innerHTML=checklist.map(([ok,title,detail,view])=>'<div class="check-item"><span class="check-mark '+(ok?"done":"pending")+'">'+(ok?"✓":"!")+'</span><div><b>'+escapeHtml(title)+'</b><p>'+escapeHtml(detail)+'</p><button class="btn" data-go="'+view+'">Open</button></div></div>').join("");
  $("system-error").textContent=statusData.error||"";
  $("storage-list").innerHTML=[["State",statusData.state_dir],["Models",localModels.length+" found"],["Interface","Litestar + HTML/CSS/JS"]].map(([k,v])=>'<div class="list-item"><b>'+escapeHtml(k)+'</b><p>'+escapeHtml(v)+'</p></div>').join("");
 }catch(e){
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

async function loadSettings(){
 try{
  const data=await api("/api/settings");
  $("setting-mode").value=data.mode||"auto";
  $("setting-provider").value=data.active_provider||"gemini";
  $("setting-model").value=data.provider_model||"";
  $("setting-endpoint").value=data.custom_base_url||"";
  $("custom-endpoint-field").hidden=$("setting-provider").value!=="custom-openai";
  $("setting-critique").checked=!!data.self_critique;
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
  $("setting-tool-approval").checked=data.tool_approval_required!==false;
  $("hf-token-state").textContent=data.hf_token_configured?"Hugging Face token configured locally.":"No Hugging Face token saved (some models may require access approval/token).";
  $("updates-enabled").checked=!!data.updates_enabled;
  $("update-interval").value=data.update_check_interval_hours||24;
  const configured=data.provider_configured||{};
  const rows=[["State directory",data.state_dir],["Models directory",data.models_dir],...Object.entries(configured).map(([k,v])=>[k,v?"API key configured":"API key missing"])];
  $("storage-list").innerHTML=rows.map(([k,v])=>'<div class="list-item"><b>'+escapeHtml(k)+'</b><p>'+escapeHtml(v)+'</p></div>').join("");
 }catch(e){$("settings-error").textContent=e.message;}
}
$("setting-provider").addEventListener("change",()=>{$("custom-endpoint-field").hidden=$("setting-provider").value!=="custom-openai";});

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
   provider_model:$("setting-model").value,custom_base_url:$("setting-endpoint").value,
   api_key:$("setting-api-key").value,hf_token:$("setting-hf-token").value,
   self_critique:$("setting-critique").checked,
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
   tool_approval_required:$("setting-tool-approval").checked
  })});
  $("setting-hf-token").value="";
  $("settings-saved").textContent="Saved";$("setting-api-key").value="";
  await loadSettings();await loadStatus();
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
const routeViews={"/":"overview","/overview":"overview","/chat":"chat","/sessions":"sessions","/models":"models","/diagnostics":"diagnostics","/memory":"memory","/goals":"goals","/self":"self","/skills":"skills","/tools":"tools","/learning":"learning","/improvements":"improvements","/selfx":"selfx","/settings":"settings"};
const initialView=routeViews[location.pathname]||new URLSearchParams(location.search).get("view");
if(titles[initialView])showView(initialView);
