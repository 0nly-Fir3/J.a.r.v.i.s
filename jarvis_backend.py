import json, os, re, subprocess, time, webbrowser
from datetime import datetime
from pathlib import Path
from flask import Flask, jsonify, request
try: import psutil
except Exception: psutil=None
try: import pyautogui
except Exception: pyautogui=None
try: import pyperclip
except Exception: pyperclip=None

APP_DIR=Path(__file__).resolve().parent
APPS_FILE=APP_DIR/'apps.json'
FOLDERS_FILE=APP_DIR/'folders.json'
SCREENSHOT_DIR=APP_DIR/'screenshots'
SCREENSHOT_DIR.mkdir(exist_ok=True)
app=Flask(__name__)
PENDING_ACTION=None
PENDING_CREATED=0
PENDING_TIMEOUT_SECONDS=30

@app.after_request
def cors(r):
    r.headers['Access-Control-Allow-Origin']='*'
    r.headers['Access-Control-Allow-Headers']='Content-Type'
    r.headers['Access-Control-Allow-Methods']='GET, POST, OPTIONS'
    return r

@app.route('/health',methods=['GET','OPTIONS'])
def health():
    return jsonify(ok=True,name='JARVIS PC Controller',version='2.0',host='127.0.0.1',port=5050,pending_action=bool(PENDING_ACTION))

@app.route('/command',methods=['POST','OPTIONS'])
def command():
    if request.method=='OPTIONS': return jsonify(ok=True)
    data=request.get_json(silent=True) or {}
    text=str(data.get('text','')).strip()
    lang=str(data.get('lang','en')).lower()
    if not text: return jsonify(ok=False,message='No command text received.'),400
    try:
        return jsonify(ok=True,**handle_command(text,lang))
    except PermissionError as e:
        return jsonify(ok=False,message=str(e)),403
    except Exception as e:
        return jsonify(ok=False,message=f'PC controller error: {e}'),500

def load_json(path,default):
    if not path.exists():
        path.write_text(json.dumps(default,indent=4),encoding='utf-8')
        return default
    try: return json.loads(path.read_text(encoding='utf-8'))
    except Exception: return default
def save_json(path,data): path.write_text(json.dumps(data,indent=4),encoding='utf-8')
def normalize(t): return re.sub(r'\s+',' ',str(t).lower().strip())
def reply(en,sv,lang): return sv if lang.startswith('sv') else en

