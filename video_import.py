"""Local video-to-review proposals. OCR is evidence, never automatic ownership."""
import csv, io, json, math, re, subprocess, tempfile
from pathlib import Path
from PIL import Image
import catalog

TITLE = re.compile(r"([A-Za-z][A-Za-z0-9 '\-]{2,80})\s*<([^<>]{2,45})>")
# The badge's icon is often OCR'd as a letter (for example "W 12 Battle").
# Search for the number immediately before the catalog suffix, never the icon.
LEVEL = re.compile(r'(?<!\d)(1[0-7]|[1-9])\s+([A-Za-z][A-Za-z ]+?)\s*$', re.I)
SLOT = {'weapon':'weapon_mod','helmet':'helmet_mod','mask':'mask_mod','top':'chest_mod','gloves':'gloves_mod','bottoms':'pants_mod','shoes':'boots_mod'}

def video_info(path):
    r=subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-show_entries','stream=width,height:format=duration','-of','json',str(path)],capture_output=True,text=True,timeout=15,check=True)
    j=json.loads(r.stdout);s=j['streams'][0]
    return {'width':int(s['width']),'height':int(s['height']),'duration':float(j['format']['duration'])}

def frame_at(path,seconds,target,scale=None):
    target.parent.mkdir(parents=True,exist_ok=True)
    cmd=['ffmpeg','-v','error','-ss',str(seconds),'-i',str(path),'-frames:v','1']
    if scale:cmd+=['-vf',f"scale='min({int(scale)},iw)':-1"]
    subprocess.run(cmd+['-y',str(target)],capture_output=True,timeout=30,check=True)
    return target

def ocr_lines(path):
    p=subprocess.run(['tesseract',str(path),'stdout','--psm','11','tsv'],capture_output=True,text=True,timeout=25)
    if p.returncode:return []
    grouped={}
    for row in csv.DictReader(io.StringIO(p.stdout),delimiter='\t'):
        if row.get('level')!='5' or not row.get('text','').strip():continue
        key=(row['block_num'],row['par_num'],row['line_num'])
        grouped.setdefault(key,[]).append(row)
    lines=[]
    for words in grouped.values():
        good=[w for w in words if w['text'].strip()]
        x=min(int(w['left']) for w in good);y=min(int(w['top']) for w in good)
        right=max(int(w['left'])+int(w['width']) for w in good)
        bottom=max(int(w['top'])+int(w['height']) for w in good)
        conf=[float(w['conf']) for w in good if float(w['conf'])>=0]
        lines.append({'text':' '.join(w['text'].strip() for w in good),'x':x,'y':y,'w':right-x,'h':bottom-y,'confidence':round(sum(conf)/len(conf),1) if conf else 0})
    return sorted(lines,key=lambda q:(q['y'],q['x']))

def titles(lines):
    found=[]
    for i,line in enumerate(lines):
        text=line['text']
        if '<' in text and '>' not in text:
            next_line=next((n for n in lines[i+1:i+4] if n['y']>line['y'] and n['y']-line['y']<60 and '>' in n['text']),None)
            if next_line:text+=' '+next_line['text']
        m=TITLE.search(text)
        if not m:continue
        title=' '.join(m.group(0).split())
        match=catalog.matching(title,kind='mod')
        if match['status']!='matched' or match['confidence']<.95:continue
        found.append({'title':title,'catalog_id':match['id'],'header':line,'match_confidence':match['confidence']})
    return found

def header_rarity(im,header):
    # Color of the tooltip title band. Neutral/ambiguous bands stay unknown.
    x0=max(0,header['x']-8);x1=min(im.width,header['x']+header['w']+90)
    y0=max(0,header['y']-8);y1=min(im.height,header['y']+header['h']+30)
    gold=purple=0
    for y in range(y0,y1,3):
        for x in range(x0,x1,3):
            r,g,b=im.getpixel((x,y))[:3]
            if 38<r<220 and 30<g<180 and 18<b<150 and r>g*1.12 and g>b*1.13:gold+=1
            if 30<r<180 and 17<g<130 and 35<b<180 and b>g*1.12 and r>g*1.08:purple+=1
    if max(gold,purple)<15 or min(gold,purple)*1.5>max(gold,purple):return None,{'gold_pixels':gold,'purple_pixels':purple}
    return ('legendary' if gold>purple else 'epic'),{'gold_pixels':gold,'purple_pixels':purple}

