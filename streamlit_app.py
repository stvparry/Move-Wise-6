import re, html, requests, streamlit as st, pandas as pd
st.set_page_config(page_title='MoveWise 6.0 Clean Build',page_icon='🏡',layout='wide')
UA={'User-Agent':'MoveWise-6-clean educational app'}
THEMES=['Travel','Green space','Daily amenities','Healthcare','Social life','Lower recorded crime']
def get(url,params=None,timeout=30,headers=None):
 r=requests.get(url,params=params,headers=headers or UA,timeout=timeout);r.raise_for_status();return r.json()
@st.cache_data(ttl=86400,show_spinner=False)
def find_places(q,limit=5):
 out=[];q=q.strip();m=re.search(r'\b([A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2})\b',q.upper())
 if m:
  try:
   x=get('https://api.postcodes.io/postcodes/'+m.group(1).replace(' ',''))['result'];out.append({'label':x['postcode']+' · '+str(x.get('admin_district','')),'lat':x['latitude'],'lon':x['longitude']})
  except Exception:pass
 try:
  for x in get('https://nominatim.openstreetmap.org/search',{'q':q+', United Kingdom','format':'jsonv2','limit':limit,'countrycodes':'gb'}):
   z={'label':x['display_name'],'lat':float(x['lat']),'lon':float(x['lon'])}
   if not any(abs(z['lat']-a['lat'])<.0001 and abs(z['lon']-a['lon'])<.0001 for a in out):out.append(z)
 except Exception:pass
 return out[:limit]
@st.cache_data(ttl=21600,show_spinner=False)
def map_data(lat,lon,radius):
 query='[out:json][timeout:25];('+''.join([f'{x}(around:{radius},{lat},{lon});' for x in ['node[railway=station]','node[highway=bus_stop]','node[leisure=park]','way[leisure=park]','node[shop]','way[shop]','node[amenity~"hospital|clinic|doctors|pharmacy"]','node[amenity~"restaurant|cafe|pub"]','way[amenity~"restaurant|cafe|pub"]']])+');out center tags;'
 for server in ['https://overpass.kumi.systems/api/interpreter','https://overpass-api.de/api/interpreter']:
  try:
   rows=get(server,{'data':query},45).get('elements',[]);c={k:0 for k in THEMES[:-1]}
   for e in rows:
    t=e.get('tags',{})
    if t.get('railway')=='station' or t.get('highway')=='bus_stop':c['Travel']+=1
    if t.get('leisure')=='park':c['Green space']+=1
    if 'shop' in t:c['Daily amenities']+=1
    if t.get('amenity') in ['hospital','clinic','doctors','pharmacy']:c['Healthcare']+=1
    if t.get('amenity') in ['restaurant','cafe','pub']:c['Social life']+=1
   if rows:return c,{'ok':True,'source':'OpenStreetMap/Overpass','detail':f'{len(rows)} objects returned'}
  except Exception:pass
 return None,{'ok':False,'source':'OpenStreetMap/Overpass','detail':'Unavailable; amenity themes excluded'}
@st.cache_data(ttl=3600,show_spinner=False)
def crime(lat,lon):
 try:
  rows=get('https://data.police.uk/api/crimes-street/all-crime',{'lat':lat,'lng':lon});return len(rows),{'ok':True,'source':'Police.uk','detail':f'{len(rows)} records returned'}
 except Exception:return None,{'ok':False,'source':'Police.uk','detail':'Unavailable; crime theme excluded'}
@st.cache_data(ttl=86400,show_spinner=False)
def road(a,b):
 try:
  x=get(f"https://router.project-osrm.org/route/v1/driving/{a['lon']},{a['lat']};{b['lon']},{b['lat']}",{'overview':'false'})['routes'][0];return (x['distance']/1609.344,x['duration']/60),{'ok':True,'source':'OSRM','detail':'Approximate route without live traffic'}
 except Exception:return None,{'ok':False,'source':'OSRM','detail':'Unavailable'}
def profile(loc,radius):
 c,ms=map_data(loc['lat'],loc['lon'],radius);n,cs=crime(loc['lat'],loc['lon']);s={}
 if c:
  caps={'Travel':30,'Green space':10,'Daily amenities':80,'Healthcare':20,'Social life':70};s={k:min(100,c[k]*100/caps[k]) for k in caps}
 if n is not None:s['Lower recorded crime']=max(0,100-n/8)
 return {'scores':s,'status':[ms,cs]}
