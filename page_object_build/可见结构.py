"""可见结构：把活页面转换成给 AI 使用的可见 DOM 与语义结构。
 
三个互补视角：
    页面结构    从 body 完整采集、保守删除、折叠空壳，再增强分区/字段/表格/富文本
    aria        Playwright 无障碍树，提供角色、无障碍名和选中态
    只读文本    经过 elementFromPoint 命中测试的扁平文字，适合查当前未被遮挡的文案
 
页面结构采用“剥洋葱”原则：默认保留，只有确定无用的节点才删除。语义规则
识别失败只会让树更普通、更深，不会导致原始可见内容消失。
"""
 
from __future__ import annotations
 
import contextlib
 
 
# ── 完整可见 DOM：保守删除 → 空壳折叠 → 语义增强 ──────────────────────────
_页面结构JS = r"""
(cfg) => {
  const 规范 = (s) => (s || '').replace(/\s+/g, ' ').trim();
  const 硬删除标签 = new Set([
    'script', 'style', 'template', 'noscript', 'meta', 'link', 'source',
    'path', 'use', 'g', 'defs', 'circle', 'rect', 'line', 'polygon', 'tspan'
  ]);
  const 结构标签 = new Set([
    'main','header','footer','nav','aside','article','section','form','fieldset','legend',
    'label','ul','ol','li','dl','dt','dd','table','thead','tbody','tfoot','tr','th','td',
    'h1','h2','h3','h4','h5','h6','dialog','button','input','textarea','select','option','a'
  ]);
  const 保留角色 = new Set([
    'main','navigation','banner','contentinfo','complementary','article','region','dialog',
    'alertdialog','heading','form','group','list','listitem','table','grid','treegrid','row',
    'rowgroup','columnheader','rowheader','cell','gridcell','button','link','tab','tabpanel',
    'textbox','combobox','checkbox','radio','switch','alert','status'
  ]);
  const 标题选择器 = 'h1,h2,h3,h4,h5,h6,[role="heading"],.head-title';
  const 截断文本 = (s) => {
    const t = 规范(s);
    return t.length > cfg.textCap ? t.slice(0, cfg.textCap) + '…' : t;
  };
  const 自身文本 = (el) => {
    let t = '';
    for (const n of el.childNodes) if (n.nodeType === Node.TEXT_NODE) t += n.nodeValue || '';
    return 截断文本(t);
  };
  const 类名 = (el) => typeof el.className === 'string'
    ? el.className.trim().split(/\s+/).filter(Boolean).slice(0, 6) : [];
  const 类串 = (el) => 类名(el).join(' ');
  const 是测量或技术副本 = (el) =>
    el.matches('.ant-table-measure-row,[aria-hidden="true"],input[type="hidden"]');
  const 硬不可见 = (el) => {
    if (el.hidden || el.getAttribute('aria-hidden') === 'true') return true;
    const cs = getComputedStyle(el);
    return cs.display === 'none' || cs.visibility === 'hidden' || cs.visibility === 'collapse';
  };
  const 视口信息 = (el) => {
    const rects = el.getClientRects();
    if (!rects.length) return {有矩形:false, 视口外:false, 矩形:null};
    const r = el.getBoundingClientRect();
    return {
      有矩形: r.width > 0 && r.height > 0,
      视口外: r.right < 0 || r.bottom < 0 || r.left > innerWidth || r.top > innerHeight,
      矩形: {x:Math.round(r.left), y:Math.round(r.top), w:Math.round(r.width), h:Math.round(r.height)}
    };
  };
  const 命中状态 = (el, 视口) => {
    if (!视口.有矩形 || 视口.视口外) return null;
    const r = el.getBoundingClientRect();
    const 点 = [
      [r.left+r.width/2,r.top+r.height/2], [r.left+r.width*.25,r.top+r.height*.5],
      [r.left+r.width*.75,r.top+r.height*.5], [r.left+r.width*.5,r.top+r.height*.25],
      [r.left+r.width*.5,r.top+r.height*.75]
    ];
    let 有视口内点 = false;
    for (const [x,y] of 点) {
      if (x < 0 || y < 0 || x > innerWidth || y > innerHeight) continue;
      有视口内点 = true;
      const hit = document.elementFromPoint(x,y);
      if (hit && (hit === el || el.contains(hit))) return false;
    }
    return 有视口内点 ? true : null;
  };
  const 属性 = (el) => {
    const out = {};
    for (const name of ['id','role','aria-label','aria-labelledby','aria-describedby','aria-expanded',
      'aria-selected','aria-checked','title','name','placeholder','type','href','for','contenteditable']) {
      const v = el.getAttribute(name);
      if (v !== null && v !== '') out[name] = 截断文本(v);
    }
    for (const name of ['disabled','readonly','required','checked','selected','multiple'])
      if (el.hasAttribute(name)) out[name] = true;
    const tag = el.tagName.toLowerCase();
    if (['input','textarea','select'].includes(tag) &&
        (el.getAttribute('type') || '').toLowerCase() !== 'password') {
      const v = el.value;
      if (v) out.value = 截断文本(v);
    }
    return out;
  };
  const 语义 = (el) => {
    const tag = el.tagName.toLowerCase();
    const role = el.getAttribute('role') || '';
    const cls = 类串(el);
    if (el.matches(标题选择器)) return '标题';
    if (tag === 'table' || role === 'table' || role === 'grid' || role === 'treegrid') return '表格';
    if (tag === 'th' || role === 'columnheader' || role === 'rowheader') return '表头';
    if (tag === 'tr' || role === 'row') return '表格行';
    if (tag === 'td' || role === 'cell' || role === 'gridcell') return '单元格';
    if (el.isContentEditable || /tiptap-editor-container|notion-like-editor|ProseMirror/.test(cls)) return '富文本';
    if (role === 'dialog' || tag === 'dialog') return '对话框';
    if (/\blabel\b/.test(cls) || tag === 'label') return '字段标签';
    if (tag === 'main' || role === 'main') return '主要区域';
    if (tag === 'nav' || role === 'navigation') return '导航区域';
    if (tag === 'form' || role === 'form') return '表单';
    return null;
  };
 
  let 已访问 = 0, 已保留 = 0, 硬删除 = 0, 空节点删除 = 0, 折叠数 = 0, 已截断 = false;
  const 构建 = (el, depth) => {
    if (!(el instanceof Element)) return null;
    已访问++;
    const tag = el.tagName.toLowerCase();
    if (硬删除标签.has(tag) || 是测量或技术副本(el) || 硬不可见(el)) { 硬删除++; return null; }
    if (depth > cfg.depthCap || 已保留 >= cfg.nodeCap) { 已截断 = true; return null; }
 
    const children = [];
    for (const child of el.children) {
      const node = 构建(child, depth + 1);
      if (node) children.push(node);
    }
    const text = 自身文本(el);
    const attrs = 属性(el);
    const semantic = 语义(el);
    const classes = 类名(el);
    const viewport = 视口信息(el);
    const 有信息 = !!text || children.length > 0 || semantic || Object.keys(attrs).length > 0;
    if (!有信息) { 空节点删除++; return null; }
 
    已保留++;
    const node = {标签:tag};
    if (semantic) node.语义 = semantic;
    if (classes.length) node.类名 = classes;
    if (Object.keys(attrs).length) node.属性 = attrs;
    if (text) node.文本 = text;
    if (viewport.视口外) node.视口外 = true;
    const covered = 命中状态(el, viewport);
    if (covered === true) node.被遮挡 = true; // 标记而不删除
    if (children.length) node.子节点 = children;
    return node;
  };
 
  const 是有意义包装 = (node) => {
    // 类名可能就是前端唯一的业务语义（如 operate-records-title、req-id）。
    // 宁可多保留一层，也不能为了压缩结构把这种身份折掉。
    if (node.语义 || node.文本 || node.属性 || (node.类名 && node.类名.length)) return true;
    if (结构标签.has(node.标签)) return true;
    return false;
  };
  const 折叠 = (node) => {
    if (node.子节点) node.子节点 = node.子节点.map(折叠).filter(Boolean);
    const kids = node.子节点 || [];
    if (!是有意义包装(node) && kids.length === 1 && ['div','span'].includes(node.标签)) {
      折叠数++;
      const child = kids[0];
      child.折叠包装层 = (child.折叠包装层 || 0) + 1;
      return child;
    }
    return node;
  };
  const 构建分区内容结构 = (el) => {
    // 分区需要与整页树相同精度的 DOM 结构，但重复构建不能污染整页统计。
    const 原统计 = {已访问,已保留,硬删除,空节点删除,折叠数,已截断};
    已访问 = 0; 已保留 = 0; 硬删除 = 0; 空节点删除 = 0; 折叠数 = 0; 已截断 = false;
    const node = 构建(el, 1);
    const result = node ? 折叠(node) : null;
    ({已访问,已保留,硬删除,空节点删除,折叠数,已截断} = 原统计);
    return result;
  };
 
  const 可见元素 = (el) => el instanceof Element && !硬不可见(el) && !是测量或技术副本(el);
  const 全文本 = (el) => 截断文本(el.innerText || el.textContent || '');
  const 标题文本 = (el) => {
    const precise = el.querySelector(':scope > .title-area > .title, :scope > .title');
    return 全文本(precise || el);
  };
  const 简述 = (el) => {
    const c = 类名(el);
    return el.tagName.toLowerCase() + (c.length ? '.' + c.join('.') : '');
  };
  const 字段组 = (roots) => {
    const result = [];
    const seen = new Set();
    for (const root of roots) {
      const candidates = root.matches('.ant-col,dt') ? [root] :
        Array.from(root.querySelectorAll('.ant-col, dt'));
      for (const item of candidates) {
        if (seen.has(item)) continue;
        let label = null, valueRoot = null;
        if (item.tagName.toLowerCase() === 'dt') {
          label = item; valueRoot = item.nextElementSibling?.matches('dd') ? item.nextElementSibling : null;
        } else {
          label = item.querySelector(':scope > .label, :scope label, :scope > [class*="label"]');
          if (label) valueRoot = Array.from(item.children).find(x => x !== label && 可见元素(x)) || null;
        }
        if (!label || !valueRoot) continue;
        const nameNode = label.querySelector('[title],.text') || label;
        const name = (nameNode.getAttribute?.('title') || 全文本(nameNode)).replace(/\s*:\s*$/, '');
        const value = 全文本(valueRoot);
        if (!name) continue;
        seen.add(item);
        result.push({名称:name, 值:value || '', 空值:!value || value === '-' || value === '--',
          容器:简述(item)});
      }
    }
    return result;
  };
  const 表格组 = (roots) => {
    const result = [];
    for (const root of roots) for (const table of (root.matches('table') ? [root] : root.querySelectorAll('table'))) {
      const columns = Array.from(table.querySelectorAll('thead th')).filter(可见元素).map(全文本);
      const rows = [];
      for (const tr of table.querySelectorAll('tbody tr:not([aria-hidden="true"]):not(.ant-table-measure-row)')) {
        if (!可见元素(tr)) continue;
        const cells = Array.from(tr.querySelectorAll(':scope > th,:scope > td')).map(全文本);
        const mapped = {};
        cells.forEach((v,i) => { mapped[columns[i] || `第${i+1}列`] = v; });
        rows.push(mapped);
      }
      result.push({列:columns, 行:rows, 行数:rows.length, 容器:简述(table)});
    }
    return result;
  };
  const 富文本组 = (roots) => {
    const found = [];
    const seen = new Set();
    for (const root of roots) {
      const candidates = [root, ...root.querySelectorAll('.tiptap-editor-container,.notion-like-editor-content,.ProseMirror,[contenteditable="true"]')];
      for (const el of candidates) {
        if (!可见元素(el) || seen.has(el)) continue;
        const cls = 类串(el);
        if (!(el.isContentEditable || /tiptap-editor-container|notion-like-editor-content|ProseMirror/.test(cls))) continue;
        // 只保留最外层编辑器区域，避免同一内容按三层容器重复输出。
        if (Array.from(seen).some(parent => parent.contains(el))) continue;
        seen.add(el);
        const text = 全文本(el);
        found.push({文本:text, 空内容:!text, 只读:el.getAttribute('contenteditable') === 'false' || el.classList.contains('is-readonly'),
          容器:简述(el)});
      }
    }
    return found;
  };
 
  const 文本项 = (root) => {
    const result = [], seen = new Set();
    for (const el of [root, ...root.querySelectorAll('*')]) {
      if (!可见元素(el)) continue;
      const text = 自身文本(el);
      if (!text || text === '|' || seen.has(text)) continue;
      seen.add(text);
      result.push(text);
    }
    return result;
  };
  const 独立结构内容 = (root, type) => {
    const result = {文本项:文本项(root)};
    if (type === '导航区' || type === '侧边栏' || type === '浮层') {
      const items = [];
      // 选项、菜单项、可点项：靠“可选/可点”的通用语义收集，不认具体业务类名。
      const candidates = root.querySelectorAll(
        '[role="option"],[role="menuitem"],[role="menuitemcheckbox"],[role="treeitem"],'+
        'li,.menu-item,a,button,.pointer,.back-btn');
      for (const el of candidates) {
        if (!可见元素(el)) continue;
        const text = 全文本(el);
        if (!text || items.some(x => x.文本 === text)) continue;
        items.push({文本:text, 当前:el.classList.contains('active') ||
          el.getAttribute('aria-current') !== null || el.getAttribute('aria-selected') === 'true'});
      }
      if (items.length) result.项目 = items;
    }
    if (type === '摘要卡片') {
      const fields = [];
      for (const item of root.querySelectorAll('.meta-item,dl > div')) {
        if (!可见元素(item)) continue;
        const label = item.querySelector('.meta-label,dt,[class*="label"]');
        const value = item.querySelector('.meta-value,dd,[class*="value"]');
        const name = label ? 全文本(label).replace(/[：:]\s*$/, '') : '';
        if (name && value) fields.push({名称:name, 值:全文本(value)});
      }
      const nameNode = root.querySelector('.title-row .title,[class*="title"]');
      if (nameNode && 全文本(nameNode)) result.名称 = 全文本(nameNode);
      if (fields.length) result.字段 = fields;
    }
    return result;
  };
 
  const sections = [];
  // 没有标题开头的固定结构也有业务意义。它们不参与“标题 + 后续兄弟”的
  // 推断，而是凭原生语义/ARIA/结构线索独立成区；没有内容则不输出。
  const 语义独立选择器 = 'header,nav,aside,dialog,[role="banner"],[role="navigation"],'+
    '[role="complementary"],[role="dialog"],[role="alertdialog"],[role="menu"],[role="listbox"],'+
    '[role="tooltip"],.top-nav,.summary-card,.operate-records-panel';
  const 语义候选 = Array.from(document.body.querySelectorAll(语义独立选择器))
    .filter(el => 可见元素(el) && !!全文本(el));
 
  // 浮层的通用识别（不认业务类名）：脱离正常文档流、绝对/固定定位、且“浮”在
  // 顶层的可见容器。下拉、气泡、菜单、提示这类 portal 到 body（或渲染到触发点
  // 旁边）的层都满足这个形态。判据用 offsetParent：
  //   position:fixed          → offsetParent 为 null，定位基准是视口
  //   portal 到 body 的绝对层  → offsetParent 就是 body / documentElement
  // 而挂在 position:relative 卡片里的绝对定位装饰，其 offsetParent 是那张卡片，
  // 不是 body，因此被排除。取最外层，避免把浮层内部再拆成碎片。
  const 是浮层 = (el) => {
    if (!可见元素(el) || !全文本(el)) return false;
    const cs = getComputedStyle(el);
    if (cs.position !== 'fixed' && cs.position !== 'absolute') return false;
    const r = el.getBoundingClientRect();
    if (r.width < 8 || r.height < 8) return false;
    // 父链（到 body 为止）里再有定位祖先，就交给那个更外层的容器。
    for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
      const pcs = getComputedStyle(p);
      if (pcs.position === 'fixed' || pcs.position === 'absolute') return false;
    }
    return cs.position === 'fixed'
      || el.offsetParent === document.body
      || el.offsetParent === document.documentElement
      || el.offsetParent === null;
  };
  const 浮层候选 = Array.from(document.body.querySelectorAll('*')).filter(是浮层);
 
  const 独立候选 = Array.from(new Set([...语义候选, ...浮层候选]));
  const 独立根 = 独立候选.filter(el =>
    !独立候选.some(other => other !== el && other.contains(el)));
  for (const root of 独立根) {
    const cls = 类串(root);
    const role = root.getAttribute('role') || '';
    const cs = getComputedStyle(root);
    const 是定位浮层 = cs.position === 'fixed' || cs.position === 'absolute';
    const 找标题 = (sel) => { const h = root.querySelector(sel); return h && 全文本(h) ? 全文本(h) : ''; };
    let type = '独立区域', title = root.getAttribute('aria-label') || '';
    if (root.matches('.operate-records-panel')) {
      type = '操作面板';
      title ||= 找标题('[class*="-title"],[role="heading"],h1,h2,h3,h4,h5,h6') || '操作面板';
    } else if (root.matches('dialog,[role="dialog"],[role="alertdialog"]')) {
      type = '弹层';
      title ||= 找标题('[class*="title"],[role="heading"],h1,h2,h3,h4,h5,h6') || '弹层';
    } else if (root.tagName.toLowerCase() === 'aside' || role === 'complementary' ||
        /(?:^|\s)(?:.*sider|.*sidebar)(?:\s|$)/i.test(cls)) {
      type = '侧边栏'; title ||= '侧边栏';
    } else if (/summary-card/.test(cls)) {
      type = '摘要卡片'; title ||= '摘要卡片';
    } else if (root.tagName.toLowerCase() === 'nav' || role === 'navigation' ||
               root.matches('header,[role="banner"],.top-nav')) {
      type = '导航区'; title ||= root.matches('.top-nav') ? '顶部导航' : '导航';
    } else if (role === 'menu' || role === 'listbox' || role === 'tooltip' || 是定位浮层) {
      // 通用浮层兜底：下拉、气泡、菜单、提示。标题优先取无障碍名/标题节点，
      // 再退回第一条可见文本，最后才用“浮层”。
      type = '浮层';
      title ||= 找标题('[role="heading"],h1,h2,h3,h4,h5,h6,[class*="title"]')
        || (文本项(root)[0] || '浮层');
    }
    const content = 独立结构内容(root, type);
    const contentStructure = 构建分区内容结构(root);
    sections.push({标题:title || type, 类型:type, 容器:简述(root), ...content,
      内容结构:contentStructure, _dom:root});
  }
 
  const headings = Array.from(document.body.querySelectorAll(标题选择器)).filter(可见元素);
  const parents = new Map();
  for (const h of headings) {
    const p = h.parentElement;
    if (!p) continue;
    if (!parents.has(p)) parents.set(p, []);
    parents.get(p).push(h);
  }
  for (const [parent, hs] of parents) {
    // 一个标题也保留；多个同胞标题时，DOM 顺序天然给出清晰分区边界。
    const direct = hs.filter(h => h.parentElement === parent);
    for (const heading of direct) {
      const roots = [];
      let n = heading.nextElementSibling;
      while (n && !direct.includes(n)) {
        if (可见元素(n) && !n.matches('.diviers,.divider,hr')) roots.push(n);
        n = n.nextElementSibling;
      }
      const title = 标题文本(heading);
      if (!title) continue;
      const fields = 字段组(roots), tables = 表格组(roots), editors = 富文本组(roots);
      let type = '普通内容';
      if (fields.length) type = '字段组';
      else if (tables.length) type = '表格';
      else if (editors.length) type = '富文本';
      const section = {标题:title, 类型:type, 标题节点:简述(heading),
        内容容器:roots.map(简述),
        内容结构:roots.map(构建分区内容结构).filter(Boolean), _dom:heading};
      if (fields.length) section.字段 = fields;
      if (editors.length) section.富文本 = editors;
      if (tables.length) section.表格 = tables;
      sections.push(section);
    }
  }
  sections.sort((a,b) => {
    if (a._dom === b._dom) return 0;
    return a._dom.compareDocumentPosition(b._dom) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1;
  });
  for (const section of sections) delete section._dom;
 
  const bodyChildren = [];
  if (document.body) for (const child of document.body.children) {
    const node = 构建(child, 1);
    if (node) bodyChildren.push(折叠(node));
  }
  return {
    去掉无意义元素之后的dom结构: bodyChildren,
    分区: sections,
    统计: {遍历节点:已访问, 保留节点:已保留, 硬删除, 空节点删除, 折叠包装层:折叠数,
      截断:已截断, 节点上限:cfg.nodeCap, 深度上限:cfg.depthCap}
  };
}
"""
 
 
# ── 只读文本：经过命中测试的扁平文案 ────────────────────────────────────
_只读文本JS = r"""
(cfg) => {
  const 跳过标签 = new Set(['script','style','template','br','hr','svg','path','use','g',
    'defs','circle','rect','line','polygon','tspan','text','input','textarea','select']);
  const 规范 = (s) => (s || '').replace(/\s+/g, ' ').trim();
  const 自身文本 = (el) => {
    let t = '';
    for (const n of el.childNodes) if (n.nodeType === 3) t += n.nodeValue;
    return 规范(t);
  };
  const 是自己或后代 = (命中, self) => !!命中 && (命中 === self || self.contains(命中));
  const 命中测试 = (el) => {
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) return {命中:false, 视口外:false};
    const 试点 = [
      [r.left+r.width/2,r.top+r.height/2], [r.left+r.width*.25,r.top+r.height*.5],
      [r.left+r.width*.75,r.top+r.height*.5], [r.left+r.width*.5,r.top+r.height*.25],
      [r.left+r.width*.5,r.top+r.height*.75],
    ];
    let 挡 = null, 视口外 = false;
    for (const [x,y] of 试点) {
      if (x < 0 || y < 0 || x > innerWidth || y > innerHeight) { 视口外 = true; continue; }
      const 命中 = document.elementFromPoint(x,y);
      if (是自己或后代(命中, el)) return {命中:true, 视口外:false};
      if (命中 && !挡) 挡 = 命中;
    }
    return {命中:false, 视口外:视口外 && !挡};
  };
  const 简述 = (el) => {
    const 类 = el.className && typeof el.className === 'string'
      ? '.' + el.className.trim().split(/\s+/).slice(0,3).join('.') : '';
    return el.tagName.toLowerCase() + 类;
  };
  const 出 = [];
  let 被挡 = 0, 视口外 = 0;
  for (const el of document.body.querySelectorAll('*')) {
    const tag = el.tagName.toLowerCase();
    if (跳过标签.has(tag) || !el.getClientRects().length) continue;
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.opacity === '0') continue;
    const t = 自身文本(el);
    if (!t) continue;
    const 命 = 命中测试(el);
    if (!命.命中 && !命.视口外) { 被挡++; continue; }
    if (命.视口外) 视口外++;
    const r = el.getBoundingClientRect();
    出.push({文本:t.slice(0,cfg.textCap), 位置:简述(el),
      role显式:el.getAttribute('role') || null, 视口外:!!命.视口外,
      矩形:{x:Math.round(r.left),y:Math.round(r.top),w:Math.round(r.width),h:Math.round(r.height)}});
    if (出.length >= cfg.cap) break;
  }
  return {文本节点:出, 被挡, 视口外, 整页节点数:document.body.querySelectorAll('*').length};
}
"""
 
 
_没有新增 = object()
_分区身份字段 = ("标题", "类型", "容器", "标题节点")
 
 
def _递归新增内容(之前, 之后):
    """返回“之后 - 之前”，不把相同内容重复塞给 AI。
    列表按完整元素做有序多重集差；字段值变化会作为新的完整字段返回。
    字典递归到最小变化键。``_没有新增`` 与合法的 None 值严格区分。
    """
    if isinstance(之前, dict) and isinstance(之后, dict):
        新增 = {}
        for 键, 新值 in 之后.items():
            if 键 not in 之前:
                新增[键] = 新值
                continue
            差 = _递归新增内容(之前[键], 新值)
            if 差 is not _没有新增:
                新增[键] = 差
        return 新增 if 新增 else _没有新增
    if isinstance(之前, list) and isinstance(之后, list):
        未匹配旧值 = list(之前)
        新增列表 = []
        for 新值 in 之后:
            try:
                位置 = 未匹配旧值.index(新值)
            except ValueError:
                新增列表.append(新值)
            else:
                未匹配旧值.pop(位置)
        return 新增列表 if 新增列表 else _没有新增
    return _没有新增 if 之前 == 之后 else 之后
 
 
