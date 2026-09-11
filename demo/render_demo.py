"""Render a deterministic 28-second portfolio demo with illustrative market data.

Requires Pillow and imageio-ffmpeg. Run: python demo/render_demo.py
"""
from pathlib import Path
import math
import subprocess
import random
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg

OUT = Path(__file__).resolve().parent
W, H, FPS, DURATION = 1920, 1080, 30, 28
BG = '#090d13'
PANEL = '#111923'
LINE = '#253343'
WHITE = '#e8eef6'
MUTED = '#8e9db0'
BLUE = '#66bbff'
GREEN = '#5bdbb0'
RED = '#e18d99'
FONTS = {}

def font(size, bold=False):
    key = (size, bold)
    if key not in FONTS:
        FONTS[key] = ImageFont.truetype('C:/Windows/Fonts/' + ('segoeuib.ttf' if bold else 'segoeui.ttf'), size)
    return FONTS[key]

def text(d, xy, value, size=24, fill=WHITE, bold=False):
    d.text(xy, value, font=font(size, bold), fill=fill)

def center(d, y, value, size, fill=WHITE, bold=False):
    width = d.textlength(value, font=font(size, bold))
    text(d, ((W-width)/2, y), value, size, fill, bold)

def box(d, rect, fill=PANEL, outline=LINE, radius=16):
    d.rounded_rectangle(rect, radius, fill=fill, outline=outline, width=2)

def ease(x):
    x = min(1, max(0, x))
    return x*x*(3-2*x)

def logo(d, x, y, size=50):
    box(d, (x,y,x+size,y+size), '#122c3b', '#2b5367', 12)
    d.line([(x+size*.22,y+size*.7),(x+size*.42,y+size*.46),(x+size*.57,y+size*.56),(x+size*.79,y+size*.26)], fill=GREEN, width=4)

def pill(d, x,y,value, color=BLUE):
    width = d.textlength(value,font=font(19))+28
    box(d,(x,y,x+width,y+34),'#162431',LINE,8)
    text(d,(x+14,y+3),value,19,color)

def base(section, index):
    im = Image.new('RGB',(W,H),BG)
    d = ImageDraw.Draw(im)
    logo(d,52,30)
    text(d,(118,33),'Option Edge',30,WHITE,True)
    text(d,(302,42),'AI',19,BLUE,True)
    for x,label in [(475,'Dashboard'),(663,'Scanner'),(810,'News'),(930,'Insiders')]:
        text(d,(x,43),label,22,WHITE if label=='Dashboard' else MUTED)
    pill(d,1530,37,'DEMO  /  SAMPLE DATA',MUTED)
    d.line((48,104,1872,104),fill=LINE,width=2)
    text(d,(54,126),section,21,BLUE,True)
    text(d,(1510,128),'RESEARCH WORKSPACE',18,MUTED)
    d.line((48,993,1872,993),fill=LINE,width=1)
    text(d,(54,1013),'Illustrative data • Provider access and quote delays depend on configuration.',19,MUTED)
    labels = ['SEARCH','DATA','OPTIONS','INTELLIGENCE']
    for j,label in enumerate(labels):
        x = 1170+j*178
        d.ellipse((x,1022,x+8,1030),fill=GREEN if index==j else LINE)
        text(d,(x+18,1013),label,17,WHITE if index==j else MUTED)
    return im,d

def searchbar(d, ticker='AAPL', active=False):
    box(d,(54,181,1866,252), '#121e2b', BLUE if active else LINE,12)
    d.ellipse((80,203,98,221),outline=MUTED,width=2)
    d.line((96,220,105,229),fill=MUTED,width=2)
    text(d,(125,194),ticker,30,WHITE,True)
    text(d,(260,201),'Apple Inc.  /  NASDAQ',23,MUTED)
    pill(d,1646,199,'Analyze',GREEN)

RNG = random.Random(24)
PRICES = [225.4]
for i in range(100):
    PRICES.append(PRICES[-1]+RNG.uniform(-.22,.26))
PRICES = [225.25+(v-min(PRICES))/(max(PRICES)-min(PRICES))*2.2 for v in PRICES]
PRICES[-1]=227.41

