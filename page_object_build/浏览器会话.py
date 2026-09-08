"""浏览器会话：给 AI 用的工具层第 1/3 层 —— 把浏览器开起来、停在一个可观测的状态上。

登录、配置、影子库预热全部收在**同目录**的 登录.py 里，本目录对仓库零依赖：
    登录.py   账号/域名/online 开关、CAS 登录、cookie 注入、影子库预热
              （current_config / cookies_manager / prepare_and_wait / login）

三个文件的分工
────────────
    浏览器会话.py   打开页面、等到可观测、执行动作、读取文本   ← 本文件
    可点元素.py     我能点什么、怎么点（定位器 + 未被遮挡）
    可见结构.py     这页有什么、是什么（语义角色 + 只读文本）
用法与坑见同目录 SKILL.md。
"""

from __future__ import annotations

import contextlib
from typing import Any

# 本目录自包含，不再把仓库根塞进 sys.path。_这里 仍用于定位同目录的会话缓存文件。
_这里 = __import__("os").path.dirname(__import__("os").path.abspath(__file__))


# ── 等待与稳定的参数。改这些之前先读 打开并等到首屏稳定 的注释 ──────────────
#
# 首屏下限 10 秒不是保守，是**必须**。实测踩过两次：这个站是 SPA，
# goto 之后会先渲染首页、再路由到目标页，而首页本身是「稳定」的
# （签名 34 条、连续几张一致）。只判稳定就会早退到首页，
# 然后你拿着首页的 4 个元素以为那是目标页 —— 不报错，纯静默。
首屏最少等待ms = 10000
# 上限放宽到 45s：加了「不忙碌」这一条判据之后，慢接口的页面要在这个预算里
# 等 spinner 转完。只有真的还在转/还在变时才会用到这么久，正常页仍是 10~12s 退出。
首屏最长等待ms = 45000
首屏轮询间隔ms = 500
首屏连续一致快照数 = 3
# 白屏判据：稳定 ≠ 正常。白屏的签名恒定 2 条、完美「稳定」。
# 实测正常页面 147~231 条，所以 20 是个很宽松的下限。
页面健康最少签名数 = 20
白屏重载重试次数 = 2
单动作等待ms = 1200

# 「数据加载中」遮罩。采集前必须等它消失，否则采到的是骨架屏。
#
# ⚠ 这里踩过一次，产物为证：原来第一条写的是
#       div.ant-spin-spinning[aria-busy="true"]
#   而这个站的 spinner 实际长这样（ddd.json 里三处一模一样）：
#       div.css-1p3hq3p.ant-spin.ant-spin-spinning.ant-spin-show-text
#         └ div.ant-spin-text 「加载中...」
#   **没有 aria-busy 属性**。于是三条选择器（另两条是 .ant-skeleton 和
#   [aria-busy="true"]）一条都不命中，等待逻辑静默空转，
#   「基本信息」分区采回来的内容结构只有一个「加载中...」。
#   所以判据只用 antd 自己的状态类名 .ant-spin-spinning，不要求任何属性。
忙碌选择器 = (
    ".ant-spin-spinning",      # antd 「正在转」的状态类名，唯一可靠的那条
    ".ant-spin-blur",          # 被 Spin 包住、正在变灰的内容区
    ".ant-skeleton",
    '[aria-busy="true"]',      # 规范写法，留着兜别的组件
    ".el-loading-mask",
    ".vxe-loading--wrapper",
)
忙碌最长等待ms = 20000
忙碌轮询间隔ms = 250

# 一次 evaluate 数清「现在还有几个可见的加载态节点」，顺带回样本给人看。
#
# 为什么不用 locator(...).first.wait_for(state="hidden")：
#   一、`.first` 只管第一个。这一页同时有三个 spin-container 在转
#       （基本信息 / 需求内容 / 被加入的基线&需求包），第一个转完就放行，
#       另两个照样被采成「加载中...」。
#   二、locator.count() 数的是**挂载**而不是**可见**，判据口径和 hidden 不一致。
#   三、六条选择器逐条 wait_for 最坏要串 6×20s。一次 evaluate 是毫秒级，
#       而且能对所有匹配一起判可见。
忙碌JS = r"""
(sels) => {
  const 可见 = (el) => {
    if (!el || !el.getClientRects || !el.getClientRects().length) return false;
    const cs = getComputedStyle(el);
    return cs.visibility !== 'hidden' && cs.opacity !== '0';
  };
  const 出 = [], 见过 = new Set();
  for (const sel of sels) {
    let nodes;
    try { nodes = document.querySelectorAll(sel); } catch (e) { continue; }
    for (const el of nodes) {
      if (见过.has(el) || !可见(el)) continue;
      见过.add(el);
      const cls = (el.className && typeof el.className === 'string')
        ? '.' + el.className.trim().split(/\s+/).slice(0, 4).join('.') : '';
      出.push({
        选择器: sel,
        节点: el.tagName.toLowerCase() + cls,
        文本: (el.innerText || '').replace(/\s+/g, ' ').trim().slice(0, 40),
      });
      if (出.length >= 20) return 出;
    }
  }
  return 出;
}
"""


def _加载态样本(残留: list[dict], 取几个: int = 3) -> str:
    """把加载态节点列成一句人话。

    ⚠ 只用 ASCII 标点。Windows 控制台是 gbk，而 `⚠`（U+26A0）这类符号
    gbk 编不出来 —— 实测这行 print 直接抛 UnicodeEncodeError 把命令干掉了，
    「提醒你页面没加载完」的代码反而成了崩溃点。JSON 里的 `等待说明`
    同样会被 print 到 stdout，所以那边也不能带。
    """
    return "、".join(f'{n.get("节点")}"{n.get("文本")}"' for n in 残留[:取几个])


def _配置():
    from .登录 import current_config

    return current_config


def 配置里的域名() -> str:
    """从 config/testing.ini 读被测站点域名。**只用于报错时提示**，不做自动补全。

    为什么不补全：相对路径 + 自动拼域名会让「我到底在测哪个环境」变成隐式的。
    URL 必须由调用方写全 —— 环境写错了应该一眼看出来，而不是靠配置兜。
    """
    conf = _配置()
    for 键 in ("domain_r", "domain"):
        with contextlib.suppress(Exception):
            v = conf.get_conf(键, 键)
            if v:
                return str(v).rstrip("/")
    return "（config/testing.ini 里没读到 domain_r / domain）"


def 检查是完整url(url: str) -> str:
    """URL 必须是完整地址。残缺的输入直接拒绝，不猜。"""
    if url.startswith(("http://", "https://")):
        return url
    raise SystemExit(
        f"--url 必须是完整地址（http:// 或 https:// 开头），收到的是 {url!r}。\n"
        f"        当前配置的域名是 {配置里的域名()}，"
        "拼全之后再传，例如：\n"
        "          https://dev-mude-r.tsp.mioffice.cn/#/req-mgmt/tabs/baseline"
        "?projectBusId=3dce85a6-1fa9-4726-920c-066c5aca1803\n"
        "        不做自动补全是刻意的：环境写错了应该一眼看出来，不该靠配置兜。"
    )


def 是影子库模式() -> bool:
    """online == True 意味着请求带 x-ut-run-id，写操作落影子库。"""
    with contextlib.suppress(Exception):
        return _配置().get_conf("online", "online") == "True"
    return False


def 账号回显() -> str:
    """回显用的是哪个账号键。只回键名与用户名，不碰密码。"""
    conf = _配置()
    try:
        if conf.get_boolean("enable_mude_r_login", "enable_mude_r_login"):
            return f"username_r = {conf.get_conf('username_r', 'username_r')}（-R 站点）"
        return f"username = {conf.get_conf('username', 'username')}"
    except Exception:
        return "无法从 config/testing.ini 读出账号键"


def _预热影子库() -> str | None:
    """online=True 时先让后端把本 runId 的影子库准备好，再开浏览器。

    不做这一步的后果：cookie 里带着一个后端从没见过的 x-ut-run-id，
    写操作落到哪里是未定义的 —— 「写操作落影子库」就只是一句口号，而且不报错。
    """
    if not 是影子库模式():
        return None
    import os

    from .登录 import cookies_manager, prepare_and_wait

    run_id = cookies_manager.get_ude_cookies()
    if os.environ.get("POB_SHADOW_DB_READY") == run_id:
        return run_id[:8]
    print(f"  影子库预热中（runId {run_id[:8]}…，后端复制快照，最长等 600s）")
    prepare_and_wait(run_id)
    os.environ["POB_SHADOW_DB_READY"] = run_id
    print("  影子库就绪")
    return run_id[:8]


# ── 共享会话：登录 + 影子库只做一次，后续命令全都复用 ──────────────────────
#
# 为什么需要它（用户三问同一件事）
# ────────────────────────────
# 影子库按 runId 隔离，而每个 python -m 命令是独立进程，
# cookies_manager.get_ude_cookies() 里是 uuid.uuid1() —— 每进程各生成一个新 runId，
# 于是每条命令都预热一个全新的影子库（后端复制快照，实测约 60 秒）。纯浪费。
#
# 解法是 stageA 并行探索早就用过的 SHARED_COOKIES_FILE：登录一次、把 cookie 与
# runId 写进一个文件，后续进程读它 —— 同一个 runId → 影子库只热一次，
# 而且 login() 读到这个文件会跳过 CAS、直接注 cookie（见同目录 登录.py）。
#
# 这里比 stageA 多做一步：不依赖用户手动 export 环境变量，而是把缓存写到**固定路径**，
# 每条命令启动时自己去看那个文件在不在。AI 用起来就是「先跑一次 --准备，之后照常」。
_会话缓存文件 = __import__("os").path.join(_这里, ".会话缓存.json")
_影子库有效小时 = 5   # 实测影子库 expiresAt 是 startedAt + 6 小时，留 1 小时余量


def 准备共享会话(headless: bool = True) -> dict:
    """登录一次 + 预热影子库一次，写进缓存文件。之后所有命令自动复用。

    跑一次这个，把 60 秒的影子库预热和 CAS 登录一次付清；
    后续每条 可点元素 / 可见结构 / 浏览器会话 命令都跳过这两步，
    只剩「开浏览器 + 注 cookie + 首屏等待」约 15~20 秒。
    """
    import json
    import os
    import time

    from .登录 import cookies_manager

    # 强制真实登录：先清掉可能残留的共享文件环境变量，别读到旧的。
    os.environ.pop("SHARED_COOKIES_FILE", None)
    cookies = cookies_manager.get_cookies()
    if not cookies:
        raise SystemExit("登录失败：拿到的 cookie 是空的，不能建共享会话")
    run_id = cookies_manager.get_ude_cookies()

    影子库 = 是影子库模式()
    if 影子库:
        from .登录 import prepare_and_wait
        print(f"  影子库预热中（runId {run_id[:8]}…，后端复制快照，最长等 600s）"
              "—— 只此一次，后续命令复用")
        prepare_and_wait(run_id)
        print("  影子库就绪")

    # ⚠ 必须 ensure_ascii=True（默认），写成纯 ASCII。
    # 这个文件会被 登录.load_shared_cookies() 读，
    # 而它 open() 时**没指定编码** —— Windows 上按 gbk 读。cookie 值里有
    # 非 gbk 字节（实测 0x93 智能引号）时，用 utf-8/ensure_ascii=False 写出来的
    # 文件 gbk 读不了，报 UnicodeDecodeError。纯 ASCII 谁都读得进去。
    # 那个文件的读法沿用原样（登录.load_shared_cookies 里没指定编码），所以从写这一侧规避。
    with open(_会话缓存文件, "w", encoding="ascii") as f:
        json.dump({"cookies": cookies, "ude_cookies": run_id,
                   "写入时刻": time.time(), "影子库": 影子库,
                   "账号": 账号回显()}, f)
    return {"runId": run_id[:8], "影子库": 影子库, "缓存文件": _会话缓存文件,
            "有效期小时": _影子库有效小时, "账号": 账号回显()}


def _尝试用共享会话() -> dict | None:
    """命令启动时调：缓存在且没过期，就设 SHARED_COOKIES_FILE 让 login() 跳过 CAS，
    并返回一份信息表示「影子库已就绪、预热可跳」。过期或不存在返回 None。
    """
    import json
    import os
    import time

    if not os.path.exists(_会话缓存文件):
        return None
    try:
        data = json.load(open(_会话缓存文件, encoding="utf-8"))
    except Exception:
        return None
    岁数小时 = (time.time() - data.get("写入时刻", 0)) / 3600
    if 岁数小时 > _影子库有效小时:
        print(f"  [提示] 共享会话缓存已过期（{岁数小时:.1f} 小时前建的，"
              f"上限 {_影子库有效小时}），忽略。重新跑 --准备 可再复用")
        return None
    os.environ["SHARED_COOKIES_FILE"] = _会话缓存文件
    return data


