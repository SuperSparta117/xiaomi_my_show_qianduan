"""可点元素：给 AI 用的工具层第 2/3 层 —— 我能点什么、怎么点。
 
回答的问题与 可见结构.py 互补，几乎不重叠：
    本文件      定位器 + 实测匹配数 + 有没有被别的元素盖住
    可见结构.py  语义角色 + 无障碍名 + 只读文本 + 列头 + 选中态
 
为什么两件事要分开：aria 树给不了定位器（它没有选择器），
而元素采集给不了语义（只能从类名猜）。合成一个函数只会让两边都变模糊。
 
本目录完全独立于 stageA_page_object_build，见 浏览器会话.py 的模块头。
"""
 
from __future__ import annotations
 
from .浏览器会话 import 元素采集JS, 分身体检JS, 采集参数
 
# ── 候选策略的分档。判据来自实测，不是偏好 ────────────────────────────────
#
# 能拿去 page.locator() 执行的策略。**role+文字 不在里面**：
# 它存的是 `get_by_role("button", name="x")`，那是一段 API 调用的写法，
# 不是选择器字符串，locator() 吃不进去。要用它得走 page.get_by_role(...)，
# 所以单独列一档交给 AI 自己决定。
可执行策略 = {
    "业务ID属性", "业务ID属性存在", "行标识属性", "id", "placeholder", "name属性",
    "role属性+类名", "标签+类名", "类名", "容器+子类名", "作用域+类名",
    "外层容器+类名", "弹层容器+类名", "弹层容器+标签", "作用域+文本",
    # 结构位置（nth-child）刻意**不在**这一档：它匹配数常常是 1，
    # 但前端插一个元素序号就全错。它只在 备选 里出现，并且带 不稳定 标记。
}
# 这些策略天生只匹配一个、而且跨轮稳定，优先给 AI 用。
首选策略顺序 = ("id", "业务ID属性", "placeholder", "name属性", "行标识属性",
          "弹层容器+类名", "容器+子类名", "作用域+类名", "外层容器+类名",
          "标签+类名", "类名", "作用域+文本")
 
 
def _文本收窄(page, 元素: dict, 候选们: list[dict]) -> tuple[str | None, dict | None]:
    """同胞元素只有文本不同时，用文本把匹配多个的候选收窄成唯一。
    治的是这一类（实测最常见）：弹窗页脚的「确定」「取消」都是
    `div.custom-modal-footer > button.u-button`、匹配 2、父链完全相同，
    只有文本不同。它们以前 定位 是 null，调用方得自己想到用文本收窄。
 
    ⚠ 用 `:has-text()` 而不是 `:text-is()`，这是踩出来的
    ──────────────────────────────────────────
    `:text-is()` 匹配「包含该文本的**最小**元素」。而按钮的文字在嵌套 `<span>` 里，
    所以 `button.u-button:text-is("确定")` 匹配到的是那个 span、不是 button ——
    对 button 加这个伪类的结果是**匹配 0 个**，白等 8 秒超时。
    `:has-text()` 匹配祖先，能命中 button 本身。
 
    ⚠ 必须**现场数一遍**才敢用
    ────────────────────
    has-text 是子串匹配：兄弟俩若是「确定」与「确定并关闭」，
    `has-text("确定")` 会同时命中两个。所以这里不猜，直接问浏览器
    `locator(表达).count()`，等于 1 才采纳。一次 count 是毫秒级。
 
    只试前 3 档候选、只对文本不超过 30 字的元素试 —— 长文本大概率是数据不是标签。
    """
    名 = (元素.get("可见文本") or "").strip()
    if not 名 or len(名) > 30 or '"' in 名:
        return None, None
    for c in 候选们[:3]:
        if (c.get("匹配") or 0) <= 1 or c.get("不稳定"):
            continue
        表达 = f'{c["表达"]}:has-text("{名}")'
        try:
            if page.locator(表达).count() != 1:
                continue
        except Exception:
            continue
        return 表达, {"策略": f"{c.get('策略')}+含文本", "表达": 表达, "匹配": 1,
                    "文本收窄自": c["表达"], "收窄前匹配": c.get("匹配")}
    return None, None
 
 