def chart(d, rect, progress=1):
    x,y,r,b=rect
    for j in range(4):
        yy=y+j*(b-y)/3
        d.line((x,yy,r,yy),fill=LINE,width=1)
        text(d,(r+12,yy-12),f'{228-j:.2f}',18,MUTED)
    pts=[(x+i*(r-x)/100,b-(p-225)/3*(b-y)) for i,p in enumerate(PRICES)]
    pts=pts[:max(2,int(len(pts)*progress))]
    d.polygon([(x,b)]+pts+[(pts[-1][0],b)],fill='#112a2c')
    for j in range(4):
        yy=y+j*(b-y)/3
        d.line((x,yy,r,yy),fill=LINE,width=1)
    d.line(pts,fill=GREEN,width=3)
    ex,ey=pts[-1]
    d.ellipse((ex-5,ey-5,ex+5,ey+5),fill=GREEN)
    for i,label in enumerate(['09:30','11:00','12:30','14:00','16:00']):
        text(d,(x+i*(r-x)/4-10,b+14),label,18,MUTED)

def quote(d):
    text(d,(78,279),'AAPL',38,WHITE,True)
    text(d,(202,293),'Apple Inc.',23,MUTED)
    text(d,(78,331),'$227.41',57,WHITE,True)
    text(d,(330,356),'+1.32  (+0.58%)',25,GREEN)
    for x,label,value in [(750,'VOLUME','42.8M'),(1040,'DAY RANGE','225.10 – 228.02'),(1480,'SOURCE','yfinance')]:
        text(d,(x,293),label,18,MUTED)
        text(d,(x,329),value,28,WHITE,True)

def dashboard(t):
    im,d=base('01 / TICKER RESEARCH',0)
    chars = max(0,min(4,int((t-.45)*5)))
    entered = 'AAPL'[:chars]+('|' if t<1.5 and int(t*4)%2==0 else '')
    searchbar(d,entered if t<1.6 else 'AAPL',t<1.7)
    if t<1.7:
        box(d,(54,273,770,355))
        text(d,(80,292),'AAPL',28,WHITE,True)
        text(d,(207,296),'Apple Inc. • NASDAQ',23,MUTED)
        text(d,(81,420),'Search a ticker. Trace every insight to its data.',39,WHITE,True)
        text(d,(81,486),'Equities, option chains and market context in one workspace.',27,MUTED)
        for i,(a,b) in enumerate([('01','Market data'),('02','Options analytics'),('03','AI intelligence')]):
            x=80+i*588
            box(d,(x,605,x+550,805))
            text(d,(x+28,630),a,24,BLUE)
            text(d,(x+28,691),b,33,WHITE,True)
    else:
        quote(d)
        box(d,(54,425,1260,954))
        text(d,(80,445),'Price action',27,WHITE,True)
        pill(d,1030,447,'1D  /  5 MIN')
        chart(d,(85,532,1155,870),ease((t-1.7)/.7))
        box(d,(1282,425,1866,954))
        text(d,(1312,450),'Research snapshot',28,WHITE,True)
        for j,(a,b) in enumerate([('Options feed','Alpaca · indicative'),('News context','Finnhub + RSS'),('Sentiment model','FinBERT'),('Data provenance','Source-tagged results')]):
            text(d,(1312,520+j*94),a,21,MUTED)
            text(d,(1312,551+j*94),b,25,WHITE)
    return im

def providers(t):
    im,d=base('02 / MULTI-PROVIDER MARKET DATA',1)
    text(d,(70,200),'Many sources. One research view.',48,WHITE,True)
    text(d,(70,270),'Retrieve → normalize → analyze • Every result retains its source.',26,MUTED)
    sources=[('yfinance','Equity quotes + OHLCV'),('Alpaca','Options + Greeks + IV'),('Finnhub + RSS','Financial news'),('FRED','Macro context')]
    for i,(name,desc) in enumerate(sources):
        y=370+i*124
        box(d,(70,y,540,y+99))
        text(d,(96,y+15),name,28,WHITE,True)
        text(d,(96,y+56),desc,21,MUTED)
        d.line([(540,y+50),(650,y+50),(750,587)],fill=LINE,width=3)
        p=(t*.55+i*.23)%1
        sx,sy=(540,y+50)
        ex,ey=(750,587)
        px=sx+(ex-sx)*p; py=sy+(ey-sy)*p
        d.ellipse((px-5,py-5,px+5,py+5),fill=BLUE)
    box(d,(750,485,1200,690),'#142b37','#387a96',20)
    logo(d,783,518)
    text(d,(855,524),'Provider registry',30,WHITE,True)
    text(d,(783,596),'Normalize • validate • cache',25,MUTED)
    d.line((1200,587,1350,587),fill=BLUE,width=3)
    box(d,(1350,427,1850,753))
    text(d,(1380,454),'AAPL research',31,WHITE,True)
    for j,item in enumerate(['Price + market context','Options analytics','News sentiment','Source attribution']):
        cy=531+j*52
        d.line([(1380,cy),(1386,cy+6),(1397,cy-7)],fill=GREEN if t>j*.4 else MUTED,width=3)
        text(d,(1410,514+j*52),item,24,WHITE if t>j*.4 else MUTED)
    pill(d,70,909,'Real-Time Data Processing')
    text(d,(442,912),'Fallback adapters: Stooq • Twelve Data • Alpha Vantage • Tradier',22,MUTED)
    return im