def 清除共享会话() -> bool:
    import os

    if os.path.exists(_会话缓存文件):
        os.remove(_会话缓存文件)
        return True
    return False


class 会话:
    """一个活着的浏览器会话。**必须用 with 或者记得调 关闭()。**

        with 会话() as s:
            s.打开("/#/req-mgmt/tabs/baseline?projectBusId=…")
            可点 = 取可点元素(s.page)

    为什么要有这个类而不是让调用方自己 sync_playwright()：
    登录（CAS + cookie 注入）、影子库预热、首屏等待、白屏重载
    四件事都是站点特异且**判据错了会静默失败**的，不该抄到调用方。
    """

    def __init__(self, headless: bool | None = None, 预热影子库: bool = True) -> None:
        """预热影子库=False 只在**纯观察**时用。

        影子库预热是启动里最贵的一步（实测后端复制快照 12~14 次轮询、约 60 秒），
        而它保护的是**写操作**：cookie 里的 x-ut-run-id 后端认了，写才会落到隔离库。
        只看不点的时候没有写操作，跳过它能把一次调用从约 80 秒压到约 20 秒。
        反过来 —— 要做动作就别跳，否则写操作落到哪里是未定义的。
        """
        self._pw = None
        self._browser = None
        self._context = None
        self.page: Any = None
        self.预热影子库 = 预热影子库
        if headless is None:
            with contextlib.suppress(Exception):
                headless = _配置().get_boolean("headless", "headless")
        self.headless = bool(headless)

    # ── 生命周期 ────────────────────────────────────────────────────────
    def 启动(self) -> "会话":
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=self.headless,
            args=["--start-maximized", "--disable-dev-shm-usage", "--no-sandbox",
                  "--disable-features=VizDisplayCompositor"],
        )
        from .登录 import login

        缓存 = _尝试用共享会话()
        if 缓存:
            # 有共享会话：login() 会读 SHARED_COOKIES_FILE 跳过 CAS，
            # 影子库也已由 --准备 那次热好，这里两样都不用再做。
            print(f"  复用共享会话（runId {str(缓存.get('ude_cookies'))[:8]}…）："
                  "跳过 CAS 登录与影子库预热")
        elif self.预热影子库:
            _预热影子库()
        else:
            print("  跳过影子库预热（纯观察模式）——**这个会话不要做写操作**")
        # 同目录 登录.login() 最后强制等 networkidle。这个站有轮询、埋点或长连接时，
        # 页面已经可用但 networkidle 永远不成立，原实现会在 30 秒后把已创建好的
        # context/page 一起“丢”在异常栈里。独立工具不能因此无法观察页面：只对
        # Playwright 的超时降级，并从 browser 取回 login() 已创建的上下文；真正的
        # 页面健康仍由后面的 打开() 用 DOM 签名数量和连续稳定快照判断。
        from playwright.sync_api import TimeoutError as Playwright超时
        try:
            self._context, self.page = login(self._browser)
        except Playwright超时:
            上下文 = self._browser.contexts
            if not 上下文 or not 上下文[-1].pages:
                raise
            self._context = 上下文[-1]
            self.page = self._context.pages[-1]
            print("  login() 等待 networkidle 超时；页面和 cookie 已建立，"
                  "继续由目标页的 DOM 稳定检查判断是否可用")
        self.page.set_default_timeout(30000)
        self.page.set_default_navigation_timeout(30000)
        return self

    def 关闭(self) -> None:
        for 关 in (lambda: self._context and self._context.close(),
                  lambda: self._browser and self._browser.close(),
                  lambda: self._pw and self._pw.stop()):
            with contextlib.suppress(Exception):
                关()

    def __enter__(self) -> "会话":
        return self.启动()

    def __exit__(self, *exc) -> None:
        self.关闭()

    # ── 打开一个页面并停在可观测的状态上 ────────────────────────────────
    def 打开(self, url: str) -> dict:
        """导航 + 等到首屏真的稳定 + 白屏重试。返回一份自检信息。

        返回 {url, 指纹, 签名条数, 等待说明, 是白屏, 仍在加载, 加载态残留}。
        **拿到之后请核对 url 里有没有你要的路由** —— SPA 会先落首页再路由，
        等待逻辑写错就会停在首页上，而那也是一个「稳定」的页面。
        **也请核对 仍在加载** —— 它为 True 时页面上还有转圈的 spinner，
        采回来的分区内容可能是「加载中...」而不是真数据。
        """
        目标 = 检查是完整url(url)
        for 第几次 in range(1, max(1, 白屏重载重试次数) + 2):
            if 第几次 == 1:
                self.page.goto(目标)
            elif 第几次 <= 白屏重载重试次数:
                # 白屏用 reload 而不是 goto：goto 到只差 hash 的同一地址是
                # same-document navigation，不新建文档，而白屏的根因是 ESM
                # 缓存了一条 rejected module promise —— 不新建文档等于没做。
                self.page.reload(wait_until="domcontentloaded")
            else:
                self.page.goto(目标)
            self.安顿(单动作等待ms)
            快照, 说明, 忙碌 = self._等到指纹稳定()
            # 两个口径都回：原始条数是「整页有多少条签名」，净条数是
            # 「滤掉时间戳/条数/业务号这类易变文本之后还剩多少」。
            # 判稳定与算指纹用的都是**净**的那份，所以两个数不一样是正常的。
            条数 = len((快照 or {}).get("signatures") or {})
            净条数 = len(_净指纹(快照))
            if 条数 >= 页面健康最少签名数:
                if 忙碌["超时"]:
                    print(f"  [仍在加载] 还有 {len(忙碌['残留'])} 个可见加载态节点，"
                          "采回来的内容可能是骨架屏："
                          + _加载态样本(忙碌["残留"]), flush=True)
                return {"url": self.page.url, "指纹": 指纹(快照),
                        "签名条数": 条数, "净签名条数": 净条数,
                        "等待说明": 说明, "是白屏": False,
                        "仍在加载": 忙碌["超时"], "加载态残留": 忙碌["残留"]}
            print(f"  [白屏] 签名只有 {条数} 条，"
                  f"{'reload' if 第几次 <= 白屏重载重试次数 else '回 URL'} 重试"
                  f"（第 {第几次}/{白屏重载重试次数} 次）")
        return {"url": self.page.url, "指纹": 指纹(快照), "签名条数": 条数,
                "净签名条数": len(_净指纹(快照)), "等待说明": 说明, "是白屏": True,
                "仍在加载": 忙碌["超时"], "加载态残留": 忙碌["残留"]}

    def 忙碌节点(self) -> list[dict]:
        """当前还可见的加载态节点。空列表 = 页面不忙了。绝不抛。"""
        try:
            return self.page.evaluate(忙碌JS, list(忙碌选择器)) or []
        except Exception:
            return []

    def 等到不忙碌(self, 超时ms: int = 忙碌最长等待ms) -> dict:
        """轮询到一个可见的加载态节点都不剩。返回一份可回给调用方的报告。

        返回 {忙过, 等了ms, 超时, 残留}。**超时不抛异常**：观察工具的职责是
        如实报告页面处在什么状态，而不是拒绝观察。但 超时=True 必须一路传到
        打开() 的返回值里 —— 否则就又变成「静默采到骨架屏」，
        而那正是 ddd.json 里三处「加载中...」的来历。
        """
        import time

        起点 = time.time()
        残留 = self.忙碌节点()
        忙过 = bool(残留)
        while 残留 and (time.time() - 起点) * 1000 < 超时ms:
            self.page.wait_for_timeout(忙碌轮询间隔ms)
            残留 = self.忙碌节点()
        return {"忙过": 忙过, "等了ms": int((time.time() - 起点) * 1000),
                "超时": bool(残留), "残留": 残留[:6]}

    def 安顿(self, 等待ms: int = 800) -> dict:
        """等页面安静：domcontentloaded + networkidle + 加载态消失 + 固定稳定期。

        只等 networkidle 不够 —— 状态变更常常是本地赋值，不重新拉接口。
        返回 等到不忙碌() 的报告，供上层决定要不要往外报。
        """
        with contextlib.suppress(Exception):
            self.page.wait_for_load_state("domcontentloaded")
        with contextlib.suppress(Exception):
            self.page.wait_for_load_state("networkidle", timeout=15000)
        报告 = self.等到不忙碌()
        self.page.wait_for_timeout(等待ms)
        return 报告

    def _等到指纹稳定(self) -> tuple[dict, str, dict]:
        """先硬等下限，再轮询到连续 N 张净指纹一致、且页面不忙。

        三个条件都要：**稳定** 且 **签名条数够多** 且 **没有可见的加载态节点**。
        返回 (快照, 说明, 忙碌报告)。

        ⚠ 第三条是补上的，缺了它前两条形同虚设。骨架屏的签名集合是**恒定**的
        （「加载中...」就是一段静止文本），外壳签名条数又轻松过健康线，
        于是 10 秒下限一到、连拍 3 张一致 → 判「已稳定」返回，
        采集器接着把 spinner 当页面内容采走。ddd.json 里「基本信息」
        分区的内容结构只剩一个「加载中...」，就是这么来的：
        原注释说「骨架屏是完美稳定的，那是这一步存在的全部理由」，
        但判据里其实没有任何一项在看骨架。
        """
        import time

        起点 = time.time()
        self.page.wait_for_timeout(首屏最少等待ms)
        快照 = self.拍指纹()
        上一次 = _净指纹(快照)
        首张条数 = len(上一次)
        忙碌 = {"忙过": False, "等了ms": 0, "超时": False, "残留": []}
        一致, 轮次 = 1, 0
        while (time.time() - 起点) * 1000 < 首屏最长等待ms:
            够稳 = 一致 >= max(2, 首屏连续一致快照数)
            够多 = len(上一次) >= 页面健康最少签名数
            if 够稳 and 够多:
                # 稳定且健康之后才检查忙碌：忙碌检查要走一次 evaluate，
                # 没必要在每一轮轮询里都付这个钱。
                残留 = self.忙碌节点()
                if not 残留:
                    等挂载 = (f"；期间在等 SPA 挂载，首张只有 {首张条数} 条"
                           if 首张条数 < 页面健康最少签名数 else "")
                    等加载 = (f"；其中等加载态消失 {忙碌['等了ms']}ms"
                           if 忙碌["忙过"] else "")
                    return 快照, (f"首屏已稳定：等待 {time.time() - 起点:.1f}s"
                                f"（下限 {首屏最少等待ms / 1000:.0f}s + 轮询 {轮次} 次，"
                                f"连续 {max(2, 首屏连续一致快照数)} 张一致，"
                                f"无加载态{等挂载}{等加载}），"
                                f"签名 {len(上一次)} 条"), 忙碌
                忙碌 = {"忙过": True,
                      "等了ms": int((time.time() - 起点) * 1000 - 首屏最少等待ms),
                      "超时": True, "残留": 残留[:6]}
            self.page.wait_for_timeout(首屏轮询间隔ms)
            轮次 += 1
            快照 = self.拍指纹()
            当前 = _净指纹(快照)
            一致 = 一致 + 1 if 当前 == 上一次 else 1
            上一次 = 当前
        if 忙碌["超时"]:
            样本 = _加载态样本(忙碌["残留"])
            return 快照, (f"[仍在加载] 首屏等到 {time.time() - 起点:.1f}s（已达上限）"
                        f"页面**仍在加载**：还有 {len(忙碌['残留'])} 个可见加载态节点"
                        f"（{样本}）。采到的内容可能是骨架屏，"
                        "请重跑一次，或确认接口是不是挂了"), 忙碌
        return 快照, (f"首屏在 {time.time() - 起点:.1f}s 内未稳定（已达上限），"
                    f"签名仍在变、最后 {len(上一次)} 条，"
                    f"连续一致只到 {一致}"), 忙碌

    # ── 观测与动作 ──────────────────────────────────────────────────────
    def 拍指纹(self) -> dict:
        """整页可见节点各碾成一条 `tag.稳定类名|自身文本`，返回 {hash, signatures, overlays}。

        用途：判「页面稳没稳」与「刚才那一下有没有引起变化」。
        ⚠ 它刻意**不做**命中测试（不判被遮挡）：命中测试依赖滚动位置与视口，
        同一个页面滚一下签名就变，那样「稳定」永远不成立、指纹也不能当身份用。
        """
        return self.page.evaluate(指纹JS, 采集参数)

    def 做(self, 定位: str, 动作: str = "click", 值: str | None = None,
          取第几个: int = 0, 超时ms: int = 8000) -> dict:
        """执行一个动作，返回**页面变化的差分**——这是给 AI 判断"成没成"的依据。

        返回 {做了什么, 有变化, 新增签名, 消失签名, 新增弹层, 路由变了, 前指纹, 后指纹}。

        ⚠ 写操作是**真的**。影子库兜住了数据（online=True 时），但
        「发布」「移除」这类动作在影子库里也是真执行、不可撤销。
        另外别点「退出登录/注销/登出」—— 会话当场作废，之后所有调用都无效。
        """
        前 = self.拍指纹()
        错误 = None
        try:
            loc = self.page.locator(定位).nth(取第几个)
            if 动作 == "click":
                loc.click(timeout=超时ms)
            elif 动作 == "dblclick":
                loc.dblclick(timeout=超时ms)
            elif 动作 == "hover":
                loc.hover(timeout=超时ms)
            elif 动作 == "fill":
                loc.fill(str(值 or ""), timeout=超时ms)
            elif 动作 == "press":
                self.page.keyboard.press(str(值 or "Escape"))
            else:
                raise ValueError(f"不支持的动作 {动作!r}（只有 click/dblclick/hover/fill/press）")
        except Exception as exc:
            错误 = f"{type(exc).__name__}: {exc}"[:200]
        self.page.wait_for_timeout(单动作等待ms)
        后 = self.拍指纹()
        差 = 差分(前, 后)
        # 差分**必须**在这之前算完：toast 只活约 1.2 秒，而下面这一等可能几秒，
        # 等完 toast 早没了，`新增签名` 里就拿不到提示文案（SKILL.md 里写预期
        # 结果全靠它）。所以顺序是先拍后差、再等加载 ——
        # 等这一下是为**后续的采集**：动作触发的接口没回来就采，
        # 采到的还是「加载中...」。
        忙碌 = self.等到不忙碌()
        return {"做了什么": f"{动作} {定位}" + (f" = {值!r}" if 值 is not None else ""),
                **({"错误": 错误} if 错误 else {}), **差,
                **({"仍在加载": True, "加载态残留": 忙碌["残留"]}
                   if 忙碌["超时"] else {}),
                "前指纹": 指纹(前), "后指纹": 指纹(后)}

    def 读(self, 定位: str, 取第几个: int = 0) -> dict:
        """读一个元素的文本与属性，给断言用。绝不抛。

        返回 {匹配, 文本, 全部文本, 属性, 可见}；匹配=0 时其余为空。
        `全部文本` 是这个选择器匹配到的**所有**节点的文本列表 ——
        取整列值就靠它（比如列头下面那一列单元格）。
        """
        try:
            loc = self.page.locator(定位)
            n = loc.count()
            if n == 0:
                return {"匹配": 0, "文本": None, "全部文本": [], "属性": {}, "可见": False}
            一个 = loc.nth(取第几个)
            全部 = []
            for i in range(min(n, 200)):
                with contextlib.suppress(Exception):
                    全部.append((loc.nth(i).inner_text() or "").strip())
            return {
                "匹配": n,
                "文本": (一个.inner_text() or "").strip(),
                "全部文本": 全部,
                "属性": self.page.evaluate(
                    "el => Object.fromEntries(Array.from(el.attributes)"
                    ".filter(a => a.name !== 'style')"
                    ".map(a => [a.name, a.value.slice(0, 120)]))",
                    一个.element_handle()),
                "可见": 一个.is_visible(),
            }
        except Exception as exc:
            return {"匹配": None, "错误": f"{type(exc).__name__}: {exc}"[:160],
                    "文本": None, "全部文本": [], "属性": {}, "可见": False}


