
function visible(el) {
  const r = el.getBoundingClientRect();
  const s = window.getComputedStyle(el);
  return r.width > 2 && r.height > 2 && s.visibility !== "hidden" && s.display !== "none" && r.bottom >= 0 && r.right >= 0 && r.top <= innerHeight && r.left <= innerWidth;
}
function labelFor(el) {
  return (el.innerText || el.value || el.getAttribute("aria-label") || el.getAttribute("title") || el.getAttribute("placeholder") || el.href || "").replace(/\s+/g," ").trim();
}
function elements() {
  const q = "a, button, input, textarea, select, [role='button'], [role='link'], [onclick], summary";
  return Array.from(document.querySelectorAll(q)).filter(visible).map((el, i) => {
    const r = el.getBoundingClientRect();
    return {index:i+1, tag:el.tagName.toLowerCase(), label:labelFor(el).slice(0,200), x:r.left+r.width/2, y:r.top+r.height/2, width:r.width, height:r.height, href:el.href || ""};
  }).filter(e => e.label || ["input","textarea","select"].includes(e.tag));
}
function snapshot() {
  return {ok:true, title:document.title, url:location.href, selectedText:String(getSelection()), text:document.body.innerText.slice(0,50000), elements:elements().slice(0,250)};
}
function clickText(target, ordinal=1) {
  const t = String(target || "").toLowerCase().trim();
  let matches = Array.from(document.querySelectorAll("a,button,input,textarea,select,[role='button'],[role='link'],[onclick],summary"))
    .filter(visible)
    .filter(el => labelFor(el).toLowerCase().includes(t));
  const el = matches[Math.max(0, Number(ordinal || 1)-1)];
  if (!el) return {ok:false, error:`Could not find visible element matching ${target}.`, snapshot:snapshot()};
  el.scrollIntoView({behavior:"smooth", block:"center"});
  setTimeout(() => el.click(), 200);
  return {ok:true, clicked:labelFor(el), tag:el.tagName.toLowerCase()};
}
function inputText(text) {
  const el = document.activeElement;
  if (!el) return {ok:false, error:"No active element."};
  if ("value" in el) {
    el.value = text;
    el.dispatchEvent(new Event("input", {bubbles:true}));
    el.dispatchEvent(new Event("change", {bubbles:true}));
    return {ok:true};
  }
  document.execCommand("insertText", false, text);
  return {ok:true};
}
chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === "snapshot") sendResponse(snapshot());
  else if (msg.type === "click_text") sendResponse(clickText(msg.target, msg.ordinal));
  else if (msg.type === "input_text") sendResponse(inputText(msg.text));
  else sendResponse({ok:false, error:"Unknown content action."});
  return true;
});
