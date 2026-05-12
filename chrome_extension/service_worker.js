const BASE = "http://127.0.0.1:5050";

async function postJSON(path, body) {
  try {
    const r = await fetch(BASE + path, {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(body || {})});
    return await r.json();
  } catch (e) { return {ok:false, error:String(e)}; }
}
async function getJSON(path) {
  try { const r = await fetch(BASE + path, {cache:"no-store"}); return await r.json(); } catch (e) { return {ok:false, error:String(e)}; }
}
function flattenBookmarks(nodes, out=[]) {
  for (const n of nodes || []) {
    if (n.url) out.push({title:n.title || "Bookmark", url:n.url, id:n.id});
    if (n.children) flattenBookmarks(n.children, out);
  }
  return out;
}
async function activeTab() {
  const tabs = await chrome.tabs.query({active:true, currentWindow:true});
  return tabs[0];
}
function isRestrictedUrl(url) {
  return !url || url.startsWith("chrome://") || url.startsWith("edge://") || url.startsWith("chrome-extension://") || url.startsWith("about:") || url.startsWith("view-source:");
}
async function sendToActive(message) {
  const tab = await activeTab();
  if (!tab?.id) return {ok:false, error:"No active tab."};
  if (isRestrictedUrl(tab.url || "")) return {ok:false, restricted:true, error:"The active tab is a restricted Chrome page. Open a normal website tab first.", title:tab.title || "", url:tab.url || ""};
  try { return await chrome.tabs.sendMessage(tab.id, message); }
  catch(e) {
    try {
      await chrome.scripting.executeScript({target:{tabId:tab.id}, files:["content_script.js"]});
      return await chrome.tabs.sendMessage(tab.id, message);
    } catch (e2) { return {ok:false, error:String(e2), title:tab.title || "", url:tab.url || ""}; }
  }
}
async function heartbeat(last_error="") {
  await postJSON("/api/chrome/heartbeat", {last_error});
}
async function pushState() {
  try {
    const tabs = await chrome.tabs.query({});
    const tree = await chrome.bookmarks.getTree();
    const tab = await activeTab();
    let page = await sendToActive({type:"snapshot"});
    let last_error = "";
    if (!page?.ok) {
      last_error = page?.error || "No page snapshot.";
      page = {ok:false, title:tab?.title || "", url:tab?.url || "", text:"", elements:[], error:last_error, restricted:!!page?.restricted};
    }
    await postJSON("/api/chrome/state", {
      tabs: tabs.map(t => ({id:t.id, title:t.title || "", url:t.url || "", active:t.active, windowId:t.windowId, index:t.index})),
      bookmarks: flattenBookmarks(tree).slice(0,500),
      page,
      last_error
    });
  } catch(e) {
    await heartbeat(String(e));
  }
}
async function runAction(job) {
  const action = job.action;
  const p = job.payload || {};
  let result = {ok:false, error:"Unknown action: " + action};
  try {
    if (action === "snapshot") result = await sendToActive({type:"snapshot"});
    if (action === "click_text") result = await sendToActive({type:"click_text", target:p.target, ordinal:p.ordinal || 1});
    if (action === "input_text") result = await sendToActive({type:"input_text", text:p.text || ""});
    if (action === "list_tabs") {
      const tabs = await chrome.tabs.query({});
      result = {ok:true, tabs:tabs.map(t=>({id:t.id,title:t.title || "",url:t.url || "",active:t.active,index:t.index,windowId:t.windowId}))};
    }
    if (action === "switch_tab") {
      const tabs = await chrome.tabs.query({});
      let target = tabs.find(t => (t.title||"").toLowerCase().includes((p.query||"").toLowerCase()) || (t.url||"").toLowerCase().includes((p.query||"").toLowerCase()));
      if (p.index) target = tabs[Number(p.index)-1] || target;
      if (target) { await chrome.tabs.update(target.id, {active:true}); await chrome.windows.update(target.windowId, {focused:true}); result={ok:true,title:target.title}; }
      else result={ok:false,error:"Tab not found."};
    }
    if (action === "close_tab") {
      const tab = p.id ? {id:p.id} : await activeTab();
      await chrome.tabs.remove(tab.id); result = {ok:true};
    }
    if (action === "open_bookmark") {
      const tree = await chrome.bookmarks.getTree(); const bms = flattenBookmarks(tree);
      let b = null;
      if (p.index) b = bms[Number(p.index)-1];
      if (!b && p.query) b = bms.find(x => (x.title||"").toLowerCase().includes(String(p.query).toLowerCase()) || (x.url||"").toLowerCase().includes(String(p.query).toLowerCase()));
      if (b) { await chrome.tabs.create({url:b.url}); result={ok:true,title:b.title,url:b.url}; }
      else result={ok:false,error:"Bookmark not found."};
    }
  } catch(e) { result = {ok:false,error:String(e)}; }
  await postJSON("/api/chrome/result", {id:job.id, result});
  await pushState();
}
async function poll() {
  await heartbeat();
  const job = await getJSON("/api/chrome/pending");
  if (job && job.id) await runAction(job);
}
async function tick() { await poll(); }
setInterval(tick, 700);
setInterval(pushState, 2500);
chrome.runtime.onInstalled.addListener(() => { pushState(); tick(); });
chrome.runtime.onStartup.addListener(() => { pushState(); tick(); });
chrome.tabs.onActivated.addListener(() => setTimeout(pushState, 350));
chrome.tabs.onUpdated.addListener((tabId, changeInfo) => { if (changeInfo.status === "complete") setTimeout(pushState, 500); });
tick();
pushState();
