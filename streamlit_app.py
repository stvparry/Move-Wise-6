import re,html,io,requests,streamlit as st,pandas as pd,xml.etree.ElementTree as ET
st.set_page_config(page_title='MoveWise 8 Next Chapter',page_icon='🏡',layout='wide')
UA={'User-Agent':'MoveWise-7 evidence edition'}; THEMES=['Travel','Green space','Shops','Healthcare','Social life','Lower recorded crime']
def req(url,params=None,timeout=30,headers=None):
 r=requests.get(url,params=params,headers=headers or UA,timeout=timeout);r.raise_for_status();return r
def places(q,limit=5):
 out=[];q=q.strip();m=re.search(r'\b([A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2})\b',q.upper())
 if m:
  try:
   x=req('https://api.postcodes.io/postcodes/'+m.group(1).replace(' ','')).json()['result'];out.append({'label':x['postcode']+' · '+str(x.get('admin_district','')),'lat':x['latitude'],'lon':x['longitude'],'postcode':x['postcode']})
  except Exception:pass
 try:
  for x in req('https://nominatim.openstreetmap.org/search',{'q':q+', United Kingdom','format':'jsonv2','limit':limit,'countrycodes':'gb'}).json():
   z={'label':x['display_name'],'lat':float(x['lat']),'lon':float(x['lon']),'postcode':''}
   if not any(abs(z['lat']-p['lat'])<.0001 and abs(z['lon']-p['lon'])<.0001 for p in out):out.append(z)
 except Exception:pass
 return out[:limit]
def overpass(lat,lon,radius):
 qs=['node[railway=station]','node[highway=bus_stop]','node[leisure=park]','way[leisure=park]','node[shop]','way[shop]','node[amenity~"hospital|clinic|doctors|pharmacy"]','node[amenity~"restaurant|cafe|pub"]','way[amenity~"restaurant|cafe|pub"]']
 query='[out:json][timeout:25];('+''.join(f'{q}(around:{radius},{lat},{lon});' for q in qs)+');out center tags;'
 for server in ['https://overpass.kumi.systems/api/interpreter','https://overpass-api.de/api/interpreter']:
  try:
   rows=req(server,{'data':query},45).json().get('elements',[]);c={k:0 for k in THEMES[:-1]}
   for e in rows:
    t=e.get('tags',{})
    if t.get('railway')=='station' or t.get('highway')=='bus_stop':c['Travel']+=1
    if t.get('leisure')=='park':c['Green space']+=1
    if 'shop' in t:c['Shops']+=1
    if t.get('amenity') in ['hospital','clinic','doctors','pharmacy']:c['Healthcare']+=1
    if t.get('amenity') in ['restaurant','cafe','pub']:c['Social life']+=1
   if rows:return c,{'ok':True,'source':'OpenStreetMap/Overpass','detail':f'{len(rows)} objects'}
  except Exception:pass
 return None,{'ok':False,'source':'OpenStreetMap/Overpass','detail':'Unavailable; omitted'}
def police(lat,lon):
 try:
  x=req('https://data.police.uk/api/crimes-street/all-crime',{'lat':lat,'lng':lon}).json();return len(x),{'ok':True,'source':'Police.uk','detail':f'{len(x)} records'}
 except Exception:return None,{'ok':False,'source':'Police.uk','detail':'Unavailable; omitted'}
def food(lat,lon,radius):
 try:
  x=req('https://api.ratings.food.gov.uk/Establishments',{'latitude':lat,'longitude':lon,'maxDistanceLimit':min(10,radius/1000),'pageSize':500},35,{**UA,'x-api-version':'2'}).json().get('establishments',[]);vals=[]
  for z in x:
   try:vals.append(int(z.get('RatingValue')))
   except Exception:pass
  return {'count':len(x),'high':sum(v>=4 for v in vals)},{'ok':True,'source':'Food Standards Agency','detail':f'{len(x)} establishments'}
 except Exception:return None,{'ok':False,'source':'Food Standards Agency','detail':'Unavailable'}
def route(a,b):
 try:
  x=req(f"https://router.project-osrm.org/route/v1/driving/{a['lon']},{a['lat']};{b['lon']},{b['lat']}",{'overview':'false'}).json()['routes'][0];return (x['distance']/1609.344,x['duration']/60),{'ok':True,'source':'OSRM','detail':'Road estimate; no live traffic'}
 except Exception:return None,{'ok':False,'source':'OSRM','detail':'Unavailable'}