# ── 指纹与差分：判「变了没变」的唯一口径 ──────────────────────────────────
import hashlib as _hashlib
import re as _re

# 易变文本：跟状态无关，进差分只会制造噪音。
# 业务号用**通用形状**而不是前缀白名单 —— 白名单实测漏过 RS（基线）与 RP（项目）。
_易变文本模式 = [
    r"\d{4}[-/]\d{1,2}[-/]\d{1,2}",
    r"\d{1,2}:\d{2}",
    r"\d+\s*(秒|分钟|小时|天|周|个月|年)前",
    r"^\d+$",
    r"^\d+\s*(条|项|个|页|%)$",
    r"(共|第)\s*\d+",
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}",
    r"[A-Za-z]{1,4}\d{4,}",
    r"^V\d+(\.\d+)*$",
]
_易变正则 = _re.compile("|".join(_易变文本模式))


def _净指纹(快照: dict | None) -> set:
    """滤掉易变文本之后的签名集合。判「稳定」与算指纹都用这一份。

    不滤的后果：时间戳、条数这类每秒都在变的文本会让「稳定」永远不成立。
    """
    出 = set()
    for s in (快照 or {}).get("signatures") or {}:
        文本 = s.split("|", 1)[1] if "|" in s else ""
        if 文本 and _易变正则.search(文本):
            continue
        出.add(s)
    return 出


def 指纹(快照: dict | None) -> str:
    """这一屏的身份 = 路由 + 净签名集合的 sha1 前 12 位。

    只看签名「有没有」，不看「有几个」—— 列表多一行不算换了页面。
    AI 用它判断「我点完之后是不是还在原地」。
    """
    sigs = sorted(_净指纹(快照))
    raw = ((快照 or {}).get("hash") or "") + "\n" + "\n".join(sigs)
    return _hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def 差分(前: dict, 后: dict, 举例: int = 8) -> dict:
    """两张指纹的集合差。回答「刚才那一下引起了什么变化」。"""
    a, b = _净指纹(前), _净指纹(后)
    新增, 消失 = b - a, a - b
    前弹层 = {o.get("选择器") for o in (前.get("overlays") or [])}
    新弹层 = [o for o in (后.get("overlays") or [])
            if o.get("选择器") not in 前弹层]
    路由变了 = (前.get("hash") or "") != (后.get("hash") or "")
    return {
        "有变化": bool(新增 or 消失 or 新弹层 or 路由变了),
        "新增签名数": len(新增), "消失签名数": len(消失),
        "新增签名": sorted(新增, key=len)[:举例],
        "消失签名": sorted(消失, key=len)[:举例],
        "新增弹层": 新弹层,
        "路由变了": (后.get("hash") if 路由变了 else None),
    }


# ══════════════════════════════════════════════════════════════════════
#  以下三段 JS 与一份参数，是从 stageA 按字节拷过来的快照（由 _生成会话文件.py 写入）。
#  拷贝而非 import 是刻意的：本目录要对 stageA 零依赖。
#  代价：两边从此各自演进，不会自动同步。改这里不会影响那边，反之亦然。
#
#  元素采集JS   整页扫一遍 → 可点元素 + 每个元素 8~16 档候选选择器 + 实测匹配数
#               + 命中测试（elementFromPoint，判有没有被别的元素盖住）
#  指纹JS       只返回 {指纹→条数} 字典，供前后差分与「稳没稳」判定，不返回元素
#  分身体检JS    一个选择器匹配多个节点时，定出该点第几个（零副作用，毫秒级）
# ══════════════════════════════════════════════════════════════════════

采集参数 = {
    "businessAttrs": [
        "data-space-id",
        "data-project-id",
        "data-reqid"
    ],
    "rowIdAttrs": [
        "rowid",
        "row-id",
        "data-rowid",
        "data-row-id",
        "data-row-key",
        "data-rowkey",
        "data-key",
        "data-id"
    ],
    "rowIdHops": 6,
    "volatileClassRe": "^(is-|has-)|(^|-)(active|selected|checked|disabled|open|opened|closed|show|shown|hidden|hide|hover|focus|focused|current|expanded|collapsed|loading|dragging|copying|highlight|highlighted|error|warning|success|editing|readonly)$",
    "animClassRe": "(^|[-_.])(wave|ripple|transition|fade|zoom|slide|motion|spin-dot|animat[a-z]*)([-_.]|$)",
    "noiseClassPrefixes": [
        "ant-",
        "vxe-",
        "ude-",
        "u-",
        "el-",
        "iconfont",
        "anticon"
    ],
    "textCap": 120,
    "sigTextCap": 24,
    "sigCap": 6000,
    "elementCap": 4000,
    "maxCandidates": 16
}