def context_capture(frame, tooltip, target):
    """Keep the in-game Mods/slot header with the tooltip evidence."""
    with Image.open(frame) as full, Image.open(tooltip) as detail:
        header=full.crop((0,0,max(1,int(full.width*.40)),max(1,int(full.height*.16))))
        if header.width!=detail.width:
            header=header.resize((detail.width,max(1,round(header.height*detail.width/header.width))))
        combined=Image.new('RGB',(detail.width,header.height+detail.height),(12,16,19))
        combined.paste(header,(0,0));combined.paste(detail,(0,header.height))
        combined.save(target)
    return target

def parse_tooltip(lines,catalog_id):
    entry=catalog.ENTRIES[catalog_id];suffix=str(entry.get('variant') or '')
    title_index=next((i for i,l in enumerate(lines) if TITLE.search(l['text'])),None)
    if title_index is None:
        title_index=next((i for i,l in enumerate(lines) if '<' in l['text'] and any(
            0<n['y']-l['y']<60 and TITLE.search(l['text']+' '+n['text'])
            for n in lines[i+1:i+4])),None)
    if title_index is None:return None
    start=lines[title_index]['y'];following=[l for l in lines[title_index+1:] if l['y']>start]
    slot_line=next((l for l in following[:5] if re.search(r'(?:Weapon|Armor)\s+Mods?\s*[-–]\s*(?:All\s+)?(Weapon|Helmet|Mask|Top|Gloves|Bottoms|Shoes)',l['text'],re.I)),None)
    slot=None
    if slot_line:
        m=re.search(r'[-–]\s*(?:All\s+)?(Weapon|Helmet|Mask|Top|Gloves|Bottoms|Shoes)',slot_line['text'],re.I)
        slot=SLOT.get(m.group(1).lower()) if m else None
    marker=None;level=None
    for l in following:
        m=LEVEL.search(l['text'])
        if m and suffix and re.sub(r'\W+','',m.group(2).lower())==re.sub(r'\W+','',suffix.lower()):
            level=int(m.group(1));marker=l;break
    locked=any(re.fullmatch(r'Locked',l['text'].strip(),re.I) for l in following)
    if marker is None and locked and suffix:
        marker=next((l for l in following if l['y']>(slot_line['y'] if slot_line else start) and
                     re.search(r'\b'+re.escape(suffix)+r'\b',l['text'],re.I)),None)
    equip=any(re.search(r'\bEquip\b',l['text'],re.I) for l in following)
    ownership='locked' if locked else 'unlocked' if equip and level is not None else 'unknown'
    end_main=marker['y'] if marker else (following[-1]['y'] if following else start)
    effect=[l['text'] for l in following if slot_line and l['y']>slot_line['y'] and l['y']<end_main
            and l['x']>=slot_line['x']-10 and len(l['text'].strip())>2
            and not re.search(r'\bLocked\b',l['text'],re.I)]
    # The repeated family heading precedes the actual effect text.
    if effect and catalog.normalized(effect[0])==catalog.normalized(entry['name']):effect=effect[1:]
    main_effect=' '.join(effect).strip()[:650] or None
    attribute_lines=[]
    if marker:
        tail=[]
        for l in following:
            if l['y']<=marker['y']:continue
            if re.search(r'^Level\s+\d+\s+and\s+above|attribute rolls|\bEquip\b',l['text'],re.I):break
            if not re.search(r'[A-Za-z]{3}',l['text']) and not re.search(r'\d+(?:\.\d+)?\s*%',l['text']):continue
            if l['text'].strip().lower()==suffix.lower():continue
            tail.append(l)
        chunks=[]
        for l in tail:
            # Adjacent rolled rows can be only ~70 px apart at native size;
            # wrapped text within one row is typically ~30 px apart.
            if not chunks or l['y']-chunks[-1][-1]['y']>45:chunks.append([l])
            else:chunks[-1].append(l)
        attribute_lines=[' '.join(x['text'] for x in block).strip() for block in chunks if any('%' in x['text'] for x in block)]
    return {'slot':slot,'level':level,'ownership':ownership,'ownership_cues':(['explicit Locked'] if locked else ['Equip action','visible level and suffix'] if ownership=='unlocked' else []),'main_effect':main_effect,'attribute_rows':attribute_lines,'raw_ocr':'\n'.join(l['text'] for l in lines),'ocr_confidence':round(sum(l['confidence'] for l in lines)/len(lines),1) if lines else 0}