def choose(title,key,default=''):
 st.subheader(title);q=st.text_input('Address, postcode, village, town, city or county',default,key=key+'q',label_visibility='collapsed');rows=find_places(q) if q else []
 if not rows:
  if q:st.warning('No UK match found. Add a county or postcode.')
  return None
 return rows[st.selectbox('Confirm intended location',range(len(rows)),format_func=lambda i:rows[i]['label'],key=key+'s')]
def score(p,w):
 k=[x for x in THEMES if x in p['scores'] and w[x]>0];return None if not k else sum(p['scores'][x]*w[x] for x in k)/sum(w[x] for x in k)
def short(x):return x['label'].split(',')[0].split(' · ')[0]
def feel(p,name):
 s=p['scores'];bits=[]
 if s.get('Green space',0)>=50:bits.append('green space should register in ordinary daily life')
 if s.get('Social life',0)>=50:bits.append('there appears to be enough café, pub and restaurant provision for some spontaneity')
 if s.get('Travel',0)>=50:bits.append('the area looks connected rather than isolated')
 if s.get('Daily amenities',0)>=50:bits.append('routine errands may be reasonably convenient')
 return name+' may feel like a place where '+('; '.join(bits) if bits else 'the live evidence does not establish a strong lifestyle signature, making a walking visit particularly important')+'.'
def bars(a,b):
 return f'<svg viewBox="0 0 700 190"><rect width="700" height="190" rx="20" fill="#eff8f5"/><text x="30" y="35" font-family="Arial" font-size="20">Weighted evidence</text><text x="30" y="82" font-family="Arial">Current</text><rect x="145" y="65" width="500" height="20" rx="10" fill="#d7e6e0"/><rect x="145" y="65" width="{5*a:.0f}" height="20" rx="10" fill="#2563eb"/><text x="654" y="82" font-family="Arial">{a:.0f}</text><text x="30" y="137" font-family="Arial">Destination</text><rect x="145" y="120" width="500" height="20" rx="10" fill="#d7e6e0"/><rect x="145" y="120" width="{5*b:.0f}" height="20" rx="10" fill="#0f766e"/><text x="654" y="137" font-family="Arial">{b:.0f}</text></svg>'
def route_picture(a,b,t,ra,rb):
 f=lambda r:'Unavailable' if not r else f'{r[0]:.0f} miles · {r[1]/60:.1f} hours'
 return f'<svg viewBox="0 0 760 280"><rect width="760" height="280" rx="20" fill="#f1f7fa"/><path d="M150 75 C330 20 470 25 630 140" stroke="#2563eb" stroke-width="7" fill="none"/><path d="M150 210 C330 265 470 255 630 140" stroke="#0f766e" stroke-width="7" fill="none"/><circle cx="150" cy="75" r="15" fill="#2563eb"/><circle cx="150" cy="210" r="15" fill="#0f766e"/><circle cx="630" cy="140" r="18" fill="#f97316"/><text x="25" y="48" font-family="Arial" font-weight="bold">{html.escape(short(a))}</text><text x="25" y="105" font-family="Arial">{f(ra)}</text><text x="25" y="185" font-family="Arial" font-weight="bold">{html.escape(short(b))}</text><text x="25" y="240" font-family="Arial">{f(rb)}</text><text x="580" y="105" font-family="Arial" font-weight="bold">{html.escape(short(t))}</text></svg>'