元素采集JS = r"""
(cfg) => {
  const VOLATILE = new RegExp(cfg.volatileClassRe);
  // 'i' 是必须的：Python 侧那份是 re.I。漏了它 `ant-Wave` 这类写法就漏掉，且不报错。
  const ANIM = new RegExp(cfg.animClassRe, 'i');
  const INTERACTIVE_TAGS = new Set(['button','a','input','textarea','select','label','option']);
  const INTERACTIVE_ROLES = new Set(['button','tab','checkbox','radio','menuitem','menuitemcheckbox',
    'link','option','switch','columnheader','row','gridcell','cell','treeitem','combobox','textbox']);
  // 注意这里**故意不含 svg** —— 与签名脚本的同名集合不一样，那边可以跳过 svg。
  // 实测踩到的：这个站有一批可点元素**本身就是 <svg>**，还自带 inline cursor:pointer，
  //   导出   <svg class="icon export-icon"  style="cursor:pointer">
  //   发布   <svg class="icon publish-icon" style="cursor:pointer">
  // 把 svg 放进 SKIP_TAGS，它们在第 1 道就被丢掉，第 3 道的 pointer起点 判据根本没机会生效，
  // 于是「导出 / 发布通知 / 描述编辑」这一批纯图标入口整体缺席
  // （stageA_plan.md 3.9 账单第 2 条估的 15~25 条用例损失，主力就是这一类）。
  // 放行 svg 不会引入噪音：装饰性 svg 要么没有 cursor:pointer，
  // 要么是从可点父节点继承来的 —— 后者会被「父元素不是 pointer」那条挡掉。
  // path / use / g / defs 这些 svg 内部节点仍然跳过，它们永远不是可点单位。
  const SKIP_TAGS = new Set(['path','use','g','defs','circle','rect','line','polygon',
    'script','style','br','hr','tspan','text','template']);

  const norm = (s) => (s || '').replace(/\s+/g, ' ').trim();
  const cap  = (s, n) => (s && s.length > n ? s.slice(0, n) : (s || ''));
  const esc  = (s) => (window.CSS && CSS.escape) ? CSS.escape(s) : String(s).replace(/([^\w-])/g, '\\$1');

  const isVisible = (el) => {
    if (!el || !el.getClientRects || !el.getClientRects().length) return false;
    const cs = getComputedStyle(el);
    return cs.visibility !== 'hidden' && cs.opacity !== '0';
  };

  // ── 命中测试：CSS 说可见 ≠ 人类看得见 ────────────────────────────────
  //
  // isVisible 那三条（有布局盒 / 非 hidden / 非 opacity:0）判不出「被别的元素盖住」。
  // 实测（探针，真浏览器，这一页）：
  //   整页 3495 节点 → CSS 可见 281 → elementFromPoint 命中自己 166
  //                                 被挡 33 ｜ 视口外 41 ｜ 零尺寸 41
  //   整页一次命中测试 8 ms —— 便宜到可以进热路径
  // 弹窗打开时，「项目文档」「基线」「需求包」「创建基线」四个背景元素全部
  // 命中自己=false、挡路者=ant-modal-wrap.create-baseline-modal。
  // 也就是说遮罩问题在这条判据下**自动消失**，不需要 assemble 侧再按
  // 所属弹层容器 去过滤背景元素。
  //
  // 试点用中心 + 四个内缩 25% 的点，与 分身体检的JS 完全一致：异形元素
  // （圆角、图标字体、被裁切的单元格）中心可能落在空隙里，只试一个点会误判成被挡。
  //
  // ⚠ 视口外**不算不可见**，只标记。它和「被挡」性质完全不同：
  //   被挡  = 人类现在点不到，而且滚动也没用（上面盖着东西）→ 该丢
  //   视口外 = 人类滚一下就能看到（表格第二屏、折叠区）→ 不能丢，丢了就是漏采
  // elementFromPoint 只在视口内有效，所以对视口外的节点它没有发言权，
  // 这里如实记「说不清」而不是替它下结论。
  //
  // ⚠ 这套判据**只用在元素采集**，不进指纹脚本。指纹在每个动作前后各拍一张、
  //   首屏轮询里还要反复拍，而命中测试的结果依赖滚动位置与视口大小 ——
  //   同一个状态两次拍摄只要滚动差一点，命中集合就不同 → 签名不同 →
  //   state_key 不稳，而软复位与回放落点校验全靠它。指纹必须对偶然滚动免疫。
  const 是自己或后代 = (命中, self) => !!命中 && (命中 === self || self.contains(命中));
  const 命中测试 = (el) => {
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) {
      return { 命中: false, 零尺寸: true, 在视口外: false, 挡路者: null };
    }
    const 试点 = [
      [r.left + r.width / 2,    r.top + r.height / 2],
      [r.left + r.width * 0.25, r.top + r.height * 0.5],
      [r.left + r.width * 0.75, r.top + r.height * 0.5],
      [r.left + r.width * 0.5,  r.top + r.height * 0.25],
      [r.left + r.width * 0.5,  r.top + r.height * 0.75],
    ];
    let 挡路者 = null, 在视口外 = false;
    for (const [x, y] of 试点) {
      if (x < 0 || y < 0 || x > innerWidth || y > innerHeight) { 在视口外 = true; continue; }
      const 命中 = document.elementFromPoint(x, y);
      if (是自己或后代(命中, el)) return { 命中: true, 在视口外: false, 挡路者: null };
      if (命中 && !挡路者) {
        const cls = (命中.className && typeof 命中.className === 'string')
          ? '.' + 命中.className.trim().split(/\s+/).slice(0, 3).join('.') : '';
        挡路者 = 命中.tagName.toLowerCase() + cls;
      }
    }
    return { 命中: false, 在视口外: 在视口外 && !挡路者, 挡路者: 挡路者 };
  };

  const classesOf = (el) => Array.from(el.classList || []);
  const stableClasses = (el) => classesOf(el).filter(c => c && !VOLATILE.test(c));
  const semanticClasses = (el) => stableClasses(el)
    .filter(c => !cfg.noiseClassPrefixes.some(p => c.startsWith(p)));
  const ownText = (el) => {
    let t = '';
    for (const n of el.childNodes) if (n.nodeType === 3) t += n.nodeValue;
    return norm(t);
  };
  const implicitRole = (el) => {
    const explicit = el.getAttribute('role');
    if (explicit) return explicit;
    const tag = el.tagName.toLowerCase();
    if (tag === 'button') return 'button';
    if (tag === 'a') return el.hasAttribute('href') ? 'link' : null;
    if (tag === 'textarea') return 'textbox';
    if (tag === 'select') return 'combobox';
    if (tag === 'input') {
      const t = (el.getAttribute('type') || 'text').toLowerCase();
      if (t === 'checkbox') return 'checkbox';
      if (t === 'radio') return 'radio';
      if (t === 'button' || t === 'submit') return 'button';
      return 'textbox';
    }
    return null;
  };

  const countCache = new Map();
  // rootSel 传了就在那个容器内数，不传就全文档数。
  //
  // 为什么需要「容器内数」这个口径：`匹配` 一直是全文档数的，而元素是**在某个状态里**
  // 被采到的，弹层态的作用域其实只有那个弹层。实测同一条
  // `input[placeholder="文件夹/需求文档名称"]` 在三条元素记录上给出 1 和 2 两个值 ——
  // 取决于采集那一刻弹窗开没开。这个数按全文档报，下游就没法回答
  // 「我现在在这个弹窗里，这条选择器指几个」，而那才是它真正要问的问题。
  //
  // 两个口径都留：`匹配` 回答「整页有几个」，`容器内匹配` 回答
  // 「先收进这个弹窗之后有几个」。下游按状态类型选用哪个，不必猜。
  const countOf = (sel, rootSel) => {
    const key = (rootSel || '') + '\u0000' + sel;
    if (countCache.has(key)) return countCache.get(key);
    let res;
    try {
      let root = document;
      if (rootSel) {
        root = document.querySelector(rootSel);
        if (!root) { res = { total: 0, visible: 0 }; countCache.set(key, res); return res; }
      }
      const nodes = root.querySelectorAll(sel);
      let vis = 0;
      nodes.forEach(n => { if (isVisible(n)) vis++; });
      res = { total: nodes.length, visible: vis };
    } catch (e) {
      res = { total: null, visible: null, error: String(e && e.name || 'SelectorError') };
    }
    countCache.set(key, res);
    return res;
  };

  const chainOf = (el, depth) => {
    const out = [];
    let p = el.parentElement;
    while (p && p !== document.body && out.length < depth) {
      const sem = semanticClasses(p);
      out.push(p.tagName.toLowerCase() + (sem.length ? '.' + sem[0] : ''));
      p = p.parentElement;
    }
    return out.reverse();
  };

  // 祖先的**全部稳定类名**，不做组件库前缀过滤。
  // 祖先链（chainOf）过滤了噪音前缀，于是 li.ant-pagination-prev 只剩 li，语义就丢了；
  // 而分页按钮自己的类名是 ant-pagination-item-link（也是噪音），
  // 「上一页 / 下一页」这个语义**完整地只存在于祖先的类名上**。
  // 所以命名要用的这一份必须保留原样。
  const ancestorClasses = (el, depth) => {
    const out = [];
    let p = el.parentElement;
    while (p && p !== document.body && out.length < depth) {
      const cs = stableClasses(p);
      if (cs.length) out.push(cs);
      p = p.parentElement;
    }
    return out;
  };

  // 图标线索：iconfont / svg symbol 的 id 往往就是语义（icon-shanchu = 删除）。
  // SKIP_TAGS 把 svg / use 整个跳过了，所以 <use xlink:href="#icon-shanchu"> 这条
  // 最直接的线索原来是被扔掉的。这里单独取回来。
  const iconHintOf = (el) => {
    const u = el.querySelector('use');
    const href = u && (u.getAttribute('xlink:href') || u.getAttribute('href'));
    if (href) return String(href).replace(/^#/, '');
    const pool = classesOf(el).slice();
    for (const c of Array.from(el.querySelectorAll('*')).slice(0, 6)) {
      pool.push.apply(pool, classesOf(c));
    }
    const hit = pool.find(c => /^(icon|anticon)[-_]/i.test(c));
    return hit || null;
  };

  // 自下而上的祖先容器链。direct 表示它就是直接父节点——
  // 这时能用 `>` 直接子元素组合器，比后代组合器更严，正好对上 stageA_plan.md
  // 样本里 `div.view-change > div.document` 那种写法。
  //
  // 两个教训，都是真实 DOM 上撞出来的：
  //  1. 不能只取最近一个带类名的祖先。目录树收起态的两份 DOM 都在 div.tree-wrap 里，
  //     只有再往上到 div.left-tree 才区分得开，所以要返回整条链让调用方逐层升级。
  //  2. 祖先这一侧不能过滤组件库前缀。vxe 固定列的区分容器恰恰叫
  //     div.vxe-table--fixed-left，把 vxe- 当噪音滤掉就等于把唯一的解丢了。
  //     噪音过滤只对元素自己的选择器有意义，对作用域没有。
  //  3. 两道上限都放宽了（5 / 8 → 12 / 20）。原来的值让上面第 2 条那句话
  //     变成一句空话：span.baseline-id 走到 div.vxe-table--fixed-left 要经过
  //       .vxe-cell--wrapper → .vxe-cell → td → tr → tbody → table
  //       → .vxe-table--body-wrapper → .vxe-table--fixed-left
  //     八层以上，而 out.length<5 早在 tr.vxe-body--row 就停了。
  //     实测产物为证：e2841e91 的候选最深就是 tr.vxe-body--row span.baseline-id，
  //     没有任何一条带 fixed-left —— 注释说它是唯一的解，代码却走不到。
  //     放宽后在合成 DOM 上复现验证过：`div.vxe-table--fixed-left span.baseline-id`
  //     匹配 1 —— 唯一候选出来了，表格行元素第一次变得可定位。
  //     代价只有 countOf() 多调几次，而调用处的升级循环一旦 匹配===1 就 break，
  //     绝大多数元素在前两三层就停了，实际开销几乎没变。
  const ancestorScopes = (el, max) => {
    const out = [];
    let p = el.parentElement, hops = 0;
    while (p && p !== document.body && out.length < max && hops < 20) {
      const sem = semanticClasses(p);
      const cls = sem.length ? sem : stableClasses(p);
      if (cls.length) {
        out.push({ sel: p.tagName.toLowerCase() + '.' + esc(cls[0]), direct: hops === 0 });
      }
      p = p.parentElement; hops++;
    }
    return out;
  };


  const OVERLAY_CLASS_RE = /(modal|dialog|popover|dropdown|drawer|tooltip|overlay|popup)/i;

  // 不假设浮层挂在 body 上。这里踩过两次坑，都记下来：
  //   第一次：判定要求「body 的直接子元素自己带浮层类名」，而 ant-design-vue 4 的 Modal
  //           外层是无 class 的 wrapper div、浮层类名在它子元素上 → 全漏。
  //   第二次：改成「body 直接子元素或其直接子元素」之后弹窗对了，
  //           但 popover / dropdown / select 仍然全漏 —— 它们**根本不在 body 下**
  //           （很多项目把 getPopupContainer 设成触发元素的父节点，避开滚动问题）。
  //           实测表现：7 个弹层态全部「没有容器」、门禁判失败；
  //           而 hover→元素 那条分支因为拿不到新增浮层，压根没被触发。
  // 所以现在全 DOM 找，判据只用浮层自身的特征：类名/role + 脱离文档流的定位。
  const OVERLAY_SEL =
    '[class*="popover"],[class*="dropdown"],[class*="modal"],[class*="dialog"],' +
    '[class*="drawer"],[class*="tooltip"],[class*="overlay"],[class*="popup"],' +
    '[role="dialog"],[role="tooltip"],[role="menu"],[role="listbox"],[aria-modal="true"]';

  // 遮罩背板不是内容容器。它满足浮层的全部形式特征（fixed + 类名带 modal），
  // 但里面什么都没有；不排掉它就会被当成 新增弹层[0]、进而成为状态的「容器」，
  // 而下游拿这个容器去 scope 内部元素会一个都找不到。
  const MASK_RE = /(mask|backdrop)/i;

  const isOverlayNode = (el) => {
    if (!el || el.nodeType !== 1 || !el.matches(OVERLAY_SEL)) return false;
    if (MASK_RE.test(classesOf(el).join(' '))) return false;
    if (!isVisible(el)) return false;
    // 浮层一定脱离文档流。这一条把「触发器」滤掉：
    // .ant-dropdown-trigger 类名里也带 dropdown，但它是 position: static。
    const cs = getComputedStyle(el);
    return cs.position === 'fixed' || cs.position === 'absolute';
  };

  // 只留最外层：任何祖先已经是浮层节点的，都不是根
  const overlayRoots = () => {
    const found = Array.from(document.querySelectorAll(OVERLAY_SEL)).filter(isOverlayNode);
    const set = new Set(found);
    return found.filter(el => {
      let p = el.parentElement;
      while (p) { if (set.has(p)) return false; p = p.parentElement; }
      return true;
    });
  };

  const overlaySelectorOf = (root) => {
    let pick = stableClasses(root).filter(c => OVERLAY_CLASS_RE.test(c));
    if (!pick.length) pick = semanticClasses(root);
    if (!pick.length) pick = stableClasses(root);
    if (!pick.length) {
      const r = root.getAttribute('role');
      return r ? root.tagName.toLowerCase() + '[role="' + r + '"]' : null;
    }
    return '.' + pick.map(esc).join('.');
  };

  // 元素所属的浮层容器：向上找最外层的那个浮层节点
  const overlayContainerOf = (el) => {
    let p = el, outermost = null;
    while (p && p !== document.body) {
      if (isOverlayNode(p)) outermost = p;
      p = p.parentElement;
    }
    return outermost ? overlaySelectorOf(outermost) : null;
  };

  const listOverlays = (textCap) => overlayRoots()
    .map(el => {
      const titleEl = el.querySelector(
        '[class*="modal-title"],[class*="dialog-title"],[class*="popover-title"],' +
        '[class*="drawer-title"],[role="heading"]');
      return {
        选择器: overlaySelectorOf(el),
        类名: classesOf(el),
        标题: titleEl ? cap(norm(titleEl.textContent), 40) : null,
        文本摘要: cap(norm(el.innerText), textCap)
      };
    })
    .filter(o => o.选择器)
    // 内容多的排前面：下游取 新增弹层[0] 当状态容器，得拿到真正装东西的那一层
    .sort((a, b) => (b.文本摘要 || '').length - (a.文本摘要 || '').length);


  const overlayOf = (el) => overlayContainerOf(el);

  // 哪些档值得再跟弹层容器组合一次（见 buildCandidates 第 8.5 步）。
  // 只收**纯 CSS 形态的判别式**：拼上容器前缀之后仍是合法 CSS，
  // querySelectorAll 数得动、locator() 点得动。
  // 刻意不收：
  //   id           已经全局唯一，再加前缀没有信息量
  //   结构位置      本身标着不稳定，加了作用域也还是 nth-child，别给它涨身价
  //   作用域+类名 / 容器+子类名 / 外层容器+类名  它们自己就是作用域档，
  //                再套一层容器只会让表达式更长更脆，而收窄能力没有增加
  //   类名 / 标签+类名  第 8 步的 `弹层容器+类名`（= 容器 + tag + 全部自有类名）
  //                    已经严格强于它们，再生成只会多出**同名不同表达**的两条候选
  //                    （实测跑出过两条都叫 弹层容器+类名、匹配数一个 2 一个 5），
  //                    读产物的人分不清哪条是哪条
  const 组合到弹层的档 = new Set([
    'placeholder', 'name属性', 'role属性+类名',
    '业务ID属性', '业务ID属性存在', '行标识属性',
  ]);

  const buildCandidates = (el) => {
    const tag = el.tagName.toLowerCase();
    const out = [];
    const push = (策略, 表达, extra) => {
      if (!表达) return;
      if (out.some(c => c.表达 === 表达)) return;
      out.push(Object.assign({ 策略, 表达 }, extra || {}));
    };
    const sem = semanticClasses(el);
    // 元素自己的类名选择器：优先用语义类名；全是组件库前缀时退回稳定类名，
    // 否则像 span.baseline-id 这种只有 vxe 语境的元素会一条候选都生成不出来。
    const own = (sem.length ? sem : stableClasses(el)).map(c => '.' + esc(c)).join('');
    const semSel = own;

    // 1 业务 ID 属性（全库只有 3 个，有则首选）
    for (const a of cfg.businessAttrs) {
      if (el.hasAttribute(a)) {
        push('业务ID属性', tag + '[' + a + '="' + el.getAttribute(a) + '"]', { 含实例值: true });
        push('业务ID属性存在', tag + '[' + a + ']');
      }
    }
    // 1.5 行标识属性（表格行入口的唯一活路，理由见模块头 行标识属性名 那段注释）
    // 顺着祖先链找第一个带行标识属性的节点。找元素自己也算 —— 有的表格把
    // data-id 直接挂在可点的单元格上。
    (() => {
      let p = el, hops = 0;
      while (p && hops <= (cfg.rowIdHops || 6)) {
        for (const a of (cfg.rowIdAttrs || [])) {
          const v = p.getAttribute && p.getAttribute(a);
          // 空串要排除：vue 的 data-v-xxxx 之类是空值属性，拼出来的
          // [data-key=""] 会匹配一大片，比不加更糟。
          if (v) {
            const 锚 = '[' + a + '="' + v.replace(/"/g, '\\"') + '"]';
            // 元素自己就是携带者 → 锚点本身就是它；否则锚点是祖先，要再接上自己。
            const 表达 = (p === el) ? el.tagName.toLowerCase() + 锚
                                    : 锚 + ' ' + tag + (own || '');
            push('行标识属性', 表达, {
              含实例值: true, 行标识属性: a, 行标识值: v,
              行标识在自己身上: p === el,
            });
            return;   // 只取最近的一层，再往上就是整张表了
          }
        }
        p = p.parentElement; hops++;
      }
    })();
    // 2 稳定 id
    if (el.id && !/^\d|[\s:]|^ant-|^v-|^rc_/.test(el.id)) push('id', '#' + esc(el.id));
    // 3 表单锚点
    const ph = el.getAttribute('placeholder');
    if (ph) push('placeholder', tag + '[placeholder="' + ph + '"]');
    const nm = el.getAttribute('name');
    if (nm) push('name属性', tag + '[name="' + nm + '"]');
    // 4 显式 role + 类名
    const role = el.getAttribute('role');
    if (role) push('role属性+类名', tag + '[role="' + role + '"]' + semSel);
    // 5 标签 + 全部语义类名
    if (sem.length) push('标签+类名', tag + semSel);
    // 6 单个最具体类名
    if (sem.length) {
      const best = sem.slice().sort((a, b) => b.length - a.length)[0];
      push('类名', '.' + esc(best));
    }
    // 7 作用域限定（治「同名节点出现两份」）
    // 直接父节点用 `>`，更严；同时保留一条后代组合器的松版本——
    // 前端插一层 wrapper 时 `>` 会失效而后代版还活着，两条都留给下游换候选用。
    const scopes = ancestorScopes(el, 12);
    if (scopes.length && own) {
      if (scopes[0].direct) push('容器+子类名', scopes[0].sel + ' > ' + tag + own);
      push('作用域+类名', scopes[0].sel + ' ' + tag + own);
    }
    // 8 弹层容器限定（弹层全挂 body，不 scope 必冲突）
    const ov = overlayOf(el);
    if (ov && own) push('弹层容器+类名', ov + ' ' + tag + own);
    else if (ov) push('弹层容器+标签', ov + ' ' + tag);
    // 8.5 弹层容器 × **每一档判别式**，不只类名（一次真实的点错逼出来的）
    //
    // 原来容器只跟类名组合过一次。实测「添加需求」弹窗里的搜索框：
    //   弹层容器 + 类名        → .ant-modal-wrap...reqSelect... input.css-1p3hq3p  匹配 2
    // 因为这个弹窗里有两个 input.ant-input.css-1p3hq3p（文件夹名称 / 需求名称ID）。
    // 而
    //   弹层容器 + placeholder → .ant-modal-wrap...reqSelect... input[placeholder="文件夹/需求文档名称"]  匹配 1
    // 是唯一解 —— 但这条组合压根没生成过。类名撞车时容器救不回来，
    // 换个判别式就救回来了，缺的只是这层组合。
    //
    // 为什么这是通用的而不是给这个弹窗打补丁：判别式（placeholder / role / name /
    // 业务属性 / 行标识）和作用域（弹层容器）是**两个正交的维度**，
    // 原来只连了其中一格。补全笛卡尔积，任何站点的「同名控件分处内外」都能解开。
    if (ov) {
      for (const c of out.slice()) {
        if (!组合到弹层的档.has(c.策略)) continue;
        push('弹层容器+' + c.策略, ov + ' ' + c.表达, {
          含实例值: c.含实例值, 行标识属性: c.行标识属性, 行标识值: c.行标识值,
          行标识在自己身上: c.行标识在自己身上,
        });
      }
    }
    // 9 结构兜底：明确标不稳定，只在前面全不唯一时才有意义
    if (el.parentElement) {
      const idx = Array.prototype.indexOf.call(el.parentElement.children, el) + 1;
      const pscope = (scopes[0] && scopes[0].sel) || el.parentElement.tagName.toLowerCase();
      push('结构位置', pscope + ' > ' + tag + ':nth-child(' + idx + ')', { 不稳定: true });
    }

    for (const c of out) {
      const r = countOf(c.表达);
      c.匹配 = r.total;
      c.可见匹配 = r.visible;
      if (r.error) c.错误 = r.error;
      // 元素住在弹层里时，再给一个「先收进这个弹层之后指几个」的数。
      // 已经自带容器前缀的那些档不用再算 —— 它们的 `匹配` 本身就是容器内的数。
      if (ov && !String(c.策略 || '').startsWith('弹层容器+')) {
        const rc = countOf(c.表达, ov);
        c.容器内匹配 = rc.total;
        c.容器内可见匹配 = rc.visible;
      }
    }

    // 到这里还没有唯一候选，就逐层往外升级作用域，直到唯一或者祖先用完。
    // 目录树的两份 DOM 与 vxe 固定列重复渲染都是在这一步被解开的。
    if (own && !out.some(c => c.匹配 === 1)) {
      for (const s of scopes.slice(1)) {
        const expr = s.sel + ' ' + tag + own;
        if (out.some(c => c.表达 === expr)) continue;
        const r = countOf(expr);
        out.push({
          策略: '外层容器+类名', 表达: expr, 匹配: r.total, 可见匹配: r.visible
        });
        if (r.total === 1) break;
      }
      // 作用域升到最外一层还是不唯一 → 记一笔。这是 ancestorScopes 那个上限
      // 有没有在真的干活的**唯一**信号。原来它是静默的：上限填 5 时
      // span.baseline-id 永远走不到 div.vxe-table--fixed-left，
      // 而产物里看起来就像「这个元素本来就不可定位」。
      if (!out.some(c => c.匹配 === 1)) {
        账.作用域升到顶仍不唯一 += 1;
        if (scopes.length >= 12) 账.作用域档数用满 += 1;
      }
    }

    // 截断时优先保住唯一候选，别把唯一的解切掉。
    // 行标识属性 那一档跟唯一候选一起保 —— 它的匹配数天生是 2（固定列分身），
    // 落进 rest 就可能被 maxCandidates 切掉，而对表格行元素它是**唯一的活路**。
    const uniq = out.filter(c => c.匹配 === 1 || c.策略 === '行标识属性');
    const rest = out.filter(c => !(c.匹配 === 1 || c.策略 === '行标识属性'));
    // maxCandidates 撞顶要留痕。虽然截断时优先保唯一候选、切的是"多余"的那些，
    // 但"多余"是按当前排序判的，换个站可能切掉真正需要的档。
    // 这个 cap 原来是完全静默的 —— 撞了也没人知道。
    if (uniq.length + rest.length > cfg.maxCandidates) {
      账.候选被截断 += 1;
      if (uniq.length > cfg.maxCandidates) 账.候选截断伤到唯一候选 += 1;
    }
    return uniq.concat(rest).slice(0, cfg.maxCandidates);
  };

  // ── 候选元素筛选 ──────────────────────────────────────────────────
  //
  // 「账」是这一整段的丢弃台账。加它的理由（一条实测教训）：
  // 每一处 continue / filter 都在**不可逆地**减少下游能用的素材，
  // 而它们原来全是静默的。elementCap=600 撞顶丢过元素、ancestorScopes=5
  // 让表格行元素永远拿不到唯一候选，这两件事都是事后靠翻产物才发现的。
  // 一个悄悄丢东西的成本保护，比一次慢的运行坏得多 —— 它把「数据没了」
  // 伪装成「数据本来就是这样」。所以现在每一处丢弃都要报数。
  const 账 = {
    标签黑名单跳过: 0,
    不可见跳过: 0,
    不可见且本来可交互: 0,
    五条规则都不命中跳过: 0,
    // 只在 :hover 里才声明 cursor:pointer 的节点数（判据见 hover才pointer）。
    // 这一笔为 0 而页面上明明有小手，说明 hover规则 那一段没扫到样式表。
    hover才pointer采到: 0,
    同框父子丢子: 0,
    同框丢掉的子里有语义类名: 0,
    候选被截断: 0,
    候选截断伤到唯一候选: 0,
    作用域升到顶仍不唯一: 0,
    作用域档数用满: 0,
    // 签名侧丢掉的纯动画节点数。0 有两种含义要能分开：
    // 「这个站没有动画节点」还是「animClassRe 写错了一个都没匹配上」——
    // 后者会让 div.ant-wave 重新溜进 state_key、凭空造出假状态。
    动画节点跳过: 0,
    // ── 命中测试的三笔账（判据见 命中测试）────────────────────────────
    // 被挡跳过：CSS 说可见、但被别的节点盖住 → 人类点不到，丢掉。
    //   弹窗打开时的背景元素全落在这里，这一笔非 0 才说明遮罩过滤真的生效了。
    // 视口外留下：滚一下就能看到的，**不丢**，只标记。这一笔大不代表有问题，
    //   但它和「一整块 UI 从没被展开过」是同一类信号。
    // 零尺寸跳过：宽或高为 0，命中测试无从下手。
    被挡跳过: 0,
    被挡且本来可交互: 0,
    视口外留下: 0,
    零尺寸跳过: 0,
  };
  // document.body 为 null 的防护，理由与签名脚本里同名的那处相同（实测崩过）。
  // 键名必须与正常返回完全一致：Python 侧按 elements / signatures / meta 取，
  // 缺键只会拿到 None 而不报错。
  if (!document.body) {
    return {
      meta: { url: location.href, hash: location.hash, 标题: '', 视口: {w: 0, h: 0},
              元素总数: 0, 候选原始数: 0, 候选保留数: 0, 签名条数: 0,
              截断: { 元素: false, 签名: false }, 丢弃台账: 账, 文档未就绪: true },
      elements: [], signatures: {}, overlays: [],
    };
  }
  // ── 只在 :hover 里才给 cursor:pointer 的那批节点 ──────────────────────
  //
  // getComputedStyle 读的是**当前**样式，鼠标不在元素上时 :hover 规则不参与计算。
  // 于是这种写法（这个站的侧边栏和标签，实测就是这么写的）
  //     .req-sidebar .menu-item:hover { color: #086FFF; cursor: pointer; }
  //     .linkTag:hover { cursor: pointer; }
  // 静止时 cursor 是 auto，第 5 条判据判 False，元素整批落进
  // 「五条规则都不命中跳过」—— 用户报的「基本信息/关联关系/关联任务/案例执行
  // 四个侧边栏项和基线标签，鼠标移上去都是小手，为什么采不到」就是这一条。
  //
  // 解法不是去 hover 每个节点（3000+ 节点逐个 hover 不可行，还会触发浮层、
  // 改变页面状态，破坏「观察不改变被观察对象」）。而是**读样式表**：
  // 把所有「:hover 里设了 cursor:pointer」的规则收集一次，去掉 :hover
  // 得到静态选择器，再用 el.matches() 判。一次性 O(规则数)，之后每个节点
  // O(hover规则数)；实测这一页 16 条规则，整页多带 6 个节点、零噪音。
  //
  // `.a:hover .b {cursor:pointer}` 这种祖先 hover 的写法去掉 :hover 得到
  // `.a .b`，语义仍然对：鼠标在 b 上必然也在 a 上（b 在 a 里面）。
  const hover选择器 = [];
  for (const ss of Array.from(document.styleSheets)) {
    let rules;
    // 跨域样式表读 cssRules 会抛 SecurityError，忽略即可（拿不到就当没有）。
    try { rules = ss.cssRules; } catch (e) { continue; }
    if (!rules) continue;
    for (const ru of Array.from(rules)) {
      if (!ru.selectorText || !ru.style) continue;
      if (!/:hover/.test(ru.selectorText)) continue;
      if (ru.style.cursor !== 'pointer') continue;
      // 一条规则可以有多个逗号分隔的选择器，只取真的带 :hover 的那些
      for (const 一条 of ru.selectorText.split(',')) {
        if (!/:hover/.test(一条)) continue;
        const 去掉 = 一条.replace(/:hover/g, '').trim();
        if (去掉) hover选择器.push(去掉);
      }
    }
  }
  const hover才pointer = (el) => {
    for (const s of hover选择器) {
      try { if (el.matches(s)) return true; } catch (e) { /* 选择器不合法，跳过 */ }
    }
    return false;
  };
  // 「这个节点在人眼看来是不是小手」——现在有两个来源：当前 cursor，或 hover 规则。
  // 父子都是小手时只留外层（原来的 pc !== 'pointer' 守卫就是这个意思），
  // 否则一个人名 chip 会在 5 层嵌套上各报一次（实测放宽父守卫多带 37 个，
  // 其中 svg / img / u-tag-icon / avatar-container 这类纯噪音占绝大多数）。
  const 是小手 = (el) => {
    if (!el) return false;
    try {
      return getComputedStyle(el).cursor === 'pointer' || hover才pointer(el);
    } catch (e) { return false; }
  };

  const all = Array.from(document.body.querySelectorAll('*'));
  const raw = [];
  for (const el of all) {
    const tag = el.tagName.toLowerCase();
    if (SKIP_TAGS.has(tag)) { 账.标签黑名单跳过 += 1; continue; }
    if (!isVisible(el)) {
      账.不可见跳过 += 1;
      // 单独数一笔「本来是可交互的，只是此刻不可见」。这一笔才是真正值得看的：
      // 折叠区域、未展开的下拉、v-show 藏起来的那一份都落在这里，
      // 它们不是垃圾，是「换个状态再来采就能拿到」的东西。
      // 数字很大不等于有问题（整页几千个节点大多不可见），
      // 但它和这一笔一起看就能判断「是不是有一整块 UI 从没被展开过」。
      try {
        const cs0 = getComputedStyle(el);
        if (INTERACTIVE_TAGS.has(tag) || el.getAttribute('role')
            || el.hasAttribute('placeholder') || cs0.cursor === 'pointer') {
          账.不可见且本来可交互 += 1;
        }
      } catch (e) { /* getComputedStyle 对已脱离文档的节点会抛，忽略 */ }
      continue;
    }
    const cs = getComputedStyle(el);
    const reasons = [];
    if (INTERACTIVE_TAGS.has(tag)) reasons.push('交互标签');
    const role = el.getAttribute('role');
    if (role && INTERACTIVE_ROLES.has(role)) reasons.push('role=' + role);
    for (const a of cfg.businessAttrs) if (el.hasAttribute(a)) reasons.push('业务ID锚点');
    if (el.hasAttribute('placeholder')) reasons.push('输入框');
    // 第 5 条：小手的最外层。两个来源——当前就是 pointer，或只在 :hover 里是。
    // 父节点也是小手时不报自己（留外层，它才是挂 handler 的那个）。
    const 自己是小手 = cs.cursor === 'pointer';
    const 悬停才小手 = !自己是小手 && hover才pointer(el);
    if ((自己是小手 || 悬停才小手) && !是小手(el.parentElement)) {
      reasons.push(自己是小手 ? 'pointer起点' : 'hover才pointer');
      if (悬停才小手) 账.hover才pointer采到 += 1;
    }
    if (!reasons.length) { 账.五条规则都不命中跳过 += 1; continue; }

    // ── 命中测试：人类现在到底看不看得见它 ────────────────────────────
    // 放在可交互筛选**之后**是为了省时间：命中测试比读 computedStyle 贵一点，
    // 而这里只剩几十个候选了。判据与三笔账见 命中测试 与 账 的注释。
    const 命 = 命中测试(el);
    if (命.零尺寸) { 账.零尺寸跳过 += 1; continue; }
    if (!命.命中 && !命.在视口外) {
      // 确定被盖住 —— 滚动也救不回来（上面压着遮罩/固定列/透明覆盖层）。
      // 这一笔取代了 assemble 侧按 所属弹层容器 过滤背景元素的那一整套。
      账.被挡跳过 += 1;
      if (INTERACTIVE_TAGS.has(tag) || role || el.hasAttribute('placeholder')
          || cs.cursor === 'pointer') {
        账.被挡且本来可交互 += 1;
      }
      continue;
    }
    if (命.在视口外) 账.视口外留下 += 1;
    raw.push({ el, reasons, 视口外: !!命.在视口外 });
  }

  // 同 rect 同文本的父子只留外层：外层才是挂 handler 的那个。
  //
  // ⚠ 这条是猜测性丢弃，而且不可逆（元素不进表，后面所有环节都不知道它存在）。
  // 但它的**触发面比想象的小得多**，这一点实测确认过，值得写下来免得再误判：
  // 它要求父与子**都已经进了 raw**（都独立通过了可交互性筛选）。
  // 一度以为它会误伤这个形状：
  //     <div class="vxe-cell--wrapper" rowid="…"><span class="baseline-id">…</span>
  // 实测**不会** —— wrapper 没有 cursor:pointer、没有 role、不是交互标签，
  // 压根不在 raw 里，规则对这一对从不生效（合成 DOM 实测 同框父子丢子 = 0）。
  // 真正会命中的是「外层 div 和内层 span 都有 cursor:pointer 且同框同文本」，
  // 那种情况下事件冒泡，点哪个都一样，丢子留父是合理的。
  //
  // 想过改成「只标注不丢弃、把决定推迟到有真凭据时」，**没做**，两个理由：
  //   1. 那个「真凭据」不成立：第一档判据本该是 CDP 的 getEventListeners
  //      （谁真的挂了 handler），但这个站覆盖率只有 32/243 ——
  //      Vue 的合成事件大多取不到。没有 oracle，改完只会退化成
  //      「两个都留着、都点一遍」，元素数与动作数翻倍换来的仍然是猜。
  //   2. 触发面本来就小（见上），收益配不上代价。
  // 现在它撞没撞到、有没有在误伤，看 丢弃台账.同框父子丢子 与
  // 丢弃台账.同框丢掉的子里有语义类名 —— 后者非 0 才需要回来重新考虑这一条。
  const rawSet = new Set(raw.map(r => r.el));
  const kept = raw.filter(({ el }) => {
    let p = el.parentElement;
    while (p && p !== document.body) {
      if (rawSet.has(p)) {
        const a = el.getBoundingClientRect(), b = p.getBoundingClientRect();
        const same = Math.abs(a.width - b.width) < 2 && Math.abs(a.height - b.height) < 2
                  && Math.abs(a.left - b.left) < 2 && Math.abs(a.top - b.top) < 2;
        if (same && norm(el.innerText) === norm(p.innerText)) {
          账.同框父子丢子 += 1;
          // 这一笔才是判断这条规则有没有在误伤的关键：子有语义类名、
          // 而留下的父只有组件库噪音类名（vxe-cell--wrapper 那种），
          // 说明丢掉的正是能唯一定位的那个。span.baseline-id 就落在这里。
          if (semanticClasses(el).length && !semanticClasses(p).length) {
            账.同框丢掉的子里有语义类名 += 1;
          }
          return false;
        }
        return true;
      }
      p = p.parentElement;
    }
    return true;
  }).slice(0, cfg.elementCap);

  const elements = kept.map(({ el, reasons, 视口外 }, i) => {
    const attrs = {};
    for (const a of Array.from(el.attributes || [])) {
      const n = a.name.toLowerCase();
      if (n === 'class' || n === 'style') continue;
      if (n.startsWith('data-') || n.startsWith('aria-')
          || ['role','type','placeholder','title','href','name','value','disabled','for','tabindex'].includes(n)) {
        attrs[a.name] = cap(a.value, 120);
      }
    }
    const rect = el.getBoundingClientRect();
    return {
      序: i,
      tag: el.tagName.toLowerCase(),
      role: implicitRole(el),
      role显式: el.getAttribute('role') || null,
      类名: classesOf(el),
      稳定类名: stableClasses(el),
      语义类名: semanticClasses(el),
      状态类名: classesOf(el).filter(c => VOLATILE.test(c)),
      可见文本: cap(norm(el.innerText), cfg.textCap),
      自身文本: cap(ownText(el), cfg.textCap),
      属性: attrs,
      祖先链: chainOf(el, 5),
      祖先类名: ancestorClasses(el, 4),
      图标线索: iconHintOf(el),
      作用域: (ancestorScopes(el, 1)[0] || {}).sel || null,
      弹层容器: overlayOf(el),
      兄弟序号: el.parentElement
        ? Array.from(el.parentElement.children).filter(c => c.tagName === el.tagName).indexOf(el)
        : 0,
      矩形: { x: Math.round(rect.left), y: Math.round(rect.top),
              w: Math.round(rect.width), h: Math.round(rect.height) },
      真disabled: el.disabled === true || el.getAttribute('aria-disabled') === 'true',
      伪禁用: classesOf(el).some(c => /^(disabled|is-disabled)$/.test(c)) && el.disabled !== true,
      // 采集时它在视口外，命中测试对它没有发言权（elementFromPoint 只在视口内有效）。
      // 留着而不是丢掉：滚一下就能看到的东西不是「人类看不见」。
      // 下游要点它得先滚动，Playwright 的 click 会自动滚，所以这只是个提示。
      视口外: !!视口外,
      命中规则: reasons,
      候选: buildCandidates(el)
    };
  });

  // ── 全量签名集合（Pass 4 差分的原料）────────────────────────────
  // ⚠ 这个循环与 给页面拍状态指纹的轻量JS 里那个必须**逐条一致**，
  //   否则两个脚本算出的 state_key 不同，同一个状态会被登记两遍且不报错。
  const sigs = {};
  let sigCount = 0;
  for (const el of all) {
    if (SKIP_TAGS.has(el.tagName.toLowerCase())) continue;
    if (!isVisible(el)) continue;
    const sc = stableClasses(el).slice().sort();
    const t = cap(ownText(el), cfg.sigTextCap);
    if (!sc.length && !t) continue;
    // sel 与 key 分开算。⚠ 动画判定**必须只看 sel**，不能拿整个 key 去测：
    // animClassRe 的词尾边界是 `([-_.]|$)`，而 key 在类名后面接了 '|' + 文本，
    // 于是 `div.ant-wave|` 里 wave 后面是 '|' —— 既不是边界字符也不是串尾，
    // 正则不匹配、过滤静默失效、波纹重新溜进 state_key。这一条是写的时候真踩到的。
    const sel = el.tagName.toLowerCase() + (sc.length ? '.' + sc.join('.') : '');
    const key = sel + '|' + t;
    // 纯动画/过渡节点：命中动画类名**且自身无文本**才丢。
    // 第二个条件缺不得：antd 的过渡包装类（ant-fade / ant-zoom / ant-motion）裹在
    // 真弹窗外面，弹窗内容的签名挂在后代节点上、各自带文本；包装节点自身无文本。
    // 少了它会把真弹窗的判据一起剔掉。判据与那次事故记在 core/词表.动画类名词表。
    if (!t && ANIM.test(sel)) { 账.动画节点跳过 += 1; continue; }
    if (!(key in sigs)) {
      if (sigCount >= cfg.sigCap) continue;
      sigs[key] = 0;
      sigCount++;
    }
    sigs[key] += 1;
  }

  // ── 当前挂在 body 上的弹层容器 ───────────────────────────────────
  const overlays = listOverlays(160);

  // ⚠ 最外层这四个键（meta / elements / signatures / overlays）以及 meta.url、
  //   meta.hash 不能中文化：Python 侧是按字符串取的
  //   （explore.py 的 result.get("elements")、state_key() 的 snap.get("signatures")、
  //    diff_snapshots() 的 before.get("overlays")）。
  //   取不到只会得到 None 而不会报错 —— signatures 拿成 None，签名集合恒为空，
  //   所有状态的 state_key 都一样，探索一个状态都发现不了，同样是静默失效。
  //   里层的中文键（标题 / 视口 / 元素总数 / 截断 …）是安全的，Python 侧就是按中文取的。
  return {
    meta: {
      url: location.href,
      hash: location.hash,
      标题: document.title,
      视口: { w: innerWidth, h: innerHeight },
      元素总数: all.length,
      候选原始数: raw.length,
      候选保留数: kept.length,
      签名条数: sigCount,
      截断: { 元素: raw.length > cfg.elementCap, 签名: sigCount >= cfg.sigCap },
      // 丢弃台账：每一处 continue / filter / slice 丢了多少。
      // 一次 --report-only 就能看出哪个 cap 在真的干活、哪个从来没碰到过，
      // 从此按实测调，不按拍脑袋的数调。键名是中文，Python 侧按中文取。
      丢弃台账: 账
    },
    elements: elements,
    signatures: sigs,
    overlays: overlays
  };
}
"""

