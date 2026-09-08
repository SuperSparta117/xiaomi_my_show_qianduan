---
name: page_object_build
description: Use this skill when you need to inspect a live web page before writing or fixing UI automation code — to find out what is clickable and how to address it (selectors with measured match counts, occluded elements already excluded), or what is on the page semantically (roles, accessible names, column headers, read-only text), or what toast/validation message an action produces. Triggers on phrases like "看看页面上有什么元素"、"这个按钮怎么定位"、"页面对象"、"元素定位器"、"找不到元素"、"选择器匹配多个"、"勘查页面"、"提示文案是什么"、"page object"、"元素采集". Runs a real logged-in browser against the MUDE-R site. Not for generating test cases from requirement docs — that is generate-testcases.
---
 
# 页面现场勘查
 
在真实浏览器里回答三个问题：**我能点什么、怎么点**、**这页上有什么、是什么**、**点了会弹出什么提示**。
 
三个命令行入口：
 
| 命令 | 回答 | 给你什么 | 给不了什么 |
|---|---|---|---|
| `可点元素` | 我能点什么、怎么点 | 定位器 + 实测匹配数 + 已排除被遮挡的 | 语义（只能从类名猜） |
| `可见结构` | 这页有什么、是什么、层级如何 | 去掉无意义元素之后的 DOM 结构 + 分区/字段/富文本/表格 + aria + 只读文本 | 定位器 |
| `浏览器会话` | 点了会发生什么 | 动作前后的页面差分（含提示文案）、读整列值 | — |
 
前两个**互补不重叠**：要点东西看 `可点元素`，要断言看 `可见结构`。
 
## 先跑一次 `--准备`，之后所有命令快 60 秒
 
影子库按 runId 隔离，而每条命令是独立进程、各生成一个新 runId，于是**默认每条命令都重新复制一遍影子库（约 60 秒）**。跑一次 `--准备` 把登录和影子库预热一次付清，写进缓存文件，之后所有命令自动复用：
 
```bash
python -m tools.page_object_build.浏览器会话 --准备
```
 
跑完之后每条 `可点元素` / `可见结构` / `浏览器会话` 命令都会**自动**认这个缓存，跳过 CAS 登录和影子库预热——不用你 export 任何环境变量。实测：准备那次约 80 秒，之后每条命令约 **18~20 秒**（原来每条 80~90 秒）。
 
缓存有效约 5 小时（影子库后端存活 6 小时）。过期后命令会提示你重跑 `--准备`。要提前作废：
 
```bash
python -m tools.page_object_build.浏览器会话 --清除会话
```
 
一串勘查任务开头先 `--准备`，是标准姿势。
 
## URL 必须写全
 
`--url` 只接受 `http://` / `https://` 开头的**完整地址**，不接受相对路径、不做域名补全。写错了会直接报错并提示当前配置的域名（在开浏览器**之前**就退出，不浪费登录时间）。
 
这是刻意的：环境（dev / staging）写错了应该一眼看出来，不该靠配置兜。
 
## 常用命令
 
**开头先跑这一次**（登录 + 预热影子库，之后所有命令复用、每条省约 60 秒）：
 
```bash
python -m tools.page_object_build.浏览器会话 --准备      # 登录 + 预热影子库各一次，写缓存
python -m tools.page_object_build.浏览器会话 --清除会话   # 作废缓存，下次重新登录 + 预热
```
 
看这一页能点什么（只回能直接点的，省一半 token）：
 
```bash
python -m tools.page_object_build.可点元素 \
    --url 'https://dev-mude-r.tsp.mioffice.cn/#/req-mgmt/tabs/baseline?projectBusId=3dce85a6-1fa9-4726-920c-066c5aca1803' \
    --只要有定位
```
 
按名字找一个元素（`--文本含` 不区分大小写）：
 
```bash
python -m tools.page_object_build.可点元素 \
    --url 'https://dev-mude-r.tsp.mioffice.cn/#/req-mgmt/tabs/baseline?projectBusId=3dce85a6-1fa9-4726-920c-066c5aca1803' \
    --文本含 创建 --只要有定位
```
 
看这一页的完整层级结构、aria 和只读文本：
 
