"""Mandalakalam Diary - Vercel-ready Flask app.
Data is saved in a Redis database (Upstash) connected through Vercel.
Optional settings (Vercel > Settings > Environment Variables):
  APP_PIN     = a PIN that committee members must enter
  SECRET_KEY  = any long random text
"""
import json, os, urllib.request
from flask import Flask, request, session, jsonify, redirect, Response
from werkzeug.exceptions import HTTPException

BASE = os.path.dirname(os.path.abspath(__file__))
N = 41
PIN = os.environ.get("APP_PIN", "")


def find_env(suffixes):
    """Find the database setting even if Vercel added a prefix to its name."""
    for k, v in os.environ.items():
        if v and "READ_ONLY" not in k and any(k.endswith(x) for x in suffixes):
            return v


URL = find_env(("KV_REST_API_URL", "REDIS_REST_URL"))
TOKEN = find_env(("KV_REST_API_TOKEN", "REDIS_REST_TOKEN"))
PERSISTENT = bool(URL and TOKEN)
FILE = "/tmp/diary.json" if os.environ.get("VERCEL") else os.path.join(BASE, "diary_data.json")

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Mandalakalam Diary</title>
<style>
:root{--bg:#fff8ef;--card:#fff;--ink:#2b1d12;--mut:#7a6552;--acc:#c2410c;--acc-ink:#fff;--line:#ecd9c3;--soft:rgba(194,65,12,.12)}
@media (prefers-color-scheme:dark){:root{color-scheme:dark;--bg:#1b130d;--card:#261b13;--ink:#f6e9da;--mut:#b9a48f;--acc:#f97316;--acc-ink:#1b130d;--line:#43322a;--soft:rgba(249,115,22,.18)}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:system-ui,-apple-system,"Segoe UI",sans-serif;line-height:1.45}
.wrap{max-width:960px;margin:0 auto;padding:16px}
h1{font-size:1.3rem;margin:0 0 2px}h2{font-size:1.05rem;margin:0 0 10px}
.sub{color:var(--mut);font-size:.85rem;margin-bottom:8px}
.tabs{display:flex;gap:6px;margin:10px 0;overflow-x:auto}.tabs button{white-space:nowrap}
button,select,input,textarea{font:inherit;color:var(--ink);background:var(--card);border:1px solid var(--line);border-radius:8px;padding:8px 10px}
button{cursor:pointer}button.pri,.tabs button.on{background:var(--acc);color:var(--acc-ink);border-color:var(--acc)}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px;margin-bottom:14px}
.row{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px}.row>*{flex:1;min-width:120px}
label{display:block;font-size:.8rem;color:var(--mut);margin-bottom:3px}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:8px;margin-bottom:14px}
.stat{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px}
.stat b{display:block;font-size:1.15rem}.stat span{font-size:.78rem;color:var(--mut)}
.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:.85rem}
th,td{border-bottom:1px solid var(--line);padding:6px;text-align:left;vertical-align:top}
td input,td select{width:100%;min-width:90px;padding:5px 6px}
.msg{color:var(--acc);font-size:.85rem}
.g2{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px}
.bar{display:flex;align-items:center;gap:8px;margin:6px 0;font-size:.85rem}.bar i{display:block;height:10px;background:var(--acc);border-radius:5px;min-width:2px}
.bar span:first-child{width:100px;flex:none}.prog{height:12px;background:var(--soft);border-radius:6px;overflow:hidden}.prog i{display:block;height:100%;background:var(--acc)}
.chip{display:inline-block;margin:3px;padding:4px 9px;border:1px solid var(--line);border-radius:14px;font-size:.8rem;cursor:pointer;background:var(--card)}
textarea{width:100%;height:200px;font-family:ui-monospace,Menlo,monospace;font-size:.78rem}
</style>
</head>
<body>
<div class="wrap">
<h1>🪔 Mandalakalam Digital Diary</h1>
<div class="sub">41 days · 17 Nov 2026 to 27 Dec 2026 · shared committee diary</div>
<div id="dbstat" class="sub" style="font-weight:600">Page version 3 · checking database…</div>
<div id="warn" hidden class="card" style="border-color:#c00;color:#c00">Database not connected: data will NOT be saved permanently. Connect the Redis database in Vercel (see setup steps).</div>
<div class="tabs"><button data-t="dash" class="on">Dashboard</button><button data-t="diary">Daily Diary</button><button data-t="list">Sponsor List</button><button data-t="rep">Reports</button></div>