def handle_command(text,lang):
    global PENDING_ACTION,PENDING_CREATED
    cmd=normalize(text)
    if is_confirmation(cmd): return run_pending_action(lang)
    if is_cancel(cmd):
        PENDING_ACTION=None;PENDING_CREATED=0
        return {'message':reply('Cancelled, sir.','Avbrutet.',lang),'action':'cancel_pending'}
    teach=parse_teach_app(text)
    if teach: return teach_app(teach['name'],teach['path'],lang)
    if any(w in cmd for w in ['delete','remove file','format','wipe','disable antivirus','powershell','cmd','command prompt','terminal','regedit','radera','ta bort fil','formatera']):
        raise PermissionError(reply('That action is blocked in PC Controller v2 for safety.','Den åtgärden är blockerad i PC Controller v2 av säkerhetsskäl.',lang))
    close_target=extract_close_target(cmd)
    if close_target: return request_confirmation('close_app',f'close {close_target}',{'target':close_target},lang)
    if any(x in cmd for x in ['shutdown','shut down','restart','reboot','stäng av','starta om']):
        return request_confirmation('power_action',cmd,{'command':cmd},lang)
    hotkey=parse_hotkey(cmd)
    if hotkey: return press_hotkey(hotkey,lang)
    if cmd in ['copy','kopiera'] or cmd.endswith(' copy') or cmd.endswith(' kopiera'): return press_hotkey(['ctrl','c'],lang,reply('Copied, sir.','Kopierat.',lang),'copy')
    if cmd in ['paste','klistra in'] or cmd.endswith(' paste') or cmd.endswith(' klistra in'): return press_hotkey(['ctrl','v'],lang,reply('Pasted, sir.','Klistrat in.',lang),'paste')
    m=re.match(r'^\s*(?:type|write|skriv)\s+(.+)$',text,re.I)
    if m: return type_text(m.group(1),lang)
    if 'clipboard' in cmd or 'urklipp' in cmd: return read_clipboard(lang)
    if is_stats(cmd): return system_stats(lang)
    if 'screenshot' in cmd or 'screen shot' in cmd or 'skärmbild' in cmd or 'skärmdump' in cmd: return screenshot(lang)
    if 'lock pc' in cmd or 'lock computer' in cmd or 'lås dator' in cmd or 'lås datorn' in cmd:
        subprocess.Popen(['rundll32.exe','user32.dll,LockWorkStation'],shell=False)
        return {'message':reply('Locking the PC, sir.','Låser datorn.',lang),'action':'lock_pc'}
    if 'mute' in cmd or 'unmute' in cmd or 'tysta' in cmd: return media('volumemute',reply('Toggled mute, sir.','Växlade ljud av/på.',lang),'volume_mute')
    if 'volume up' in cmd or 'höj volym' in cmd: return media('volumeup',reply('Volume increased, sir.','Volymen höjdes.',lang),'volume_up',5)
    if 'volume down' in cmd or 'sänk volym' in cmd: return media('volumedown',reply('Volume decreased, sir.','Volymen sänktes.',lang),'volume_down',5)
    m=re.search(r'(?:set volume to|volume to|sätt volym(?:en)? till)\s*(\d{1,3})',cmd)
    if m: return set_volume(max(0,min(100,int(m.group(1)))),lang)
    folder=extract_folder(cmd)
    if folder: return open_folder(folder,lang)
    app_target=extract_app(cmd)
    if app_target: return open_app(app_target,lang)
    return {'message':reply('I received the command, but PC Controller v2 does not support that action yet.','Jag tog emot kommandot, men PC Controller v2 stöder inte den åtgärden än.',lang),'action':'unsupported'}

def request_confirmation(t,label,payload,lang):
    global PENDING_ACTION,PENDING_CREATED
    PENDING_ACTION={'type':t,'label':label,'payload':payload};PENDING_CREATED=time.time()
    return {'message':reply(f'Confirm action: {label}. Say or type confirm to continue, or cancel to stop.',f'Bekräfta åtgärd: {label}. Säg eller skriv bekräfta för att fortsätta, eller avbryt för att stoppa.',lang),'action':'confirmation_required','pending':PENDING_ACTION}
def is_confirmation(cmd): return any(cmd==x or cmd.endswith(' '+x) for x in ['confirm','yes','do it','go ahead','continue','bekräfta','ja','kör','fortsätt'])
def is_cancel(cmd): return any(cmd==x or cmd.endswith(' '+x) for x in ['cancel','abort','never mind','stop','avbryt','nej','stopp'])
def run_pending_action(lang):
    global PENDING_ACTION,PENDING_CREATED
    if not PENDING_ACTION: return {'message':reply('There is no pending action to confirm.','Det finns ingen väntande åtgärd att bekräfta.',lang),'action':'confirm_none'}
    if time.time()-PENDING_CREATED>PENDING_TIMEOUT_SECONDS:
        PENDING_ACTION=None;PENDING_CREATED=0
        return {'message':reply('The pending action expired, sir.','Den väntande åtgärden har gått ut.',lang),'action':'confirm_expired'}
    a=PENDING_ACTION;PENDING_ACTION=None;PENDING_CREATED=0
    if a['type']=='close_app': return close_app(a['payload']['target'],lang)
    if a['type']=='power_action': return power_action(a['payload']['command'],lang)
    return {'message':'Unknown pending action.','action':'confirm_unknown'}

def parse_teach_app(text):
    for p in [r'^\s*(?:remember|teach|save)\s+app\s+(.+?)\s+(?:is|=)\s+(.+?)\s*$',r'^\s*(?:kom ihåg|spara)\s+app\s+(.+?)\s+(?:är|=)\s+(.+?)\s*$']:
        m=re.match(p,text,re.I)
        if m: return {'name':m.group(1).strip().strip('"'),'path':m.group(2).strip().strip('"')}
    return None