```bash
python -m tools.page_object_build.可见结构 \
    --url 'https://dev-mude-r.tsp.mioffice.cn/#/req-mgmt/tabs/baseline?projectBusId=3dce85a6-1fa9-4726-920c-066c5aca1803'
```
 
只要“剥洋葱”后的页面结构（不输出 aria 和扁平只读文本，大幅省 token）：
 
```bash
python -m tools.page_object_build.可见结构 \
    --url 'https://dev-mude-r.tsp.mioffice.cn/#/req-mgmt/req-info?projectBusId=73146101-1227-4feb-b46e-598a93069d73&reqBusId=104cfae3-4881-4ef2-8097-47c905069812&reqInfoTab=basic' \
    --只要页面结构
```
 
只看指定语义分区。`--分区` 按标题包含匹配，只过滤 `页面结构.分区`，完整 DOM 树仍然保留，避免漏元素：
 
```bash
python -m tools.page_object_build.可见结构 \
    --url 'https://dev-mude-r.tsp.mioffice.cn/#/req-mgmt/req-info?projectBusId=73146101-1227-4feb-b46e-598a93069d73&reqBusId=104cfae3-4881-4ef2-8097-47c905069812&reqInfoTab=basic' \
    --只要页面结构 --分区 基本信息
```
 
页面结构的处理顺序固定为：从 `body` 完整采集 → 只删除确定不可见/技术节点 → 折叠无语义的单子节点包装层 → 增强分区、字段组、富文本和表格。分区既包括“标题 + 后续兄弟内容”，也包括没有标题前缀但自身有内容的独立导航、摘要卡片、侧边栏、操作面板、弹层，以及**通用浮层**。浮层不靠业务类名识别，而是按“脱离正常文档流、绝对/固定定位、且不在页面主体内容里”的形态判定，因此下拉、气泡、菜单、提示这类 portal 到 body 的层都能被捕捉。因为观察走 `page.evaluate`、不移动鼠标也不触发 blur，鼠标移出才消失的浮层在采集时仍然存在。每个分区都保留 `内容结构`：使用与整页结构相同的标签、类名、属性、文本和子节点层级；`文本项`、`字段`、`表格`、`富文本` 只是方便 AI 快速读取的摘要，不能替代 `内容结构`。无法识别的内容仍以普通 DOM 节点保留；被遮挡节点只标记，不从结构树删除。
 
命令带 `--做` 时，工具会在最后一个操作执行前额外采一次页面结构，并把最后一步前后的差集写入：
 
```text
可见结构.页面结构.操作之后的页面结构
```
 
它与 `页面结构` 同构，含三个子键：
 
```text
去掉无意义元素之后的dom结构   新出现或变化的 DOM 子树（节点级递归差；全新子树整块保留，
                             已有节点只是某后代变了就只回那条变化链）
分区                         新出现的分区，或已有分区里新增/变化的内容
统计                         比较范围、最后操作、新增或变化的根节点数与分区数
```
 
如果有连续多步操作，只比较最后一步执行前和执行后，不把前面步骤造成的变化混入。
 
只找某段扁平文案（大幅省 token；不裁剪页面结构）：
 
```bash
python -m tools.page_object_build.可见结构 \
    --url 'https://dev-mude-r.tsp.mioffice.cn/#/req-mgmt/tabs/baseline?projectBusId=3dce85a6-1fa9-4726-920c-066c5aca1803' \
    --文本含 创建时间
```
 
**先点开弹窗，再看弹窗里有什么元素可操作可做动作**（`--做` 是动作序列，观察前执行）：
```bash
python -m tools.page_object_build.可点元素 \
    --url 'https://dev-mude-r.tsp.mioffice.cn/#/req-mgmt/tabs/baseline?projectBusId=3dce85a6-1fa9-4726-920c-066c5aca1803' \
    --做 'click:div.btn > button.css-1p3hq3p.create-btn' \
    --在浮层内 .ant-modal-wrap.create-baseline-modal
```
 
**先连续点两个元素，打开弹窗，看弹窗里面有什么元素可见**
```bash
python -m tools.page_object_build.可见结构 \
    --url 'https://dev-mude-r.tsp.mioffice.cn/#/req-mgmt/req-info?projectBusId=73146101-1227-4feb-b46e-598a93069d73'\
    --做 'click:.flex-m-c.pointer' 'click:.operate-records-panel .user-selector .ant-select-selector'
    --只要页面结构
```
 