def news(place):
 try:
  r=req('https://news.google.com/rss/search',{'q':f'"{place}" UK when:30d','hl':'en-GB','gl':'GB','ceid':'GB:en'});root=ET.fromstring(r.content);items=[]
  for x in root.findall('.//item')[:8]:items.append({'title':x.findtext('title',''),'link':x.findtext('link',''),'date':x.findtext('pubDate','')})
  return items,{'ok':True,'source':'Google News RSS','detail':f'{len(items)} recent search results'}
 except Exception:return [],{'ok':False,'source':'Google News RSS','detail':'Unavailable'}
def prof(loc,radius):
 c,os=overpass(loc['lat'],loc['lon'],radius);n,ps=police(loc['lat'],loc['lon']);f,fs=food(loc['lat'],loc['lon'],radius);s={}
 if c:
  caps={'Travel':30,'Green space':10,'Shops':80,'Healthcare':20,'Social life':70};s={k:min(100,c[k]*100/caps[k]) for k in caps}
 if n is not None:s['Lower recorded crime']=max(0,100-n/8)
 return {'scores':s,'counts':c,'food':f,'status':[os,ps,fs]}
def pick(title,key,default=''):
 st.subheader(title);q=st.text_input('Town, county, address or postcode',default,key=key+'q',label_visibility='collapsed');rows=places(q) if q else []
 if not rows:return None
 return rows[st.selectbox('Confirm match',range(len(rows)),format_func=lambda i:rows[i]['label'],key=key+'s')]
def short(x):return x['label'].split(',')[0].split(' · ')[0]
def weighted(p,w):
 k=[x for x in THEMES if x in p['scores'] and w[x]>0];return None if not k else sum(p['scores'][x]*w[x] for x in k)/sum(w[x] for x in k)
def property_summary(df,budget):
 if df is None or df.empty:return None
 d=df.copy();d.columns=[x.strip().lower() for x in d.columns]
 if not {'area','price'}.issubset(d.columns):return {'error':'CSV needs area and price columns.'}
 d['price']=pd.to_numeric(d['price'],errors='coerce');d=d.dropna(subset=['price']);d['within_budget']=d['price']<=budget
 rows=[]
 for area,g in d.groupby('area'):
  rows.append({'Area':area,'Listings':len(g),'Within budget':int(g.within_budget.sum()),'Median asking price':g.price.median(),'Detached':int((g.get('property_type',pd.Series('',index=g.index)).astype(str).str.lower()=='detached').sum())})
 return pd.DataFrame(rows)

def life_stage_assessment(u,p,property_data=None):
    scores=p.get('scores',{})
    now=[];mid=[];later=[]
    if scores.get('Travel',0)>=50: now.append(('positive','Transport provision supports current connections and outings.'))
    else: now.append(('check','Test real journeys; mapped transport provision is not strong.'))
    if scores.get('Social life',0)>=45: now.append(('positive','The mapped social-life footprint supports an active routine.'))
    else: now.append(('check','Social choice may be limited within the selected radius.'))
    if u.get('work') in ['Office/site','Hybrid','Home-based']: now.append(('check','Broadband and the real work journey need direct verification.'))
    if property_data is None: now.append(('gap','Current-market budget fit is unverified without a listing sample or licensed feed.'))
    if u.get('maintenance') in ['Low','Very low']: mid.append(('check','The preferred home should minimise garden, exterior and systems maintenance.'))
    else: mid.append(('positive','The stated maintenance appetite does not currently constrain the search.'))
    if u.get('stairs')!='No concern': mid.append(('check','Prioritise step-free access or an adaptable ground-floor layout.'))
    if scores.get('Healthcare',0)>=40: mid.append(('positive','Mapped healthcare provision provides a useful starting point.'))
    else: mid.append(('check','GP, pharmacy and hospital access require stronger direct checks.'))
    if u.get('car_future') in ['One car','No car']: later.append(('check','Stress-test shopping, healthcare and social trips with reduced car use.'))
    else: later.append(('check','Even with two cars planned, test whether one-car living would remain practical.'))
    if u.get('final_move')=='Yes': later.append(('check','Treat adaptability, stairs, maintenance and support-network access as purchase criteria now.'))
    if scores.get('Shops',0)>=45 and scores.get('Healthcare',0)>=35: later.append(('positive','Mapped shops and healthcare suggest some resilience for everyday needs.'))
    else: later.append(('check','Everyday living may become car-dependent; verify walkable essentials.'))
    return {'0–3 years':now,'3–8 years':mid,'8–15 years':later}