<div id="dash">
  <div class="stats" id="ds"></div>
  <div class="card"><h2>Sponsorship progress</h2><div class="prog"><i id="pg"></i></div><div class="sub" id="pgt" style="margin-top:6px"></div></div>
  <div class="g2">
    <div class="card"><h2>Money by payment method</h2><div id="pmb"></div></div>
    <div class="card"><h2>Top sponsors</h2><div id="top"></div></div>
  </div>
  <div class="card"><h2>Days still needing a sponsor</h2><div id="pend"></div></div>
</div>

<div id="diary" hidden>
  <div class="card"><label for="day">Select day</label><select id="day" style="width:100%"></select></div>
  <div class="card"><h2>Daily sponsor (daily expense)</h2>
    <div class="row"><div style="flex:2"><label>Sponsor name</label><input id="sp" style="width:100%"></div>
    <div><label>Bill amount (Rs)</label><input id="bill" type="number" min="0" style="width:100%"></div>
    <div><label>Payment method</label><select id="pm" style="width:100%"></select></div></div>
    <label>Notes</label><input id="nt" style="width:100%;margin-bottom:8px">
    <button class="pri" id="saveDay">Save daily sponsor</button> <span class="msg" id="m1"></span></div>
  <div class="card"><h2>Other sponsors</h2>
    <div class="row"><div><label>Type</label><select id="ty"><option>Money</option><option>Item</option></select></div>
    <div><label>Sponsor name</label><input id="nm" style="width:100%"></div>
    <div id="amtBox"><label>Amount (Rs)</label><input id="am" type="number" min="0" style="width:100%"></div>
    <div id="itBox" hidden><label>Item (oil, rice, flowers…)</label><input id="it" style="width:100%"></div>
    <div id="pmBox"><label>Payment method</label><select id="pm2" style="width:100%"></select></div></div>
    <button class="pri" id="add">Add sponsor</button> <span class="msg" id="m2"></span>
    <div class="scroll" style="margin-top:10px"><table><thead><tr><th>Sponsor</th><th>Type</th><th>Amount</th><th>Item</th><th>Payment</th><th></th></tr></thead><tbody id="elist"></tbody></table></div>
    <div class="sub" style="margin:8px 0 0">Edit any cell directly; changes save automatically.</div></div>
  <div class="stats" id="dstats"></div>
</div>

<div id="list" hidden>
  <div class="card"><div class="row">
    <div><label>Search</label><input id="fq" placeholder="Name or item" style="width:100%"></div>
    <div><label>Type</label><select id="ft" style="width:100%"><option>All</option><option>Daily</option><option>Money</option><option>Item</option></select></div>
    <div><label>Payment</label><select id="fp" style="width:100%"></select></div></div>
    <div class="sub" id="fcount"></div>
    <div class="scroll"><table><thead><tr><th>Day</th><th>Date</th><th>Sponsor</th><th>Type</th><th>Amount</th><th>Item</th><th>Payment</th></tr></thead><tbody id="lb"></tbody></table></div></div>
</div>

<div id="rep" hidden>
  <div class="card"><h2>Export report</h2>
    <div class="row"><div><label>Report</label><select id="rt" style="width:100%">
      <option value="all">All sponsors (daily + other)</option><option value="days">Day-wise summary (41 days)</option>
      <option value="pay">Payment method summary</option><option value="items">Item sponsors only</option></select></div></div>
    <textarea id="csv" readonly></textarea>
    <div style="margin-top:8px"><button class="pri" id="dl">Download CSV file</button> <button id="cp">Copy</button> <span class="msg" id="m3"></span></div>
    <div class="sub" style="margin-top:8px">The downloaded CSV file opens in Excel.</div></div>