指纹JS = r"""
(cfg) => {
  const VOLATILE = new RegExp(cfg.volatileClassRe);
  // 'i' 是必须的，理由与元素脚本里同名的那处相同（Python 侧是 re.I）。
  const ANIM = new RegExp(cfg.animClassRe, 'i');
  const SKIP_TAGS = new Set(['svg','path','use','g','defs','circle','rect','line','polygon',
    'script','style','br','hr','tspan','text','template']);
  const norm = (s) => (s || '').replace(/\s+/g, ' ').trim();
  const cap = (s, n) => (s && s.length > n ? s.slice(0, n) : (s || ''));
  const isVisible = (el) => {
    if (!el || !el.getClientRects || !el.getClientRects().length) return false;
    const cs = getComputedStyle(el);
    return cs.visibility !== 'hidden' && cs.opacity !== '0';
  };
  const classesOf = (el) => Array.from(el.classList || []);
  const stable = (el) => classesOf(el).filter(c => c && !VOLATILE.test(c));
  const ownText = (el) => {
    let t = '';
    for (const n of el.childNodes) if (n.nodeType === 3) t += n.nodeValue;
    return norm(t);
  };
  // document.body 会是 null —— 不是理论风险，实测崩过：
  //   Page.evaluate: TypeError: Cannot read properties of null (reading 'querySelectorAll')
  // 触发时机是「文档正在被替换」的那一瞬间：goto/reload 已经卸载旧文档、
  // 新文档的 body 还没建出来，而复位循环恰好在这一刻拍了一张。
  // 抛出去的后果是整轮探索带着 traceback 结束（实测丢了 34 个状态之后的全部进度）。
  // 返回空签名而不是抛：调用方本来就有「首张只有 N 条签名」这条判据，
  // 空签名会被当成「还没稳定」，下一次轮询自然重来 —— 正是想要的行为。
  // 键名与正常返回保持一致（hash / signatures / overlays / 焦点标签），
  // 否则 state_key() 与 diff_snapshots() 会拿到 None 而不报错 —— 又是一处静默失效。
  const 根 = document.body;
  if (!根) {
    return { hash: location.hash, signatures: {}, overlays: [],
             动画节点跳过: 0, 焦点标签: null, 文档未就绪: true };
  }
  const sigs = {};
  let n = 0;
  let 动画节点跳过 = 0;
  for (const el of Array.from(根.querySelectorAll('*'))) {
    if (SKIP_TAGS.has(el.tagName.toLowerCase())) continue;
    if (!isVisible(el)) continue;
    const sc = stable(el).slice().sort();
    const t = cap(ownText(el), cfg.sigTextCap);
    if (!sc.length && !t) continue;
    // 与元素脚本里那个签名循环**逐条一致**，改一处必须改两处。
    // 动画判定只看 sel、不看 key，理由（词尾边界被 '|' 挡掉）见那边的注释。
    const sel = el.tagName.toLowerCase() + (sc.length ? '.' + sc.join('.') : '');
    const key = sel + '|' + t;
    if (!t && ANIM.test(sel)) { 动画节点跳过 += 1; continue; }
    if (!(key in sigs)) { if (n >= cfg.sigCap) continue; sigs[key] = 0; n++; }
    sigs[key] += 1;
  }
  // 补齐共用浮层判定需要的别名（classesOf / norm / cap / isVisible 上面已有）
  const semanticClasses = stable;   // 签名侧不区分语义与稳定类名
  const stableClasses = stable;
  const esc = (s) => (window.CSS && CSS.escape) ? CSS.escape(s) : String(s).replace(/([^\w-])/g, '\\$1');

  const OVERLAY_CLASS_RE = /(modal|dialog|popover|dropdown|drawer|tooltip|overlay|popup)/i;

  // 不假设浮层挂在 body 上。这里踩过两次坑，都记下来：
  //   第一次：判定要求「body 的直接子元素自己带浮层类名」，而 ant-design-vue 4 的 Modal
  //           外层是无 class 的 wrapper div、浮层类名在它子元素上 → 全漏。
  //   第二次：改成「body 直接子元素或其直接子元素」之后弹窗对了，
  //           但 popover / dropdown / select 仍然全漏 —— 它们**根本不在 body 下**
  //           （很多项目把 getPopupContainer 设成触发元素的父节点，避开滚动问题）。
  //           实测表现：7 个弹层态全部「没有容器」、门禁判失败；
  //           而 hover→元素 那条分支因为拿不到新增浮层，压根没被触发。
  // 所以现在全 DOM 找，判据只用浮层自身的特征：类名/role + 脱离文档流的定位。
  const OVERLAY_SEL =
    '[class*="popover"],[class*="dropdown"],[class*="modal"],[class*="dialog"],' +
    '[class*="drawer"],[class*="tooltip"],[class*="overlay"],[class*="popup"],' +
    '[role="dialog"],[role="tooltip"],[role="menu"],[role="listbox"],[aria-modal="true"]';

  // 遮罩背板不是内容容器。它满足浮层的全部形式特征（fixed + 类名带 modal），
  // 但里面什么都没有；不排掉它就会被当成 新增弹层[0]、进而成为状态的「容器」，
  // 而下游拿这个容器去 scope 内部元素会一个都找不到。
  const MASK_RE = /(mask|backdrop)/i;

  const isOverlayNode = (el) => {
    if (!el || el.nodeType !== 1 || !el.matches(OVERLAY_SEL)) return false;
    if (MASK_RE.test(classesOf(el).join(' '))) return false;
    if (!isVisible(el)) return false;
    // 浮层一定脱离文档流。这一条把「触发器」滤掉：
    // .ant-dropdown-trigger 类名里也带 dropdown，但它是 position: static。
    const cs = getComputedStyle(el);
    return cs.position === 'fixed' || cs.position === 'absolute';
  };

  // 只留最外层：任何祖先已经是浮层节点的，都不是根
  const overlayRoots = () => {
    const found = Array.from(document.querySelectorAll(OVERLAY_SEL)).filter(isOverlayNode);
    const set = new Set(found);
    return found.filter(el => {
      let p = el.parentElement;
      while (p) { if (set.has(p)) return false; p = p.parentElement; }
      return true;
    });
  };

  const overlaySelectorOf = (root) => {
    let pick = stableClasses(root).filter(c => OVERLAY_CLASS_RE.test(c));
    if (!pick.length) pick = semanticClasses(root);
    if (!pick.length) pick = stableClasses(root);
    if (!pick.length) {
      const r = root.getAttribute('role');
      return r ? root.tagName.toLowerCase() + '[role="' + r + '"]' : null;
    }
    return '.' + pick.map(esc).join('.');
  };

  // 元素所属的浮层容器：向上找最外层的那个浮层节点
  const overlayContainerOf = (el) => {
    let p = el, outermost = null;
    while (p && p !== document.body) {
      if (isOverlayNode(p)) outermost = p;
      p = p.parentElement;
    }
    return outermost ? overlaySelectorOf(outermost) : null;
  };

  const listOverlays = (textCap) => overlayRoots()
    .map(el => {
      const titleEl = el.querySelector(
        '[class*="modal-title"],[class*="dialog-title"],[class*="popover-title"],' +
        '[class*="drawer-title"],[role="heading"]');
      return {
        选择器: overlaySelectorOf(el),
        类名: classesOf(el),
        标题: titleEl ? cap(norm(titleEl.textContent), 40) : null,
        文本摘要: cap(norm(el.innerText), textCap)
      };
    })
    .filter(o => o.选择器)
    // 内容多的排前面：下游取 新增弹层[0] 当状态容器，得拿到真正装东西的那一层
    .sort((a, b) => (b.文本摘要 || '').length - (a.文本摘要 || '').length);

  const overlays = listOverlays(120);
  // ⚠ hash / signatures / overlays 三个键名不能中文化，理由同上：
  //   state_key() 与 diff_snapshots() 直接按这三个字符串取值，取不到不报错只给 None。
  return { hash: location.hash, signatures: sigs, overlays: overlays,
           动画节点跳过: 动画节点跳过,
           焦点标签: document.activeElement ? document.activeElement.tagName.toLowerCase() : null };
}
"""

