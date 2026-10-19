# 逆向分析工具集

小米音乐（内嵌 QQ 音乐简洁版）的静态分析脚本。当小米音乐版本更新、
Hook 失效时，按下面流程重新定位检查点并修改 `src/.../MainHook.java`。

依赖：`pip install androguard pyaxmlparser`（纯分析，无需设备）

所有脚本用环境变量 `XMPU_APK` 指定宿主 APK，默认 `E:\QQ下载\base.apk`：

```powershell
$env:XMPU_APK = "D:\某处\小米音乐_新版.apk"
```

## 推荐工具链（4.47.0.1 分析时新增，纯 Python 无需第三方库）

`dexscan.py` 是自写的轻量 dex 解析器，比 androguard 快得多（11 个 dex、
96MB 全量索引约 1 分钟），且能精确到**方法级**给出引用关系：

```powershell
# 1. 解包关键 dex 到 analysis/xm_dex/
python extract_dex.py

# 2. 建立全量类索引（82316 个类，~1 分钟）
python dex_index.py
python search_index.py quickplay              # 按关键字找类
python search_index.py 'fragment/home/'       # 找某包下所有类

# 3. 方法级引用反查：谁引用了某个类/字段/方法/字符串
python dexscan.py find-ref xm_dex/classes10.dex 'shelfcard2/TopTab' method
python dexscan.py find-ref xm_dex/classes9.dex 'top_tab_display' string

# 4. 打印类结构（字段 + 方法签名 + code offset）
python dexscan.py dump xm_dex/classes10.dex 'fragment/home/BaseHomeFragment;'

# 5. 反汇编指定类/方法为 smali 风格指令（核心工具）
python disasm.py xm_dex/classes10.dex 'fragment/home/BaseHomeFragment;' 'getTabs'
python disasm.py xm_dex/classes10.dex 'fragment/home/BaseHomeFragment;'   # 整个类

# 6. 字符串池提取（自动处理 uleb128 长度 + MUTF-8）
python extract_strings.py                     # 编辑 NEEDLES 列表

# 7. arsc 按资源名查值（定位文案资源）
python arsc_by_name.py nav_quick_play_title free_mode_menu_title
python arsc_find.py                           # 按「值」反查资源 ID
```

`disasm.py` 的 `invoke-*` 行会直接渲染出 `类->方法(参数)返回`，改功能时
看调用关系最快。注意它的形参个数是估算值（`{N args}` 里的 N 是 opcode 编码
的寄存器数，不是真实参数个数）。

## 旧流程（4.46.2.1 歌单限制功能，androguard 系）

```bash
# 0. 解出宿主 dex
unzip -o ../小米音乐.apk "classes*.dex" -d xm_dex

# 1. 确认包名/版本
python -c "from pyaxmlparser import APK; a=APK('../小米音乐.apk'); print(a.package, a.version_name)"

# 2. 找限制文案（资源 or dex 字符串）
python find_limit.py            # 修改脚本内路径指向新 APK 解包目录
#   -> 文案在 resources.arsc: 记下资源名（如 qq_music_playlist_song_over_size）

# 3. arsc -> 资源 ID
python arsc_find.py             # -> 0x7f140ad0 @string/qq_music_playlist_song_over_size

# 4. dex 反查引用（哪个类用了这个资源）
python dex_debug.py             # -> sget 命中的类/方法（如 SongListAddViewModel$addSong$1.invokeSuspend）

# 5. 反汇编看检查逻辑
python dump_addsong.py          # 参考 addsong_dump.txt（4.46.2.1 的现场存档）

# 6. 定位数据类签名（hook 目标是否仍是 public 等）
python find_folderinfo.py       # -> FolderInfo.getCount()I / getId()J
```

## 4.46.2.1 的结论存档（功能一：歌单 1000 首限制）

- 检查点唯一：`SongListAddViewModel$addSong$1.invokeSuspend`（classes8.dex）
- 逻辑：`limit = (getId()==201 ? 10000 : 1000); if (getCount() >= limit) toast+return`
- Hook 目标：`com.tencent.qqmusic.core.folder.FolderInfo`（classes7.dex，public，未混淆）
- 其余脚本（check_strings / deep_analysis / lite_analysis / check_ad_classes /
  final_checks）是当初评估 QMHelper 移植可行性用的双 APK 对比工具，含 QM
  特征串清单，排查其他功能时可直接复用。


