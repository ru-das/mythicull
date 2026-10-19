"""Chromium UI regression using production JS/CSS and synthetic, mocked data.

Run: .venv/bin/python scripts/ui_regression.py --browser /path/to/chrome
No server, model, network, real photos, or additional dependencies required.
Artifacts default to /tmp/mythicull-ui; repeat with --width/--theme/--preview.
"""
from __future__ import annotations

import argparse
import base64
import io
import re
from pathlib import Path
import subprocess

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
MOCK = r'''
const calls = [];
let modelReady = false, failSave = false, failSearch = false, failModel = true;
const fixture = Array.from({length:8}, (_, i) => ({id:String(i), filename:i === 0 ? 'Wedding_長い名前_' + 'long_name_'.repeat(12) + '.jpg' : `Photo_${i}.jpg`, capture_time:'2026-10-19T14:30:00',time_source:i===0?'mtime':'exif',status:null,stars:0,group_id:i<2?'burst':String(i),is_group_pick:i!==1}));
const project = {id:'test', name:'Wedding — a long project name for responsive review',folder:'/synthetic/shoot',photo_count:8,chapter_gap_minutes:15,vibe_weight:0.5,last_import:{found:8,imported:8,already_present:0,skipped:[]}};
window.fetch = async (url, opts = {}) => {
 const body = opts.body ? JSON.parse(opts.body) : null;
 calls.push({url,body});
 let out = [], ok = true;
 if(url==='/api/model') out={ready:modelReady};
 else if(url==='/api/model/download') out={job_id:'download'};
 else if(url==='/api/folders/choose') out={folder:'/synthetic/export'};
 else if(url==='/api/projects' && opts.method==='POST') out={project,job_id:'import'};
 else if(url==='/api/projects') out=[project];
 else if(url==='/api/projects/test') out=project;
 else if(url.endsWith('/chapters')) out=[{id:'chapter',title:'Ceremony and reception',photo_count:8,kept_count:fixture.filter(p=>p.status==='keep').length,rejected_count:fixture.filter(p=>p.status==='reject').length}];
 else if(url.endsWith('/cameras')) out=[{camera_model:'Body A',photo_count:4,offset_seconds:0},{camera_model:'Body B',photo_count:4,offset_seconds:0}];
 else if(url.includes('/photos') && url.startsWith('/api/projects/')) out=fixture.map(p=>({...p}));
 else if(url.includes('/search?')) {ok=!failSearch;out=failSearch?{detail:'Search unavailable: model failure'}:fixture.slice(0,2).map(p=>({...p}));}
 else if(url.endsWith('/decision')) {
  ok=!failSave; out=ok?body:{detail:'Disk unavailable'};
  if(ok) Object.assign(fixture.find(p=>p.id===url.split('/')[3]),body);
 }
 else if(url.endsWith('/index')) out={job_id:'analysis'};
 else if(url.includes('/export/')) out={job_id:'export'};
 else if(url.startsWith('/api/jobs/')) out={status:url.endsWith('download')&&failModel?'failed':'done',done:8,total:8,failures:url.endsWith('download')&&failModel?[{error:'Download unavailable'}]:url.endsWith('export')?[{item:'foreign.xmp',error:'Existing sidecar skipped'}]:[]};
 return {ok,json:async()=>out};
};
window.addEventListener('error', e=>document.body.dataset.error=e.message);
window.addEventListener('unhandledrejection', e=>document.body.dataset.error=String(e.reason));
'''
CHECKS = r'''
const wait = () => new Promise(r=>setTimeout(r,60));
const assert = (value, message) => {if(!value) throw Error(message);};
const button = text => [...document.querySelectorAll('button')].find(b=>b.textContent===text);
const key = (value, target=document.activeElement, extra={}) => target.dispatchEvent(new KeyboardEvent('keydown',{key:value,bubbles:true,cancelable:true,...extra}));
(async()=>{
 try {
  await wait();
  assert(document.querySelector('.model-dialog'), 'Deferred setup prompt');
  assert(app.inert && document.body.style.overflow==='hidden','Model locks background');
  button('Not now').click();
  const name=document.querySelector('[aria-label="Project name"]'); name.value='Wedding';
  await document.querySelector('[aria-label="Choose photo folder"]').onclick();
  await document.querySelector('form').onsubmit({preventDefault(){}}); await wait(); await wait();
  assert(cells.length===7,'Import and grouped browsing');
  assert(document.querySelector('.sidebar').firstElementChild.textContent==='Chapters','Chapters first');
  assert(button('Analysis settings').getAttribute('aria-expanded')==='false','Settings collapsed');
  assert(cells.filter(c=>c.tabIndex===0).length===1,'One photo tab stop');
  cells[0].focus(); key('ArrowRight'); assert(document.activeElement===cells[1] && selected===1,'Arrow selection moves focus');
  key('Enter'); assert(current===1 && document.activeElement===closeBtn,'Keyboard opens preview');
  assert(app.inert && topbar.inert,'Preview inert background');
  document.getElementById('search').focus(); assert(overlay.contains(document.activeElement),'Background cannot receive focus');
  key('/'); assert(overlay.contains(document.activeElement),'Search shortcut stays in preview');
  for(let i=0;i<25;i++) {key('Tab');assert(overlay.contains(document.activeElement),'Tab containment');}
  key('Tab',document.activeElement,{shiftKey:true}); assert(overlay.contains(document.activeElement),'Reverse Tab containment');
  autoAdvance=false;
  nextBtn.click(); assert(current===2,'Next'); previousBtn.click(); assert(current===1,'Previous');
  decisionButtons[0].click(); await wait(); assert(photos[1].status==='keep','Visible Keep');
  starButtons[5].focus();starButtons[5].click(); await wait();assert(document.activeElement===starButtons[5],'Rating retains focus'); assert(photos[1].stars===5 && caption.textContent.includes('5 stars'),'Visible stars synchronized');
  await undo(); assert(photos[1].stars===0,'Undo rating');
  decisionButtons[1].click(); await wait(); assert(photos[1].status==='reject','Visible Reject');
  decisionButtons[2].click(); await wait(); assert(photos[1].status===null,'Clear decision');
  failSave=true; starButtons[4].click(); await wait(); assert(photos[1].stars===0 && previewError.textContent.includes('Could not save'),'Failed save rolls back'); failSave=false;
  bigImg.click(); caption.click(); actions.click(); assert(current===1,'Preview content stays open');
  key('Escape'); assert(current===-1 && document.activeElement===cells[1] && !app.inert,'Escape restores opener');
  cells[0].focus(); openPreview(0); assert(previousBtn.disabled,'Previous boundary'); openPreview(photos.length-1); assert(nextBtn.disabled,'Next boundary');
  closeBtn.click(); assert(current===-1,'Close button');
  cells[0].focus(); openPreview(0); imageStage.click(); assert(current===-1,'Backdrop closes');
  cells[0].focus(); openPreview(0); cells[0].remove(); key('Escape'); assert(document.activeElement===document.getElementById('home') && !app.inert,'Removed opener fallback'); renderGrid();
  cells[0].focus(); key('p'); await wait(); assert(photos[0].status==='keep','Keyboard Keep');
  autoAdvance=true; openPreview(0); key('x'); await wait(); assert(current===1,'Auto advance after successful save');
  openPreview(-1);
  document.querySelector('.count').click(); assert(cells.length===8 && document.activeElement.classList.contains('count'),'Group expansion accessible');
  const sliderSidebarToggle=document.querySelector('.side-toggle');if(getComputedStyle(sliderSidebarToggle).display!=='none' && sliderSidebarToggle.getAttribute('aria-expanded')!=='true')sliderSidebarToggle.click();
  button('Analysis settings').click();
  const commits=[]; const testSlider=slider({value:0.5,onCommit:v=>commits.push(v)});document.querySelector('.sidebar').append(testSlider);testSlider.focus();
  // Synthetic events cannot claim native pointer capture; stub only that browser boundary.
  let releases=0;testSlider.setPointerCapture=()=>{};testSlider.hasPointerCapture=()=>true;testSlider.releasePointerCapture=()=>releases++;
  const bounds=testSlider.getBoundingClientRect();
  testSlider.dispatchEvent(new PointerEvent('pointerdown',{pointerId:7,button:0,clientX:bounds.left+bounds.width*0.7}));
  testSlider.dispatchEvent(new PointerEvent('pointermove',{pointerId:7,clientX:bounds.left+bounds.width*0.85}));
  testSlider.dispatchEvent(new PointerEvent('pointercancel',{pointerId:7}));testSlider.dispatchEvent(new PointerEvent('lostpointercapture',{pointerId:7}));testSlider.blur();
  assert(commits.length===1 && commits[0]===0.85 && releases===1 && !testSlider.classList.contains('drag'),'Cancelled drag commits displayed value exactly once');
  testSlider.dispatchEvent(new PointerEvent('pointerdown',{pointerId:8,button:0,clientX:bounds.left+bounds.width*0.1}));window.dispatchEvent(new Event('blur'));
  assert(commits.length===2 && commits[1]===0.1 && releases===2 && !testSlider.classList.contains('drag'),'Window blur commits displayed value');testSlider.remove();if(sliderSidebarToggle.getAttribute('aria-expanded')==='true')sliderSidebarToggle.click();
  const search=document.getElementById('search');search.value='dancing';key('Enter',search);await wait();assert(cells.length===2,'Search results');
  failSearch=true;key('Enter',search);await wait();await wait();assert(document.querySelector('.hit').textContent.includes('Search unavailable') && cells.length>0,'Search failure recovers browsing');failSearch=false;
  await button('Analyze photos').onclick(); assert(document.querySelector('.model-dialog'),'Analysis requests deferred model');
  await button('Download model').onclick();assert(document.querySelector('.model-card .error').textContent.includes('Download unavailable'),'Model failure visible');
  failModel=false;modelReady=true;await button('Retry download').onclick();assert(button('Done'),'Model retry installed');button('Done').click();
  await button('Analyze photos').onclick();assert(calls.some(c=>c.url.endsWith('/index')),'Analysis runs');
  button('Export').click();await button('Save ratings to XMP').onclick();await wait();assert(app.textContent.includes('7 written, 1 skipped') && app.textContent.includes('foreign.xmp'),'Export summary and skips');
  await document.querySelector('[aria-label="Choose copy photos to"]').onclick();button('Copy kept photos').click();await wait();assert(calls.some(c=>c.body?.destination==='/synthetic/export'),'Copy export');
  filter='keep';allPhotos.forEach(p=>p.status=null);renderGrid();assert(gridEl.textContent.includes('No kept photos'),'Accessible filtered empty state');
  allPhotos=[];renderGrid();assert(gridEl.textContent.includes('No photos imported'),'Accessible import empty state');
  filter='all';allPhotos=fixture.map(p=>({...p}));renderGrid();
  cells[0].focus();openPreview(0);location.hash='#/';await wait();assert(current===-1 && !app.inert && document.body.style.overflow!=='hidden','Route closes preview');
  location.hash='#/p/test';await wait();await wait();
  applyTheme(TEST_THEME,false);
  if(TEST_ZOOM) document.documentElement.style.zoom='2';
  assert(document.documentElement.scrollWidth<=innerWidth+1,'No horizontal overflow');
  const luminance = rgb => rgb.slice(0,3).map(v=>{v/=255;return v<=0.04045?v/12.92:((v+0.055)/1.055)**2.4;}).reduce((n,v,i)=>n+v*[0.2126,0.7152,0.0722][i],0);
  const contrast = (a,b) => {const x=luminance(a),y=luminance(b);return (Math.max(x,y)+0.05)/(Math.min(x,y)+0.05);};
  for(const node of [document.querySelector('.summary p'),document.querySelector('.fname'),document.querySelector('.seg-b:not(.on)')]) {
    const fg=getComputedStyle(node).color.match(/[\d.]+/g).map(Number);let parent=node,bg;
    while(parent) {bg=getComputedStyle(parent).backgroundColor.match(/[\d.]+/g).map(Number);if(bg.length===3 || bg[3]===1) break;parent=parent.parentElement;}
    assert(contrast(fg,bg)>=4.5,'Text contrast: '+node.className);
  }
  const toggleSidebar=document.querySelector('.side-toggle');if(getComputedStyle(toggleSidebar).display!=='none') toggleSidebar.click();
  const settingButton=button('Analysis settings');settingButton.click();await wait();
  assert(document.querySelector('.sidebar').scrollWidth<=document.querySelector('.sidebar').clientWidth+1,'Settings do not overflow');settingButton.click();if(toggleSidebar.getAttribute('aria-expanded')==='true')toggleSidebar.click();
  for(const name of ['--surround','--tile']) {
    const color=getComputedStyle(document.documentElement).getPropertyValue(name).trim();assert(/^#([0-9a-f])\1([0-9a-f])\2([0-9a-f])\3$/i.test(color) || color==='#222222'||color==='#303030'||color==='#d4d4d4'||color==='#bfbfbf','Neutral surround');
  }
  for(const node of document.querySelectorAll('[role="progressbar"]')) assert(node.getAttribute('aria-label'),'Progress name');
  assert(!document.body.dataset.error,document.body.dataset.error);
  assert(!performance.getEntriesByType('resource').some(r=>/^https?:/.test(r.name)),'No external requests');
  window.scrollTo(0,0);
  if(TEST_SETTINGS) {const b=document.querySelector('.side-toggle');if(getComputedStyle(b).display!=='none') b.click();button('Analysis settings').click();await wait();}
  if(TEST_PREVIEW) {openPreview(0);await wait();document.body.dataset.geometry=JSON.stringify({overlay:overlay.getBoundingClientRect().toJSON(),footer:document.querySelector('.lb-footer').getBoundingClientRect().toJSON(),height:innerHeight,scrollY});assert(document.querySelector('.lb-footer').getBoundingClientRect().bottom<=innerHeight+1,'Footer stays in viewport');assert(bigImg.getBoundingClientRect().bottom<=document.querySelector('.lb-footer').getBoundingClientRect().top+1,'Image and footer do not overlap');}
  document.body.dataset.checks='passed';
 } catch(e) {document.body.dataset.checks='failed: '+e.message;}
})();
'''


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--browser', required=True)
    parser.add_argument('--output', default='/tmp/mythicull-ui')
    parser.add_argument('--width', type=int, default=390)
    parser.add_argument('--theme', choices=['dark', 'light'], default='dark')
    parser.add_argument('--preview', action='store_true')
    parser.add_argument('--settings', action='store_true')
    parser.add_argument('--zoom', action='store_true', help='Simulate 200 percent with CSS zoom')
    parser.add_argument('--reduced', action='store_true')
    args = parser.parse_args()
    image = Image.new('RGB', (720, 480), '#888888')
    draw = ImageDraw.Draw(image)
    for i, color in enumerate(['#222222', '#555555', '#aaaaaa', '#dddddd']):
        draw.rectangle((40 + i * 165, 70, 170 + i * 165, 410), fill=color)
    buf = io.BytesIO()
    image.save(buf, 'JPEG')
    photo = 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode()
    js = (ROOT / 'web/app.js').read_text()
    for size in ['thumb', 'preview']:
        js = js.replace('`/api/photos/${p.id}/' + size + '`', repr(photo))
    css = (ROOT / 'web/styles.css').read_text().replace('url("/fonts/', f'url("file://{ROOT}/web/fonts/')
    html = (ROOT / 'web/index.html').read_text().replace('<link rel="stylesheet" href="/styles.css">', '<style>' + css + '</style>')
    html = html.replace('<link rel="preload"', '<link rel="alternate"')
    config = f'const TEST_THEME={args.theme!r}, TEST_PREVIEW={str(args.preview).lower()}, TEST_ZOOM={str(args.zoom).lower()}, TEST_SETTINGS={str(args.settings).lower()};'
    html = html.replace('<script type="module" src="/app.js"></script>', '<script>"use strict";\n' + config + MOCK + js + CHECKS + '</script>')
    output = Path(args.output).resolve()
    output.with_suffix('.html').write_text(html)
    command = [args.browser, '--headless', '--no-sandbox', '--disable-gpu', '--disable-background-networking', '--allow-file-access-from-files', '--window-size=' + str(args.width) + ',900', '--virtual-time-budget=10000', '--dump-dom', '--screenshot=' + str(output.with_suffix('.png'))]
    if args.reduced:
        command.append('--force-prefers-reduced-motion')
    result = subprocess.run(command + [output.with_suffix('.html').as_uri()], capture_output=True, text=True, timeout=30)
    output.with_suffix('.dom.html').write_text(result.stdout)
    output.with_suffix('.log').write_text(result.stderr)
    status = re.search(r'data-checks="([^"]*)"', result.stdout)
    print(status.group(1) if status else 'Browser did not finish; see ' + str(output.with_suffix('.log')))
    if result.returncode or not status or status.group(1) != 'passed':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