def options(t):
    im,d=base('03 / OPTIONS ANALYTICS',2)
    searchbar(d)
    quote(d)
    box(d,(54,422,1866,954))
    text(d,(80,445),'Options chain',31,WHITE,True)
    pill(d,1160,449,'Expiry  Sep 18, 2026')
    pill(d,1453,449,'Alpaca / indicative',MUTED)
    text(d,(87,511),'CALLS',22,GREEN,True)
    text(d,(1005,511),'PUTS',22,RED,True)
    headers=['Bid','Ask','Volume','Open int.','IV','Strike','Bid','Ask','Volume','Open int.','IV']
    xs=[90,234,370,514,687,860,1030,1176,1320,1465,1650]
    for x,h in zip(xs,headers): text(d,(x,554),h,21,MUTED)
    rows=[['9.25','9.45','1,842','8,610','25.8%','220.00','1.83','2.03','962','6,230','27.1%'],['5.75','5.90','4,316','14,250','25.1%','225.00','3.31','3.47','2,784','11,890','26.3%'],['3.12','3.25','6,528','18,420','24.7%','230.00','5.66','5.83','3,145','15,670','25.9%'],['1.48','1.60','2,913','12,840','24.9%','235.00','8.99','9.19','1,026','9,410','26.1%']]
    for j,row in enumerate(rows):
        y=600+j*68
        if j==1 and t>1:
            box(d,(72,y-5,1848,y+55),'#18302f','#285b4c',8)
        for k,(x,value) in enumerate(zip(xs,row)):
            text(d,(x,y+9),value,24,BLUE if k==5 else WHITE,k==5)
        d.line((81,y+59,1840,y+59),fill=LINE,width=1)
    text(d,(89,899),'Near the money: $225 strike',22,GREEN)
    text(d,(700,899),'Compare liquidity, spreads and implied volatility across calls and puts.',22,MUTED)
    return im

def intelligence(t):
    im,d=base('04 / AI MARKET INTELLIGENCE',3)
    searchbar(d)
    box(d,(54,280,1097,704))
    text(d,(82,302),'AI-generated market insights',32,WHITE,True)
    pill(d,825,312,'Factor-based',MUTED)
    findings=[('Price trend','AAPL trades above its intraday mean.','yfinance · OHLCV'),('Options context','Near-the-money contracts show active participation.','Alpaca · option chain'),('News sentiment','Mixed to mildly positive; monitor new headlines.','FinBERT · Finnhub + RSS')]
    for j,(title,body,source) in enumerate(findings):
        if t>j*.4:
            y=375+j*102
            d.ellipse((86,y+10,94,y+18),fill=BLUE)
            text(d,(110,y),title,23,WHITE,True)
            text(d,(110,y+33),body,24,WHITE)
            text(d,(110,y+66),source,18,MUTED)
    box(d,(1120,280,1866,704))
    text(d,(1151,304),'Opportunity identification',30,WHITE,True)
    pill(d,1151,365,'WATCHLIST',GREEN)
    text(d,(1151,422),'AAPL · Sep 18 · $225 call',30,WHITE,True)
    text(d,(1151,477),'Narrow spread / active open interest',24,MUTED)
    text(d,(1151,522),'Review IV, event risk and liquidity.',24,MUTED)
    d.line((1151,579,1834,579),fill=LINE,width=1)
    text(d,(1151,609),'Research signal • probabilistic forecast',23,BLUE)
    text(d,(1151,646),'No execution or guaranteed outcome.',21,MUTED)
    box(d,(54,727,1866,960))
    text(d,(82,751),'Financial news & sentiment',29,WHITE,True)
    pill(d,1480,750,'Illustrative headlines',MUTED)
    text(d,(86,812),'Apple supplier outlook draws investor attention',25,WHITE)
    text(d,(87,854),'Technology shares mixed as investors assess rates',25,WHITE)
    text(d,(87,915),'Finnhub + RSS  →  FinBERT classification  →  market context',21,MUTED)
    pill(d,1480,811,'Mildly positive',GREEN)
    pill(d,1480,857,'Neutral',MUTED)
    return im

