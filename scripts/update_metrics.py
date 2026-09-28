"""Generate durable SVG cards from public GitHub data; standard library only."""
import argparse
import datetime as dt
import html
import json
import os
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
QUERY = '''query($login:String!){user(login:$login){
 repositories(first:1,privacy:PUBLIC,ownerAffiliations:OWNER){totalCount}
 contributionsCollection { contributionCalendar { totalContributions weeks {
 contributionDays { date contributionCount }
 } } }
}}'''

def fetch(login):
    token = os.environ.get('GH_TOKEN')
    if not token:
        raise RuntimeError('GH_TOKEN is required for GitHub GraphQL; existing cards remain unchanged.')
    request = urllib.request.Request('https://api.github.com/graphql',
        data=json.dumps({'query':QUERY,'variables':{'login':login}}).encode(),
        headers={'Authorization':f'Bearer {token}','Content-Type':'application/json',
                 'User-Agent':'VhoCheng-profile-metrics'})
    with urllib.request.urlopen(request,timeout=40) as response:
        result = json.load(response)
    if result.get('errors') or not result.get('data',{}).get('user'):
        raise RuntimeError('GitHub did not return complete profile data; previous cards retained.')
    user=result['data']['user'];cal=user['contributionsCollection']['contributionCalendar']
    today=dt.datetime.now(dt.timezone.utc).date().isoformat()
    return {'as_of':today,'public_repos':user['repositories']['totalCount'],
            'total':cal['totalContributions'],
            'days':{day['date']:day['contributionCount'] for w in cal['weeks'] for day in w['contributionDays']}}

def text(x,y,value,size=16,color='#334155',weight=400):
    return f'<text x="{x}" y="{y}" fill="{color}" font-family="Segoe UI,Arial,sans-serif" font-size="{size}" font-weight="{weight}">{html.escape(str(value))}</text>'

def svg(body,height,label):
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="{height}" viewBox="0 0 1200 {height}" role="img" aria-label="{html.escape(label,quote=True)}"><rect width="1200" height="{height}" rx="18" fill="#F8FBFF" stroke="#E2E8F0" stroke-width="1"/>{body}</svg>'

def render(data):
    days=sorted(data['days'].items());assert days, 'No contribution calendar received'
    assert all(isinstance(n,int) and n>=0 for _,n in days)
    active=sum(n>0 for _,n in days)
    longest=run=0;previous=None
    for date,n in days:
        day=dt.date.fromisoformat(date)
        consecutive=previous is not None and (day-previous).days==1
        run=(run+1 if consecutive else 1) if n else 0
        longest=max(longest,run);previous=day
    body=text(35,38,'GITHUB / AT A GLANCE',15,'#0891B2',600)
    body+=text(880,38,'Updated '+data['as_of']+' UTC',13,'#64748B')
    for i,(number,label) in enumerate([(data['total'],'Contributions / past year'),(data['public_repos'],'Public repositories'),(active,'Active days / calendar window'),(longest,'Longest streak / calendar window')]):
        x=35+i*293
        body+=text(x,104,number,44,'#172554',700)+text(x,137,label,13,'#64748B')
        if i<3:body+=f'<path d="M{x+266} 68V145" stroke="#DCE6F0"/>'
    overview=svg(body,170,'GitHub statistics as of '+data['as_of'])
    months={}
    for date,n in days:months[date[:7]]=months.get(date[:7],0)+n
    # Edge months can be partial; date range is stated explicitly.
    entries=list(months.items())
    body=text(35,40,'CONTRIBUTION SIGNAL',18,'#0891B2',600)
    body+=text(35,66,f"{days[0][0]} — {days[-1][0]} · GitHub contribution calendar",13,'#64748B')
    maximum=max(1,max(months.values()));step=1110/len(entries)
    for fraction in [0,.5,1]:
        y=238-fraction*125
        body+=f'<path d="M35 {y}H1160" stroke="#E2E8F0" stroke-dasharray="3 6"/>'
    for i,(month,n) in enumerate(entries):
        x=42+i*step;height=125*n/maximum
        color='#8B5CF6' if i%2 else '#0891B2'
        body+=f'<rect x="{x}" y="{238-height}" width="{step-22}" height="{max(height,2)}" rx="4" fill="{color}" opacity="{1 if n else .15}"><title>{month}: {n} contributions</title></rect>'
        body+=text(x,228-height,n,13,'#334155')+text(x,260,month[2:],12,'#64748B')
    body+=text(35,293,'Public profile data · Edge months may be partial · Not a measure of research output',12,'#64748B')
    return {'overview.svg':overview,'activity.svg':svg(body,315,'Monthly contributions over the displayed calendar window')}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--snapshot',type=Path)
    parser.add_argument('--output',type=Path,default=ROOT/'assets/cards');args=parser.parse_args()
    data=json.loads(args.snapshot.read_text()) if args.snapshot else fetch(os.getenv('PROFILE_USERNAME','VhoCheng'))
    rendered=render(data) # Validate and render everything before modifying any files.
    args.output.mkdir(parents=True,exist_ok=True)
    for name,content in rendered.items():
        temp=args.output/(name+'.tmp');temp.write_text(content);temp.replace(args.output/name)
    print('Updated overview.svg and activity.svg from GitHub calendar data.')

if __name__=='__main__':main()