连续点击时的命令，看页面发生了什么变化 + 弹出什么提示（判断"成没成"就靠这个）：
```bash
python -m tools.page_object_build.浏览器会话 \
    --url 'https://dev-mude-r.tsp.mioffice.cn/#/req-mgmt/tabs/baseline?projectBusId=3dce85a6-1fa9-4726-920c-066c5aca1803' \
    --做 'click:div.btn > button.css-1p3hq3p.create-btn' 'click:div.custom-modal-footer button.u-button#含文本=确定'
```
 
填表单 + 提交（`#值=` 传值，`#含文本=` 区分同胞按钮）：
```bash
python -m tools.page_object_build.浏览器会话 \
    --url 'https://dev-mude-r.tsp.mioffice.cn/#/req-mgmt/tabs/baseline?projectBusId=3dce85a6-1fa9-4726-920c-066c5aca1803' \
    --做 'click:div.btn > button.css-1p3hq3p.create-btn' \
       "fill:input[placeholder='请输入基线名称']#值=基线A" \
       "fill:textarea[placeholder='请输入基线描述']#值=描述内容" \
       'click:div.custom-modal-footer button.u-button#含文本=确定'
```
 
取整列的值（aria 给不了，只能这样取）：
```bash
python -m tools.page_object_build.浏览器会话 \
    --url 'https://dev-mude-r.tsp.mioffice.cn/#/req-mgmt/tabs/baseline?projectBusId=3dce85a6-1fa9-4726-920c-066c5aca1803' \
    --读 'td.col_4' 'td.col_2'
```
 
一个选择器匹配多个时，定出该点第几个：
 
```bash
python -m tools.page_object_build.可点元素 \
    --url 'https://dev-mude-r.tsp.mioffice.cn/#/req-mgmt/tabs/baseline?projectBusId=3dce85a6-1fa9-4726-920c-066c5aca1803' \
    --定分身 'li.ant-menu-submenu > div.ant-menu-submenu-title'
```
 
## 选择器写法：三个后缀（PowerShell 友好，不用嵌套引号）
 
```
sel#含文本=确定   → sel:has-text("确定")    包含。**同胞按钮用这个**
sel#文本=确定     → sel:text-is("确定")     全串相等
sel#值=基线A      → fill / press 的值
```
 
`#值=` 不是可选的糖：选择器里带 `=`（属性选择器）时**必须**用它。裸 `=` 会按最后一个等号切，`fill:input[placeholder='x']=值` 这种能用，但值里再有 `=` 就得用 `#值=`。
 
CSS 属性选择器里用**单引号**：`input[placeholder='请输入基线名称']`，整个参数用双引号包起来。在 PowerShell 里反过来写（外单内双）双引号会被吃掉。
 
## 公共参数
 
```
--url 完整URL     必填，http(s):// 开头
--做 动作:定位[#值=文本]   观察前执行的动作序列，可给多个
                  动作只有 click / dblclick / hover / fill / press
                  可见结构会额外采集最后一步前后的分区差集，写入
                  页面结构.操作之后的新增分区；多步时只比较最后一步
--遇错即停        --做 里某步失败就不做后面的（默认继续，容易在残局上误操作）
--输出 文件        JSON 写文件而不是打 stdout（大输出建议用，然后读文件）
--紧凑            JSON 不缩进，省 token
--headed          显示浏览器窗口（默认无头）
--预热影子库 自动|是|否   默认「自动」：有 --做 就预热、纯观察就跳过。
                  跑过 --准备 之后这个参数无所谓了，一律复用缓存
```
 
`浏览器会话` 独有的两个模式（不需要 --url）：
 
```
--准备            登录 + 预热影子库各一次，写缓存。之后所有命令复用
--清除会话        删缓存，下次重新登录 + 预热
```
 
`可见结构` 独有参数：
 