分身体检JS = r"""
(arg) => {
  const nodes = Array.from(document.querySelectorAll(arg.selector));
  const 简述 = (el) => {
    if (!el) return null;
    const cls = (el.className && typeof el.className === 'string')
      ? '.' + el.className.trim().split(/\s+/).slice(0, 3).join('.') : '';
    return el.tagName.toLowerCase() + cls;
  };
  const 是自己或后代 = (命中, self) => !!命中 && (命中 === self || self.contains(命中));
  return {
    匹配: nodes.length,
    分身: nodes.map((el, i) => {
      const rects = el.getClientRects();
      if (!rects || !rects.length) {
        return { 序号: i, 可见: false, 可点: false, 判据: '没有布局盒（display:none 或未渲染）' };
      }
      const cs = getComputedStyle(el);
      if (cs.visibility === 'hidden' || cs.display === 'none' || parseFloat(cs.opacity || '1') === 0) {
        return { 序号: i, 可见: false, 可点: false,
                 判据: 'computedStyle 判定不可见：visibility=' + cs.visibility
                       + ' display=' + cs.display + ' opacity=' + cs.opacity };
      }
      const r = el.getBoundingClientRect();
      // 中心 + 四个内缩 25% 的点。异形元素中心可能落在空隙里，多试几个点。
      const 试点 = [
        [r.left + r.width / 2, r.top + r.height / 2],
        [r.left + r.width * 0.25, r.top + r.height * 0.5],
        [r.left + r.width * 0.75, r.top + r.height * 0.5],
        [r.left + r.width * 0.5, r.top + r.height * 0.25],
        [r.left + r.width * 0.5, r.top + r.height * 0.75],
      ];
      let 挡路者 = null;
      let 在视口外 = false;
      for (const [x, y] of 试点) {
        if (x < 0 || y < 0 || x > innerWidth || y > innerHeight) { 在视口外 = true; continue; }
        const 命中 = document.elementFromPoint(x, y);
        if (是自己或后代(命中, el)) {
          return { 序号: i, 可见: true, 可点: true,
                   矩形: { x: Math.round(r.left), y: Math.round(r.top),
                           w: Math.round(r.width), h: Math.round(r.height) },
                   判据: 'elementFromPoint 在该点命中它自己或其后代' };
        }
        if (命中 && !挡路者) 挡路者 = 简述(命中);
      }
      return {
        序号: i, 可见: true, 可点: false,
        矩形: { x: Math.round(r.left), y: Math.round(r.top),
                w: Math.round(r.width), h: Math.round(r.height) },
        判据: 在视口外 && !挡路者
          ? '五个试点全在视口外，需要先滚动才能判定'
          : '五个试点都被别的节点接住，挡路者 ' + (挡路者 || '未知'),
      };
    }),
  };
}
"""