def teach_app(name,path,lang):
    apps=load_json(APPS_FILE,default_apps());apps[normalize(name)]={'path':path,'aliases':[]};save_json(APPS_FILE,apps)
    return {'message':reply(f'I saved {name} in apps.json, sir.',f'Jag sparade {name} i apps.json.',lang),'action':'teach_app','target':normalize(name),'path':path}
def extract_close_target(cmd):
    m=re.search(r'\b(?:close|quit|kill|stäng|avsluta)\s+(.+)$',cmd)
    if not m: return None
    t=re.sub(r'\b(app|application|program|window|fönster|appen)\b','',m.group(1)).strip()
    return t or None
def close_app(target,lang):
    if psutil is None: return {'message':'psutil is not installed. Run install_requirements.bat first.','action':'close_app'}
    target_l=normalize(target);apps=load_json(APPS_FILE,default_apps());names={target_l}
    for n,e in apps.items():
        alln=[n]+e.get('aliases',[])
        if any(normalize(x) in target_l or target_l in normalize(x) for x in alln):
            names.add(normalize(n));names.add(Path(os.path.expandvars(e.get('path',''))).stem.lower())
            if normalize(n)=='discord': names.add('discord')
    killed=[]
    for proc in psutil.process_iter(['pid','name','exe']):
        try:
            pn=normalize(proc.info.get('name') or '');px=normalize(Path(proc.info.get('exe') or '').stem)
            if any(n and (n in pn or n in px) for n in names):
                proc.terminate();killed.append(proc.info.get('name') or str(proc.pid))
        except Exception: pass
    if not killed: return {'message':reply(f'I could not find a running app matching {target}.',f'Jag hittade ingen körande app som matchar {target}.',lang),'action':'close_app_none'}
    return {'message':reply(f'Closed {target}, sir.',f'Stängde {target}.',lang),'action':'close_app','closed':killed[:10]}
def power_action(cmd,lang):
    if 'restart' in cmd or 'reboot' in cmd or 'starta om' in cmd:
        subprocess.Popen(['shutdown','/r','/t','10']);return {'message':reply('Restart scheduled in 10 seconds, sir.','Omstart schemalagd om 10 sekunder.',lang),'action':'restart'}
    subprocess.Popen(['shutdown','/s','/t','10']);return {'message':reply('Shutdown scheduled in 10 seconds, sir.','Avstängning schemalagd om 10 sekunder.',lang),'action':'shutdown'}
def parse_hotkey(cmd):
    mapping={'alt tab':['alt','tab'],'alt-tab':['alt','tab'],'windows d':['win','d'],'win d':['win','d'],'show desktop':['win','d'],'windows r':['win','r'],'win r':['win','r'],'windows e':['win','e'],'win e':['win','e'],'select all':['ctrl','a'],'save':['ctrl','s'],'new tab':['ctrl','t'],'close tab':['ctrl','w'],'reopen tab':['ctrl','shift','t'],'refresh':['f5'],'fullscreen':['f11'],'visa skrivbord':['win','d'],'kopiera':['ctrl','c'],'klistra in':['ctrl','v']}
    for phrase,keys in mapping.items():
        if phrase in cmd: return keys
    m=re.search(r'(?:press|hotkey|tryck)\s+(.+)$',cmd)
    if m:
        return [norm_key(x) for x in re.split(r'\s*\+\s*|\s+plus\s+|\s+och\s+',m.group(1).strip()) if norm_key(x)]
    return None
def norm_key(k):
    k=normalize(k);return {'windows':'win','window':'win','control':'ctrl','escape':'esc'}.get(k,k)
def press_hotkey(keys,lang,message=None,action='hotkey'):
    if pyautogui is None: return {'message':'pyautogui is not installed. Run install_requirements.bat first.','action':action}
    if len(keys)==1: pyautogui.press(keys[0])
    else: pyautogui.hotkey(*keys)
    return {'message':message or reply(f"Pressed {' + '.join(keys)}, sir.",f"Tryckte {' + '.join(keys)}.",lang),'action':action,'keys':keys}
