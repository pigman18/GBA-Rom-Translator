// Node 实跑验证：抽出 HTML 里的 <script>，在最小 DOM 垫片上跑一遍
const fs = require('fs');
const path = 'C:/code/GBA-Rom-Translator/docs/b2_render_sim.html';
const html = fs.readFileSync(path, 'utf8');
const m = html.match(/<script>([\s\S]*?)<\/script>/);
if (!m) { console.log('NO SCRIPT'); process.exit(1); }
const code = m[1];

// --- 最小 DOM 垫片 ---
const created = [];
function makeEl(tag) {
  const el = {
    tagName: tag, children: [], _text: '', className: '', style: { cssText: '' },
    width: 0, height: 0,
    appendChild(c) { this.children.push(c); return c; },
    set textContent(v) { this._text = v; },
    get textContent() { return this._text; },
    set innerHTML(v) { this._html = v; },
    get innerHTML() { return this._html; },
    getContext() {
      const rec = { fills: 0, strokes: 0, texts: [] };
      return {
        _rec: rec,
        set fillStyle(v) { this._f = v; }, get fillStyle() { return this._f; },
        set strokeStyle(v) { this._s = v; }, get strokeStyle() { return this._s; },
        set lineWidth(v) { this._w = v; }, get lineWidth() { return this._w; },
        fillRect() { rec.fills++; },
        strokeRect() {},
        beginPath() {}, moveTo() {}, lineTo() {}, stroke() { rec.strokes++; },
        clearRect() {}, save() {}, restore() {}, fillText(t) { rec.texts.push(t); },
      };
    },
  };
  return el;
}
const registry = {};
global.document = {
  createElement: (t) => { const e = makeEl(t); created.push(e); return e; },
  getElementById: (id) => (registry[id] = registry[id] || makeEl('div')),
  addEventListener: () => {},
};
global.window = { addEventListener: () => {} };
global.console = console;

try {
  eval(code);
  console.log('\n=== 实跑成功 ===');
  console.log('canvas 创建数 =', created.filter(e => e.tagName === 'canvas').length);
  ['rows', 'rowsB'].forEach(id => {
    const el = registry[id];
    console.log(`#${id} 子节点数 =`, el ? el.children.length : 'MISSING');
  });
} catch (e) {
  console.log('RUNTIME ERROR:', e.message);
  console.log(e.stack.split('\n').slice(0, 6).join('\n'));
  process.exit(1);
}