def _挑定位(元素: dict) -> tuple[str | None, dict | None, list[dict]]:
    """挑一个能唯一命中、且 locator() 直接吃得进去的候选。
 
    返回 (定位表达式, 命中的那档候选, 其余可参考的候选)。挑不出来时第一项是 None。
 
    三轮，越往后越不可靠：
      1. 总匹配 == 1 且不带 不稳定 标记 —— 只有这一档可以直接用，nth 无歧义
      2. 可见匹配 == 1 —— **必须再定 nth**，见 定分身()。
         「可见的只有 1 个」不等于「可见的那个排在第 0 位」：
         vxe 固定列把同一行渲染两份，藏起来的那份常常排在前面。
      3. 一个都没有 —— 返回 None，并把 备选 交给 AI 判断（见 SKILL.md 的
         「定位=null 怎么办」）
    """
    候选 = [c for c in (元素.get("候选") or [])
          if isinstance(c, dict) and c.get("策略") in 可执行策略]
    序 = {名: i for i, 名 in enumerate(首选策略顺序)}
    候选.sort(key=lambda c: 序.get(str(c.get("策略")), 99))
 
    for c in 候选:
        if c.get("匹配") == 1 and not c.get("不稳定"):
            return c["表达"], c, []
    for c in 候选:
        if c.get("可见匹配") == 1 and (c.get("匹配") or 0) > 1:
            return c["表达"], c, [x for x in 候选 if x is not c][:4]
    return None, None, 候选[:5]
 
 