def type_text(text,lang):
    if pyautogui is None: return {'message':'pyautogui is not installed. Run install_requirements.bat first.','action':'type_text'}
    pyautogui.write(text,interval=.01);return {'message':reply('Typed the text, sir.','Skrev texten.',lang),'action':'type_text'}
def read_clipboard(lang):
    if pyperclip is None: return {'message':'pyperclip is not installed. Run install_requirements.bat first.','action':'clipboard'}
    content=pyperclip.paste()
    return {'message':reply('Clipboard contains: '+content[:400],'Urklipp innehåller: '+content[:400],lang) if content else reply('The clipboard is empty.','Urklipp är tomt.',lang),'action':'clipboard','content':content}
def is_stats(cmd): return any(x in cmd for x in ['cpu usage','ram usage','memory usage','system stats','battery','system status','processor','minne','systemstatistik','batteri'])
def system_stats(lang):
    if psutil is None: return {'message':'psutil is not installed. Run install_requirements.bat first.','action':'system_stats'}
    cpu=psutil.cpu_percent(interval=.6);mem=psutil.virtual_memory();disk=psutil.disk_usage(str(Path.home().anchor or 'C:\\'));bat=psutil.sensors_battery()
    b='No battery detected' if not bat else f"{bat.percent:.0f}% {'charging' if bat.power_plugged else 'on battery'}"
    return {'message':reply(f'CPU {cpu:.0f} percent. RAM {mem.percent:.0f} percent. Disk {disk.percent:.0f} percent. Battery: {b}.',f'CPU {cpu:.0f} procent. RAM {mem.percent:.0f} procent. Disk {disk.percent:.0f} procent. Batteri: {b}.',lang),'action':'system_stats'}
def screenshot(lang):
    if pyautogui is None: return {'message':'pyautogui is not installed. Run install_requirements.bat first.','action':'screenshot'}
    p=SCREENSHOT_DIR/f"jarvis_screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png";pyautogui.screenshot().save(p)
    return {'message':reply(f'Screenshot saved, sir: {p}',f'Skärmbild sparad: {p}',lang),'action':'screenshot','path':str(p)}
def media(key,msg,action,presses=1):
    if pyautogui is None: return {'message':'pyautogui is not installed. Run install_requirements.bat first.','action':action}
    for _ in range(presses): pyautogui.press(key);time.sleep(.03)
    return {'message':msg,'action':action}
def set_volume(level,lang):
    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        dev=AudioUtilities.GetSpeakers();interface=dev.Activate(IAudioEndpointVolume._iid_,CLSCTX_ALL,None);vol=cast(interface,POINTER(IAudioEndpointVolume));vol.SetMasterVolumeLevelScalar(level/100,None)
        return {'message':reply(f'Volume set to {level} percent, sir.',f'Volymen satt till {level} procent.',lang),'action':'set_volume'}
    except Exception:
        if pyautogui:
            for _ in range(50): pyautogui.press('volumedown')
            for _ in range(int(level/2)): pyautogui.press('volumeup')
        return {'message':reply(f'Volume adjusted close to {level} percent, sir.',f'Volymen justerades ungefär till {level} procent.',lang),'action':'set_volume'}
def extract_folder(cmd):
    folders={'downloads':['downloads','download folder','downloads folder','hämtade filer'],'desktop':['desktop','desktop folder','skrivbord'],'documents':['documents','documents folder','dokument'],'pictures':['pictures','photos','bilder'],'music':['music','musik'],'videos':['videos','filmer'],'home':['home folder','user folder','hem'],'explorer':['file explorer','explorer','utforskaren']}
    if not re.search(r'\b(open|show|launch|öppna|visa|starta)\b',cmd): return None
    for t,keys in folders.items():
        if any(k in cmd for k in keys): return t
    return None