def horizon_html(h):
    blocks=[]
    for title,items in h.items():
        lis=''.join(f'<li><b>{"Strength" if t=="positive" else "Evidence gap" if t=="gap" else "Check"}:</b> {html.escape(text)}</li>' for t,text in items)
        blocks.append(f'<div class="card"><h3>{title}</h3><ul>{lis}</ul></div>')
    return '<div class="horizons">'+''.join(blocks)+'</div>'
def propertydata_prices(postcode,bedrooms,key):
    if not key or not postcode:return None,{'ok':False,'source':'PropertyData','detail':'No API key or full postcode supplied'}
    try:
        r=requests.get('https://api.propertydata.co.uk/prices',params={'postcode':postcode.replace(' ',''),'bedrooms':bedrooms},headers={'X-API-Key':key},timeout=35);r.raise_for_status();x=r.json()
        if x.get('status')!='success':return None,{'ok':False,'source':'PropertyData','detail':str(x.get('message','API response was not successful'))}
        return x.get('data',{}),{'ok':True,'source':'PropertyData','detail':'Licensed asking-price evidence returned'}
    except Exception as e:return None,{'ok':False,'source':'PropertyData','detail':'API call unavailable or rejected'}

def report(r):
 a,b,u,pa,pb,w=r['a'],r['b'],r['user'],r['pa'],r['pb'],r['weights'];sa,sb=weighted(pa,w),weighted(pb,w);life=life_stage_assessment(u,pb,r.get('property'));life_html=horizon_html(life);common=[k for k in THEMES if k in pa['scores'] and k in pb['scores']];delta={k:pb['scores'][k]-pa['scores'][k] for k in common};rows=''.join(f'<tr><td>{k}</td><td>{pa["scores"][k]:.0f}</td><td>{pb["scores"][k]:.0f}</td><td>{delta[k]:+.0f}</td></tr>' for k in common);ps=r.get('property');pt='<p>No listing CSV supplied.</p>' if ps is None else ('<p>'+html.escape(ps.get('error'))+'</p>' if isinstance(ps,dict) else ps.to_html(index=False,formatters={'Median asking price':lambda x:f'£{x:,.0f}'}));jt='<p>No regular destination supplied.</p>' if not r.get('target') else f'<p>From {short(a)}: {r["ra"][0]:.0f} miles / {r["ra"][1]:.0f} minutes. From {short(b)}: {r["rb"][0]:.0f} miles / {r["rb"][1]:.0f} minutes.</p>' if r.get('ra') and r.get('rb') else '<p>Journey data unavailable.</p>';news='<h3>'+short(a)+'</h3><ul>'+''.join(f'<li>{html.escape(x["title"])}</li>' for x in r['na'])+'</ul><h3>'+short(b)+'</h3><ul>'+''.join(f'<li>{html.escape(x["title"])}</li>' for x in r['nb'])+'</ul>';sources=''.join(f'<li>{"Available" if x["ok"] else "Unavailable"}: <b>{x["source"]}</b> – {x["detail"]}</li>' for x in r['statuses']);verdict='Insufficient comparable data.' if sa is None else f'{short(b)} scores {sb:.0f}/100 versus {sa:.0f}/100 for {short(a)}. This is a provision score, not a happiness rating.'
 return f'''<!doctype html><html><head><meta charset=utf-8><style>body{{font-family:Segoe UI,Arial;background:#edf4f1;margin:0;color:#17332d;line-height:1.5}}main{{max-width:950px;margin:auto;background:white}}header{{background:linear-gradient(120deg,#123f52,#0f766e);color:white;padding:42px}}section{{padding:25px 40px;border-bottom:1px solid #ddd}}h1{{font-size:40px;margin:0}}h2{{color:#0f766e}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:18px}}.card{{padding:17px;background:#f6faf8;border-radius:14px}}table{{width:100%;border-collapse:collapse}}th,td{{padding:9px;border-bottom:1px solid #ddd;text-align:left}}th{{background:#eff8f5}}.callout{{font-size:20px;border-left:6px solid #e8a838;background:#fff8e8;padding:17px}}@media print{{section{{break-inside:avoid}}}}</style></head><body><main><header><div>THE NEXT CHAPTER EVIDENCE REPORT</div><h1>MoveWise 8</h1><p>{short(a)} → {short(b)}</p></header><section><h2>Bottom line</h2><p class=callout>{html.escape(verdict)}</p><p><b>Profile:</b> {html.escape(u['age'])}, {html.escape(u['house'])}, {html.escape(u['work'])}, budget £{u['budget']:,.0f}. Must-haves: {html.escape(u['must'] or 'not stated')}. Deal-breakers: {html.escape(u['avoid'] or 'not stated')}.</p></section><section><h2>Will it fit the next chapter?</h2>{life_html}<p>The horizons are structured stress-tests based on the profile and returned evidence, not forecasts of health or personal circumstances.</p></section><section><h2>Property reality</h2>{pt}<p>Listing data is user supplied. Asking prices are not completed-sale prices.</p></section><section><h2>Relationship geography</h2>{jt}</section><section><h2>Comparable evidence</h2><table><tr><th>Theme</th><th>Current</th><th>Destination</th><th>Difference</th></tr>{rows}</table></section><section><h2>Local pulse: recent headlines</h2>{news}<p>Headlines are search results, not sentiment scores. Read the underlying coverage before drawing conclusions.</p></section><section><h2>Evidence gaps requiring direct checks</h2><ul><li>Land Registry completed-sale prices and property-type trends</li><li>ONS demographic and household indicators</li><li>Ofcom postcode broadband and mobile availability</li><li>NHS GP/hospital locations and registration/catchment detail</li><li>Long-term flood risk, planning applications and exact property searches</li><li>Current live property availability unless supplied in the CSV</li></ul></section><section><h2>Source health</h2><ul>{sources}</ul></section><section><h2>If you only visit once</h2><ol><li>Walk from the likely residential area to the centre, pharmacy and food shop.</li><li>Make the regular family/work journey at its normal time.</li><li>Visit a weekday evening and a weekend morning.</li><li>Inspect what the budget actually buys, not the area average.</li><li>Ask whether the destination offers a better life, not merely a different address.</li></ol></section></main></body></html>'''