def 取可点元素(page, 只要有定位: bool = False, 文本含: str | None = None,
         在浮层内: str | None = None) -> dict:
    """采一次当前页面上**人类能看见、并且看起来能交互**的元素。
 
    入参
        page        活着的 Playwright Page（用 浏览器会话.会话 拿）
        只要有定位   True 只回能直接点的那批（定位 非空），少一半 token
        文本含       只回可见文本包含这段字的（不区分大小写）
        在浮层内     只回落在这个浮层容器里的（弹窗打开时用它把背景排除干净）
 
    返回
        {
          "个数": 36, "整页节点数": 3495,
          "元素": [{"序": 0, "名": "创建基线", "tag": "button", "role": "button",
                   "定位": "button.css-1p3hq3p.create-btn", "定位策略": "标签+类名",
                   "匹配": 1, "取第几个": 0,
                   "可点理由": ["交互标签"], "在浮层": null,
                   "禁用": false, "视口外": false,
                   "备选": [...]}],
          "台账": {...},   # 这一次采集丢掉了什么、为什么（见下）
          "说明": [...],   # 人读的提示，比如「有 9 个元素没有唯一定位」
        }
 
    ── 关于「人类能看见」这条判据（实测，别改成只看 CSS）────────────────
    CSS 可见（有布局盒 + 非 hidden + 非 opacity:0）**判不出被别的元素盖住**。
    实测这一页：整页 3495 节点 → CSS 可见 281 → elementFromPoint 命中自己 166，
    其中 33 个是「CSS 说可见、其实被盖住」。弹窗打开时更明显：
    37 个背景元素全部被遮罩挡着，它们以前会混进元素表，
    下游拿去点就是超时；而弹窗内外有同名控件时（实测「文件夹/需求文档名称」
    输入框目录树里一个、弹窗里一个）会**静默点错**。
    所以采集侧就用 elementFromPoint 把它们剔掉，台账里记 被挡跳过。
 
    视口外的元素**不剔除**，只标 视口外=true —— 它和「被挡」性质不同：
    被挡是滚动也没用，视口外是滚一下就能看到。Playwright 的 click 会自动滚。
 
    ── 三个已知的信息缺口（DOM 里本来就没有，换 API 也变不出来）─────────
    1. 定位=null：同构列表成员（日期格子、项目列表项）无 id、无 data-*、
       类名相同、父链相同、文本还跨面板重复。实测这一页 9/31 是这种。
    2. 名=null：图标按钮没有文本，aria 树里也只是裸 img。实测 8/36。
    3. 表格整列的值取不到（aria 只给列头）。要整列用 浏览器会话.会话.读() 的
       全部文本，自己按列选择器取。
    """
    结果 = page.evaluate(元素采集JS, 采集参数)
    元素们 = 结果.get("elements") or []
    meta = 结果.get("meta") or {}
 
    出: list[dict] = []
    没定位 = 0
    靠文本收窄 = 0
    for e in 元素们:
        名 = (e.get("可见文本") or "").strip() or None
        浮层 = e.get("弹层容器")
        if 文本含 and 文本含.lower() not in (名 or "").lower():
            continue
        if 在浮层内 and not (浮层 and (在浮层内 in str(浮层) or str(浮层) in 在浮层内)):
            continue
        定位, 档, 备选 = _挑定位(e)
        if 定位 is None:
            # 类名系候选全不唯一时，再试一次「用文本收窄」。判据现场数，不猜。
            定位, 档 = _文本收窄(page, e, 备选)
            if 定位 is not None:
                靠文本收窄 += 1
        if 定位 is None:
            没定位 += 1
            if 只要有定位:
                continue
        条 = {
            "序": len(出),
            "名": 名[:40] if 名 else None,
            "tag": e.get("tag"),
            "role": e.get("role显式") or e.get("role"),
            "定位": 定位,
            "定位策略": (档 or {}).get("策略"),
            "匹配": (档 or {}).get("匹配"),
            # 匹配>1 时必须先定 nth，否则 .first 可能是点不动的那份分身。
            "取第几个": 0 if (档 or {}).get("匹配") == 1 else None,
            "可点理由": e.get("命中规则") or [],
        }
        if 浮层:
            条["在浮层"] = str(浮层)
        if e.get("真disabled") or e.get("伪禁用"):
            条["禁用"] = True
        if e.get("视口外"):
            条["视口外"] = True
        if 备选:
            条["备选"] = [{"策略": c.get("策略"), "表达": c.get("表达"),
                        "匹配": c.get("匹配"), "可见匹配": c.get("可见匹配"),
                        **({"不稳定": True} if c.get("不稳定") else {})}
                       for c in 备选]
        if e.get("语义类名"):
            条["语义类名"] = e["语义类名"][:4]
        出.append(条)
 
    账 = {k: v for k, v in (meta.get("丢弃台账") or {}).items() if v}
    说明: list[str] = []
    if 靠文本收窄:
        说明.append(
            f"{靠文本收窄} 个元素的类名系候选都不唯一，是靠**文本**收窄成唯一的"
            "（定位策略 带 +含文本 后缀，比如弹窗页脚的确定/取消）。"
            "这些定位都现场数过 count()==1，可以直接用")
    if 没定位:
        说明.append(
            f"{没定位} 个元素连文本也收窄不了（同构列表成员：日期格子、列表项 —— "
            "父链相同、类名相同、文本还跨面板重复）。"
            "它们的 定位 是 null、备选 里是匹配多个的候选 —— "
            "不要瞎猜 nth，用行标识属性收窄或先用 定分身() 现场定，"
            "定不出来就如实说「这个元素当前不可稳定定位」")
    if 账.get("被挡跳过"):
        说明.append(
            f"{账['被挡跳过']} 个元素被别的元素盖住（遮罩/固定列/透明覆盖层），"
            "已剔除 —— 它们人类点不到，不是漏采")
    if 账.get("视口外留下"):
        说明.append(
            f"{账['视口外留下']} 个元素在视口外，**保留**并标了 视口外=true："
            "滚一下就看得见，click 会自动滚")
    if (meta.get("截断") or {}).get("元素"):
        说明.append("⚠ 元素采集被截断（撞到 elementCap），这一页可能漏采")
 
    return {"个数": len(出), "整页节点数": meta.get("元素总数"),
            "有定位": sum(1 for x in 出 if x["定位"]),
            "靠文本收窄": 靠文本收窄, "没定位": 没定位,
            "元素": 出, "台账": 账, "说明": 说明}
 
 
