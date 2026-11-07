"""Conservative visual/OCR identification of Field Guide and blueprint sightings."""
import re,subprocess,tempfile
from pathlib import Path
from PIL import Image, ImageOps, ImageEnhance
import catalog

MOD_LEVEL_RE=re.compile(r'(?m)^[ \t]*[|iI]?[ \t]*(1[0-7]|[1-9])[ \t]+(?:[A-Za-z][A-Za-z -]{2,35})[ \t]*$')

def selected_border(image_path):
    """Detect the cyan selection rectangle; color alone never proves ownership."""
    with Image.open(image_path) as original:
        im=original.convert('RGB');im.thumbnail((2200,1100))
        w,h=im.size;px=im.load();xs=[0]*w;ys=[0]*h
        for y in range(max(80,int(h*.1)),min(h,int(h*.95))):
            for x in range(min(w,1600)):
                r,g,b=px[x,y]
                if g>115 and b>90 and g>r*1.5 and b>r*1.3 and abs(g-b)<100:
                    xs[x]+=1;ys[y]+=1
        vertical=[x for x,n in enumerate(xs) if n>=35]
        horizontal=[y for y,n in enumerate(ys) if n>=60]
        if not vertical or not horizontal:return None
        # UI accent lines are common; require two distinct vertical and horizontal edges.
        for left in vertical:
            rights=[x for x in vertical if 65<=x-left<=270]
            for top in horizontal:
                bottoms=[y for y in horizontal if 65<=y-top<=270]
                if rights and bottoms:
                    scale_x=original.width/w;scale_y=original.height/h
                    return {'x':round(left*scale_x),'y':round(top*scale_y),'w':round((rights[-1]-left)*scale_x),'h':round((bottoms[-1]-top)*scale_y),'cue':'cyan rectangle'}
    return None

def icon_fingerprint(image_path,region):
    """Perceptual fingerprint of the selected card's central icon, for corroboration only."""
    if not region:return None
    with Image.open(image_path) as im:
        x,y,w,h=(region[k] for k in ('x','y','w','h'))
        box=(x+round(w*.18),y+round(h*.18),x+round(w*.82),y+round(h*.82))
        if box[0]<0 or box[1]<0 or box[2]>im.width or box[3]>im.height:return None
        pixels=list(ImageOps.grayscale(im.crop(box)).resize((8,8)).getdata())
        mean=sum(pixels)/64
        return f'{sum((1<<i) for i,p in enumerate(pixels) if p>=mean):016x}'

def scan_visible_grid(image_path,selected=None):
    """Read visible Field Guide card badges around a verified selection.

    Anonymous cards stay anonymous: a shared icon shape cannot establish a mod
    name or ownership. The tooltip and action/lock cues decide the selected card.
    """
    selected=selected or selected_border(image_path)
    if not selected:return []
    cards=[]
    lock_template=Image.open(Path(__file__).with_name('recognition_templates')/'lock_badge_1900px.png').convert('L')
    lock_pixels=[value>95 for value in lock_template.get_flattened_data()]
    with Image.open(image_path) as image:
        step_x=round(selected['w']*1.075);step_y=round(selected['h']*1.07)
        for dy in range(-3,4):
            for dx in range(-3,4):
                x=selected['x']+dx*step_x;y=selected['y']+dy*step_y
                if x<0 or y<0 or x+selected['w']>image.width*.55 or y+selected['h']>image.height:continue
                lock_crop=image.crop((x+25,y+25,x+85,y+85)).convert('L')
                current=[value>95 for value in lock_crop.get_flattened_data()]
                overlap=sum(a and b for a,b in zip(lock_pixels,current))
                union=sum(a or b for a,b in zip(lock_pixels,current))
                lock_score=overlap/union if union else 0
                locked=lock_score>=.75
                badge=image.crop((x+5,y+5,x+65,y+65)).convert('L')
                badge=ImageEnhance.Contrast(badge).enhance(2).resize((320,320))
                with tempfile.NamedTemporaryFile(suffix='.png') as temp:
                    badge.save(temp.name)
                    result=subprocess.run(['tesseract',temp.name,'stdout','--psm','6','-c','tessedit_char_whitelist=0123456789'],capture_output=True,text=True,timeout=8)
                digits=result.stdout.strip()
                level=int(digits) if re.fullmatch(r'1[0-7]|[1-9]',digits) else None
                is_selected=dx==0 and dy==0
                if level is None and not locked and not is_selected:continue
                cards.append({'region':{'x':x,'y':y,'w':selected['w'],'h':selected['h']},'level_badge':level if not locked else None,'level_ocr':digits,'selected':is_selected,'identity':'unresolved' if not is_selected else 'selected tooltip identity only','ownership':'locked' if locked else 'unknown','lock_match':round(lock_score,3),'visual_state':'selected' if is_selected else 'padlock and darkened card' if locked else 'visible level card; identity unverified'})
    return cards