st.markdown('<style>.hero{background:linear-gradient(120deg,#123f52,#0f766e);color:white;padding:26px;border-radius:20px}.stButton button,.stDownloadButton button{background:#0f766e;color:white}</style>',unsafe_allow_html=True)
st.markdown('<div class=hero><h1>🏡 MoveWise 8: Next Chapter Edition</h1><p>Less waffle. More property, journey, live-source and local-pulse evidence.</p></div>',unsafe_allow_html=True)
if 'v7' not in st.session_state:st.session_state.v7=None
with st.sidebar:
 st.header('Priorities');weights={k:st.slider(k,0,10,7 if k in ['Travel','Green space','Healthcare'] else 5,key=k) for k in THEMES};radius=st.select_slider('Local radius',[1000,2000,3000,5000],3000,format_func=lambda x:f'{x/1000:g} km')
c1,c2=st.columns(2)
with c1:a=pick('Current location','a','Marlow, Buckinghamshire')
with c2:b=pick('Possible destination','b','Henley-on-Thames, Oxfordshire')
st.subheader('Regular workplace, family or care destination');tq=st.text_input('Journey destination',placeholder='e.g. St Albans or a postcode');trs=places(tq) if tq else [];target=trs[st.selectbox('Confirm journey location',range(len(trs)),format_func=lambda i:trs[i]['label'],key='t')] if trs else None
with st.expander('Household and next-chapter profile',expanded=True):
 c1,c2,c3=st.columns(3);age=c1.selectbox('Life stage',['Under 40','40–54','55–64','65–74','75+','Mixed ages']);house=c2.selectbox('Household',['One person','Couple','Family','Multi-generational','Other']);work=c3.selectbox('Work pattern',['Office/site','Hybrid','Home-based','Retired','Not working','Mixed']);budget=st.number_input('Budget (£)',0,10000000,1000000,25000);must=st.text_area('Must-haves');avoid=st.text_area('Deal-breakers')