def 定分身(page, 定位: str) -> dict:
    """一个选择器匹配多个节点时，定出**该点第几个**。零副作用，毫秒级。
    什么时候用：`取可点元素` 给的 匹配 > 1、或者 取第几个 是 None。
    返回 {匹配, 分身:[{序号, 可见, 可点, 判据, 矩形}], 取第几个, 说明}。
    `取第几个` 是第一个可点的序号；一个都点不到时是 None，
    此时 说明 里写清每一份为什么点不到（挡路者的选择器也在里面）。
 
    为什么用 elementFromPoint 而不是「真点一遍试试」：
      · 点到点不动的那份 → 8 秒超时，白等
      · 点到能点的那份 → **页面就跳走了**，而这一步只是想「体检」，
        副作用应该由 做() 统一承担
    elementFromPoint 回答的正是 Playwright 点击前那道 actionability 检查所问的
    问题：「这个坐标上最上层的节点是不是它（或它的后代）」。
 
    异形元素（图标字体、被圆角裁掉的单元格）中心点可能落在空隙里，
    所以试了中心 + 四个内缩 25% 的点，任一命中就算点得到。
    """
    try:
        r = page.evaluate(分身体检JS, {"selector": 定位}) or {}
    except Exception as exc:
        return {"匹配": None, "分身": [], "取第几个": None,
                "说明": f"体检失败：{type(exc).__name__}: {exc}"[:160]}
    分身 = r.get("分身") or []
    可点的 = [d for d in 分身 if d.get("可点")]
    if 可点的:
        k = 可点的[0]["序号"]
        return {**r, "取第几个": k,
                "说明": (f"{r.get('匹配')} 份分身里第 {k} 份点得到"
                       + (f"（另有 {len(可点的) - 1} 份也点得到，取序号最小的）"
                          if len(可点的) > 1 else "")
                       + "；" + str(可点的[0].get("判据")))}
    return {**r, "取第几个": None,
            "说明": f"{r.get('匹配')} 份分身一个都点不到："
                    + "；".join(f"[{d.get('序号')}] {d.get('判据')}" for d in 分身[:4])}
 
 
# ── 命令行入口 ────────────────────────────────────────────────────────────
def _main() -> int:
    import argparse
 
    from .浏览器会话 import 加公共参数, 打开并按需做, 输出
 
    ap = argparse.ArgumentParser(
        prog="python -m tools.page_object_build.可点元素",
        description="看当前页面上我能点什么、怎么点（带定位器，已排除被遮挡的）。")
    加公共参数(ap)
    ap.add_argument("--只要有定位", action="store_true",
                    help="只回能直接点的那批。省一半 token —— 没有定位的元素"
                         "带着 备选 列表，是最占地方的一块")
    ap.add_argument("--文本含", metavar="字串", help="只回可见文本包含这段字的")
    ap.add_argument("--在浮层内", metavar="容器选择器",
                    help="只回落在这个浮层里的。弹窗打开后用它，"
                         "比如 --在浮层内 .ant-modal-wrap.create-baseline-modal")
    ap.add_argument("--定分身", metavar="定位",
                    help="单独给一个匹配多个的选择器做体检，定出该点第几个")
    args = ap.parse_args()
 
    s, 自检, 做了 = 打开并按需做(args)
    try:
        结果 = {"打开": 自检, **({"做了": 做了} if 做了 else {}),
              "可点元素": 取可点元素(s.page, 只要有定位=args.只要有定位,
                              文本含=args.文本含, 在浮层内=args.在浮层内)}
        if args.定分身:
            结果["定分身"] = 定分身(s.page, args.定分身)
    finally:
        s.关闭()
    输出(结果, args)
    if 自检["是白屏"]:
        print("！白屏，页面没打开成", flush=True)
        return 2
    if not 结果["可点元素"]["个数"]:
        print("！一个可点元素都没采到 —— 大概率是页面没等稳或落错页了，核对 打开.url",
              flush=True)
        return 1
    return 0
 
 
if __name__ == "__main__":
    raise SystemExit(_main())