def _分区身份(分区: dict) -> tuple:
    return tuple(分区.get(字段) for 字段 in _分区身份字段)
 
 
def _节点身份(节点: dict) -> tuple:
    """跨快照匹配同一个 DOM 节点的弱身份：标签 + 类名 + 关键定位属性。"""
    属性 = 节点.get("属性") or {}
    return (节点.get("标签"), tuple(节点.get("类名") or []),
            属性.get("id"), 属性.get("role"), 属性.get("title"),
            属性.get("placeholder"), 属性.get("href"), 属性.get("aria-label"))
 
 
def _树差(之前树: list, 之后树: list) -> list:
    """节点级递归差：按弱身份匹配，匹配上就下钻，只留新增/变化的分支。
    全新节点（portal 浮层、下拉等）整棵子树保留；已有节点只是某个后代变了，
    就只回那条变化链，不会把整个 app 根节点倾倒出来。
    """
    未匹配 = list(之前树)
    结果: list = []
    for 新节点 in 之后树:
        位置 = next((i for i, 旧 in enumerate(未匹配)
                   if _节点身份(旧) == _节点身份(新节点)), None)
        if 位置 is None:
            结果.append(新节点)          # 全新节点：整棵子树都是新增
            continue
        旧节点 = 未匹配.pop(位置)
        子差 = _树差(旧节点.get("子节点") or [], 新节点.get("子节点") or [])
        自身变化 = {键: 新节点[键] for 键 in ("文本", "属性", "语义", "视口外", "被遮挡")
                 if 键 in 新节点 and 新节点.get(键) != 旧节点.get(键)}
        if not 子差 and not 自身变化:
            continue
        片段 = {"标签": 新节点.get("标签")}
        if 新节点.get("类名"):
            片段["类名"] = 新节点["类名"]
        片段.update(自身变化)
        if 子差:
            片段["子节点"] = 子差
        结果.append(片段)
    return 结果
 
 