with st.expander('Next-chapter planning',expanded=True):
 c1,c2,c3=st.columns(3);stay=c1.selectbox('Expected stay',['Under 5 years','5–10 years','10–15 years','15+ years']);final_move=c2.selectbox('Intended final major move?',['Unsure','Yes','No']);maintenance=c3.selectbox('Property-maintenance appetite',['High','Moderate','Low','Very low'])
 c1,c2,c3=st.columns(3);stairs=c1.selectbox('Stairs over time',['No concern','Prefer fewer stairs','Step-free important']);car_future=c2.selectbox('Likely car use in 8–15 years',['Two or more cars','One car','No car','Unsure']);guest=c3.selectbox('Guest/family accommodation',['Not important','Occasional guest room','Regular guest room','Frequent family stays'])

with st.expander('Optional: current property listings CSV',expanded=True):
 st.caption('Columns required: area, price. Optional: property_type, bedrooms, url. Build the CSV from listings you are entitled to use; MoveWise does not scrape property portals.');up=st.file_uploader('Upload listings CSV',type=['csv']);pdf=None
 if up:
  try:pdf=pd.read_csv(up);st.dataframe(pdf.head(),hide_index=True,use_container_width=True)
  except Exception as e:st.error(str(e))
with st.expander('Optional licensed property evidence',expanded=False):
 st.caption('If PROPERTYDATA_API_KEY is stored in Streamlit Secrets, V8 can request asking-price evidence for full postcodes. The key is never entered into the public form.')
 pd_key=st.secrets.get('PROPERTYDATA_API_KEY','') if hasattr(st,'secrets') else ''
 bedrooms=st.selectbox('Bedrooms for asking-price comparison',[1,2,3,4,5],index=3)
 st.write('PropertyData connector: '+('configured' if pd_key else 'not configured'))

if st.button('Build evidence report',type='primary',use_container_width=True) and a and b:
 with st.spinner('Collecting live evidence and compiling the report…'):
  pa,pb=prof(a,radius),prof(b,radius);ra,ras=route(a,target) if target else (None,{'ok':False,'source':'OSRM','detail':'No regular destination'});rb,rbs=route(b,target) if target else (None,{'ok':False,'source':'OSRM','detail':'No regular destination'});na,nas=news(short(a));nb,nbs=news(short(b));prop=property_summary(pdf,budget);pda,pdas=propertydata_prices(a.get('postcode',''),bedrooms,pd_key);pdb,pdbs=propertydata_prices(b.get('postcode',''),bedrooms,pd_key);st.session_state.v7={'a':a,'b':b,'target':target,'pa':pa,'pb':pb,'ra':ra,'rb':rb,'na':na,'nb':nb,'property':prop,'pda':pda,'pdb':pdb,'statuses':pa['status']+pb['status']+[ras,rbs,nas,nbs,pdas,pdbs],'weights':weights.copy(),'user':{'age':age,'house':house,'work':work,'budget':budget,'must':must,'avoid':avoid,'stay':stay,'final_move':final_move,'maintenance':maintenance,'stairs':stairs,'car_future':car_future,'guest':guest}}
r=st.session_state.v7
if r:
 sa,sb=weighted(r['pa'],r['weights']),weighted(r['pb'],r['weights']);st.success('Evidence report complete.')
 if sa is not None:st.metric('Destination versus current',f'{sb:.0f} vs {sa:.0f}',f'{sb-sa:+.0f}')
 st.subheader('Next-chapter fit')
 for hz,items in life_stage_assessment(r['user'],r['pb'],r.get('property')).items():
  st.markdown('#### '+hz)
  for kind,text in items:st.write(('✅ ' if kind=='positive' else '⚠️ ')+text)
 if r['property'] is not None and not isinstance(r['property'],dict):st.subheader('Property reality');st.dataframe(r['property'],hide_index=True,use_container_width=True)
 st.download_button('⬇ Download Next Chapter evidence report',report(r),'movewise_8_next_chapter_report.html','text/html',type='primary',use_container_width=True)
 with st.expander('Source health',expanded=True):
  for x in r['statuses']:st.markdown(('✅' if x['ok'] else '⚠️')+f" **{x['source']}**: {x['detail']}")
st.caption('MoveWise 8 · Search headlines and user-supplied listings are evidence inputs, not endorsements or complete market coverage.')