# ══════════════════════════════════════════════════════════════════════
#  命令行层：三个模块共用这一段，所以放在这里
#
#  为什么要有命令行而不只是 Python API：调用方是 AI，它最自然的用法是
#  「跑一条命令、读一段 JSON」，而不是写一段 import 再管会话生命周期。
#  用法与实测耗时见同目录 SKILL.md。
# ══════════════════════════════════════════════════════════════════════
import argparse as _argparse
import json as _json


def 加公共参数(ap: "_argparse.ArgumentParser") -> None:
    """--url / --做 / --headed / --预热影子库 / --输出。三个模块的命令行都用这一套。"""
    ap.add_argument("--url", required=True, metavar="完整URL",
                    help="要看的页面的**完整**地址，必须 http:// 或 https:// 开头。"
                         "不接受相对路径、不做域名补全 —— 环境写错了要一眼看出来。"
                         "例：https://dev-mude-r.tsp.mioffice.cn/#/req-mgmt/tabs/"
                         "baseline?projectBusId=3dce85a6-1fa9-4726-920c-066c5aca1803")
    ap.add_argument("--做", nargs="*", default=[], metavar="动作:定位[=值]",
                    help="观察之前先执行的动作序列，用来走到嵌套状态。"
                         "格式 动作:定位 或 动作:定位=值，"
                         "例 'click:button.create-btn' 'fill:input.ant-input=基线A'。"
                         "同胞元素用 #文本= 后缀区分（不用嵌套引号，PowerShell 友好）："
                         "'click:button.u-button#文本=确定'。"
                         "⚠ 带这个参数就会预热影子库（可能有写操作）")
    ap.add_argument("--headed", action="store_true", help="显示浏览器窗口（默认无头）")
    ap.add_argument("--预热影子库", choices=["自动", "是", "否"], default="自动",
                    help="自动=有 --做 就热、纯观察就跳过（省约 60 秒）。"
                         "要做写操作**不要**填否")
    ap.add_argument("--输出", metavar="文件",
                    help="把 JSON 写到文件而不是打印到 stdout")
    ap.add_argument("--紧凑", action="store_true", help="JSON 不缩进，省 token")
    ap.add_argument("--遇错即停", action="store_true",
                    help="--做 里某一步失败就不做后面的。"
                         "不加的话后面照旧执行 —— 实测过：第 2 步超时之后第 3~5 步"
                         "继续在没填完的表单上点，最后又点了一次确定")