def 计算操作之后的页面结构(操作前页面结构: dict | None,
                  操作后页面结构: dict | None, 最后操作: dict | None) -> dict:
    """比较最后一步操作前后，返回与 ``页面结构`` 同构的差集。
 
    三个子键与 ``页面结构`` 一致：
        去掉无意义元素之后的dom结构  新出现或变化的 DOM 子树（节点级递归差）
        分区                        新出现的分区，或已有分区里新增/变化的内容
        统计                        本次差集的元信息与计数
    """
    最后操作 = 最后操作 or {}
    统计: dict = {
        "比较范围": "最后一个操作执行前 → 最后一个操作执行后",
        "最后操作": 最后操作.get("做了什么"),
    }
    # 把最后一步动作本身的效果带上：空差集时靠它一眼看出是“没点开”还是“真没变”。
    if 最后操作.get("错误"):
        统计["最后操作报错"] = 最后操作["错误"]
    if "有变化" in 最后操作:
        统计["最后操作有变化"] = 最后操作["有变化"]
    if 最后操作.get("新增弹层"):
        统计["最后操作新增弹层"] = 最后操作["新增弹层"]
    if 最后操作.get("新增签名"):
        统计["最后操作新增签名"] = 最后操作["新增签名"]
    结果: dict = {"去掉无意义元素之后的dom结构": [], "分区": [], "统计": 统计}
    if not 操作前页面结构 or not 操作后页面结构:
        统计["说明"] = "操作前或操作后的页面结构采集失败，无法计算差集"
        return 结果
 
    # 1) 整棵可见树的差集
    树差 = _树差(
        操作前页面结构.get("去掉无意义元素之后的dom结构") or [],
        操作后页面结构.get("去掉无意义元素之后的dom结构") or [])
    结果["去掉无意义元素之后的dom结构"] = 树差
 
    # 2) 分区的差集：新分区整块保留，已有分区只回新增/变化的内容
    之前分区 = 操作前页面结构.get("分区") or []
    之后分区 = 操作后页面结构.get("分区") or []
    已使用旧分区: set[int] = set()
    for 新分区 in 之后分区:
        匹配位置 = next((i for i, 旧分区 in enumerate(之前分区)
                       if i not in 已使用旧分区 and _分区身份(旧分区) == _分区身份(新分区)), None)
        if 匹配位置 is None:
            结果["分区"].append(新分区)
            continue
        已使用旧分区.add(匹配位置)
        差 = _递归新增内容(之前分区[匹配位置], 新分区)
        if 差 is _没有新增:
            continue
        # 标题/类型/容器是差集的归属上下文，不代表它们本身刚刚出现。
        带归属的差 = {字段: 新分区[字段] for 字段 in _分区身份字段 if 字段 in 新分区}
        带归属的差.update(差)
        结果["分区"].append(带归属的差)
 
    统计["新增或变化根节点数"] = len(树差)
    统计["新增或变化分区数"] = len(结果["分区"])
    # 空差集时给出可执行的排查方向，而不是让 AI 面对一个沉默的空对象。
    if not 树差 and not 结果["分区"]:
        if 统计.get("最后操作报错"):
            统计["说明"] = ("最后一步动作报错，页面没变化——多半是选择器没匹配到、"
                        "或命中的是禁用/不可点元素。先修选择器再看差集")
        elif 统计.get("最后操作有变化") is False:
            统计["说明"] = ("最后一步动作没有引起页面变化：可能点到了禁用元素，或选择器 "
                        "nth(0) 落在了同名的另一个元素上（如基本信息里禁用的同名下拉）。"
                        "用 浏览器会话 --做 看这一步的 新增弹层/新增签名 确认")
        else:
            统计["说明"] = ("最后一步前后页面结构无差异。若确信应有新内容，检查最后一步"
                        "选择器是否命中预期元素，或适当加大动作后的等待")
    return 结果
 
 