```
--只要页面结构     只输出完整 DOM 结构树和语义分区，不采 aria/扁平只读文本
--分区 标题         只返回标题包含该文字的语义分区；完整 DOM 树不裁剪
--结构节点上限 N   结构树最多保留 N 个节点，默认 2000；撞限会标记“截断”
--无aria           不采 aria 快照
--无只读文本       不采经过遮挡命中测试的扁平文本
--文本含 字串       只过滤扁平只读文本，不影响页面结构树
--条数上限 N       扁平只读文本上限，默认 400
```
 
## 可见结构的三种视角
 
- `页面结构`：完整性优先。默认从 `body` 保留全部有效分支，保守删除和折叠后输出 `去掉无意义元素之后的dom结构`；另有 `分区` 字段增强标题内容、独立导航、摘要卡片、侧边栏、字段、表格和富文本。没有标题前缀的固定结构只要可见且有内容也会独立成区；识别失败不丢原节点。
- `aria`：浏览器无障碍语义事实，适合判断 `columnheader`、`cell`、`selected` 等角色和状态。
- `只读文本`：扁平但经过 `elementFromPoint`，被遮挡的背景文字已剔除，适合查当前真正露出的文案。
 
表格增强只包含当前 DOM 已挂载的行；虚拟滚动未挂载的数据或精确整列仍使用 `浏览器会话 --读`。
 
## 退出码
 
```
0   正常
1   有动作执行失败（看 做了[].错误），或一个可点元素都没采到
2   白屏 / 页面没打开成
```
 
## 实测数字（基线列表页，2026-08-27）
 
```
纯观察（跳过影子库）   约 20~25 秒／次，绝大部分是 CAS 登录 + 首屏等 11.1s
带 --做（预热影子库）  约 80~90 秒／次，多出来的是后端复制影子库快照
 
可点元素 --只要有定位   30 个｜17.0 KB ≈ 8k tokens
可点元素（全量）        48 个｜20.6 KB ≈ 10k tokens（没定位的带 备选，最占地方）
弹窗内                7 个｜有定位 7｜靠文本收窄 4｜没定位 0
可见结构（全量）        aria 179 行 + 只读文本 86 条｜14.5 KB ≈ 7k tokens
可见结构 --文本含 创建   aria 179 行 + 只读文本 4 条｜7.6 KB ≈ 3k tokens
aria 角色分布          cell 66｜img 30｜text 30｜row 14｜columnheader 11｜button 4｜tab 3
 
弹窗打开后：可点元素只回 19 个，全部在弹窗容器内；
           背景元素（项目文档/需求包/比对/创建基线）一个都不回 —— 被遮罩挡着，已剔除
```
 
## 提示文案怎么拿（写预期结果要用）
 
toast 在动作后 1.2 秒的快照里还活着，所以它出现在 `新增签名` 里。实测「创建基线」这条链：
 
```
click 创建基线                    → 新增 31 条，新增弹层 .ant-modal-wrap.create-baseline-modal
click 确定（没填名称）             → 新增 ['span|基线名称不能为空']         ← 反向用例的预期结果
fill 名称 + fill 描述 + click 确定 → 新增 ['span|基线创建成功',
                                        'span.baseline-name|基线A',
                                        'div.ant-message-custom-content|']  ← 正向用例的预期结果
```
 
取法：`新增签名` 里形如 `tag.类名|文案` 的，`|` 右边就是文案。
 
## 九个已经踩过的坑
 
**一、拿到结果先核对 `打开.url` 和 `打开.仍在加载`。**
这个站是 SPA，`goto` 之后会先渲染首页、再路由到目标页。首页本身是"稳定"的（签名 34 条、连续几张一致），等待逻辑只判"稳定"就会**停在首页**——然后你拿着首页那几个元素以为那是目标页，不报错。写这份文档的过程中踩了两次。命令里有 10 秒硬下限就是为这个，但仍然要核对。
 
`仍在加载` 是同一类问题的另一面：为 `true` 时页面上还有转圈的 spinner，采回来的分区内容可能是"加载中..."而不是真数据，`加载态残留` 里是残留的节点。**这时候的结果不能用**，重跑一次，或者去查接口是不是挂了。等待逻辑现在把"没有可见加载态节点"也算进稳定判据，所以正常情况下它就是 `false`。
 