def 规范化定位(定位: str) -> str:
    """把 `#文本=确定` / `#含文本=创建` 这种后缀翻成 Playwright 的文本伪类。

    为什么要这个糖（一个真踩到的坑）
    ──────────────────────────
    同胞元素只能靠文本区分（弹窗里「确定」和「取消」都是 button.u-button、匹配 2），
    而 Playwright 的写法是 `:text-is("确定")` —— **里面必须有双引号**。
    在 PowerShell 里 `--做 'click:sel:text-is("确定")'` 的双引号会被吃掉，
    Playwright 收到 `:text-is(确定)` 然后报
    `"text-is" engine expects a single string`。
    这个仓库是 PowerShell，所以这个坑对每个调用方都成立。

    有了这个糖就不用嵌套引号：
        sel#文本=确定    → sel:text-is("确定")     全串相等
        sel#含文本=创建   → sel:has-text("创建")    包含
    """
    for 后缀, 伪类 in (("#文本=", "text-is"), ("#含文本=", "has-text")):
        if 后缀 in 定位:
            前, 值 = 定位.split(后缀, 1)
            值 = 值.strip().strip('"').strip("'")
            if '"' in 值:
                raise SystemExit(f"{后缀} 的值里不能再有双引号：{值!r}")
            return f'{前.strip()}:{伪类}("{值}")'
    return 定位.strip()


def 解析动作(串: str) -> tuple[str, str, str | None]:
    """把 `动作:定位[#值=文本]` 拆成 (动作, 定位, 值)。

        click:button.create-btn                    → ('click', 'button.create-btn', None)
        click:button.u-button#含文本=确定            → ('click', 'button.u-button:has-text("确定")', None)
        fill:input.x#值=基线A                       → ('fill', 'input.x', '基线A')
        fill:input[placeholder='请输入基线名称']#值=A  → ('fill', "input[placeholder='请输入基线名称']", 'A')
        press:body#值=Escape                       → ('press', 'body', 'Escape')

    ⚠ 为什么值要用 `#值=` 而不是裸 `=`（一个真踩到的坑）
    ────────────────────────────────────────────
    最早是按第一个 `=` 切的，于是
        fill:input[placeholder='请输入基线名称']=基线A
    被切成 定位=`input[placeholder`、值=`'请输入基线名称']=基线A` ——
    **属性选择器里的 `=` 把它劈开了**，报
    `Unexpected token "" while parsing css selector`。
    裸 `=` 仍然支持（按**最后一个** `=` 切，兼容 `fill:input.x=值` 这种简单写法），
    但选择器里带 `=` 时请用 `#值=`，它没有歧义。
    """
    if ":" not in 串:
        raise SystemExit(f"--做 的格式不对：{串!r}，要 动作:定位 或 动作:定位#值=文本")
    动作, 其余 = 串.split(":", 1)
    动作 = 动作.strip()
    if 动作 not in ("click", "dblclick", "hover", "fill", "press"):
        raise SystemExit(f"不支持的动作 {动作!r}（只有 click/dblclick/hover/fill/press）")

    # 1 首选：显式的 #值= 分隔符，没有歧义
    if "#值=" in 其余:
        定位, 值 = 其余.split("#值=", 1)
        return 动作, 规范化定位(定位), 值
    # 2 fill / press 才需要值。按**最后一个** `=` 切，这样属性选择器里的 `=` 不会误伤。
    #   但 #文本= / #含文本= 后缀本身带 `=`，要先把它摘出来再判。
    文本后缀 = next((s for s in ("#含文本=", "#文本=") if s in 其余), None)
    if 文本后缀:
        前, 之后 = 其余.split(文本后缀, 1)
        if 动作 in ("fill", "press") and "=" in 之后:
            文本值, 值 = 之后.rsplit("=", 1)
            return 动作, 规范化定位(f"{前}{文本后缀}{文本值}"), 值
        return 动作, 规范化定位(f"{前}{文本后缀}{之后}"), None
    if 动作 in ("fill", "press") and "=" in 其余:
        定位, 值 = 其余.rsplit("=", 1)
        return 动作, 规范化定位(定位), 值
    return 动作, 规范化定位(其余), None


def 打开并按需做(args, 最后操作前回调=None) -> tuple["会话", dict, list[dict]]:
    """命令行三个入口的公共前半段：校验入参 → 起会话 → 打开 → 按 --做 执行动作序列。

    调用方负责最后 s.关闭()。返回 (会话, 打开自检, 每个动作的差分)。
    ``最后操作前回调`` 若提供，只在动作序列最后一步即将执行前调用一次，
    入参是活的 page。它让观察命令能够比较“最后一步前 → 最后一步后”，
    不改变其他命令原有的返回值和执行顺序。

    ⚠ 入参校验**必须排在起浏览器之前**。踩过：URL 残缺的检查原来在 打开() 里，
    于是要先付一次 CAS 登录（约 20 秒）才告诉你「--url 写错了」。
    --做 的格式也一样 —— 第五步的动作串拼错，不该等前四步都做完才发现。
    """
    检查是完整url(args.url)
    动作序列 = [解析动作(串) for 串 in args.做]      # 全部先解析，格式错当场退出

    要热 = (args.预热影子库 == "是"
          or (args.预热影子库 == "自动" and bool(args.做)))
    s = 会话(headless=not args.headed, 预热影子库=要热).启动()
    自检 = s.打开(args.url)
    做了: list[dict] = []
    for 序号, (动作, 定位, 值) in enumerate(动作序列):
        if 最后操作前回调 is not None and 序号 == len(动作序列) - 1:
            最后操作前回调(s.page)
        r = s.做(定位, 动作, 值)
        做了.append(r)
        if r.get("错误") and getattr(args, "遇错即停", False):
            print(f"！第 {len(做了)} 步失败，--遇错即停 生效，剩下 "
                  f"{len(动作序列) - len(做了)} 步不做了", flush=True)
            break
    return s, 自检, 做了


def 输出(结果: dict, args) -> None:
    文本 = _json.dumps(结果, ensure_ascii=False,
                     indent=None if args.紧凑 else 2)
    if args.输出:
        with open(args.输出, "w", encoding="utf-8") as f:
            f.write(文本)
        print(f"已写入 {args.输出}（{len(文本) / 1024:.1f} KB）")
    else:
        print(文本)


def _main() -> int:
    ap = _argparse.ArgumentParser(
        prog="python -m tools.page_object_build.浏览器会话",
        description="打开页面、执行动作、看页面变化的差分。只想看有什么请用"
                    " 可点元素 / 可见结构 那两个入口。")
    # --准备 / --清除会话 是两个独立模式，不需要 --url，所以放在 加公共参数 之前，
    # 并把 --url 改成非必填、在真正要打开页面时再检查。
    ap.add_argument("--准备", action="store_true",
                    help="登录 + 预热影子库各一次，写缓存。之后所有命令自动复用 ——"
                         "不再重登、不再重热影子库（每条命令省约 60 秒）。先跑这个")
    ap.add_argument("--清除会话", action="store_true",
                    help="删掉共享会话缓存，下次重新登录 + 预热")
    ap.add_argument("--url", metavar="完整URL", default=None,
                    help="要看的页面的**完整**地址，http(s):// 开头，不做域名补全")
    ap.add_argument("--做", nargs="*", default=[], metavar="动作:定位[#值=文本]",
                    help="观察前执行的动作序列，格式 动作:定位、动作:定位#值=文本，"
                         "同胞元素用 #含文本= 区分。⚠ 带它就可能有写操作")
    ap.add_argument("--headed", action="store_true", help="显示浏览器窗口（默认无头）")
    ap.add_argument("--预热影子库", choices=["自动", "是", "否"], default="自动")
    ap.add_argument("--输出", metavar="文件")
    ap.add_argument("--紧凑", action="store_true")
    ap.add_argument("--遇错即停", action="store_true")
    ap.add_argument("--读", nargs="*", default=[], metavar="定位",
                    help="动作做完之后读这些选择器的文本（取整列值就用它）")
    args = ap.parse_args()

    if args.清除会话:
        print("已删除共享会话缓存" if 清除共享会话() else "没有共享会话缓存可删")
        if not args.准备:
            return 0
    if args.准备:
        信息 = 准备共享会话(headless=not args.headed)
        print(f"\n共享会话已就绪：runId {信息['runId']}…｜账号 {信息['账号']}｜"
              f"影子库 {信息['影子库']}｜有效约 {信息['有效期小时']} 小时")
        print("  之后每条 可点元素 / 可见结构 / 浏览器会话 命令都会自动复用它，"
              "跳过登录与影子库预热。")
        print(f"  缓存文件：{信息['缓存文件']}（要重来就 --清除会话 或等它过期）")
        return 0

    if not args.url:
        raise SystemExit("要么给 --url 打开一个页面，要么用 --准备 / --清除会话。"
                         "三者至少给一个。")
    s, 自检, 做了 = 打开并按需做(args)
    try:
        结果 = {"打开": 自检, "做了": 做了,
              "读到": {定位: s.读(定位) for 定位 in args.读}}
    finally:
        s.关闭()
    输出(结果, args)
    # 退出码：2 = 页面没打开成（白屏 / 落错页），1 = 有动作报错，0 = 正常。
    if 自检["是白屏"]:
        print("！白屏，页面没打开成", flush=True)
        return 2
    if any(x.get("错误") for x in 做了):
        print("！有动作执行失败，看 做了[].错误", flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