def 取可见结构(page, 要aria: bool = True, 要只读文本: bool = True,
         文本含: str | None = None, 文本上限: int = 120,
         条数上限: int = 400, 要页面结构: bool = True,
         分区: str | None = None, 结构节点上限: int = 2000) -> dict:
    """一次取得页面结构、aria 和未被遮挡的只读文本。
 
    ``page`` 必须是活着的 Playwright Page。``分区`` 按分区标题包含匹配，
    只过滤 ``页面结构.分区``，不会破坏完整的 ``页面结构.去掉无意义元素之后的dom结构``。调用方若只想
    要结构，可把 ``要aria``、``要只读文本`` 都设为 False。
    """
    出: dict = {}
    说明: list[str] = []
 
    if 要页面结构:
        try:
            页面结构 = page.evaluate(_页面结构JS, {
                "textCap": 文本上限, "nodeCap": 结构节点上限, "depthCap": 40,
            })
            if 分区:
                所有分区 = 页面结构.get("分区") or []
                页面结构["分区"] = [x for x in 所有分区
                              if 分区.lower() in str(x.get("标题", "")).lower()]
                页面结构["分区筛选"] = 分区
                页面结构["筛选前分区数"] = len(所有分区)
                if not 页面结构["分区"]:
                    说明.append(f"没有找到标题包含 {分区!r} 的页面分区；完整 DOM 树仍保留")
            出["页面结构"] = 页面结构
            统计 = 页面结构.get("统计") or {}
            if 统计.get("截断"):
                说明.append(f"⚠ 页面结构撞到节点上限={结构节点上限} 或深度上限，树已明确标记截断")
        except Exception as exc:
            出["页面结构"] = None
            说明.append(f"页面结构扫描失败：{type(exc).__name__}: {exc}"[:200])
 
    if 要aria:
        try:
            aria = page.locator("body").aria_snapshot()
            出["aria"] = aria
            出["aria行数"] = len([line for line in aria.splitlines() if line.strip()])
        except Exception as exc:
            出["aria"] = None
            说明.append(f"aria_snapshot 取不到（{type(exc).__name__}），可能需要 Playwright 1.49+")
 
    if 要只读文本:
        try:
            result = page.evaluate(_只读文本JS, {"textCap":文本上限,"cap":条数上限})
        except Exception as exc:
            result = {}
            说明.append(f"只读文本扫描失败：{type(exc).__name__}: {exc}"[:160])
        节点 = result.get("文本节点") or []
        if 文本含:
            节点 = [x for x in 节点 if 文本含.lower() in str(x.get("文本", "")).lower()]
        出["只读文本"] = 节点
        出["只读文本条数"] = len(节点)
        出["被遮挡丢弃"] = result.get("被挡")
        出["视口外"] = result.get("视口外")
        出["整页节点数"] = result.get("整页节点数")
        if result.get("被挡"):
            说明.append(f"{result['被挡']} 个有文字的节点被其他元素盖住，已从只读文本剔除；页面结构只标记、不删除")
        if len(节点) >= 条数上限:
            说明.append(f"⚠ 只读文本撞到 条数上限={条数上限}，可用 --文本含 缩小范围")
 
    if 要aria and 出.get("aria"):
        with contextlib.suppress(Exception):
            角色: dict[str, int] = {}
            for 行 in 出["aria"].splitlines():
                s = 行.strip().lstrip("- ")
                if not s:
                    continue
                role = s.split(" ", 1)[0].split(":")[0]
                角色[role] = 角色.get(role, 0) + 1
            出["aria角色分布"] = dict(sorted(角色.items(), key=lambda kv: -kv[1])[:12])
            if 角色.get("columnheader"):
                说明.append(f"aria 里有 {角色['columnheader']} 个 columnheader、"
                          f"{角色.get('cell',0)} 个 cell、{角色.get('row',0)} 个 row")
            说明.append("页面结构保留 DOM 层级并增强字段/表格；aria 仍是角色和选中态的独立事实来源")
 
    出["说明"] = 说明
    return 出
 
 