def overview(t):
    im=dashboard(3)
    d=ImageDraw.Draw(im)
    box(d,(1298,488,1849,935),'#111f2b',LINE,12)
    text(d,(1322,513),'Research pipeline complete',27,WHITE,True)
    for j,label in enumerate(['Multi-Provider Market Data','Options Analytics','AI Market Intelligence','Real-Time Data Processing']):
        cy=603+j*67
        d.line([(1325,cy),(1331,cy+6),(1342,cy-7)],fill=GREEN,width=3)
        text(d,(1360,586+j*67),label,23,WHITE)
    text(d,(1325,878),'Traceable inputs. Clear context.',22,MUTED)
    return im

def title(t, ending=False):
    im=Image.new('RGB',(W,H),BG); d=ImageDraw.Draw(im)
    for x in range(0,W,80): d.line((x,0,x,H),fill='#101822')
    for y in range(0,H,80): d.line((0,y,W,y),fill='#101822')
    box(d,(390,200,1530,879),'#0c131c','#233242',28)
    logo(d,920,260,80)
    center(d,382,'Option Edge AI',82,WHITE,True)
    center(d,498,'Built for smarter options research.' if ending else 'AI-Powered Options Analysis & Market Intelligence',32,MUTED)
    d.line((840,584,1080,584),fill=GREEN,width=3)
    if ending:
        center(d,622,'Python • AI/LLM • Financial APIs • Market Data • Options Analytics',24,MUTED)
        if t>.9:
            box(d,(666,726,1254,797),'#162a38','#355166',12)
            center(d,741,'View the source code on GitHub',28,WHITE,True)
    else:
        center(d,646,'MARKET DATA  /  OPTIONS  /  INTELLIGENCE',22,BLUE)
        center(d,763,'PRODUCT WALKTHROUGH',19,MUTED)
    return im

SCENES=[(0,3,lambda t:title(t)),(3,6,dashboard),(6,10,providers),(10,15,options),(15,21,intelligence),(21,24,overview),(24,28,lambda t:title(t,True))]

def frame(t):
    for j,(start,end,fn) in enumerate(SCENES):
        if t<end:
            im=fn(t-start)
            if j and t-start<.4:
                prev=SCENES[j-1]
                im=Image.blend(prev[2](prev[1]-prev[0]-.01),im,ease((t-start)/.4))
            if t<.45: im=Image.blend(Image.new('RGB',(W,H),BG),im,ease(t/.45))
            return im
    return title(4,True)

def main():
    OUT.mkdir(exist_ok=True)
    ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
    target=OUT/'option-edge-ai-demo.mp4'
    cmd=[ffmpeg,'-y','-f','rawvideo','-vcodec','rawvideo','-s',f'{W}x{H}','-pix_fmt','rgb24','-r',str(FPS),'-i','-','-an','-c:v','libx264','-preset','fast','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',str(target)]
    with (OUT/'render.log').open('w') as log:
        proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=log)
        for i in range(FPS*DURATION):
            proc.stdin.write(frame(i/FPS).tobytes())
            if i%(FPS*4)==0: print(f'Rendered {i/FPS:.0f}/{DURATION}s',flush=True)
        proc.stdin.close()
        if proc.wait(): raise RuntimeError('FFmpeg failed; see render.log')
    frame(22).save(OUT/'option-edge-ai-poster.png')
    contact=Image.new('RGB',(960*3,540*2),BG)
    for j,t in enumerate([1.8,5.7,8.5,13,19,27]):
        contact.paste(frame(t).resize((960,540),Image.Resampling.LANCZOS),((j%3)*960,(j//3)*540))
    contact.save(OUT/'storyboard.jpg',quality=92)
    print(f'Created {target} ({target.stat().st_size/1024/1024:.2f} MiB)',flush=True)

if __name__=='__main__': main()