</div>
</div>
<script>
const START=new Date(2026,10,17),N=41,PM=["Cash","UPI","Bank Transfer","Cheque","Card","Other"];
const $=id=>document.getElementById(id);
let S={days:Array.from({length:N},(_,i)=>({sp:i==0?"RAVI Thekkinkal":"",bill:0,pm:"Cash",nt:"",c:[]}))};
let cur=Math.min(Math.max(Math.floor((new Date()-START)/864e5),0),N-1);
function showWarn(m){$("warn").textContent=m;$("warn").hidden=false}
function save(){fetch("/api/day/"+cur,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(S.days[cur])}).then(async r=>{if(r.status==401){location="/login";return}if(!r.ok){const j=await r.json().catch(()=>({}));const m="NOT SAVED. "+(j.error||("Error "+r.status));showWarn(m);alert(m)}}).catch(e=>alert("NOT SAVED. Check internet. "+e.message))}
async function refresh(){try{const r=await fetch("/api/state");if(r.status==401){location="/login";return}const j=await r.json();if(!r.ok)throw new Error(j.error||("Error "+r.status));S={days:j.days};$("dbstat").textContent="Page version 3 · Database: "+(j.persistent?"CONNECTED ✓":"NOT CONNECTED ✗");if(j.persistent)$("warn").hidden=true;else showWarn("Database not connected: data will NOT be saved permanently. Connect the Redis database in Vercel.")}catch(e){$("dbstat").textContent="Page version 3 · Database: ERROR ✗";showWarn("Cannot load saved data. "+e.message)}}
const fmtD=i=>{const d=new Date(START);d.setDate(d.getDate()+i);return d.toLocaleDateString("en-GB",{day:"2-digit",month:"short",year:"numeric",weekday:"short"})};
const rs=n=>"Rs "+Number(n||0).toLocaleString("en-IN");
const esc=s=>String(s??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const pmOpts=(v,all)=>(all?["All",...PM]:PM).map(p=>`<option${p==v?" selected":""}>${p}</option>`).join("");
const sel=$("day");
for(let i=0;i<N;i++){const o=document.createElement("option");o.value=i;o.textContent="Day "+(i+1)+" – "+fmtD(i);sel.appendChild(o)}
sel.value=cur;$("pm").innerHTML=pmOpts();$("pm2").innerHTML=pmOpts();$("fp").innerHTML=pmOpts("All",true);
const stat=(l,v)=>`<div class="stat"><b>${v}</b><span>${l}</span></div>`;
function rows(){const r=[];S.days.forEach((d,i)=>{
  if(d.sp.trim())r.push({day:i+1,date:fmtD(i),name:d.sp,type:"Daily",amt:+d.bill||0,item:"",pm:d.pm||"Cash"});
  d.c.forEach(x=>r.push({day:i+1,date:fmtD(i),name:x.n,type:x.t,amt:+x.a||0,item:x.it||"",pm:x.t=="Money"?(x.pm||"Cash"):""}))});return r}
function dash(){
  const r=rows(),bill=r.filter(x=>x.type=="Daily").reduce((s,x)=>s+x.amt,0),oth=r.filter(x=>x.type=="Money").reduce((s,x)=>s+x.amt,0);
  const f=S.days.filter(d=>d.sp.trim()).length,names=new Set(r.map(x=>x.name.trim().toLowerCase()));
  $("ds").innerHTML=stat("Total daily bills",rs(bill))+stat("Other money",rs(oth))+stat("Grand total",rs(bill+oth))+stat("Item sponsors",r.filter(x=>x.type=="Item").length)+stat("Unique sponsors",names.size)+stat("Avg daily bill",rs(f?bill/f:0));
  $("pg").style.width=(f/N*100)+"%";$("pgt").textContent=f+" of "+N+" days sponsored · "+(N-f)+" pending";
  const pt={};r.filter(x=>x.amt>0&&x.pm).forEach(x=>pt[x.pm]=(pt[x.pm]||0)+x.amt);const mx=Math.max(1,...Object.values(pt));
  $("pmb").innerHTML=Object.keys(pt).length?Object.entries(pt).sort((a,b)=>b[1]-a[1]).map(([k,v])=>`<div class="bar"><span>${k}</span><i style="width:${v/mx*55}%"></i><span>${rs(v)}</span></div>`).join(""):'<div class="sub">No payments yet</div>';
  const g={};r.forEach(x=>{const k=x.name.trim().toLowerCase();g[k]=g[k]||{n:x.name,a:0,c:0};g[k].a+=x.amt;g[k].c++});
  $("top").innerHTML=Object.values(g).sort((a,b)=>b.a-a.a).slice(0,6).map(x=>`<div class="bar"><span style="width:auto;flex:1">${esc(x.n)}</span><span>${rs(x.a)} · ${x.c}×</span></div>`).join("")||'<div class="sub">No sponsors yet</div>';
  const p=S.days.map((d,i)=>d.sp.trim()?"":`<span class="chip" data-go="${i}">Day ${i+1} · ${fmtD(i).slice(0,6)}</span>`).join("");
  $("pend").innerHTML=p||'<div class="sub">All days sponsored 🙏</div>';
}
function diary(){
  const d=S.days[cur];$("sp").value=d.sp;$("bill").value=d.bill||"";$("nt").value=d.nt;$("pm").value=d.pm||"Cash";
  $("elist").innerHTML=d.c.map((x,i)=>`<tr><td><input data-i="${i}" data-f="n" value="${esc(x.n)}"></td>
  <td><select data-i="${i}" data-f="t"><option${x.t=="Money"?" selected":""}>Money</option><option${x.t=="Item"?" selected":""}>Item</option></select></td>
  <td><input type="number" min="0" data-i="${i}" data-f="a" value="${x.t=="Money"?x.a:""}" ${x.t=="Item"?"disabled":""}></td>
  <td><input data-i="${i}" data-f="it" value="${esc(x.it)}" ${x.t=="Money"?"disabled":""}></td>
  <td><select data-i="${i}" data-f="pm" ${x.t=="Item"?"disabled":""}>${pmOpts(x.pm||"Cash")}</select></td>
  <td><button data-del="${i}">✕</button></td></tr>`).join("");
  const mt=d.c.filter(x=>x.t=="Money").reduce((s,x)=>s+(+x.a||0),0);
  $("dstats").innerHTML=stat("Daily bill",rs(d.bill))+stat("Other money",rs(mt))+stat("Item sponsors",d.c.filter(x=>x.t=="Item").length);
}
function list(){
  const q=$("fq").value.toLowerCase(),t=$("ft").value,p=$("fp").value;
  const r=rows().filter(x=>(t=="All"||x.type==t)&&(p=="All"||x.pm==p)&&(!q||(x.name+" "+x.item).toLowerCase().includes(q)));
  $("lb").innerHTML=r.map(x=>`<tr><td>${x.day}</td><td>${x.date}</td><td>${esc(x.name)}</td><td>${x.type}</td><td>${x.type=="Item"?"–":rs(x.amt)}</td><td>${esc(x.item)||"–"}</td><td>${x.pm||"–"}</td></tr>`).join("");
  $("fcount").textContent=r.length+" entries · money total "+rs(r.reduce((s,x)=>s+x.amt,0));
}
const q=s=>'"'+String(s??"").replace(/"/g,'""')+'"';
const toCsv=a=>a.map(r=>r.map(q).join(",")).join("\n");
function report(){
  const t=$("rt").value,r=rows();let a;
  if(t=="all")a=[["Day","Date","Sponsor","Type","Amount","Item","Payment method"],...r.map(x=>[x.day,x.date,x.name,x.type,x.amt,x.item,x.pm])];
  else if(t=="items")a=[["Day","Date","Sponsor","Item"],...r.filter(x=>x.type=="Item").map(x=>[x.day,x.date,x.name,x.item])];
  else if(t=="pay"){const g={};r.filter(x=>x.amt>0).forEach(x=>{const k=x.pm||"Other";g[k]=g[k]||[0,0];g[k][0]++;g[k][1]+=x.amt});
    a=[["Payment method","Entries","Total (Rs)"],...Object.entries(g).map(([k,v])=>[k,v[0],v[1]])]}
  else a=[["Day","Date","Daily sponsor","Bill","Payment method","Other money","Other sponsors","Items"],...S.days.map((d,i)=>{
    const m=d.c.filter(x=>x.t=="Money"),it=d.c.filter(x=>x.t=="Item");
    return [i+1,fmtD(i),d.sp,d.bill,d.pm,m.reduce((s,x)=>s+(+x.a||0),0),m.map(x=>x.n+" ("+x.a+", "+x.pm+")").join("; "),it.map(x=>x.n+": "+x.it).join("; ")]})];
  $("csv").value=toCsv(a);
}
function flash(id,t){$(id).textContent=t;setTimeout(()=>$(id).textContent="",2000)}
function show(t){["dash","diary","list","rep"].forEach(k=>$(k).hidden=k!=t);
  document.querySelectorAll(".tabs button").forEach(b=>b.classList.toggle("on",b.dataset.t==t));
  refresh().then(()=>({dash,diary,list,rep:report})[t]())}
document.querySelector(".tabs").onclick=e=>{if(e.target.dataset.t)show(e.target.dataset.t)};
$("pend").onclick=e=>{if(e.target.dataset.go!=null){cur=+e.target.dataset.go;sel.value=cur;show("diary")}};
sel.onchange=()=>{cur=+sel.value;refresh().then(diary)};
$("saveDay").onclick=()=>{const d=S.days[cur];d.sp=$("sp").value.trim();d.bill=+$("bill").value||0;d.pm=$("pm").value;d.nt=$("nt").value.trim();save();diary();flash("m1","Saved ✓")};
$("ty").onchange=()=>{const m=$("ty").value=="Money";$("amtBox").hidden=!m;$("pmBox").hidden=!m;$("itBox").hidden=m};
$("add").onclick=()=>{const t=$("ty").value,n=$("nm").value.trim(),a=+$("am").value,it=$("it").value.trim();
  if(!n)return flash("m2","Enter sponsor name");
  if(t=="Money"&&a<=0)return flash("m2","Enter amount");
  if(t=="Item"&&!it)return flash("m2","Enter item name");
  S.days[cur].c.push({n,t,a:t=="Money"?a:0,it:t=="Item"?it:"",pm:t=="Money"?$("pm2").value:""});save();
  $("nm").value="";$("am").value="";$("it").value="";diary();flash("m2","Added ✓")};
$("elist").addEventListener("change",e=>{const i=e.target.dataset.i,f=e.target.dataset.f;if(i==null)return;const x=S.days[cur].c[i],v=e.target.value;
  if(f=="n")x.n=v;else if(f=="a")x.a=+v||0;else if(f=="it")x.it=v;else if(f=="pm")x.pm=v;
  else{x.t=v;if(v=="Item"){x.a=0;x.pm=""}else{x.it="";x.pm=x.pm||"Cash"}}
  save();diary()});
$("elist").addEventListener("click",e=>{const i=e.target.dataset.del;if(i==null)return;S.days[cur].c.splice(i,1);save();diary()});
["fq","ft","fp"].forEach(k=>$(k).oninput=list);$("rt").onchange=report;
$("cp").onclick=async()=>{try{await navigator.clipboard.writeText($("csv").value);flash("m3","Copied ✓")}catch(e){$("csv").select();flash("m3","Press Ctrl+C")}};
$("dl").onclick=()=>{const b=new Blob(["\ufeff"+$("csv").value],{type:"text/csv"}),a=document.createElement("a");a.href=URL.createObjectURL(b);a.download="mandalakalam_"+$("rt").value+".csv";document.body.appendChild(a);a.click();a.remove()};
refresh().then(dash);
</script>
</body>
</html>
"""

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or (PIN + "-temple-diary-key")


def blank(i):
    return {"sp": "RAVI Thekkinkal" if i == 0 else "", "bill": 0, "pm": "Cash", "nt": "", "c": []}


def redis(*cmd):
    req = urllib.request.Request(
        URL, data=json.dumps(list(cmd)).encode(),
        headers={"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.load(r)["result"]


def read_file():
    try:
        with open(FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def get_days():
    days = [blank(i) for i in range(N)]
    if PERSISTENT:
        vals = redis("MGET", *[f"day:{i}" for i in range(N)])
        for i, v in enumerate(vals):
            if v:
                days[i] = json.loads(v)
    else:
        for k, v in read_file().items():
            days[int(k)] = v
    return days


def put_day(i, d):
    if PERSISTENT:
        redis("SET", f"day:{i}", json.dumps(d))
    else:
        data = read_file()
        data[str(i)] = d
        with open(FILE, "w") as f:
            json.dump(data, f)


@app.errorhandler(Exception)
def on_error(e):
    if isinstance(e, HTTPException):
        return e
    if request.path.startswith("/api"):
        return jsonify(error=type(e).__name__ + ": " + str(e)[:200]), 500
    raise e


@app.before_request
def gate():
    if PIN and not session.get("ok") and request.path != "/login":
        if request.path.startswith("/api"):
            return jsonify(error="login"), 401
        return redirect("/login")


@app.route("/login", methods=["GET", "POST"])
def login():
    msg = ""
    if request.method == "POST":
        if request.form.get("pin") == PIN:
            session["ok"] = True
            session.permanent = True
            return redirect("/")
        msg = "Wrong PIN"
    return Response(
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<body style="font-family:sans-serif;max-width:320px;margin:20vh auto;text-align:center">'
        '<h2>🪔 Mandalakalam Diary</h2><form method="post">'
        '<input name="pin" type="password" placeholder="Enter PIN" autofocus '
        'style="padding:10px;width:100%;font-size:1rem"><br><br>'
        '<button style="padding:10px 24px;font-size:1rem">Open</button></form>'
        f'<p style="color:#c00">{msg}</p></body>')


@app.route("/")
def home():
    return Response(HTML, mimetype="text/html")


@app.route("/api/health")
def health():
    info = {"database_connected": PERSISTENT,
            "setting_names_found": sorted(k for k in os.environ if any(w in k for w in ("KV", "REDIS", "UPSTASH")))}
    if PERSISTENT:
        try:
            redis("PING")
            info["ping"] = "ok"
        except Exception as e:
            info["ping"] = "failed: " + str(e)[:200]
    return jsonify(info)


@app.route("/api/state")
def state():
    return jsonify(days=get_days(), persistent=PERSISTENT)


@app.route("/api/day/<int:i>", methods=["POST"])
def save_day(i):
    d = request.get_json(force=True)
    if not 0 <= i < N or not isinstance(d, dict):
        return jsonify(error="bad"), 400
    clean = {"sp": str(d.get("sp", ""))[:120], "bill": float(d.get("bill") or 0),
             "pm": str(d.get("pm", "Cash"))[:30], "nt": str(d.get("nt", ""))[:300], "c": []}
    for x in d.get("c", [])[:200]:
        clean["c"].append({"n": str(x.get("n", ""))[:120], "t": "Item" if x.get("t") == "Item" else "Money",
                           "a": float(x.get("a") or 0), "it": str(x.get("it", ""))[:200],
                           "pm": str(x.get("pm", ""))[:30]})
    put_day(i, clean)
    return jsonify(ok=True)


if __name__ == "__main__":
    app.run(debug=True)