## 4.47.0.1 的结论存档

APK：`com.miui.player` 4.47.0.1（versionCode 4470001），launcher
`com.miui.player.ui.MusicBrowserActivity`，11 个 dex，82316 个类。
设备实测环境：小米 14（houji），LSPosed，adb root。

### 关键教训：顶部 Tab 与首屏落地是两套体系

这是第一版实现失败的原因，务必先读：

- 首屏落地走 **底部导航的 NavController 路由**（`R$id.nav_host_fragment` -->
  `quickPlayFragment` / `my_fragment` / ...）
- 首页顶部那排「免费听 / 推荐 / 听书」是 **`QuickPlayFragment` 自己 header 里的
  装饰性文字**（`fragment_quick_play_container` --> `tab_header`），不是
  `TabLayout` 的 Tab（uiautomator 里它们是带 `content-desc` 的 `LinearLayout`，
  没有 `TabLayout` 节点）
- 因此「删 TopTab id=4」只影响 TabLayout 那条线，**不影响首屏**；
  真正让 App 停在免费听的是 `NavController.navigate(R$id.quickPlayFragment)`

### 首屏「免费听」自动落地的真实链路

```
MainActivity.onCreate()
  -> configNavigationAndMinibar(Bundle)          // setupWithNavController，底栏就绪
  -> MainActivity$onCreate$17.invoke(Boolean)    // 某个 LiveData/开关的回调
       if (isColdStart && PrivacyPolicyHelper.isAccept()
           && QuickPlayManager.isGotoQuickPlayTab()
           && !ProgramState.from3rdParty
           && !AppModeManager.getOfflineWithoutPrivacy()
           && !YoungModeManager.isYoungMode()) {
             QuickPlayFragment.Companion.setFrom(1)
             MainActivity.navigateToDefaultQuickPlayTab()
               -> NavController.navigate(R$id.quickPlayFragment)
       }
```

`QuickPlayManager.isGotoQuickPlayTab()`（classes10.dex）只是读 ABT：
策略 `"2025QuickStartPlay"` 的 `params["page"] == "1"` 时返回 true。
**这是唯一总开关**，4 个调用方：

| 调用方 | 作用 |
|--------|------|
| `MainActivity$onCreate$17.invoke` | 是否 navigate 到 `quickPlayFragment`（首屏根因） |
| `QuickPlayManager.isEnabled` | QuickPlay 是否启用 |
| `QuickPlayManager.needQuickPlayWhenColdStart` | 冷启动是否需要 QuickPlay |
| `BaseHomeFragment.checkTopTabStartIndex` / `QuickPlayModel.onVisible` | 顶部 Tab 起始页 |

### 顶部 Tab 链路（次要，仅影响 TabLayout）

```
com.tencent.qqmusicplayerprocess.servicenew.try.abstract()
  读 SharedPreferences("qqmusicplayer").getString("top_tab_display")
  -> Gson -> List<TopTab>
  -> MainActivityViewModel.tabs / BaseHomeFragment.getTabs()
  -> HomePageAdapter.getPageTitle(position) / getItem(position)
```

设备上 `top_tab_display` 的实际值（4.47.0.1）：

```json
[{"id":4,"name":"发现"},{"id":1,"name":"推荐"},{"id":3,"name":"有声"},{"id":2,"name":"K歌"}]
```

TopTab id -> Fragment 映射（`HomePageAdapter.getItem`）：

| id | Fragment | getPageTitle 文案 |
|----|----------|-------------------|
| 1 | `fragment.home.HomeFragment` | 推荐 |
| 2 | `fragment.home.KegeFragment` | K歌 |
| 3 | `fragment.home.LongAudioFragment` | 听书（`nav_long_audio_title`） |
| 4 | `fragment.home.quickplay.QuickPlayFragment` | 免费听（`nav_quick_play_title`） |
| 其它 | `HomeFragment` | 兜底 |

### 当前 Hook 方案（4 个点）

| # | Hook 点 | 手法 | 目的 |
|---|---------|------|------|
| 1 | `FolderInfo.getCount()` | 添加流程内返回 0 | 功能一：解除 1000 首限制 |
| 2 | `QuickPlayManager.isGotoQuickPlayTab()` | 恒返回 `false` | 功能二：阻断自动落地（主力） |
| 3 | `MainActivityViewModel.getTabs()` / `BaseHomeFragment.getTabs()` | 就地 `Iterator.remove` 掉 `id==4` | 功能二：顶部 Tab 不显示免费听 |
| 4 | `MainActivity.configNavigationAndMinibar(Bundle)` | `after` 里 `navigateTopLevelSingleTop(0x7f0b0831, null)` | 功能三：启动进「我的」 |