def make_report(r):
 a,b,u,pa,pb,w=r['a'],r['b'],r['user'],r['pa'],r['pb'],r['weights'];sa,sb=score(pa,w),score(pb,w);common=[k for k in THEMES if k in pa['scores'] and k in pb['scores']];d={k:pb['scores'][k]-pa['scores'][k] for k in common};order=sorted(common,key=lambda k:d[k],reverse=True);rows=''.join(f'<tr><td>{k}</td><td>{pa["scores"][k]:.0f}</td><td>{pb["scores"][k]:.0f}</td><td>{d[k]:+.0f}</td></tr>' for k in common);journey=route_picture(a,b,r['target'],r['ra'],r['rb']) if r.get('target') else '<p>No regular destination was resolved.</p>';sources=''.join(f'<li>{"Available" if x["ok"] else "Unavailable"}: <b>{x["source"]}</b> – {x["detail"]}</li>' for x in r['statuses']);summary='Insufficient comparable live evidence for a numerical verdict.' if sa is None else f'{short(b)} scores {sb:.0f}/100 against {sa:.0f}/100 for {short(a)}.'
 return f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><style>@page{{size:A4;margin:14mm}}*{{box-sizing:border-box}}body{{font-family:Segoe UI,Arial;margin:0;background:#edf4f1;color:#17332d;line-height:1.55}}main{{max-width:950px;margin:auto;background:white}}header{{padding:42px;background:linear-gradient(120deg,#123f52,#0f766e);color:white}}header h1{{font-size:40px;margin:0}}section{{padding:27px 42px;border-bottom:1px solid #e0ebe6}}h2{{color:#0f766e}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:18px}}.card{{background:#f6faf8;padding:18px;border:1px solid #dce9e4;border-radius:14px}}.quote{{font:20px Georgia;background:#fff8e8;border-left:6px solid #e8a838;padding:18px}}table{{width:100%;border-collapse:collapse}}th,td{{padding:10px;border-bottom:1px solid #ddd;text-align:left}}th{{background:#eff8f5}}svg{{width:100%;height:auto}}.small{{font-size:13px;color:#53645f}}@media print{{body{{background:white}}section{{break-inside:avoid}}}}</style></head><body><main><header><div>PERSONALISED LOCATION-SELECTION BRIEFING</div><h1>MoveWise 6.0 Clean Build</h1><p>{html.escape(short(a))} → {html.escape(short(b))}</p></header><section><h2>Executive judgement</h2><p><b>{html.escape(summary)}</b></p>{bars(sa or 0,sb or 0)}<p class="quote">A move is more than a score. The real test is whether the destination supports the relationships, routines and small pleasures that make everyday life feel right.</p></section><section><h2>The household lens</h2><div class="grid"><div class="card"><h3>Life context</h3><p>{u['age']}; {u['house']}; {u['work']}; {u['prop']}; budget £{u['budget']:,.0f}.</p></div><div class="card"><h3>What matters emotionally</h3><p><b>Must-haves:</b> {html.escape(u['must'] or 'Not stated')}</p><p><b>Deal-breakers:</b> {html.escape(u['avoid'] or 'Not stated')}</p></div></div></section><section><h2>How the places may feel</h2><div class="grid"><div class="card"><h3>{html.escape(short(a))}</h3><p>{html.escape(feel(pa,short(a)))}</p></div><div class="card"><h3>{html.escape(short(b))}</h3><p>{html.escape(feel(pb,short(b)))}</p></div></div><p class="small">Interpretive summaries of returned provision and stated priorities, not claims about beauty, neighbourliness or community spirit.</p></section><section><h2>Connection to work, family or care</h2>{journey}<p class="small">Approximate road routes without live traffic. Test the real journey at the time it would normally be made.</p></section><section><div class="grid"><div><h2>Reasons to lean in</h2><ul>{''.join(f'<li><b>{k}</b>: difference {d[k]:+.0f}</li>' for k in order[:3])}</ul></div><div><h2>Reasons to pause</h2><ul>{''.join(f'<li><b>{k}</b>: difference {d[k]:+.0f}</li>' for k in order[-3:])}</ul></div></div></section><section><h2>Evidence scorecard</h2><table><tr><th>Theme</th><th>Current</th><th>Destination</th><th>Difference</th></tr>{rows}</table></section><section><h2>Location illustration</h2><svg viewBox="0 0 760 250"><rect width="760" height="250" rx="20" fill="#eef6f1"/><path d="M55 205 Q200 50 380 145 T710 55" fill="none" stroke="#b7d5c8" stroke-width="25"/><path d="M70 65 Q250 220 690 175" fill="none" stroke="#c4d7e5" stroke-width="9"/><circle cx="220" cy="140" r="20" fill="#2563eb"/><circle cx="545" cy="125" r="20" fill="#0f766e"/><text x="165" y="185" font-family="Arial" font-weight="bold">{html.escape(short(a))}</text><text x="500" y="168" font-family="Arial" font-weight="bold">{html.escape(short(b))}</text><text x="20" y="235" font-family="Arial" font-size="12">Illustrative location sketch, not a geographic map.</text></svg></section><section><h2>Source health</h2><ul>{sources}</ul><p class="small">Unavailable sources are excluded rather than scored as zero.</p></section><section><h2>Recommended viewing plan</h2><ol><li>Walk the centre and residential streets on a weekday.</li><li>Repeat the regular journey at its normal time.</li><li>Visit after dark and at the weekend.</li><li>Actively test every must-have and look for every deal-breaker.</li><li>Verify flood, planning, broadband, title, survey and conveyancing evidence for any property.</li></ol></section></main></body></html>'''
st.markdown('''<style>.hero{background:linear-gradient(120deg,#123f52,#0f766e);color:white;padding:26px;border-radius:20px}.card{background:white;padding:18px;border:1px solid #dce9e4;border-radius:14px}.stButton button,.stDownloadButton button{background:#0f766e;color:white}</style>''',unsafe_allow_html=True)
st.markdown('<div class=hero><h1>🏡 MoveWise 6.0 Clean Build</h1><p>A personal location-selection consultant with an illustrated report.</p></div>',unsafe_allow_html=True)
if 'mw6' not in st.session_state:st.session_state.mw6=None
with st.sidebar:
 st.header('Priorities');weights={k:st.slider(k,0,10,7 if k in ['Travel','Green space','Healthcare'] else 5,key=k) for k in THEMES};radius=st.select_slider('Local radius',[1000,2000,3000,5000],3000,format_func=lambda x:f'{x/1000:g} km')
c1,c2=st.columns(2)
with c1:a=choose('Current location','a','Marlow, Buckinghamshire')
with c2:b=choose('Possible destination','b','Henley-on-Thames, Oxfordshire')
st.subheader('Regular workplace, family or care destination');tq=st.text_input('Place used for journey comparison',placeholder='e.g. St Albans, Paddington, Heathrow or a postcode');tr=find_places(tq) if tq else [];target=tr[st.selectbox('Confirm regular destination',range(len(tr)),format_func=lambda i:tr[i]['label'],key='target')] if tr else None
with st.expander('Tell MoveWise about the household',expanded=True):
 c1,c2,c3=st.columns(3);age=c1.selectbox('Age/life stage',['Under 25','25–39','40–54','55–64','65–74','75+','Mixed ages']);house=c2.selectbox('Household',['One person','Couple','Family with young children','Family with teenagers','Multi-generational','Other']);work=c3.selectbox('Work status',['Office/site-based','Hybrid','Home-based','Self-employed','Retired','Not working','Mixed household'])
 c1,c2,c3=st.columns(3);cars=c1.selectbox('Car access',['No car','One car','Two or more cars']);mobility=c2.selectbox('Accessibility',['No particular requirement','Prefer level walking','Step-free transport important','Mobility aid/wheelchair important']);prop=c3.selectbox('Preferred property',['No preference','Flat','Terraced','Semi-detached','Detached','Bungalow','Rural/smallholding']);budget=st.number_input('Budget (£)',0,10000000,750000,25000);must=st.text_area('Must-haves');avoid=st.text_area('Deal-breakers')
if st.button('Create illustrated location briefing',type='primary',use_container_width=True) and a and b:
 with st.spinner('Gathering live evidence and building the report…'):
  pa,pb=profile(a,radius),profile(b,radius);ab,absx=road(a,b);ra,ras=road(a,target) if target else (None,{'ok':False,'source':'OSRM','detail':'No regular destination'});rb,rbs=road(b,target) if target else (None,{'ok':False,'source':'OSRM','detail':'No regular destination'});st.session_state.mw6={'a':a,'b':b,'target':target,'pa':pa,'pb':pb,'route':ab,'ra':ra,'rb':rb,'statuses':pa['status']+pb['status']+[absx,ras,rbs],'weights':weights.copy(),'user':{'age':age,'house':house,'work':work,'cars':cars,'mobility':mobility,'prop':prop,'budget':budget,'must':must,'avoid':avoid}}
r=st.session_state.mw6
if r:
 sa,sb=score(r['pa'],r['weights']),score(r['pb'],r['weights']);st.success('Clean-build briefing complete. The illustrated report is ready below.')
 if sa is not None:st.markdown(f'<div class=card><h2>{"Promising candidate" if sb-sa>=4 else "Broadly comparable" if sb-sa>-4 else "Current location scores more strongly"}</h2><p>Destination <b>{sb:.0f}/100</b>; current <b>{sa:.0f}/100</b>.</p><p>{html.escape(feel(r["pb"],short(r["b"])))}</p></div>',unsafe_allow_html=True)
 if r.get('target'):
  c1,c2=st.columns(2);c1.metric('Current to '+short(r['target']),'Unavailable' if not r['ra'] else f"{r['ra'][0]:.0f} mi · {r['ra'][1]/60:.1f} hr");c2.metric('Destination to '+short(r['target']),'Unavailable' if not r['rb'] else f"{r['rb'][0]:.0f} mi · {r['rb'][1]/60:.1f} hr")
 st.download_button('⬇ Download illustrated consultant report',make_report(r),'movewise_6_clean_illustrated_report.html','text/html',type='primary',use_container_width=True)
 with st.expander('Source health',expanded=True):
  for x in r['statuses']:st.markdown(('✅' if x['ok'] else '⚠️')+f" **{x['source']}**: {x['detail']}")
st.caption('MoveWise 6.0 Clean Build · Emotional interpretation is evidence-qualified. Verify material property decisions independently.')
