const visible = e => {
  const r = e.getBoundingClientRect(), s = getComputedStyle(e);
  return r.width > 0 && r.height > 0 && r.bottom > 0 && r.right > 0 &&
    r.top < innerHeight && r.left < innerWidth && s.visibility !== 'hidden' && s.display !== 'none';
};
const label = e => (e.getAttribute('aria-label') ||
  (e.labels ? Array.from(e.labels).map(x => x.innerText).join(' ') : '') ||
  e.getAttribute('placeholder') || e.getAttribute('title') ||
  (e.tagName === 'INPUT' && ['submit','button'].includes(e.type) ? e.value : '') ||
  e.innerText || e.name || e.id || '').trim().slice(0, 140);
const describe = e => {
  const role = e.getAttribute('role') || (e.hasAttribute('onclick') ? 'button' : e.tagName.toLowerCase());
  const editable = (e.tagName === 'TEXTAREA' ||
    (e.tagName === 'INPUT' && ['text','search','url','email','tel'].includes(e.type)) || e.isContentEditable) && !e.readOnly;
  const clickable = ['BUTTON','A','SUMMARY'].includes(e.tagName) || e.hasAttribute('onclick') ||
    ['button','link','checkbox','radio','menuitem','tab','option'].includes(role) ||
    (e.tagName === 'INPUT' && ['submit','button','checkbox','radio'].includes(e.type));
  const value = editable || e.tagName === 'SELECT' ? String(e.value ?? e.innerText ?? '').slice(0, 250) : '';
  return {role, label: label(e), value, editable, clickable,
          selected: e.checked === true || e.getAttribute('aria-selected') === 'true',
          enabled: !e.disabled && e.getAttribute('aria-disabled') !== 'true',
          sensitive: e.type === 'password' || /password|secret|token|api.?key/i.test(label(e) + ' ' + e.name)};
};
if (arguments[0] === 'target') {
  const e = arguments[1];
  if (!e || !e.isConnected || !visible(e)) return null;
  const d = describe(e);
  const r = e.getBoundingClientRect();
  const x = Math.max(0, Math.min(innerWidth - 1, r.left + r.width / 2));
  const y = Math.max(0, Math.min(innerHeight - 1, r.top + r.height / 2));
  const root = e.getRootNode();
  const top = (typeof root.elementFromPoint === 'function' ? root : document).elementFromPoint(x, y);
  const documentTop=document.elementFromPoint(x,y);
  let host=e, reachesDocument=false;
  while (host) {
    if (documentTop && (host===documentTop || host.contains(documentTop))) reachesDocument=true;
    host=host.getRootNode().host || null;
  }
  d.covered = !reachesDocument || !(top && (e === top || e.contains(top)));
  return d;
}
const selector='button,a[href],input,textarea,select,summary,[role],[onclick],[contenteditable="true"]';
const nodes=[];
function collect(root, depth=0) {
  if (depth>8 || nodes.length>=1000) return;
  for (const e of root.querySelectorAll('*')) {
    if (nodes.length>=1000) break;
    if (e.closest('[data-jev-overlay]')) continue;
    if (e.matches(selector)) nodes.push(e);
    if (e.shadowRoot) collect(e.shadowRoot,depth+1);
  }
}
collect(document);
const elements = [];
for (const e of nodes) {
  if (elements.length >= 300) break;
  if (!visible(e)) continue;
  const d = describe(e);
  if (!d.enabled || d.sensitive) continue;
  const operations = [];
  if (d.clickable) operations.push('click');
  if (d.editable) operations.push('type_text');
  if (e.tagName === 'SELECT') operations.push('select');
  if (!operations.length) continue;
  elements.push({...d, operations, node: e,
    options: e.tagName === 'SELECT' ? Array.from(e.options).slice(0,40).map(o => ({label:o.text, value:o.value})) : []});
}
return {url:location.href, title:document.title.slice(0,160), ready:document.readyState,
        scroll:Math.round(scrollY), elements,
        text:document.body ? document.body.innerText.slice(0,1800) : ''};