改动时务必保持的约束：

1. **功能三不能挂在 `navigateToDefaultQuickPlayTab()` 上**。功能二把
   `isGotoQuickPlayTab()` 恒置 false 后，`onCreate$17` 根本不会调用它，
   那个 Hook 永远不会触发（第一版就踩了这个坑）
2. **删 TopTab 必须就地 `remove`，不能返回新 List**。`BaseHomeFragment.updateTabs()`
   会对 `getTabs()` 的结果执行 `clear()` + `addAll()`；返回新引用会让 VM 真实字段
   与调用方操作的对象脱节
3. `getTabs()` 要**两处都挂**（VM 与 BaseHomeFragment）。Fragment 的
   `tabs$delegate` 是 Lazy 转发到 VM.getTabs()，但 `updateTabs()` 可能把
   含 id=4 的列表重新 `addAll` 回去，多挂一处可在下次读取时再清
4. `isGotoQuickPlayTab()` 是纯 ABT 读取器、无副作用，置 false 安全
5. `selectTopTab(idx, ...)` 对 `idx < 0` 或 `idx >= tabCount` 安全返回 false
6. `R$id.my_fragment` = `0x7f0b0831` 是**硬编码的资源 ID**，小米音乐更新后会变，
   需重新 `aapt2 dump resources` 查 `id/my_fragment` 并更新 `NAV_ID_MY_FRAGMENT`

### 实测验证方法（关键：别只看日志）

日志只证明 Hook 装上，不证明行为对。用 adb 做行为验证：

```powershell
$adb = "D:\reasonix backup\apk开发\sdk\platform-tools\adb.exe"
# 1) 冷启动
& $adb logcat -c; & $adb shell "am force-stop com.miui.player"
& $adb shell "am start -n com.miui.player/com.miui.player.ui.MusicBrowserActivity"
Start-Sleep 12; & $adb logcat -d | Select-String 'XMPlaylistUnlock'
# 2) 看真实界面（确认落在哪一页 / 底栏选中态）
& $adb exec-out screencap -p > shot.png
& $adb shell "uiautomator dump /sdcard/u.xml"
& $adb shell "su -c 'cp /sdcard/u.xml /data/local/tmp/u.xml && chmod 666 /data/local/tmp/u.xml'"
& $adb pull /data/local/tmp/u.xml ui.xml
# ui.xml 里看 content-desc="我的" 的 selected 属性
```

### 其它「免费听」相关入口（本模块未处理）

| 位置 | 类 / 方法 | 说明 |
|------|-----------|------|
| 底栏「发现」 | `MainActivity.setQuickPlayTabVisible(Z)` / `setFreeModeTabVisible(Z)` | `R$id.quickPlayFragment` / `freeModeFragment`，**手动仍可点进去** |
| 首页悬浮 | `BaseHomeFragment.setFreeModeEntranceVisibility(Z)` | `mFreeModeEntranceArea`（ConstraintLayout） |
| 首页 VIP 条 | `TabFreeVisibleObserver` / `freemode/util/FreeModeEntranceRefresh` | `tabFreeVisible` / `tabFreeText` / `tabFreeIcon` 三个 LiveData |
| 开屏广告位 | `com.tencent.ams.fusion.widget.freemode.FreeModeSplashLayerHelper` | classes8.dex |
| ABT 下发 | `CheckFreeModeTabRepo` / `FreeModeTabRepo.showFreeMode()` | 请求 `MtHomePageSvr.GetFreeModeTabInfo` |

### 文案 / 导航资源对照（`resources.arsc`）

| 资源名 | 值 / ID |
|--------|---------|
| `string/nav_quick_play_title` (0x7f140890) | 免费听 |
| `string/mine_task_bar_title_highlight` (0x7f140722) | 免费听 |
| `string/free_mode_menu_title` (0x7f1404ff) | 赚钱 |
| `string/welfare_center_menu_title` (0x7f140ff0) | 福利 |
| `id/my_fragment` (0x7f0b0831) | 底栏「我的」导航目标 |
| `id/quickPlayFragment` (0x7f0b09fc) | 底栏「发现」导航目标 |