**二、同胞按钮的定位工具已经自动给了，别再自己拼。**
弹窗页脚的「确定」「取消」都是 `button.u-button`、匹配 2、父链相同，只有文本不同。这一类工具会**自动用文本收窄**并现场数过 `count()==1`，`定位策略` 带 `+含文本` 后缀：
 
```
确定   弹层容器+类名+含文本   .ant-modal-wrap.create-baseline-modal.ant-modal-centered button.u-button:has-text("确定")
```
 
看返回值里的 `靠文本收窄` 就知道有几个是这么来的（实测弹窗里 7 个元素 4 个靠它，`没定位` 归零）。
 
自己写选择器时注意：**要用 `has-text` 而不是 `text-is`** —— `:text-is()` 匹配「包含该文本的**最小**元素」，而按钮文字在嵌套 `<span>` 里，所以 `button.u-button:text-is("确定")` 匹配 0 个、白等 8 秒超时。`has-text` 匹配祖先，能命中按钮本身。命令行里对应 `#含文本=` 和 `#文本=`。
 
**三、同构列表成员的 `定位` 也是 `null`，但不要瞎猜 nth。**
实测 18/48。日期格子、项目切换列表项：没有 id、没有 `data-*`、类名相同、父链相同、文本还跨面板重复（`:text-is("30")` 匹配 4 个）。这类元素的身份**在 DOM 里不存在**。
 
按优先级：
 
1. 用文本收窄：`.picker-dropdown div.time-inline-pic#含文本=30`
2. 表格行用行标识属性：`[rowid="RS0000000777"] span.baseline-id`
3. `--定分身 '备选里的那条表达'` 现场定出 `取第几个`
4. 都不成 → 如实说"这个元素当前不可稳定定位"，别编一个 nth 交出去
 
**四、`名` 是 `null` 的是图标按钮。**
没有文本，aria 树里也只是裸 `img`。看 `语义类名`（`['back']`、`['icon-er']` 这种）和 `矩形` 位置，别硬猜功能。
 
**五、`只读文本` 里的 `role显式` 只有写在 HTML 上的那种。**
`th` 天生是 `columnheader`、`td` 天生是 `cell`，这些**隐含语义只有 aria 树里有**。实测：只读文本里 `role显式=columnheader` 的 **0 个**，aria 里有 **11 个**。要角色就读 `aria` 字段。
 
**六、表格整列的值 aria 给不了。**
它有 `columnheader 11 / cell 66 / row 14`，结构在，但那棵树是扁平文本。用 `--读 'td.col_4'`，返回的 `全部文本` 是这个选择器匹配到的所有节点文本、按 DOM 顺序。
 
**七、写操作是真的，而且 `--做` 序列出错不会停。**
`online=True` 时请求带 `x-ut-run-id`，写操作落影子库——**数据隔离，但动作真执行**。"发布""移除""删除"在影子库里也不可撤销。
 
`--做` 里某一步失败时**后面的步骤照旧执行**（实测：第 2 步超时之后第 3~5 步继续跑，最后又点了一次确定）。多步序列请先分段验证，或者检查每一步的 `做了[].错误`。
 
纯观察时默认跳过影子库预热（省 60 秒），此时**不要**用 `--做` 提交写操作。
 
**绝对不要点**"退出登录 / 退出系统 / 注销 / 登出 / Logout / Sign out"：会话当场作废，之后所有调用都无效，而且不报"未登录"，只表现成"页面怎么全变了"。
 
**八、`可点理由` 是 `hover才pointer` 的，是靠读样式表捞回来的。**
有一批元素的 `cursor: pointer` **只写在 `:hover` 里**，这个站的侧边栏和标签就是：
 
```css
.req-sidebar .menu-item:hover { color: #086FFF; cursor: pointer; }
.linkTag:hover { cursor: pointer; }
```
 
`getComputedStyle` 读的是当前样式，鼠标不在上面时 `:hover` 不参与计算、`cursor` 是 `auto`，于是这批元素整批落进 `台账.五条规则都不命中跳过`。实测这一页因此少采 6 个：`返回`、侧边栏四项（基本信息 / 关联关系 / 关联任务 / 案例执行）、基线标签 `RS0000000263 ×脏数据基线`。
 