def analyze(path,output,start=0,end=None,interval=1,progress=None,cancel=None):
    path=Path(path);output=Path(output);output.mkdir(parents=True,exist_ok=True)
    info=video_info(path);finish=min(info['duration'],float(end) if end is not None else info['duration'])
    start=max(0,float(start));interval=float(interval)
    if not 0<interval<=5 or finish<=start or finish-start>900:raise ValueError('Use a positive interval up to 5s and at most 15 minutes per review')
    count=min(900,math.ceil((finish-start)/interval));best={};warnings=[]
    last_seen={};encounters={}
    with tempfile.TemporaryDirectory(prefix='forge-video-scan-') as temp:
        preview=Path(temp)/'preview.png'
        for n in range(count):
            if cancel and cancel():return {'cancelled':True,'proposals':[],'warnings':[]}
            t=round(start+n*interval,2)
            try:frame_at(path,t,preview,scale=2242);scan=ocr_lines(preview)
            except Exception as e:warnings.append(f'Frame {t}s unavailable: {type(e).__name__}');continue
            for found in titles(scan):
                entry=catalog.ENTRIES[found['catalog_id']]
                native=output/f"frame-{t:g}.png"
                if not native.exists():frame_at(path,t,native)
                with Image.open(preview) as small, Image.open(native) as original:
                    hdr=found['header'];rarity,colors=header_rarity(small,hdr)
                    factor=original.width/small.width
                    left=max(0,int((hdr['x']-40)*factor));top=max(0,int((hdr['y']-30)*factor))
                    right=min(original.width,left+int(650*factor));bottom=min(original.height,top+int(850*factor))
                    crop=output/f"tooltip-{t:g}-{re.sub(r'[^a-z0-9]+','-',found['catalog_id'].lower())}.png"
                    original.crop((left,top,right,bottom)).save(crop)
                context=output/f"context-{t:g}-{re.sub(r'[^a-z0-9]+','-',found['catalog_id'].lower())}.png"
                context_capture(native,crop,context)
                detail=parse_tooltip(ocr_lines(crop),found['catalog_id'])
                if not detail:continue
                score=(30 if detail['ownership']=='unlocked' else 15 if detail['ownership']=='locked' else 0)+(10 if detail['level'] is not None else 0)+min(20,5*len(detail['attribute_rows']))+detail['ocr_confidence']/10
                proposal={'catalog_id':found['catalog_id'],'name':entry['name'],'variant':entry.get('variant'),'title':found['title'],'slot':detail['slot'] or entry.get('slot'),'level':detail['level'],'rarity':rarity,'ownership':detail['ownership'],'ownership_cues':detail['ownership_cues'],'main_effect':detail['main_effect'],'attribute_rows':detail['attribute_rows'],'source':{'timestamp':t,'frame':str(native),'tooltip':str(crop),'context':str(context)},'extraction':{'title':'OCR matched to catalog','level':'OCR of tooltip suffix line' if detail['level'] is not None else 'unknown','rarity':'title-band color classifier' if rarity else 'unknown','effect':'tooltip OCR','attributes':'tooltip OCR, review each row','ownership':'visible Locked label or Equip with level'},'raw_ocr':detail['raw_ocr'],'confidence':round(min(99,score),1),'unknowns':['Tooltip OCR and numeric values require review before commit']+(['Rarity not confidently classified'] if not rarity else [])+(['Field Guide level not readable'] if detail['level'] is None else []),'_score':score}
                base=(found['catalog_id'],detail['ownership'],detail['level'])
                previous=last_seen.get(base)
                if previous is None or n-previous>max(2,math.ceil(2.5/interval)):
                    encounters[base]=encounters.get(base,-1)+1
                last_seen[base]=n
                key=(*base,encounters[base])
                prior=best.get(key)
                if (prior and prior['attribute_rows'] and proposal['attribute_rows']
                        and prior['attribute_rows']!=proposal['attribute_rows']):
                    # Preserve conflicting partial and complete readings as
                    # separate source observations. A new Field Guide entry,
                    # level increase, or OCR noise cannot be decided here.
                    encounters[base]+=1;key=(*base,encounters[base])
                    warning='Conflicting tooltip readings; collection progression versus OCR error requires review'
                    proposal['unknowns'].append(warning);prior['unknowns'].append(warning)
                proposal['source']['encounter']=encounters[base]
                if key not in best or score>best[key]['_score']:best[key]=proposal
            if progress:progress(round((n+1)/count*100))
    resolved={p['catalog_id'] for p in best.values() if p['ownership']!='unknown'}
    proposals=sorted((p for p in best.values() if p['ownership']!='unknown' or p['catalog_id'] not in resolved),key=lambda p:p['source']['timestamp'])
    for p in proposals:p.pop('_score',None)
    if proposals:warnings.append('Cards shown without readable tooltip titles were not identified or marked owned.')
    return {'proposals':proposals,'warnings':warnings,'frames_scanned':count,'duration':info['duration']}


