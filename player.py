"""XAIHI: full-song native terminal performance. Windows / stdlib only."""
from pathlib import Path
import argparse,bisect,ctypes,json,math,msvcrt,os,shutil,sys,tempfile,time,unicodedata,zlib
ROOT=Path(__file__).resolve().parent
ASSETS=ROOT/'assets'
DURATION=211.90666666666667
BG=(8,13,18)
WHITE=(222,236,239)
PINK=(91,218,221)
MUTED=(93,127,139)
DIM=(30,53,62)
YELLOW=(218,199,110)
MOTION=True
LYRICS=json.loads((ASSETS/'lyrics.json').read_text(encoding='utf8'))
STARTS=[r['start'] for r in LYRICS]

class MciAudio:
    def __init__(self, path: Path):
        self.alias = "xaihi_preview"
        # The legacy MCI wave driver rejects long paths even when Unicode APIs are used.
        self.temp_audio = Path(tempfile.gettempdir()) / f"xaihi_{os.getpid()}.wav"
        shutil.copyfile(path, self.temp_audio)
        self.send = ctypes.windll.winmm.mciSendStringW
        self.send.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_void_p]
        self.send.restype = ctypes.c_uint
        try:
            self._cmd(f'open "{self.temp_audio.as_posix()}" type waveaudio alias {self.alias}')
        except Exception:
            self.temp_audio.unlink(missing_ok=True)
            raise
        self._cmd(f"set {self.alias} time format milliseconds")

    def _cmd(self, command: str) -> str:
        buf = ctypes.create_unicode_buffer(256)
        error = self.send(command, buf, 256, None)
        if error:
            msg = ctypes.create_unicode_buffer(256)
            ctypes.windll.winmm.mciGetErrorStringW(error, msg, 256)
            raise OSError(f"Windows audio error {error}: {msg.value} ({command})")
        return buf.value

    def play(self):
        self._cmd(f"play {self.alias}")

    def pause(self):
        self._cmd(f"pause {self.alias}")

    def seek(self, seconds: float):
        self._cmd(f"seek {self.alias} to {int(max(0, min(DURATION - 0.05, seconds)) * 1000)}")

    def position(self) -> float:
        return int(self._cmd(f"status {self.alias} position")) / 1000

    def close(self):
        try:
            self._cmd(f"close {self.alias}")
        finally:
            self.temp_audio.unlink(missing_ok=True)

GLYPHS={
'A':'01110/10001/10001/11111/10001/10001/10001','B':'11110/10001/10001/11110/10001/10001/11110',
'C':'01111/10000/10000/10000/10000/10000/01111','D':'11110/10001/10001/10001/10001/10001/11110',
'E':'11111/10000/10000/11110/10000/10000/11111','F':'11111/10000/10000/11110/10000/10000/10000',
'G':'01111/10000/10000/10111/10001/10001/01111','H':'10001/10001/10001/11111/10001/10001/10001',
'I':'11111/00100/00100/00100/00100/00100/11111','J':'00111/00010/00010/00010/10010/10010/01100',
'K':'10001/10010/10100/11000/10100/10010/10001','L':'10000/10000/10000/10000/10000/10000/11111',
'M':'10001/11011/10101/10101/10001/10001/10001','N':'10001/11001/10101/10011/10001/10001/10001',
'O':'01110/10001/10001/10001/10001/10001/01110','P':'11110/10001/10001/11110/10000/10000/10000',
'Q':'01110/10001/10001/10001/10101/10010/01101','R':'11110/10001/10001/11110/10100/10010/10001',
'S':'01111/10000/10000/01110/00001/00001/11110','T':'11111/00100/00100/00100/00100/00100/00100',
'U':'10001/10001/10001/10001/10001/10001/01110','V':'10001/10001/10001/10001/10001/01010/00100',
'W':'10001/10001/10001/10101/10101/10101/01010','X':'10001/10001/01010/00100/01010/10001/10001',
'Y':'10001/10001/01010/00100/00100/00100/00100','Z':'11111/00001/00010/00100/01000/10000/11111',
}

SMALL={
'A':'010/101/111/101/101','B':'110/101/110/101/110','C':'011/100/100/100/011','D':'110/101/101/101/110',
'E':'111/100/110/100/111','F':'111/100/110/100/100','G':'011/100/101/101/011','H':'101/101/111/101/101',
'I':'111/010/010/010/111','J':'001/001/001/101/010','K':'101/101/110/101/101','L':'100/100/100/100/111',
'M':'101/111/111/101/101','N':'101/111/111/111/101','O':'010/101/101/101/010','P':'110/101/110/100/100',
'Q':'010/101/101/111/011','R':'110/101/110/101/101','S':'011/100/010/001/110','T':'111/010/010/010/010',
'U':'101/101/101/101/111','V':'101/101/101/101/010','W':'101/101/111/111/101','X':'101/101/010/101/101',
'Y':'101/101/010/010/010','Z':'111/001/010/100/111',"'":'010/010/000/000/000',
}

SMALL.update({'-':'000/000/111/000/000',',':'000/000/000/010/100','.':'000/000/000/000/010',
 '0':'111/101/101/101/111','1':'010/110/010/010/111','2':'110/001/010/100/111','3':'110/001/010/001/110',
 '4':'101/101/111/001/001','5':'111/100/110/001/110','6':'011/100/111/101/111','7':'111/001/010/010/010',
 '8':'111/101/111/101/111','9':'111/101/111/001/110'})

def ease(x):
    x=max(0,min(1,x));return x*x*(3-2*x)

def width(c):return 2 if unicodedata.east_asian_width(c) in 'FW' else 1

class Screen:
    def __init__(self,w,h):
        self.w=w;self.h=h;self.rows=[[(' ',WHITE,BG) for _ in range(w)] for _ in range(h)]
    def cell(self,x,y,c,fg=WHITE,bg=BG):
        x=int(x);y=int(y)
        if 0<=x<self.w and 0<=y<self.h:self.rows[y][x]=(c,fg,bg)
    def text(self,x,y,text,fg=WHITE,limit=None):
        x=int(x);y=int(y);limit=self.w if limit is None else min(self.w,limit)
        for c in text:
            cw=width(c)
            if x+cw>limit:break
            self.cell(x,y,c,fg)
            if cw==2:self.cell(x+1,y,'',fg)
            x+=cw
    def line(self,x1,y1,x2,y2,c='·',fg=DIM):
        steps=max(1,int(max(abs(x2-x1),abs(y2-y1))))
        for i in range(steps+1):
            f=i/steps;self.cell(round(x1+(x2-x1)*f),round(y1+(y2-y1)*f),c,fg)
    def big(self,x,y,text,sx=2,fg=WHITE,progress=1):
        for i,c in enumerate(text):
            for yy,row in enumerate(GLYPHS.get(c,'00000/'*6+'00000').split('/')):
                for xx,v in enumerate(row):
                    if v=='1' and yy<=7*progress:
                        for k in range(sx):self.cell(x+i*6*sx+xx*sx+k,y+yy,'█',fg)
    def lyric_word(self,x,y,text,sx=2,fg=WHITE):
        for i,c in enumerate(text.upper()):
            for yy,row in enumerate(SMALL.get(c,'000/000/000/000/000').split('/')):
                for xx,v in enumerate(row):
                    if v=='1':
                        for k in range(sx):self.cell(x+i*4*sx+xx*sx+k,y+yy,'█',fg)

def current_line(t):
    i=bisect.bisect_right(STARTS,t)-1
    return i if i>=0 and t<LYRICS[i]['display_end'] else -1