# ── 命令行入口 ────────────────────────────────────────────────────────────
def _main() -> int:
    import argparse
 
    from .浏览器会话 import 加公共参数, 打开并按需做, 输出
 
    ap = argparse.ArgumentParser(
        prog="python -m tools.page_object_build.可见结构",
        description="完整采集可见 DOM，保守裁剪并输出分区、字段、富文本、表格；同时可带 aria 与只读文本。")
    加公共参数(ap)
    ap.add_argument("--无aria", action="store_true", help="不要 aria 树")
    ap.add_argument("--无只读文本", action="store_true", help="不要命中测试后的扁平文本")
    ap.add_argument("--只要页面结构", action="store_true",
                    help="只输出剥洋葱后的页面结构，不采 aria 和扁平只读文本")
    ap.add_argument("--分区", metavar="标题",
                    help="页面结构的分区只返回标题包含该文字的项；完整 DOM 树仍保留")
    ap.add_argument("--文本含", metavar="字串",
                    help="只过滤扁平只读文本，不裁剪页面结构")
    ap.add_argument("--条数上限", type=int, default=400)
    ap.add_argument("--结构节点上限", type=int, default=2000,
                    help="完整 DOM 树最多保留的节点数，默认 2000；撞限会明确标记截断")
    args = ap.parse_args()
 
    最后操作前: dict = {"页面结构": None}
    def 采集最后操作前页面结构(page) -> None:
        观察 = 取可见结构(
            page, 要aria=False, 要只读文本=False, 要页面结构=True,
            分区=args.分区, 结构节点上限=args.结构节点上限,
        )
        最后操作前["页面结构"] = 观察.get("页面结构")
 
    s, 自检, 做了 = 打开并按需做(
        args, 最后操作前回调=采集最后操作前页面结构 if args.做 else None)
    try:
        可见结构结果 = 取可见结构(
            s.page,
            要aria=not args.无aria and not args.只要页面结构,
            要只读文本=not args.无只读文本 and not args.只要页面结构,
            文本含=args.文本含,
            条数上限=args.条数上限,
            要页面结构=True,
            分区=args.分区,
            结构节点上限=args.结构节点上限,
        )
        if args.做 and 可见结构结果.get("页面结构") is not None:
            可见结构结果["页面结构"]["操作之后的页面结构"] = 计算操作之后的页面结构(
                最后操作前["页面结构"], 可见结构结果["页面结构"],
                做了[-1] if 做了 else None)
        结果 = {"打开":自检, **({"做了":做了} if 做了 else {}),
              "可见结构":可见结构结果}
    finally:
        s.关闭()
    输出(结果, args)
    if 自检["是白屏"]:
        print("！白屏，页面没打开成", flush=True)
        return 2
    return 0
 
 
if __name__ == "__main__":
    raise SystemExit(_main())