现在的做法是**读样式表**而不是去 hover 每个节点（3000+ 节点逐个 hover 不可行，还会触发浮层、改变被观察的页面）：把所有"`:hover` 里设了 `cursor:pointer`"的规则收集一次、去掉 `:hover` 当静态选择器用 `matches()` 判。实测这一页 16 条这样的规则，多带 6 个节点、**零噪音**（`台账.hover才pointer采到` 就是这个数）。这些元素点起来和别的没区别 —— 小手只是外观，handler 一直挂在那儿。
 
**九、`ant-select` 里的人名 chip 不会单独回，回的是整个 select。**
形如
 
```html
<div class="ant-select attr-user-selector">      ← 回的是这个（cursor:pointer 的最外层）
  <span class="ant-select-selection-item" title="刘明皓">…</span>   ← 不回
```
 
内层 chip 自己也是 `cursor:pointer`，但父链上每一层都是，所以只留最外层。放宽这条父守卫实测多带 37 个节点，其中 `svg` / `img` / `u-tag-icon` / `avatar-container` 这类纯噪音占绝大多数，同一个 chip 还会在 5 层嵌套上各报一次 —— 不值。点整个 select 和点里面的 chip 效果一样（都是展开下拉）。
 
顺带一个真实限制：这一页的 `创建人` 和 `最近更新人` 用的是**同一个** `div.attr-user-selector`，值又都是"刘明皓 +0"，所以类名候选全是 `匹配 2`、文本也收窄不了，`定位` 是 `null`。区分它们的信息在兄弟节点的字段标签上，工具目前不生成这种作用域。按第三条坑处理：`--定分身` 现场定 `取第几个`（实测两份分身都可点，y=201 是创建人、y=231 是最近更新人）。
 
## 判断"点成没成"
 
`取可点元素` 的返回值先看这四个数，再决定要不要细读 `元素`：
 
```
个数 48｜有定位 30｜靠文本收窄 4｜没定位 14
```
 
`没定位` 非 0 才需要你介入，其余都能直接用。
 
```jsonc
{
  "有变化": true,          // 净签名集合变了没（滤掉了时间戳/条数这类噪音）
  "新增签名数": 31,
  "新增签名": ["span|基线创建成功", "..."],   // 提示文案就在这里
  "消失签名": [],          // 点"重置"这类动作，差异全在这一侧
  "新增弹层": [{"选择器": ".ant-modal-wrap.create-baseline-modal.ant-modal-centered"}],
  "路由变了": null,        // 非 null 表示跳页了
  "前指纹": "62e0c3606880", "后指纹": "bc9fe25b6e0a"   // 相同 = 还在原地
}
```
 
`有变化: false` 就是真没反应——按定义页面还在同一状态。这时可以试 `dblclick`（有些控件靠双击进编辑态）或先 `hover`（有些菜单要悬停才出）。
 
`新增弹层[].选择器` 直接拿去当下一条命令的 `--在浮层内`。
 
## Python API
 
命令行满足不了时（要在一个会话里连续做很多步、不想反复登录）：
 
```python
from tools.page_object_build.浏览器会话 import 会话
from tools.page_object_build.可点元素 import 取可点元素, 定分身
from tools.page_object_build.可见结构 import 取可见结构
 
URL = ("https://dev-mude-r.tsp.mioffice.cn/#/req-mgmt/tabs/baseline"
       "?projectBusId=3dce85a6-1fa9-4726-920c-066c5aca1803")
 
with 会话(headless=True, 预热影子库=False) as s:   # 纯观察就关掉预热
    自检 = s.打开(URL)
    assert "baseline" in 自检["url"], f"落错页了：{自检['url']}"
 
    页面 = 取可见结构(s.page, 要aria=False, 要只读文本=False,
                     要页面结构=True, 分区="基本信息")
    print(页面["页面结构"]["分区"])
 
    可点 = 取可点元素(s.page, 只要有定位=True)
    目标 = next(e for e in 可点["元素"] if e["名"] == "创建基线")
 
    r = s.做(目标["定位"], "click")
    assert r["有变化"], "点了没反应"
 
    弹窗内 = 取可点元素(s.page, 在浮层内=r["新增弹层"][0]["选择器"])
    print([e["名"] for e in 弹窗内["元素"]])
    print(s.读("td.col_4")["全部文本"])
```