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
let exportResult={status:'done',done:8,total:8,failures:[{item:'foreign.xmp',error:'Existing sidecar skipped'}]};
const fixture = Array.from({length:8}, (_, i) => ({id:String(i), filename:i === 0 ? 'Wedding_長い名前_' + 'long_name_'.repeat(12) + '.jpg' : i===1?'Alternative.NEF':i===2?'Kept.CR2':i===3?'Photo_3.dng':`Photo_${i}.jpg`, capture_time:'2026-10-19T14:30:00',time_source:i===0?'mtime':'exif',status:null,stars:0,group_id:i<2?'burst':String(i),is_group_pick:i!==1}));
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
 else if(url.startsWith('/api/jobs/')) out=url.endsWith('export')?exportResult:{status:url.endsWith('download')&&failModel?'failed':'done',done:8,total:8,failures:url.endsWith('download')&&failModel?[{error:'Download unavailable'}]:[]};
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
  assert(!document.querySelector('.import-details').open,'Successful import details collapsed');
  const initialOptions=document.querySelector('.review-options-toggle');
  if(getComputedStyle(initialOptions).display!=='none') {
    assert(getComputedStyle(document.querySelector('.review-options-body')).display==='none','Mobile review options initially collapsed');
    initialOptions.click();assert(document.querySelector('.review-options-body').getClientRects().length,'Review options accessible on mobile');
    key('Escape',initialOptions);assert(initialOptions.getAttribute('aria-expanded')==='false','Escape closes review options');
  }
  assert(document.querySelector('.sidebar').firstElementChild.textContent==='Chapters','Chapters first');
  assert(button('Analysis settings').getAttribute('aria-expanded')==='false','Settings collapsed');
  assert(cells.filter(c=>c.tabIndex===0).length===1,'One photo tab stop');
  const columns=Math.max(1,getComputedStyle(gridEl).gridTemplateColumns.split(' ').length);
  cells[0].focus();key('ArrowDown');assert(selected===Math.min(columns,photos.length-1),'Down moves one rendered row');
  key('ArrowUp');assert(selected===0,'Up returns one rendered row');
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
  openPreview(0);await wait();zoomBtn.click();
  assert(previewZoom && currentViewport.classList.contains('zoomed') && previewInfo.textContent.includes('not original resolution'),'Zoom honestly labels cached preview');
  const zoomSelection=selected;currentViewport.focus();key('ArrowRight');
  assert(selected===zoomSelection && (currentViewport.clientWidth>=bigImg.naturalWidth || currentViewport.scrollLeft>0),'Zoom arrows pan without changing photo');
  currentViewport.style.cssText='flex:none;width:200px;height:120px';currentViewport.scrollLeft=currentViewport.scrollTop=0;
  let panReleased=0;currentViewport.setPointerCapture=()=>{};currentViewport.hasPointerCapture=()=>true;currentViewport.releasePointerCapture=()=>panReleased++;
  currentViewport.dispatchEvent(new PointerEvent('pointerdown',{pointerId:11,pointerType:'mouse',button:0,clientX:100,clientY:100}));
  currentViewport.dispatchEvent(new PointerEvent('pointermove',{pointerId:11,clientX:40,clientY:60}));
  assert(currentViewport.scrollLeft===60 && currentViewport.scrollTop===40,'Mouse drag pans cached image');
  currentViewport.dispatchEvent(new PointerEvent('pointercancel',{pointerId:11}));assert(panReleased===1 && !currentViewport.classList.contains('panning'),'Interrupted pan releases capture');
  for(const prop of ['setPointerCapture','hasPointerCapture','releasePointerCapture']) delete currentViewport[prop];currentViewport.removeAttribute('style');
  compareBtn.click();assert(!referencePane.hidden && referencePhoto.id===photos[0].id,'Pin reference');
  const alternative=burstStrip.querySelectorAll('button')[1];assert(alternative,'Burst alternative available');alternative.click();
  assert(current===1 && referencePhoto.id==='0' && !referencePane.hidden && referenceImg.alt!==bigImg.alt,'Compare keeps reference while choosing burst alternative');
  assert(caption.querySelector('.lb-filename summary').textContent===photos[current].filename,'Filename disclosure shows current photo');
  const filenameSummary=caption.querySelector('.lb-filename summary');filenameSummary.focus();key('Enter');assert(current===1,'Filename keyboard activation does not close preview');filenameSummary.click();assert(caption.querySelector('.lb-filename').open,'Full filename expands');
  clearReferenceBtn.click();assert(referencePane.hidden && document.activeElement===compareBtn,'Clear reference restores focus');
  key('z',closeBtn);assert(!previewZoom,'Keyboard returns to fit');openPreview(-1);assert(!referencePhoto && !previewZoom,'Close resets inspection');
  const sliderSidebarToggle=document.querySelector('.side-toggle');if(getComputedStyle(sliderSidebarToggle).display!=='none' && sliderSidebarToggle.getAttribute('aria-expanded')!=='true')sliderSidebarToggle.click();
  button('Analysis settings').click();
  const helpButtons=[...document.querySelectorAll('.help-button')];
  assert(helpButtons.length===3,'Three setting help buttons');
  for(const help of helpButtons) {
    const tip=document.getElementById(help.getAttribute('aria-describedby'));
    assert(getComputedStyle(tip).display==='none','Help hidden initially');
    help.focus(); assert(getComputedStyle(tip).display==='block','Focus shows help');
    assert(tip.getBoundingClientRect().right<=document.querySelector('.sidebar').getBoundingClientRect().right,'Help fits sidebar');
    key('Escape',help); assert(getComputedStyle(tip).display==='none','Escape dismisses help');
    help.blur();
  }
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
  fixture[1].status='keep';fixture[2].status='reject';fixture[3].status='keep';fixture[4].stars=4;
  button('Export').click();await wait();
  assert(document.querySelector('.export-preview').textContent.includes('2 RAW photos eligible') && document.querySelector('.export-preview').textContent.includes('2 decided photos excluded') && document.querySelector('.export-preview').textContent.includes('1 stars-only photo excluded'),'Whole-project export eligibility covers RAW/JPEG/DNG and stars-only');
  assert(app.textContent.includes('0 becomes 1') && app.textContent.includes('regardless of the chapter'),'Export mapping and scope explicit');
  await button('Save ratings to XMP').onclick();await wait();assert(app.textContent.includes('7 written, 1 skipped') && app.textContent.includes('foreign.xmp'),'Export summary and skips');
  await document.querySelector('[aria-label="Choose copy photos to"]').onclick();button('Copy kept photos').click();await wait();assert(calls.some(c=>c.body?.destination==='/synthetic/export'),'Copy export');
  exportResult={...exportResult,status:'cancelled',done:2};await button('Save ratings to XMP').onclick();await wait();assert(app.textContent.includes('1 written, 1 skipped. 6 not processed'),'Cancelled export never claims unprocessed photos were written');exportResult={...exportResult,status:'done',done:8};
  fixture[1].status='keep';fixture[2].status='keep';fixture[3].status=null;expanded.clear();filter='keep';view='best';showGrid(gridEl,fixture.map(p=>({...p})));
  assert(photos.length===2 && photos.some(p=>p.id==='1'),'Kept filter exposes non-suggested burst member');
  assert(!document.querySelector('.count'),'Filtered decisions never collapse into groups');
  filter='reject';renderGrid();assert(gridEl.classList.contains('review-rejected') && getComputedStyle(cells[0].querySelector('img')).opacity==='1','Rejected review preserves image visibility');filter='keep';renderGrid();
  openPreview(0);await rate({status:'reject'},true);
  assert(photos.length===1 && photos[0].id==='2' && current===0,'Filtered rating removes photo without skipping next or closing preview');
  assert(!previewUndo.disabled,'Visible undo enabled');await undo();
  assert(photos.length===2 && photos.some(p=>p.id==='1') && current>=0,'Undo restores filtered keeper and keeps preview');openPreview(-1);
  filter='keep';allPhotos.forEach(p=>p.status=null);renderGrid();assert(gridEl.textContent.includes('No kept photos'),'Accessible filtered empty state');
  allPhotos=[];renderGrid();assert(gridEl.textContent.includes('No photos imported'),'Accessible import empty state');
  filter='all';allPhotos=fixture.map(p=>({...p}));renderGrid();
  filter='unreviewed';view='all';autoAdvance=false;reviewChapterId='chapter';renderGrid();select(1);const resumeId=photos[selected].id;
  cells[selected].focus();openPreview(selected);location.hash='#/';await wait();assert(current===-1 && !app.inert && document.body.style.overflow!=='hidden','Route closes preview');
  location.hash='#/p/test';await wait();await wait();
  assert(photos[selected].id===resumeId && reviewChapterId==='chapter' && filter==='unreviewed' && view==='all' && !autoAdvance,'Project restores photo, chapter, filter, view and auto-next');
  button('All').click();const restoredOptions=document.querySelector('.review-options-toggle');if(getComputedStyle(restoredOptions).display!=='none') restoredOptions.click();button('Suggested').click();if(getComputedStyle(restoredOptions).display!=='none') key('Escape',restoredOptions);
  location.hash='#/';await wait();localStorage.setItem('mythicull-review-test',JSON.stringify({chapterId:'removed',photoId:'removed',filter:'all',view:'best'}));location.hash='#/p/test';await wait();await wait();
  assert(reviewChapterId===null && selected===0 && photos.length,'Stale chapter and photo resume safely');
  location.hash='#/';await wait();localStorage.setItem('mythicull-review-test','invalid JSON');location.hash='#/p/test';await wait();await wait();
  assert(filter==='all' && view==='best' && autoAdvance && selected===0,'Corrupt browser state falls back to usable defaults');
  applyTheme(TEST_THEME,false);
  if(TEST_ZOOM) document.documentElement.style.zoom='2';
  assert(document.documentElement.scrollWidth<=innerWidth+1,'No horizontal overflow');
  if(innerWidth<=600 && !TEST_ZOOM) assert(gridEl.getBoundingClientRect().top+scrollY<450,'Mobile first photos visible without excess chrome: '+JSON.stringify({gridTop:gridEl.getBoundingClientRect().top,scrollY,bar:topbar.offsetHeight,work:document.querySelector('.workbar').offsetHeight}));
  // Sample final colors rather than a compositor transition between radio states.
  const contrastStyles=document.createElement('style');contrastStyles.textContent='* {transition:none !important}';document.head.append(contrastStyles);
  const luminance = rgb => rgb.slice(0,3).map(v=>{v/=255;return v<=0.04045?v/12.92:((v+0.055)/1.055)**2.4;}).reduce((n,v,i)=>n+v*[0.2126,0.7152,0.0722][i],0);
  const contrast = (a,b) => {const x=luminance(a),y=luminance(b);return (Math.max(x,y)+0.05)/(Math.min(x,y)+0.05);};
  for(const node of [document.querySelector('.summary p'),document.querySelector('.fname'),document.querySelector('.seg-b:not(.on)')]) {
    const fg=getComputedStyle(node).color.match(/[\d.]+/g).map(Number);let parent=node,bg;
    while(parent) {bg=getComputedStyle(parent).backgroundColor.match(/[\d.]+/g).map(Number);if(bg.length===3 || bg[3]===1) break;parent=parent.parentElement;}
    assert(contrast(fg,bg)>=4.5,'Text contrast: '+node.className+' '+node.textContent+' '+JSON.stringify({fg,bg,ratio:contrast(fg,bg)}));
  }
  contrastStyles.remove();
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
  const stickySide=document.querySelector('.sidebar'), stickyToggle=document.querySelector('.side-toggle');
  const narrowSidebar=getComputedStyle(stickyToggle).display!=='none';
  if(narrowSidebar && !stickySide.classList.contains('open')) stickyToggle.click();
  const stickyView=stickySide.closest('.view'), savedAnimation=stickyView.style.animation;
  stickyView.style.animation='none';
  const stickyGrid=document.querySelector('.grid'), savedMinHeight=stickyGrid.style.minHeight;
  stickyGrid.style.minHeight='3000px';
  const stickyTop=parseFloat(getComputedStyle(stickySide).top)*(parseFloat(getComputedStyle(document.documentElement).zoom)||1);
  window.scrollTo(0,stickySide.getBoundingClientRect().top+scrollY+200);await wait();
  assert(Math.abs(stickySide.getBoundingClientRect().top-stickyTop)<2,'Sidebar stays pinned while photos scroll: '+JSON.stringify({actual:stickySide.getBoundingClientRect().top,expected:stickyTop,scrollY,height:stickySide.offsetHeight,bar:topbar.offsetHeight,layout:stickySide.parentElement.getBoundingClientRect().toJSON()}));
  // CSS zoom scales vh-based bounds differently from native browser zoom.
  if(!TEST_ZOOM) assert(stickySide.getBoundingClientRect().bottom<=innerHeight,'Sticky sidebar fits viewport');
  const priorSideScroll=stickySide.scrollTop;stickySide.scrollTop=stickySide.scrollHeight;
  if(stickySide.scrollHeight>stickySide.clientHeight) assert(stickySide.scrollTop>priorSideScroll,'Sidebar scrolls independently');
  stickySide.scrollTop=0;stickyGrid.style.minHeight=savedMinHeight;stickyView.style.animation=savedAnimation;
  if(narrowSidebar) stickyToggle.click();
  window.scrollTo(0,0);
  if(TEST_SETTINGS) {const b=document.querySelector('.side-toggle');if(getComputedStyle(b).display!=='none') b.click();button('Analysis settings').click();await wait();document.querySelector('.help-button').focus();}
  if(TEST_EXPORT) {button('Export').click();await wait();window.scrollTo(0,0);}
  if(TEST_PREVIEW) {openPreview(0);if(TEST_COMPARE){compareBtn.click();openPreview(1);}await wait();document.body.dataset.geometry=JSON.stringify({overlay:overlay.getBoundingClientRect().toJSON(),footer:document.querySelector('.lb-footer').getBoundingClientRect().toJSON(),height:innerHeight,scrollY});assert(document.querySelector('.lb-footer').getBoundingClientRect().bottom<=innerHeight+1,'Footer stays in viewport');assert(bigImg.getBoundingClientRect().bottom<=document.querySelector('.lb-footer').getBoundingClientRect().top+1,'Image and footer do not overlap');}
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
    parser.add_argument('--export-panel', action='store_true', help='Capture export preview')
    parser.add_argument('--compare', action='store_true', help='Capture pinned-reference comparison in preview')
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
        js = re.sub(r'`/api/photos/\$\{[^}]+\}/' + size + '`', lambda _: repr(photo), js)
    css = (ROOT / 'web/styles.css').read_text().replace('url("/fonts/', f'url("file://{ROOT}/web/fonts/')
    html = (ROOT / 'web/index.html').read_text().replace('<link rel="stylesheet" href="/styles.css">', '<style>' + css + '</style>')
    html = html.replace('<link rel="preload"', '<link rel="alternate"')
    config = f'const TEST_THEME={args.theme!r}, TEST_PREVIEW={str(args.preview).lower()}, TEST_ZOOM={str(args.zoom).lower()}, TEST_SETTINGS={str(args.settings).lower()}, TEST_COMPARE={str(args.compare).lower()}, TEST_EXPORT={str(args.export_panel).lower()};'
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