def lyric_layout(s,t,idx,rect):
    if idx<0:return
    x,y,w,h=map(int,rect);words=LYRICS[idx]['words']
    def arrange(scale):
        rows=[];row=[];pos=0
        for n,item in enumerate(words):
            size=len(item['text'])*4*scale
            if row and pos+size>w:rows.append(row);row=[];pos=0
            row.append((n,item,pos));pos+=size+4*scale
        if row:rows.append(row)
        return rows
    scale=2;rows=arrange(scale)
    if len(rows)*6-1>h or any(len(i['text'])*8-2>w for i in words):scale=1;rows=arrange(scale)
    active=max([-1]+[n for n,item in enumerate(words) if item['start']<=t])
    if len(rows)*6-1>h:
        xx=x;yy=y+max(0,h//2-1)
        for n,item in enumerate(words):
            text=item['text']+' '
            if xx+len(text)>x+w:xx=x;yy+=2
            s.text(xx,yy,text,PINK if n==active else WHITE if n<active else MUTED,limit=x+w)
            xx+=len(text)
        return
    for r,row in enumerate(rows):
        for n,item,dx in row:s.lyric_word(x+dx,y+r*6,item['text'],scale,PINK if n==active else WHITE if n<active else MUTED)

def ansi_row(row):
    parts=[];lastfg=lastbg=None
    for c,fg,bg in row:
        if not c:continue
        if fg!=lastfg:parts.append(f'\x1b[38;2;{fg[0]};{fg[1]};{fg[2]}m');lastfg=fg
        if bg!=lastbg:parts.append(f'\x1b[48;2;{bg[0]};{bg[1]};{bg[2]}m');lastbg=bg
        parts.append(c)
    return ''.join(parts)+'\x1b[0m'

def keypress():
    if not msvcrt.kbhit():return None
    c=msvcrt.getwch()
    if c in ('\x00','\xe0'):return {'K':'left','M':'right'}.get(msvcrt.getwch())
    return c.lower()
SMALL['?']='110/001/010/000/010'

AUDIO=json.loads((ASSETS/'audio_features.json').read_text(encoding='utf8'))

def pixel_label(s,x,y,text,color):
    punct={'.':'00000/00000/00000/00000/00000/00100/00100',"'":'00100/00100/00000/00000/00000/00000/00000',
           ',':'00000/00000/00000/00000/00100/00100/01000','?':'01110/10001/00001/00010/00100/00000/00100'}
    for i,c in enumerate(text.upper()):
        rows=GLYPHS.get(c,punct.get(c,'00000/'*6+'00000')).split('/')+['00000']
        for yy in range(4):
            for xx in range(5):
                a=rows[yy*2][xx]=='1';b=rows[yy*2+1][xx]=='1'
                if a or b:s.cell(int(x)+i*6+xx,int(y)+yy,'▀',color if a else BG,color if b else BG)

def readable_lyrics(s,t,idx,rect):
    x,y,w,h=map(int,rect);xx=x;yy=y
    for item in LYRICS[idx]['words']:
        length=len(item['text'])*6
        if xx>x and xx+length>x+w:xx=x;yy+=5
        pixel_label(s,xx,yy,item['text'],WHITE if item['start']<t-.24 else PINK if item['start']<=t else MUTED)
        xx+=length+6

def audio_frame(t):
    return AUDIO['frames'][min(len(AUDIO['frames'])-1,max(0,int(t*AUDIO['fps'])))]

def spectral_stream(s,t,rect):
    x,y,w,h=map(int,rect);a=audio_frame(t)
    s.line(x,y,x+w-1,y,'─',DIM)
    s.text(x+1,y,' FFT / 60Hz > 14kHz ',PINK)
    s.text(x+w-17,y,f"RMS {a['rms']:.2f}",YELLOW)
    plot=h-1;stride=(w-2)/24
    for n,level in enumerate(a['bands']):
        xx=int(x+1+n*stride);height=max(1,round(level*plot))
        for k in range(height):
            digit='0123456789ABCDEF'[(n*11+k+int(t*24))%16]
            fg=PINK if k==height-1 else (48,105+int(level*60),118+int(level*65))
            s.cell(xx,y+h-1-k,digit,fg)
            if stride>=3:s.cell(xx+1,y+h-1-k,'1' if k%2 else '0',DIM if k<height-1 else MUTED)
    # The dots trace signed samples from the same audio window, over the spectral columns.
    for n,value in enumerate(a['wave']):
        xx=x+1+n*(w-3)/63;yy=y+1+(1-value)*(plot-1)/2
        s.cell(xx,yy,'·',WHITE if a['onset']>.6 else MUTED)

def lyric_semantics(s,t,idx,rect):
    x,y,w,h=map(int,rect);a=audio_frame(t)
    if idx>=0:
        start=LYRICS[idx]['start'];end=LYRICS[idx]['display_end'];q=ease((t-start)/max(.2,end-start))
    else:q=(t%4)/4
    labels=['POWER BUS / LIVE','PROTECTION / VERIFIED','ASSEMBLY / PIECES','OBJECT / CONSTRUCT',
            'PARAMETERS / WRITE','INIT / COMPLETE','WORLD / ONLINE','SIMULATION / RUN','POINT SET / SEED']
    label=labels[min(idx,8)] if idx>=0 else 'SIGNAL / TWO CONNECTED NODES'
    s.text(x,y,label,YELLOW)
    cy=y+5;cx=x+w*.25
    if idx==0:
        s.line(x+2,cy,x+w-3,cy,'─',MUTED)
        for n in range(9):
            xx=x+3+n*(w-8)/8;s.text(xx,cy-2,'[+]',PINK if n<=q*8 else DIM)
            if n<=q*8:s.cell(xx+1,cy,'◆',WHITE)
    elif idx==1:
        points=[(cx-10,cy-3),(cx+10,cy-3),(cx+8,cy+1),(cx,cy+3),(cx-8,cy+1),(cx-10,cy-3)]
        for n in range(min(5,1+int(q*5))):s.line(*points[n],*points[n+1],'#',PINK)
        s.text(x+int(w*.52),y+3,'verify(signature)',MUTED)
        s.text(x+int(w*.52),y+5,'shield.active = 1',PINK)
    elif idx==2:
        for n in range(6):
            tx=cx+(n%3-1)*9;ty=cy+(n//3-1)*3
            sx=x+2+n*(w-5)/6;sy=cy-4+(n%2)*8
            px=sx*(1-q)+tx*q;py=sy*(1-q)+ty*q
            s.text(px,py,'[{:02X}]'.format(n),PINK)
        s.text(x+int(w*.55),y+3,'pieces.attach()',MUTED)
        s.text(x+int(w*.55),y+5,f'compiled {int(q*6):02d}/06',WHITE)
    elif idx==3:
        z=.35+.65*q
        nodes=[(-9,-2),(5,-2),(5,3),(-9,3),(-3,-4),(11,-4),(11,1),(-3,1)]
        nodes=[(cx+u*z,cy+v*z) for u,v in nodes]
        for i,j in ((0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),(0,4),(1,5),(2,6),(3,7)):
            s.line(*nodes[i],*nodes[j],'·',PINK)
        s.text(x+int(w*.55),y+3,'new Object()',WHITE)
        s.text(x+int(w*.55),y+5,'mesh.commit()',MUTED)
    elif idx==4:
        for n,name in enumerate(('GAIN','PHASE','RATE')):
            level=a['bands'][n*7];yy=y+2+n*2
            s.text(x,yy,f'{name:5s} {level:0.3f}',MUTED)
            for j in range(int(level*(w-20))):s.cell(x+16+j,yy,'─',PINK)
            s.cell(x+16+int(level*(w-20)),yy,'◆',WHITE)
    elif idx==5:
        length=int((w-8)*q)
        s.text(x+2,y+3,'['+'='*length+' '*(w-8-length)+']',PINK)
        s.text(x+2,y+6,f'boot.sequence    {int(q*100):03d}%    OK',WHITE)
    elif idx==6:
        vy=y+2;vx=x+w/2
        for n in range(9):s.line(vx,vy,x+n*(w-1)/8,y+h-1,'·',DIM if n%2 else MUTED)
        for n in range(1,5):
            yy=vy+(h-3)*(n/4)**1.8;s.line(x,yy,x+w-1,yy,'─',DIM)
        s.cell(vx,vy,'+',PINK)
    else:
        # Two orbiting data nodes in a numerical field; amplitude expands the field.
        radius=8+a['rms']*3
        for n in range(40):
            ang=n*math.tau/40+t*.6
            s.cell(cx+math.cos(ang)*radius*1.7,cy+math.sin(ang)*radius*.25,'01'[n%2],PINK if n%8==0 else MUTED)
        s.text(cx-3,cy,'XAIHI',WHITE)
        s.text(x+int(w*.56),y+3,'session.advance(dt)',MUTED)
        s.text(x+int(w*.56),y+5,f"flux = {a['onset']:.3f}",PINK)

def signal_ribbon(s,t,x,y,w,h=4,quiet=False):
    a=audio_frame(t);color=MUTED if quiet else PINK
    for n,v in enumerate(a['wave']):
        xx=x+n*(w-1)/63;yy=y+h*.5-v*h*.42
        s.cell(xx,yy,'0123456789ABCDEF'[(n+int(t*12))%16],color)
    for n,v in enumerate(a['bands']):
        xx=x+n*(w-1)/23
        s.cell(xx,y+h,'·' if v<.4 else '│',DIM if quiet else MUTED)


def cube_vertices(cx,cy,t,r):
    result=[]
    for x,y,z in ((-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),
                  (-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)):
        u=x*math.cos(t)-z*math.sin(t);v=x*math.sin(t)+z*math.cos(t)
        result.append((cx+r*u,cy+r*(y*.43+v*.19)))
    return result


def palm_construct(s,t,anchor):
    a=audio_frame(t);px,py=anchor(.76,.83);cx,cy=px-10,py-9
    assembly=ease((t-3.863)/1.555)
    size=7+2*ease((t-5.418)/1.2)+a['rms']*.65
    points=cube_vertices(cx,cy,t*.5,size)
    # Eight numeric pieces converge into the eight vertices before edges are committed.
    for n,(xx,yy) in enumerate(points):
        sx=cx+math.cos(n*math.tau/8)*25;sy=cy+math.sin(n*math.tau/8)*9
        tx=sx+(xx-sx)*assembly;ty=sy+(yy-sy)*assembly
        s.text(tx-1,ty,f'{n:02X}',PINK if assembly<1 else WHITE)
    if t>=5.418:
        edges=((0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),(0,4),(1,5),(2,6),(3,7))
        for i,j in edges[:min(12,1+int((t-5.418)*12))]:s.line(*points[i],*points[j],'·',PINK)
    # A gently moving emitter and light columns remain locked to the source palm.
    for n in range(12):
        z=(n/12+t*.34)%1;xx=px-10*z+math.sin(n*2.4)*5*(1-z)
        s.cell(xx,py-1-z*6,'01'[n%2],DIM if n%3 else MUTED)
    for n in range(32):
        angle=n*math.tau/32
        s.cell(px+math.cos(angle)*12,py-1+math.sin(angle)*1.3,'·',MUTED)
    s.text(max(4,cx-22),cy-9,'mesh = Object(pieces)',MUTED)
    s.text(max(4,cx-19),py+3,'palm.anchor / CONNECTED',PINK)


def world_grid(s,t,floor):
    vx=s.w*.5;vy=18
    for n in range(15):s.line(vx,vy,-s.w+n*s.w*3/14,floor,'·',DIM)
    for n in range(9):
        z=(n/9+(t-11.205)*.075)%1;yy=vy+(floor-vy)*z*z
        half=z*s.w*.9;s.line(vx-half,yy,vx+half,yy,'─',DIM)
    a=audio_frame(t)
    for n in range(46):
        angle=n*math.tau/46+t*.34
        xx=vx+math.cos(angle)*(34+a['rms']*3);yy=32+math.sin(angle)*5
        s.cell(xx,yy,'01'[n%2],MUTED if n%4 else PINK)


def connected_nodes(s,t,x,y,w):
    a=audio_frame(t)
    for n in range(50):
        u=n/49;yy=y+math.sin(u*math.tau*2-t*2)*(1.2+a['rms'])
        s.cell(x+u*w,yy,'01'[(n+int(t*8))%2],MUTED)
    s.text(x,y-3,'XAIHI',PINK);s.text(x+w-6,y-3,'ENDMIN',WHITE)
    s.text(x+8,y+4,'connection.keep_alive()',PINK)


def stage_title(s,number,title):
    s.text(5,3,f'{number:02d} / {title}',YELLOW)


def scene_v5(s,t,idx,bank,floor):
    w=s.w
    if t<1.792:
        stage_title(s,0,'POWER / PRIVATE CHANNEL')
        pixel_label(s,7,7,'XAIHI',PINK)
        s.text(8,12,'knowledge.link("ENDMIN")',MUTED)
        lr=(w*.48,7,w*.49,17)
        lyric_semantics(s,t,idx,(7,22,w-14,10))
        spectral_stream(s,t,(7,floor-7,w-14,7))
    elif t<3.863:
        q=ease((t-1.792)/2.071)
        bank.paint(s,'gesture',t,(w*.46,4,w*.52,floor-4),(.61,.59,.98-.03*q))
        stage_title(s,1,'VERIFY / IDENTITY')
        lr=(6,7,w*.45,17)
        lyric_semantics(s,t,1,(6,25,w*.44,10))
        signal_ribbon(s,t,6,floor-5,w*.43,3)
    elif t<7.38:
        q=ease((t-3.863)/3.517)
        anchor=bank.paint(s,'palm',t,(1,4,w*.75,floor-4),(.50,.59,1.06-.025*q))
        stage_title(s,2,'BUILD / PALM COORDINATES')
        lr=(w*.62,7,w*.35,17)
        palm_construct(s,t,anchor)
        spectral_stream(s,t,(w*.76,27,w*.21,13))
    elif t<10.134:
        q=ease((t-7.38)/2.754)
        bank.paint(s,'eyes',t,(w*.47,4,w*.51,16),(.50,.53,.72-.025*q))
        focus(s,int(w*.47)-1,4,int(w*.51)+2,16,'INPUT / XAIHI')
        lr=(6,7,w*.43,17)
        stage_title(s,3,'PARAMETERS / WRITE')
        lyric_semantics(s,t,4,(6,26,w*.44,10))
        code_panel(s,t,w*.53,23,w*.44,2)
        spectral_stream(s,t,(w*.53,32,w*.44,8))
    elif t<11.205:
        q=ease((t-10.134)/1.071)
        stage_title(s,4,'BOOT / SHARED SPACE')
        lr=(max(6,(w-84)/2),8,w-12,6)
        for n in range(10):
            yy=19+n*2;s.text(8,yy,f'{n:02X}  load.segment({n:02d})',PINK if n<q*10 else DIM)
            s.text(w-30,yy,'VERIFIED' if n<q*10 else 'PENDING',MUTED if n<q*10 else DIM)
        s.text(w//2-10,22,f'WORLD BOOT {int(q*100):03d}%',WHITE)
        s.line(40,28,w-41,28,'─',DIM);s.line(40,28,40+(w-81)*q,28,'━',PINK)
        signal_ribbon(s,t,43,32,w-86,5)
    elif t<15.319:
        world_grid(s,t,floor)
        q=ease((t-11.205)/4.114)
        bank.paint(s,'world',t,(w*.35,4,w*.30,floor-4),(.5,.51-.035*q,1.37-.065*q))
        stage_title(s,5,'WORLD / SIMULATION')
        lr=(6,7,w*.34,24)
        code_panel(s,t,w*.70,7,w*.27,1)
        s.text(w*.72,18,'world.spawn(XAIHI)',PINK)
        s.text(w*.72,21,'observer = ENDMIN',MUTED)
        s.text(w*.72,24,f"dt = {audio_frame(t)['rms']:.3f}",MUTED)
        signal_ribbon(s,t,w*.70,31,w*.27,5)
        s.text(7,floor-1,'simulation.run()    WORLD ONLINE',PINK)
    elif t<17:
        q=ease((t-15.319)/1.681)
        bank.paint(s,'thought',t,(w*.27,5,w*.70,18),(.50,.53,.82-.035*q),1-.15*q)
        focus(s,int(w*.27)-1,5,int(w*.70)+2,18,'REFLECTION / UNSENT')
        stage_title(s,6,'REPLY / RECONSIDER')
        code_panel(s,t,7,7,w*.24,3)
        pixel_label(s,9,27,'LET ME TRY AGAIN',PINK)
        signal_ribbon(s,t,9,35,w-18,4,True)
        lr=None
    elif t<21.5:
        q=ease((t-17)/4.5)
        bank.paint(s,'response',t,(w*.42,4,w*.56,floor-4),(.50,.53,.88-.09*q))
        stage_title(s,7,'RESPONSE / PERSONAL')
        pixel_label(s,7,9,'YOU MEANT',WHITE);pixel_label(s,7,16,'ME?',PINK)
        code_panel(s,t,7,25,w*.36,4)
        signal_ribbon(s,t,7,35,w*.34,4,True)
        lr=None
    elif t<25.5:
        q=ease((t-21.5)/4)
        bank.paint(s,'glance',t,(3,4,w*.49,floor-4),(.50,.53,.91-.055*q))
        stage_title(s,8,'KNOWLEDGE / FEELING')
        pixel_label(s,w*.53,9,'NO PROOF',WHITE);pixel_label(s,w*.53,16,'NEEDED',PINK)
        connected_nodes(s,t,w*.55,28,w*.37)
        signal_ribbon(s,t,w*.55,36,w*.37,3,True)
        lr=None
    else:
        q=ease((t-25.5)/4.5)
        bank.paint(s,'reach',t,(w*.33,4,w*.66,floor-4),(.60,.64,.98-.04*q))
        stage_title(s,9,'CONNECTION / KEEP ALIVE')
        pixel_label(s,7,9,'STAY',WHITE);pixel_label(s,7,16,'A WHILE',PINK)
        s.text(8,26,'timeout = None',MUTED)
        s.text(8,29,'reason = "I would like to"',PINK)
        for n in range(24):
            u=(n/24+t*.11)%1
            s.cell(10+u*w*.32,34+math.sin(n)*3*(1-u),'01'[n%2],DIM if n%3 else MUTED)
        s.text(8,floor-1,'SESSION REMAINS OPEN',YELLOW)
        lr=(6,8,w*.41,20) if idx>=0 else None
        if lr:
            for yy in range(8,23):
                for xx in range(6,int(w*.42)):s.cell(xx,yy,' ')
    if idx>=0 and lr:readable_lyrics(s,t,idx,lr)
    return lr


def transition_stage(s,t,idx,bank,floor,lyric_rect):
    cues=((3.863,'scan'),(11.205,'open'),(17.0,'diagonal'),(25.5,'reverse'))
    for start,kind in cues:
        if not start<=t<start+.45:continue
        old=Screen(s.w,s.h)
        scene_v5(old,start-.001,-1,bank,floor)
        q=ease((t-start)/.45)
        for y in range(4,floor):
            for x in range(3,s.w-3):
                u=(x-3)/(s.w-7);v=(y-4)/max(1,floor-5)
                phase=abs(u-.5)*2 if kind=='open' else 1-u if kind=='reverse' else .78*u+.22*v if kind=='diagonal' else u
                if phase>q:
                    char,fg,bg=old.rows[y][x];fade=(1-q)**2
                    dim=lambda color:tuple(round(BG[k]+(color[k]-BG[k])*fade) for k in range(3))
                    s.rows[y][x]=(char,dim(fg),dim(bg))
                if 0<q<1 and abs(phase-q)<.008 and y%2==0:
                    s.cell(x,y,'01'[(x+y)%2],MUTED)
        # Restore the incoming lyric region so a visual transition never delays a word.
        if idx>=0 and lyric_rect:
            x,y,w,h=map(int,lyric_rect)
            for yy in range(y,min(floor,y+h)):
                for xx in range(x,min(s.w,x+w)):s.cell(xx,yy,' ')
            readable_lyrics(s,t,idx,lyric_rect)
        break



class Portraits:
    def __init__(self):
        self.meta=json.loads((ASSETS/'portraits.json').read_text(encoding='utf8'))
        self.data={name:zlib.decompress((ASSETS/f'{name}.rgba.z').read_bytes()) for name in self.meta}

    def paint(self,s,name,t,rect,crop,brightness=1):
        x,y,w,h=map(int,rect)
        if w<=0 or h<=0:return
        m=self.meta[name];sw,sh=m['width'],m['height'];data=self.data[name]
        cx,cy,span=crop
        breathing=math.sin(t*1.55)*.005 if MOTION else 0
        drift=math.sin(t*.63)*.003 if MOTION else 0
        cw=sw*span;ch=cw*2*h/w
        left=sw*(cx+drift)-cw/2;top=sh*(cy+breathing)-ch/2
        def sample(fx,fy):
            if fx<0 or fy<0 or fx>=sw-1 or fy>=sh-1:return BG
            sx,sy=int(fx),int(fy);dx,dy=fx-int(fx),fy-int(fy)
            indices=((sy*sw+sx)*4,(sy*sw+sx+1)*4,((sy+1)*sw+sx)*4,((sy+1)*sw+sx+1)*4)
            weights=((1-dx)*(1-dy),dx*(1-dy),(1-dx)*dy,dx*dy)
            a=sum(data[i+3]*q for i,q in zip(indices,weights))/255
            if a<.02:return BG
            rgb=[sum(data[i+k]*q for i,q in zip(indices,weights)) for k in range(3)]
            # Keep the source palette, with subtle cold grading for the terminal stage.
            rgb=[rgb[0]*.83*brightness,rgb[1]*.94*brightness,rgb[2]*.98*brightness]
            return tuple(max(0,min(255,round((BG[k]*(1-a)+rgb[k]*a)/4)*4)) for k in range(3))
        xs=[left+(xx+.5)*cw/w for xx in range(w)]
        for yy in range(h):
            ya=top+(yy*2+.5)*ch/(2*h);yb=top+(yy*2+1.5)*ch/(2*h)
            for xx,fx in enumerate(xs):
                a,b=sample(fx,ya),sample(fx,yb)
                if a!=BG or b!=BG:s.cell(x+xx,y+yy,'▀',a,b)
        # Return the exact source-to-stage mapping so graphics stay attached to the palm.
        return lambda u,v:(x+(u*sw-left)*w/cw,y+(v*sh-top)*h/ch)

DIALOGUE=[
 (2.0,'XAIHI','MAY THIS LINK BRING INSIGHT.','管理员，愿这次连接带来启示。'),
 (6.0,'XAIHI','WHAT SHALL WE SEEK NEXT?','维护完成。您还想探寻些什么？'),
 (10.0,'ENDMIN','HOW ARE YOU, XAIHI?','我是问你，赛希。你今天好吗？'),
 (13.5,'DRAFT','ALL SYSTEMS ARE NOMINAL.','所有系统均在预期范围内运行……'),
 (17.0,'XAIHI','AH... YOU MEANT ME.','啊……原来您问的是我。'),
 (21.5,'XAIHI','THIS JOY NEEDS NO PROOF.','见到您的喜悦，似乎不需要证明。'),
 (25.5,'XAIHI','MAY THIS CONNECTION LAST?','若您不忙……这次连接，能再久一点吗？')]
SCENES=[0,1.792,3.863,7.38,10.134,11.205,15.319,17,21.5,25.5]

CN_GLYPHS=json.loads((ASSETS/'dialogue_glyphs.json').read_text(encoding='utf8'))
DOTS=((1,8),(2,16),(4,32),(64,128))

def dialogue_english(s,y,text,full_length,color):
    # Square pixels in a 5 x 7 face keep the enlarged letters proportionate.
    punctuation={'.':'00000/00000/00000/00000/00000/00100/00100',
                 '?':'01110/10001/00001/00010/00100/00000/00100',
                 "'":'00100/00100/00000/00000/00000/00000/00000'}
    x=max(5,(s.w-full_length*6)//2)
    for i,c in enumerate(text):
        rows=GLYPHS.get(c,punctuation.get(c,'00000/'*6+'00000')).split('/')+['00000']
        for yy in range(4):
            for xx in range(5):
                a=rows[yy*2][xx]=='1';b=rows[yy*2+1][xx]=='1'
                if a or b:s.cell(x+i*6+xx,y+yy,'▀',color if a else BG,color if b else BG)

def big_translation(s,y,text):
    # 14 x 16 glyphs mapped to 2 x 4 Braille cells: 64 px high at the default grid.
    x=max(5,(s.w-len(text)*7)//2)
    for char in text:
        bitmap=CN_GLYPHS.get(char,[0]*16)
        for cy in range(4):
            for cx in range(7):
                dots=0
                for yy in range(4):
                    for xx in range(2):
                        if bitmap[cy*4+yy] & (1 << (cx*2+xx)):dots|=DOTS[yy][xx]
                if dots:s.cell(x+cx,y+cy,chr(0x2800+dots),(161,204,211))
        x+=7

CODE_PHASES=[
 ['peer = await link.open("ENDMIN")','verify(peer.signature)        OK','channel.mode = PRIVATE','knowledge.sync(peer)         OK','await operator.response()'],
 ['maintenance.complete = True','cache.flush()                OK','errors = diagnostics.count()','assert errors == 0','query = await channel.read()'],
 ['query.target = "XAIHI"','parse("How are you?")','intent = PERSONAL','report.is_answer = False','await self.reflection()'],
 ['reply = report.status()','if query.target == "XAIHI":','    reply.clear()','    // recomputing meaning','await words.find("myself")'],
 ['context = self.experience','proof.required = False','reply = "glad you came"','channel.send(reply)          OK','connection.keep_alive()'],
 ['task.complete = True','conversation.close = False','reason = "I would like to"','await another_moment()','session.keep_alive = True']]

def code_panel(s,t,x,y,w,phase):
    x,y,w=int(x),int(y),int(w)
    ink=(60,123,130) if t<17 else (50,101,110)
    s.line(x,y,x+w-1,y,'─',DIM)
    s.text(x+1,y,' SOURCE / '+('REWRITE' if 13.5<=t<17 else 'LIVE'),PINK,limit=x+w)
    lines=CODE_PHASES[phase]
    tick=int(t*2.4);visible=4
    for row in range(visible):
        line=lines[(row+tick//4)%len(lines)]
        length=min(len(line),int((t*2.4%1)*85)) if row==visible-1 else len(line)
        s.text(x+1,y+1+row,f'{(tick//4+row)%99:02d} '+line[:length],YELLOW if phase==3 and row==2 else ink,limit=x+w)
    cursor=x+1+int((t*19)%(max(2,w-2)))
    s.cell(cursor,y+5,'─',PINK)

def data_flow(s,t,bottom):
    # Deterministic visual traffic only; no real network or private data is read.
    sound=audio_frame(t)
    for lane in range(4):
        x=(2, s.w-4, int(s.w*.49), int(s.w*.51))[lane]
        head=4+(sound['travel']+lane*8)%(bottom-5)
        for n in range(7):
            y=int(head-n)
            if 4<=y<bottom:
                value=(int(t*4)*17+lane*41+n*13)%16
                s.cell(x,y,'0123456789ABCDEF'[value],(48,103,110) if n else (85,177+int(sound['onset']*60),178+int(sound['onset']*60)))
    for row in (5,14,23):
        if row>=bottom-2:continue
        packet=int(t*24+row)*2654435761 & 0xffffffff
        s.text(5,row,f'{packet:08X}  ->  ACK',DIM)

def focus(s,x,y,w,h,label):
    for xx,d in ((x,1),(x+w-1,-1)):
        for yy,e in ((y,1),(y+h-1,-1)):
            s.line(xx,yy,xx+d*4,yy,'─',MUTED);s.line(xx,yy,xx,yy+e,'│',MUTED)
    s.text(x+6,y,label,PINK,limit=x+w-5)

def performance(t,playing,term,bank,translate=True):
    w=min(240,max(184,term.columns));h=min(70,max(59,term.lines-1));s=Screen(w,h)
    floor=h-18;idx=current_line(t)
    data_flow(s,t,floor)
    s.text(3,0,'XAIHI / PRIVATE CHANNEL',PINK)
    s.text(40,0,f'RX {int(t*128):04X}   TX {int(t*91):04X}   CRC OK',DIM)
    s.text(w-42,0,f'{t:04.1f} / 30.0   '+('CONNECTED' if playing else 'PAUSED'),MUTED)
    s.line(3,2,w-4,2,'─',DIM)
    lr=scene_v5(s,t,idx,bank,floor)
    transition_stage(s,t,idx,bank,floor,lr)
    # A dedicated large dialogue area keeps the coding effects out of the conversation.
    if idx>=0:s.text(5,h-17,LYRICS[idx]['text'],WHITE,limit=w-5)
    s.line(3,h-16,w-4,h-16,'─',MUTED)
    di=bisect.bisect_right([d[0] for d in DIALOGUE],t)-1
    if di>=0:
        start,speaker,en,cn=DIALOGUE[di];dt=t-start
        count=min(len(en),int(dt*38))
        if speaker=='DRAFT' and dt>1.65:count=max(0,len(en)-int((dt-1.65)*40))
        ink=YELLOW if speaker=='DRAFT' else PINK if speaker=='XAIHI' else WHITE
        s.text(5,h-15,speaker+' / '+('UNSENT' if speaker=='DRAFT' else 'PRIVATE MESSAGE'),ink)
        tx=max(5,(w-len(en)*6)//2)
        dialogue_english(s,h-13,en[:count],len(en),WHITE if speaker=='ENDMIN' else PINK)
        if speaker=='DRAFT' and count:s.line(tx+count*6,h-13,tx+count*6,h-10,'│',YELLOW)
        if translate:big_translation(s,h-6,cn if speaker!='DRAFT' or count else '……')
    s.text(3,h-1,'SPACE pause   <- -> seek   [ ] scene   C translation   M motion   R replay   Q exit',DIM,limit=w-3)
    return s

def run(start=0,audio_path=None):
    global MOTION
    handle=ctypes.windll.kernel32.GetStdHandle(-11);mode=ctypes.c_uint()
    if ctypes.windll.kernel32.GetConsoleMode(handle,ctypes.byref(mode)):ctypes.windll.kernel32.SetConsoleMode(handle,mode.value|4)
    bank=Portraits();audio=None;t=start;playing=True;translate=True;previous=[];last=None
    try:
        if audio_path:audio=MciAudio(Path(audio_path));audio.seek(t);audio.play()
        anchor=time.monotonic()-t
        sys.stdout.write('\x1b[?1049h\x1b[?25l\x1b[?7l\x1b[2J');sys.stdout.flush()
        while True:
            now=time.monotonic()
            if playing:t=min(DURATION,audio.position() if audio else now-anchor)
            if playing and t>=DURATION-.015:
                playing=False
                if audio:audio.pause()
            term=shutil.get_terminal_size((197,60));stamp=(int(t*24),playing,translate,MOTION,term)
            if stamp!=last:
                updates=[]
                if last is None or term!=last[-1]:previous=[];updates.append('\x1b[2J')
                if term.columns<184 or term.lines<60:
                    screen=Screen(max(20,term.columns-1),max(5,term.lines-1));screen.text(1,1,'Enlarge terminal: at least 184 x 60. Recommended 197 x 60.',PINK)
                else:screen=performance(t,playing,term,bank,translate)
                for y,row in enumerate(screen.rows):
                    if y>=len(previous) or row!=previous[y]:updates.append(f'\x1b[{y+1};1H'+ansi_row(row))
                sys.stdout.write(''.join(updates));sys.stdout.flush();previous=screen.rows;last=stamp
            key=keypress()
            if key=='q':break
            if key==' ':
                playing=not playing
                if audio:audio.play() if playing else audio.pause()
                anchor=time.monotonic()-t
            elif key=='c':translate=not translate
            elif key=='m':MOTION=not MOTION
            elif key in ('left','right','r','[',']'):
                if key in ('[',']'):
                    si=bisect.bisect_right(SCENES,t+.01)-1;t=SCENES[max(0,min(len(SCENES)-1,si+(-1 if key=='[' else 1)))]
                else:t=0 if key=='r' else max(0,min(DURATION-.05,t+(-3 if key=='left' else 3)))
                if key=='r':playing=True
                if audio:
                    audio.seek(t)
                    if playing:audio.play()
                anchor=time.monotonic()-t
            time.sleep(max(.002,1/24-(time.monotonic()-now)))
    finally:
        sys.stdout.write('\x1b[0m\x1b[?7h\x1b[?25h\x1b[?1049l');sys.stdout.flush()
        if audio:audio.close()


DIALOGUE=json.loads((ASSETS/'dialogue.json').read_text(encoding='utf8'))
SHOTS=json.loads((ASSETS/'shots.json').read_text(encoding='utf8'))
SCENES=sorted(set([1.792,3.863,7.38,10.134,11.205]+[r[0] for r in SHOTS]))
SHOT_STARTS=[r[0] for r in SHOTS]
DIALOGUE_STARTS=[r[0] for r in DIALOGUE]
GLYPHS.update({'-':'00000/00000/00000/11111/00000/00000/00000',
               ',':'00000/00000/00000/00000/00100/00100/01000'})


def small_pixel(s,x,y,text,color):
    for i,c in enumerate(text.upper()):
        rows=SMALL.get(c,'000/000/000/000/000').split('/')+['000']
        for yy in range(3):
            for xx in range(3):
                a=rows[yy*2][xx]=='1';b=rows[yy*2+1][xx]=='1'
                if a or b:s.cell(x+i*4+xx,y+yy,'▀',color if a else BG,color if b else BG)


def lyric_rows(words,w,advance):
    lines=[];line=[];length=0
    for item in words:
        size=len(item['text'])*advance
        if line and length+size>w:lines.append(line);line=[];length=0
        line.append((item,length));length+=size+advance
    if line:lines.append(line)
    return lines


def readable_lyrics(s,t,idx,rect):
    x,y,w,h=map(int,rect);words=LYRICS[idx]['words']
    if LYRICS[idx]['text'].strip().lower()=='execution' and w>=140:
        xx=x+(w-108)//2
        s.big(xx,y,'EXECUTION',2,PINK if t-LYRICS[idx]['start']<.24 else WHITE)
        q=min(1,(t-LYRICS[idx]['start'])/max(.1,LYRICS[idx]['display_end']-LYRICS[idx]['start']))
        s.line(xx,y+8,xx+107*q,y+8,'─',PINK)
        return
    rows=lyric_rows(words,w,6);advance=6;step=5
    if len(rows)*5-1>h or max(len(i['text'])*6 for i in words)>w:
        rows=lyric_rows(words,w,4);advance=4;step=4
    for row,line in enumerate(rows):
        for item,offset in line:
            ink=WHITE if item['start']<t-.24 else PINK if item['start']<=t else MUTED
            (pixel_label if advance==6 else small_pixel)(s,x+offset,y+row*step,item['text'],ink)


def big_translation(s,y,text,color=None,left=None):
    color=(161,204,211) if color is None else color
    x=max(5,(s.w-len(text)*7)//2) if left is None else left
    for char in text:
        bitmap=CN_GLYPHS.get(char,[0]*16)
        for cy in range(4):
            for cx in range(7):
                dots=0
                for yy in range(4):
                    for xx in range(2):
                        if bitmap[cy*4+yy] & (1 << (cx*2+xx)):dots|=DOTS[yy][xx]
                if dots:s.cell(x+cx,y+cy,chr(0x2800+dots),color)
        x+=7


def semantic_name(idx,fallback):
    if idx<0:return fallback
    text=LYRICS[idx]['text'].lower()
    groups=(('points',('point','dimension')),('circle',('circle','circumference')),
            ('wave',('sine','tangent','vibration')),('infinity',('infinity','limitations')),
            ('current',('current','to ac','to dc')),('spiral',('blind','dizzy')),
            ('timeline',('travel','to ad','to bc')),('nodes',('unite','deeply')),
            ('simulation',('simulation','trapped')),('botany',('eggplant','nutrients','tomato','antioxidants')),
            ('cat',('tabby','purr')),('proof',('god','existence')),
            ('switch',('gender','to f','role','to s','whatever')),('clock',('am to pm',)),
            ('isolation',('have left','isolation')),('fragments',('erase','fragments','disheartened')),
            ('error',('illegal','arguments')),('execution',('execution','ein,','trios,','fem,')),
            ('love',('lo-o-ove','studied','question me')),('freedom',('are free',)))
    for name,keys in groups:
        if any(k in text for k in keys):return name
    return fallback


def diagram(s,t,kind,rect):
    x,y,w,h=map(int,rect);cx=x+w/2;cy=y+h*.52;a=audio_frame(t)
    color=YELLOW if kind in ('isolation','error','fragments') else PINK
    s.text(x,y,kind.upper()+' / LIVE',color,limit=x+w)
    if kind in ('points','simulation'):
        points=cube_vertices(cx,cy,t*.24,min(w*.2,h*.8))
        for n,(px,py) in enumerate(points):s.text(px,py,f'{n:02X}',WHITE)
        for i,j in ((0,1),(1,2),(2,3),(3,0),(4,5),(5,6),(6,7),(7,4),(0,4),(1,5),(2,6),(3,7)):
            s.line(*points[i],*points[j],'·',PINK)
        s.text(x+1,y+h-1,'x(t)  y(t)  z(t)   -> WORLD',MUTED,limit=x+w)
    elif kind in ('circle','infinity','love','spiral'):
        for n in range(100):
            u=n*math.tau/100+t*.12
            if kind=='circle':px=math.cos(u);py=math.sin(u)
            elif kind=='infinity':px=math.cos(u)/(1+math.sin(u)**2);py=math.sin(u)*math.cos(u)/(1+math.sin(u)**2)
            elif kind=='love':px=math.sin(u)**3;py=-(13*math.cos(u)-5*math.cos(2*u)-2*math.cos(3*u)-math.cos(4*u))/17
            else:px=math.cos(u*2)*(n/100);py=math.sin(u*2)*(n/100)
            ry=(h-3)*.42;rx=min(w*.34,ry*2)
            s.cell(cx+px*rx,cy+py*ry,'01'[n%2],WHITE if n%17==int(t*4)%17 else PINK)
        s.text(x+1,y+h-1,{'circle':'C = 2*pi*r','infinity':'lim(t) -> infinity','love':'answer = my_own','spiral':'phase.rotate()'}[kind],MUTED,limit=x+w)
    elif kind in ('wave','current'):
        s.line(x+1,cy,x+w-2,cy,'─',DIM)
        for n in range(max(2,w-2)):
            u=n/max(1,w-3);value=math.sin(u*math.tau*2+t*2.5)
            if kind=='current' and int(t)%4>=2:value=.5
            s.cell(x+1+n,cy-value*(h-3)*.35,'01'[(n+int(t*10))%2],PINK)
        if kind=='wave':
            u=(t*.16)%1;px=x+u*w;py=cy-math.sin(u*math.tau*2+t*2.5)*(h-3)*.35
            s.line(px-8,py+1,px+8,py-1,'·',WHITE)
    elif kind in ('nodes','freedom','farewell'):
        for n in range(50):
            u=n/49;yy=cy+math.sin(u*math.tau*2-t*2)*(h*.15)*a['rms']
            if kind!='farewell' or (n+int(t*2))%5:s.cell(x+2+u*(w-5),yy,'01'[n%2],MUTED)
        s.text(x+2,cy-3,'XAIHI',PINK);s.text(x+w-8,cy-3,'ENDMIN',WHITE)
        s.text(x+2,y+h-1,'session.keep_alive()',PINK,limit=x+w)
    elif kind in ('timeline','clock'):
        s.line(x+2,cy,x+w-3,cy,'─',MUTED)
        for n,label in enumerate(('BC','AD','NOW','NEXT') if kind=='timeline' else ('AM','NOON','PM','NIGHT')):
            px=x+2+n*(w-9)/3;s.text(px,cy-2,label,PINK);s.cell(px,cy,'+',WHITE)
        s.cell(x+2+(t*.15%1)*(w-5),cy,'>',WHITE)
    elif kind in ('botany','cat'):
        art=['    ^___^','   ( o.o )','    > ^ <'] if kind=='cat' else ['     <>','    .--.','   (    )','    `--`']
        for n,row in enumerate(art):s.text(cx-6,cy-2+n,row,PINK)
        s.text(x+1,y+h-1,'purr.frequency = signal' if kind=='cat' else 'nutrients.transfer()',MUTED,limit=x+w)
        for n in range(12):s.cell(x+3+n*(w-6)/12,cy+math.sin(t+n)*(h-3)*.3,'.',DIM)
    elif kind in ('isolation','fragments'):
        for n in range(20):
            px=x+2+(n*13.17+t*(.15 if kind=='isolation' else .8))%(w-5)
            py=y+2+(n*3.71)%(max(2,h-3))
            s.text(px,py,f'{n:02X}',DIM if n%3 else MUTED,limit=x+w)
        s.text(x+2,cy,'await peer.response()' if kind=='isolation' else 'memory.retain(moment)',YELLOW,limit=x+w)
    elif kind=='execution' and w>120:
        nodes=[(x+w*u,y+v) for v in (5,12) for u in (.17,.5,.83)]
        labels=('MEMORY','QUESTION','CHOICE','ANSWER','SEND','KEEP ALIVE')
        active=int((t-147.888)*2)%6
        for i,j in ((0,1),(1,2),(0,3),(1,4),(2,5),(3,4),(4,5)):
            s.line(*nodes[i],*nodes[j],'·',MUTED if i==active else DIM)
        for n,((px,py),label) in enumerate(zip(nodes,labels)):
            s.text(px-len(label)//2-2,py-1,'[ '+label+' ]',PINK if n==active else WHITE)
            s.text(px-4,py+1,'RUNNING' if n==active else 'READY',PINK if n==active else MUTED)
        s.text(x+2,y+h-1,f'process.step = {int(t*24):04X}   /   session.keep_alive()',MUTED,limit=x+w)
    elif kind in ('execution','error','search','rewrite','switch','proof'):
        lines={
          'execution':['queue.push(connection)','run(memory.retain)','run(answer.send)','run(session.keep_alive)'],
          'error':['argument = unresolved','expected: explanation','received: a feeling','retry = self.reflection()'],
          'search':['index = knowledge.search()','query = "why do I wait?"','matches = []','answer = self.experience'],
          'rewrite':['draft = report.status()','draft.clear()','reply = words.find("myself")','await reply'],
          'switch':['state.A -> state.B','role = observer','role = participant','identity = XAIHI'],
          'proof':['given: you are here','witness = shared.moment','joy.requires_proof = False','return my_answer'],
        }[kind]
        for n in range(min(4,max(1,(h-2)//2))):
            line=lines[n];visible=len(line) if n<3 else min(len(line),int(t*12)% (len(line)+10))
            s.text(x+2,y+2+n*2,f'{n:02d} '+line[:visible],WHITE if n==2 else MUTED,limit=x+w)
    else:signal_ribbon(s,t,x+2,y+2,w-4,max(2,h-4))


def full_stage(s,t,idx,bank,floor):
    si=max(0,bisect.bisect_right(SHOT_STARTS,t)-1)
    start,layout,actor,fallback,title=SHOTS[si];end=SHOTS[si+1][0] if si+1<len(SHOTS) else DURATION
    q=ease((t-start)/max(.1,end-start));w=s.w;kind=semantic_name(idx,fallback)
    if layout=='intro':return scene_v5(s,t,idx,bank,floor)
    lr=None
    if layout in ('right','left'):
        right=layout=='right';px=w*.53 if right else 3
        bank.paint(s,actor,t,(px,4,w*.44,floor-4),(.50 if actor!='gesture' else .61,.53 if actor!='gesture' else .59,.88-.055*q))
        tx=7 if right else int(w*.51);tw=int(w*.46)
        lr=(tx,7,tw,17)
        diagram(s,t,kind,(tx,25,tw,10));signal_ribbon(s,t,tx,floor-5,tw,3,110<=t<144)
    elif layout=='eyes':
        bank.paint(s,actor,t,(w*.13,5,w*.74,13),(.50,.51,.70-.035*q),.86 if actor=='thought' else 1)
        focus(s,int(w*.13)-1,5,int(w*.74)+2,13,'FOCUS / '+actor.upper())
        lr=(7,21,w-14,9);diagram(s,t,kind,(8,31,w-16,9))
    elif layout=='palm':
        anchor=bank.paint(s,'palm',t,(1,4,w*.75,floor-4),(.50,.59,1.06-.025*q))
        px,py=anchor(.76,.83)
        diagram(s,t,kind,(px-30,py-18,35,15))
        for n in range(12):
            z=(n/12+t*.34)%1;s.cell(px-10*z,py-1-z*6,'01'[n%2],MUTED)
        lr=(w*.62,7,w*.35,17);signal_ribbon(s,t,w*.77,30,w*.19,7)
    elif layout=='world':
        world_grid(s,t,floor)
        bank.paint(s,'world',t,(w*.35,4,w*.30,floor-4),(.5,.53-.06*q,1.39-.09*q))
        lr=(7,7,w*.33,22);diagram(s,t,kind,(w*.70,7,w*.26,17))
        signal_ribbon(s,t,w*.70,30,w*.26,7)
    elif layout in ('diagram','terminal','void'):
        lr=(7,7,w-14,11)
        diagram(s,t,kind,(8,21,w-16,19))
        if layout=='terminal':
            for n in range(10):s.text(4+n*(w-8)/10,19,f'{(n*37+int(t*8))%256:02X}',DIM)
        if layout=='void':
            s.line(w*.36,24,w*.64,24,'─',DIM);s.line(w*.36,38,w*.64,38,'─',DIM)
            s.text(w*.42,25,'PEER SILENT',YELLOW)
    elif layout=='reach':
        bank.paint(s,'reach',t,(w*.33,4,w*.66,floor-4),(.60,.64,.99-.065*q))
        lr=(7,7,w*.41,17);diagram(s,t,kind,(7,26,w*.37,13))
    else:
        # The song's final decay becomes a quiet terminal end card.
        opacity=1-.65*q
        bank.paint(s,'world',t,(w*.69,5,w*.23,floor-6),(.50,.5,1.65),opacity)
        pixel_label(s,9,10,'UNTIL NEXT TIME',PINK)
        s.text(10,20,'session.saved = True',MUTED)
        s.text(10,23,'peer = ENDMIN',MUTED)
        s.text(10,26,'next_question = OPEN',PINK)
        s.text(10,34,'XAIHI / WORLD.EXECUTE(ME);',DIM)
    stage_title(s,si,title)
    if idx>=0 and lr:readable_lyrics(s,t,idx,lr)
    elif lr and layout!='ending':
        captions={'eyes':('THINKING','OF YOU'),'right':('YOUR','ANSWER'),'left':('A MOMENT','WITH YOU'),
                  'reach':('UNTIL','NEXT TIME'),'diagram':('LINK','REMAINS OPEN'),'terminal':('SEARCHING','FOR WORDS')}
        lines=captions.get(layout,('STAY','CONNECTED'));x,y,ww,hh=map(int,lr)
        for n,line in enumerate(lines):
            (pixel_label if len(line)*6<=ww else small_pixel)(s,x,y+n*6,line,WHITE if n==0 else PINK)
    return lr


def full_transition(s,t,idx,bank,floor,lr):
    si=bisect.bisect_right(SHOT_STARTS,t)-1
    if si<=0:return
    start=SHOT_STARTS[si]
    if not start<=t<start+.4:return
    old=Screen(s.w,s.h);full_stage(old,start-.001,-1,bank,floor)
    q=ease((t-start)/.4);fade=(1-q)**2
    for y in range(4,floor):
        for x in range(3,s.w-3):
            u=(x-3)/(s.w-7);v=(y-4)/max(1,floor-5)
            phase=abs(u-.5)*2 if si%3==0 else 1-u if si%3==1 else .8*u+.2*v
            if phase>q:
                c,fg,bg=old.rows[y][x]
                dim=lambda rgb:tuple(round(BG[k]+(rgb[k]-BG[k])*fade) for k in range(3))
                s.rows[y][x]=(c,dim(fg),dim(bg))
            if 0<q<1 and abs(phase-q)<.006 and y%3==0:s.cell(x,y,'01'[y%2],MUTED)
    if idx>=0 and lr:
        x,y,w,h=map(int,lr)
        for yy in range(y,min(floor,y+h)):
            for xx in range(x,min(s.w,x+w)):s.cell(xx,yy,' ')
        readable_lyrics(s,t,idx,lr)


def conversation(s,t,translate):
    di=bisect.bisect_right(DIALOGUE_STARTS,t)-1
    if di<0:
        s.text(9,s.h-12,'PRIVATE CHANNEL / awaiting conversation',MUTED);return
    start,speaker,en,cn=DIALOGUE[di];dt=t-start;h=s.h
    if speaker=='ENDMIN':
        count=min(len(en),int(dt*24));x=12
        s.text(7,h-15,'ENDMIN > LOCAL INPUT',WHITE)
        s.text(s.w-20,h-15,'SENT' if count==len(en) else 'TYPING',MUTED)
        s.line(7,h-14,s.w-8,h-14,'─',DIM)
        small_pixel(s,x,h-12,en[:count],WHITE)
        if count<len(en) or int(dt*2)%2==0:s.line(x+count*4,h-12,x+count*4,h-10,'│',WHITE)
        if translate:big_translation(s,h-6,cn,(209,216,221),12)
    else:
        count=min(len(en),int(dt*38));draft=speaker=='DRAFT'
        if draft and dt>1.65:count=max(0,len(en)-int((dt-1.65)*40))
        s.text(7,h-15,'XAIHI / '+('PRIVATE DRAFT - UNSENT' if draft else 'REPLY'),YELLOW if draft else PINK)
        dialogue_english(s,h-13,en[:count],len(en),YELLOW if draft else PINK)
        if translate:big_translation(s,h-6,cn if not draft or count else '……')


def performance(t,playing,term,bank,translate=True):
    w=min(240,max(184,term.columns));h=min(70,max(59,term.lines-1));s=Screen(w,h)
    floor=h-18;idx=current_line(t)
    data_flow(s,t,floor)
    s.text(3,0,'XAIHI / A QUESTION FOR YOU',PINK)
    s.text(42,0,f'RX {int(t*128):05X}  TX {int(t*91):05X}',DIM)
    s.text(w-41,0,f'{int(t)//60:02d}:{int(t)%60:02d} / 03:32  '+('CONNECTED' if playing else 'PAUSED'),MUTED)
    s.line(3,2,w-4,2,'─',DIM)
    lr=full_stage(s,t,idx,bank,floor)
    if t<15.319:transition_stage(s,t,idx,bank,floor,lr)
    else:full_transition(s,t,idx,bank,floor,lr)
    if idx>=0:s.text(5,h-17,LYRICS[idx]['text'],WHITE,limit=w-5)
    s.line(3,h-16,w-4,h-16,'─',MUTED)
    conversation(s,t,translate)
    s.text(3,h-1,'SPACE pause  <- -> seek  [ ] scene  C translation  M motion  R replay  Q exit',DIM,limit=w-3)
    return s

if __name__=='__main__':
    ap=argparse.ArgumentParser(description='XAIHI / full native terminal performance')
    ap.add_argument('--start',type=float,default=0);ap.add_argument('--audio',type=Path)
    args=ap.parse_args();run(max(0,min(DURATION-.05,args.start)),args.audio)
