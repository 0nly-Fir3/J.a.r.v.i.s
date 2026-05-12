async function check(){
  const el=document.getElementById("status");
  try{
    await fetch("http://127.0.0.1:5050/api/chrome/heartbeat", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({source:"popup"})});
    const r=await fetch("http://127.0.0.1:5050/api/chrome/status", {cache:"no-store"});
    const s=await r.json();
    el.textContent = s.connected
      ? `Connected\nTabs: ${s.tabs}\nBookmarks: ${s.bookmarks}\nPage: ${s.page_title || s.page_url || "No normal page yet"}\nLast error: ${s.last_error || "none"}`
      : `JARVIS server reached, but bridge heartbeat is not active yet. Reload the extension and open google.com.`;
  }catch(e){el.textContent="JARVIS server not reachable. Start start.bat first.";}
}
document.getElementById("push").onclick=check;
check();