def identify(text,image_path=None,kind_hint=None):
    if kind_hint is None:
        if re.search(r'\b(?:Weapon|Armor) Mods?\b',text,re.I):kind_hint='mod'
        elif re.search(r'\bB\.?P\.?\b|Blueprints',text,re.I):kind_hint=None
    match=catalog.matching(text,kind=kind_hint)
    level=None
    if kind_hint=='mod':
        m=MOD_LEVEL_RE.search(text)
        if m:level=int(m.group(1))
        if level is None and match['status']=='matched':
            variant=catalog.ENTRIES[match['id']].get('variant')
            if variant:
                pattern=r'(?m)^[^\n]{0,16}?\b(1[0-7]|[1-9])\s+'+re.escape(variant).replace(r'\ ',r'\s+')+r'\b'
                m=re.search(pattern,text,re.I)
                if m:level=int(m.group(1))
    cues=[];ownership='unknown'
    if re.search(r'\bUnlock Cost\b|\bLocked\b',text,re.I):ownership='locked';cues.append('explicit unlock cost or locked label')
    elif re.search(r'\bEquipped\b',text,re.I):ownership='equipped';cues.append('explicit equipped label')
    elif re.search(r'\b(?:F\s+)?Equip\b',text,re.I) and level is not None:
        ownership='unlocked';cues+=['equip action','visible Field Guide level']
    elif re.search(r'\bUnlocked\b',text,re.I):ownership='unlocked';cues.append('explicit unlocked label')
    elif level is not None:cues.append('visible Field Guide level; ownership needs another cue')
    border=selected_border(image_path) if image_path and match['status']=='matched' else None
    if border:cues.append('cyan selected border')
    fingerprint=icon_fingerprint(image_path,border) if border else None
    if fingerprint:cues.append('selected icon fingerprint; corroboration only')
    if match['status']=='matched':
        entry=catalog.ENTRIES[match['id']]
        cards=scan_visible_grid(image_path,border) if border else []
        for card in cards:
            if card['selected']:
                card['identity']=entry['id']
                card['ownership']=ownership
                if level is not None and card['level_badge'] is not None and card['level_badge']!=level:
                    card['level_conflict']='badge differs from hovered tooltip; review required'
        result={'match':match,'catalog_id':entry['id'],'name':entry['name'],'variant':entry.get('variant'),'slot':entry.get('slot'),'level':level,'ownership':ownership,'hovered':True,'selected':True if border else None,'selected_region':border,'visible_grid_cards':cards,'icon_fingerprint':fingerprint,'icon_reference_url':entry.get('image_url'),'icon_match_status':'unverified; visual reference only' if entry.get('image_url') else 'no catalog icon','equipped':ownership=='equipped','cues':cues}
        result['lookup']=catalog.resolve(entry['id'],level)
        return result
    return {'match':match,'catalog_id':None,'level':level,'ownership':ownership,'hovered':False,'selected':True if border else None,'selected_region':border,'icon_fingerprint':fingerprint,'equipped':ownership=='equipped','cues':cues}
