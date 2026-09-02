#!/usr/bin/env python3
import re, subprocess, urllib.request, unicodedata, time
from pathlib import Path

SOURCES=[
("iptv-org AL","https://iptv-org.github.io/iptv/countries/al.m3u"),
("iptv-org XK","https://iptv-org.github.io/iptv/countries/xk.m3u"),
("Free-TV AL","https://raw.githubusercontent.com/Free-TV/IPTV/master/playlists/playlist_albania.m3u8")]
BASIS=Path("albanische_sender_basis.m3u"); OUT=Path("albanische_sender.m3u"); REPORT=Path("albanische_sender_report.txt")

def fetch(u):
    r=urllib.request.Request(u,headers={"User-Agent":"Mozilla/5.0 AL-XK-AutoRepair"})
    with urllib.request.urlopen(r,timeout=20) as x: return x.read().decode("utf-8","replace")

def parse(t,s):
    a=[]; L=[x.strip() for x in t.splitlines()]
    for i,x in enumerate(L):
        if x.startswith("#EXTINF:"):
            n=x.split(",",1)[1].strip() if "," in x else "Unbenannt"
            j=i+1
            while j<len(L) and L[j].startswith("#"): j+=1
            if j<len(L) and L[j].startswith(("http://","https://")):
                a.append({"name":n,"url":L[j],"meta":x,"source":s})
    return a

def norm(s):
    s=unicodedata.normalize("NFKD",s)
    s="".join(c for c in s if not unicodedata.combining(c)).lower()
    s=re.sub(r"\b(1080p|720p|576p|540p|480p|360p|hd|fhd|sd|live|albania|kosova|kosovo|tv)\b"," ",s)
    return re.sub(r"\s+"," ",re.sub(r"[^a-z0-9]+"," ",s)).strip()

def ok(u):
    c=["ffprobe","-v","error","-rw_timeout","12000000","-analyzeduration","5000000","-probesize","10000000","-show_entries","stream=codec_type","-of","csv=p=0",u]
    try: p=subprocess.run(c,capture_output=True,text=True,timeout=20)
    except Exception as e: return False,str(e)[:100]
    if p.returncode: return False,(p.stderr or "Fehler").replace("\n"," ")[:100]
    t={x.strip() for x in p.stdout.splitlines() if x.strip()}
    return ("video" in t and "audio" in t),",".join(sorted(t))

C=parse(BASIS.read_text(encoding="utf-8",errors="replace"),"Basis"); errs=[]
for label,u in SOURCES:
    try: C+=parse(fetch(u),label)
    except Exception as e: errs.append(f"{label}: {e}")

seen=set(); U=[]
for c in C:
    if c["url"] not in seen: seen.add(c["url"]); U.append(c)
C=U

G={}
for c in C: G.setdefault(norm(c["name"]) or c["name"].lower(),[]).append(c)
rank={"Basis":0,"iptv-org AL":1,"iptv-org XK":2,"Free-TV AL":3}
sel=[]; det=[]; tested=0
for k,opts in sorted(G.items()):
    opts.sort(key=lambda c:(rank.get(c["source"],9),len(c["url"])))
    for c in opts:
        tested+=1; good,why=ok(c["url"])
        det.append(f'{"OK" if good else "FEHLER"}\t{c["name"]}\t{c["source"]}\t{why}\t{c["url"]}')
        if good: sel.append(c); break

sel.sort(key=lambda c:c["name"].casefold())
o=["#EXTM3U"]
for c in sel:
    m=c["meta"]
    if 'group-title="' in m: m=re.sub(r'group-title="[^"]*"','group-title="Albanische Sender"',m)
    else: m=m.replace(",", ' group-title="Albanische Sender",',1)
    o += [m,c["url"]]
OUT.write_text("\n".join(o)+"\n",encoding="utf-8")
REPORT.write_text(
"AL/XK MASTER AUTO REPORT\n"+f"UTC: {time.strftime('%Y-%m-%d %H:%M:%S',time.gmtime())}\n"+
f"Kandidaten: {len(C)}\nGetestete URLs: {tested}\nFunktionierende eindeutige Sender: {len(sel)}\n"+
(("\nQuellenfehler:\n"+"\n".join(errs)+"\n") if errs else "")+"\n"+"\n".join(det)+"\n",encoding="utf-8")
print(f"{len(sel)} Sender mit Bild+Ton")