def analyze_image(path, output):
    """Use the same guarded tooltip proposal path for an uploaded screenshot."""
    path=Path(path);output=Path(output);output.mkdir(parents=True,exist_ok=True)
    native=output/'frame-0.png';preview=output/'preview-0.png'
    with Image.open(path) as original:
        original.convert('RGB').save(native)
        if original.width>2242:
            reduced=original.copy();reduced.thumbnail((2242,original.height));reduced.convert('RGB').save(preview)
        else:
            original.convert('RGB').save(preview)
    scan=ocr_lines(preview);proposals=[]
    with Image.open(preview) as small, Image.open(native) as original:
        for index,found in enumerate(titles(scan)):
            entry=catalog.ENTRIES[found['catalog_id']]
            hdr=found['header'];rarity,_=header_rarity(small,hdr)
            factor=original.width/small.width
            left=max(0,int((hdr['x']-40)*factor));top=max(0,int((hdr['y']-30)*factor))
            right=min(original.width,left+int(650*factor));bottom=min(original.height,top+int(850*factor))
            slug=re.sub(r'[^a-z0-9]+','-',found['catalog_id'].lower())
            crop=output/f'tooltip-0-{index}-{slug}.png';original.crop((left,top,right,bottom)).save(crop)
            context=output/f'context-0-{index}-{slug}.png';context_capture(native,crop,context)
            detail=parse_tooltip(ocr_lines(crop),found['catalog_id'])
            if not detail:continue
            score=(30 if detail['ownership']=='unlocked' else 15 if detail['ownership']=='locked' else 0)+(10 if detail['level'] is not None else 0)+min(20,5*len(detail['attribute_rows']))+detail['ocr_confidence']/10
            proposals.append({'catalog_id':found['catalog_id'],'name':entry['name'],'variant':entry.get('variant'),
                'title':found['title'],'slot':detail['slot'] or entry.get('slot'),'level':detail['level'],
                'rarity':rarity,'ownership':detail['ownership'],'ownership_cues':detail['ownership_cues'],
                'main_effect':detail['main_effect'],'attribute_rows':detail['attribute_rows'],
                'source':{'timestamp':0,'encounter':index,'frame':str(native),'tooltip':str(crop),'context':str(context)},
                'extraction':{'title':'OCR matched to catalog','level':'OCR of tooltip suffix line' if detail['level'] is not None else 'unknown',
                              'rarity':'title-band color classifier' if rarity else 'unknown','effect':'tooltip OCR',
                              'attributes':'tooltip OCR, review each row','ownership':'visible Locked label or Equip with level'},
                'raw_ocr':detail['raw_ocr'],'confidence':round(min(99,score),1),
                'unknowns':['Tooltip OCR and numeric values require review before commit']+
                           (['Rarity not confidently classified'] if not rarity else [])+
                           (['Field Guide level not readable'] if detail['level'] is None else [])})
    return {'proposals':proposals,'warnings':['Only readable tooltips were proposed; off-screen cards remain unknown.'],
            'frames_scanned':1,'duration':0}

if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('video');p.add_argument('output');p.add_argument('--start',type=float,default=0);p.add_argument('--end',type=float);p.add_argument('--interval',type=float,default=1);a=p.parse_args()
 print(json.dumps(analyze(a.video,a.output,a.start,a.end,a.interval),indent=2))