def open_folder(target,lang):
    folders=load_json(FOLDERS_FILE,default_folders());path=folders.get(target)
    if not path: return {'message':f'I do not have a folder path configured for {target}.','action':'open_folder'}
    exp=os.path.expandvars(path)
    if target=='explorer': subprocess.Popen(['explorer.exe'])
    else: os.startfile(exp)
    return {'message':reply(f'Opening {target}, sir.',f'Öppnar {target}.',lang),'action':'open_folder','path':exp}
def extract_app(cmd):
    if not re.search(r'\b(open|start|launch|öppna|starta)\b',cmd): return None
    cleaned=cmd
    for w in ['open','start','launch','öppna','starta','app','application','program']: cleaned=re.sub(rf'\b{re.escape(w)}\b',' ',cleaned)
    cleaned=normalize(cleaned)
    apps=load_json(APPS_FILE,default_apps());aliases={}
    for name,e in apps.items():
        aliases[name.lower()]=name
        for a in e.get('aliases',[]): aliases[a.lower()]=name
    for alias,name in aliases.items():
        if alias in cleaned: return name
    return cleaned or None
def open_app(target,lang):
    apps=load_json(APPS_FILE,default_apps());entry=None;key=None;tl=target.lower()
    for name,e in apps.items():
        names=[name.lower()]+[a.lower() for a in e.get('aliases',[])]
        if tl in names or any(n in tl for n in names): entry=e;key=name;break
    if not entry: return {'message':reply(f'I do not have {target} in apps.json yet. Teach it with: remember app {target} is C:\\Path\\To\\App.exe',f'Jag har inte {target} i apps.json än.',lang),'action':'open_app_missing'}
    cmd=os.path.expandvars(entry.get('path',''));args=entry.get('args',[])
    try:
        if cmd.lower().startswith('http') or '://' in cmd: webbrowser.open(cmd)
        elif args: subprocess.Popen([cmd,*args])
        elif cmd.lower().endswith('.exe') or '\\' in cmd or '/' in cmd: os.startfile(cmd)
        else: subprocess.Popen([cmd])
        return {'message':reply(f'Opening {key}, sir.',f'Öppnar {key}.',lang),'action':'open_app'}
    except Exception as e: return {'message':f'I found {key}, but could not open it: {e}','action':'open_app_error'}
def default_folders(): return {'downloads':'%USERPROFILE%\\Downloads','desktop':'%USERPROFILE%\\Desktop','documents':'%USERPROFILE%\\Documents','pictures':'%USERPROFILE%\\Pictures','music':'%USERPROFILE%\\Music','videos':'%USERPROFILE%\\Videos','home':'%USERPROFILE%','explorer':'explorer.exe'}
def default_apps(): return {'discord':{'path':'%LOCALAPPDATA%\\Discord\\Update.exe','args':['--processStart','Discord.exe'],'aliases':['discord app']},'steam':{'path':'C:\\Program Files (x86)\\Steam\\steam.exe','aliases':['steam app']},'spotify':{'path':'%APPDATA%\\Spotify\\Spotify.exe','aliases':['spotify app']},'chrome':{'path':'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe','aliases':['google chrome','chrome browser']},'edge':{'path':'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe','aliases':['microsoft edge','edge browser']},'notepad':{'path':'notepad.exe','aliases':['notes']},'calculator':{'path':'calc.exe','aliases':['calculator app','calc']},'task manager':{'path':'taskmgr.exe','aliases':['taskmanager','activity manager']},'obs':{'path':'C:\\Program Files\\obs-studio\\bin\\64bit\\obs64.exe','aliases':['obs studio']},'epic games':{'path':'C:\\Program Files (x86)\\Epic Games\\Launcher\\Portal\\Binaries\\Win64\\EpicGamesLauncher.exe','aliases':['epic','epic launcher']},'fortnite':{'path':'com.epicgames.launcher://apps/Fortnite?action=launch&silent=true','aliases':['fortnite game']}}
if __name__=='__main__':
    load_json(APPS_FILE,default_apps());load_json(FOLDERS_FILE,default_folders())
    print('JARVIS PC Controller v2 running on http://127.0.0.1:5050')
    print('Keep this window open while using jarvis_pc_v2.html')
    app.run(host='127.0.0.1',port=5050,debug=False)
