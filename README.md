# XMPlaylistUnlock — 小米音乐增强模块

针对小米音乐（内嵌 QQ 音乐简洁版 `com.tencent.qqmusiclite`）的 LSPosed 模块，
当前包含两个独立功能。目标版本 **4.47.0.1**（歌单限制功能自 4.46.2.1 起可用）。

## 功能一：解除歌单 1000 首添加限制

解除"添加到歌单"时"该歌单已超过1000首歌啦"的客户端限制。原版 QQ 音乐允许超过
1000 首（服务端接受），限制只在小米音乐客户端本地。

### 原理

检查点（小米音乐 4.46.2.1，classes8.dex）：

```
com.tencent.qqmusiclite.fragment.SongListAddViewModel$addSong$1.invokeSuspend
  limit = (folderInfo.getId() == 201L /* 我喜欢 */) ? 10000 : 1000
  if (folderInfo.getCount() >= limit) -> BannerTips("该歌单已超过1000首歌啦") -> return（不发请求）
  remaining = limit - folderInfo.getCount()
  AddSongs.invoke(new AddSongs$Param(folderId, songs 截断至 remaining))
```

Hook `com.tencent.qqmusic.core.folder.FolderInfo.getCount()`（public，未混淆），
当调用栈处于 `SongListAddViewModel` 添加流程时返回 0，使检查通过；
`remaining` 变为 1000，真实 folderId 不受影响（不会加错歌单）。
调用栈过滤保证歌单列表页等处的数量显示完全不受影响。

## 功能二：启动不停留在「免费听(发现)」页

4.47.0.1 起小米音乐把默认启动页改成顶部的「免费听」（底栏叫「发现」）。模块不进入该页。

### 原理（实测修正版）

首屏走的是**底部导航的 NavController 路由**，与首页顶部 TabLayout 是两套独立体系。
顶部那排「免费听/推荐/听书」是 `QuickPlayFragment` 自己 header 里的装饰性文字
（`fragment_quick_play_container` → `tab_header`），**不是** TabLayout 的 Tab。

真实链路：

```
MainActivity.onCreate()
  -> configNavigationAndMinibar()  setupWithNavController
  -> MainActivity$onCreate$17.invoke(Boolean)
       -> QuickPlayManager.isGotoQuickPlayTab()      // ABT "2025QuickStartPlay".page == "1"
       -> QuickPlayFragment.Companion.setFrom(1)
       -> MainActivity.navigateToDefaultQuickPlayTab()
            -> NavController.navigate(R$id.quickPlayFragment)   // 底栏「发现」
```

`QuickPlayManager.isGotoQuickPlayTab()` 是唯一总开关，4 个调用方都受它控制：

| 调用方 | 作用 |
|--------|------|
| `MainActivity$onCreate$17.invoke` | 是否 navigate 到 `quickPlayFragment` |
| `QuickPlayManager.isEnabled` | QuickPlay 是否启用 |
| `QuickPlayManager.needQuickPlayWhenColdStart` | 冷启动是否需要 QuickPlay |
| `BaseHomeFragment.checkTopTabStartIndex` / `QuickPlayModel.onVisible` | 顶部 Tab 起始页 |

模块 Hook 它并恒返回 **false**。它是纯 ABT 读取器、无副作用，置 false 后上述调用方
一致地走推荐页分支。同时 Hook `MainActivityViewModel.getTabs()` 与
`BaseHomeFragment.getTabs()` 剔除 `TopTab id=4`，让顶部那一排也不显示「免费听」。

## 功能三：启动后直接进入底栏「我的」页

### 原理

```
MainActivity.configNavigationAndMinibar()
  -> ActivityKt.findNavController(R$id.nav_host_fragment)
  -> BottomNavigationView.setupWithNavController(navController)
```

该方法返回时 NavController 与底栏已就绪，模块在 `afterHookedMethod` 里调用
`navigateTopLevelSingleTop(R$id.my_fragment, null)` 切到「我的」页。

要点：

- **不能**挂在 `navigateToDefaultQuickPlayTab()` 上：功能二把 `isGotoQuickPlayTab()`
  恒置 false 后，`onCreate$17` 根本不会调用它，那个 Hook 永不触发
- `navigateTopLevelSingleTop` 是底栏切页的标准入口（single top + 顶层动画）
- `R$id.my_fragment` = `0x7f0b0831`（4.47.0.1 实测值，硬编码在代码里）
- 用 `AtomicBoolean` 保证只导航一次，避免其它入口复用 main 界面时被反复拉回「我的」

## 安装激活

1. 安装 `XMPlaylistUnlock-1.1.0.apk`
2. LSPosed → 模块 → 启用"小米歌单1000解锁"→ 作用域勾选"音乐（小米音乐）"
   （已通过 assets/xposed_scope 默认声明 com.miui.player）
3. 强制停止小米音乐后重新打开

## 验证

LSPosed 日志里应出现（前 5 条是 Hook 安装，重启小米音乐后一起出现）：

```
[XMPlaylistUnlock] hook installed via findAndHookMethod: com.tencent.qqmusic.core.folder.FolderInfo.getCount()
[XMPlaylistUnlock] hook installed: com.tencent.qqmusiclite.fragment.home.QuickPlayManager.isGotoQuickPlayTab() -> always false
[XMPlaylistUnlock] hook installed: com.tencent.qqmusiclite.activity.main.viewmodel.MainActivityViewModel.getTabs() -> strip TopTab id=4
[XMPlaylistUnlock] hook installed: com.tencent.qqmusiclite.fragment.home.BaseHomeFragment.getTabs() -> strip TopTab id=4
[XMPlaylistUnlock] hook installed: com.tencent.qqmusiclite.activity.MainActivity.configNavigationAndMinibar() -> navigate to 我的
[XMPlaylistUnlock] blocked QuickPlay landing (isGotoQuickPlayTab was true), home stays on 推荐
[XMPlaylistUnlock] removed 免费听 tab (TopTab id=4), home falls back to 推荐
[XMPlaylistUnlock] startup navigated to 我的 (id=0x7f0b0831)
[XMPlaylistUnlock] bypassed playlist limit: folderId=xxx realCount=xxx (reported 0)
```

时间线：Hook 安装 → `blocked` → `removed` → `startup navigated` 在冷启动首屏阶段依次出现；
最后一条在添加歌曲超限时出现。

实测确认（adb + uiautomator，4.47.0.1 / 小米 14）：

- 冷启动后底栏 `我的` = `selected=true`、`发现` = `selected=false`
- 首屏直接显示「我的」页面（会员卡片 / 收藏 / 本地 / 最近播放 / 自建歌单）

## 重建

```bash
bash build.sh
```

- 源码：`src/local/xmplaylist/unlock/MainHook.java`
- Xposed API 以编译期 stub 形式提供（`stubs/`），不会打进 dex
- 签名：临时目录 debug.jks（密码 android）

## 仓库布局

```
src/          模块源码（Java）
stubs/        Xposed API 编译期桩（签名必须与真实 API 完全一致，勿随意改动）
assets/       xposed_init（入口类）+ xposed_scope（作用域 com.miui.player）
analysis/     逆向分析脚本与 4.46.2.1 / 4.47.0.1 检查点存档（版本更新失效时从这里开始）
build.sh      一键构建（aapt2 不兼容中文路径，脚本自动在 ASCII 临时目录构建）
```

## 已知边界

**功能一**
- 单次批量添加最多 1000 首（客户端按 remaining 截断）；逐首/小批量添加无感知
- 若小米音乐未来版本改动 `SongListAddViewModel` / `FolderInfo`，需重新定位检查点
- 服务端行为与原版 QQ 音乐一致（同一套接口）

**功能二 / 功能三**
- 只阻断自动落地，**不删除**这个页面：底栏「发现」仍可手动点进去
- 顶部那排「免费听」文字由 `QuickPlayFragment` 自己的 header 渲染
  （`fragment_quick_play_container` → `tab_header`），Hook `getTabs()` 只能影响
  从 TopTab 列表来的项
- 依赖 `QuickPlayManager.isGotoQuickPlayTab` / `configNavigationAndMinibar` /
  `navigateTopLevelSingleTop` 三个方法名未混淆
- `R$id.my_fragment` 硬编码为 `0x7f0b0831`（4.47.0.1 实测）。**小米音乐更新后
  资源 ID 会变**，需重新用 `aapt2 dump resources` 查 `id/my_fragment` 并更新常量
- 只在冷启动的 `configNavigationAndMinibar` 后导航一次；若用户手动切走再切回，
  不会被强制拉回「我的」

## 版本历史

- **1.1.0** — 目标版本 4.47.0.1
  - 功能一：解除歌单 1000 首添加限制（原 1.0.1 逻辑，检查点不变）
  - 功能二：阻断免费听(发现)自动落地 — Hook `QuickPlayManager.isGotoQuickPlayTab()`
    恒返回 false，并在 `MainActivityViewModel/BaseHomeFragment.getTabs()` 剔除 `TopTab id=4`
  - 功能三：启动后直接进入底栏「我的」页 — Hook `configNavigationAndMinibar()`
    完成后 `navigateTopLevelSingleTop(R$id.my_fragment)`
- **1.0.1** — 功能一（解除歌单 1000 首添加限制），目标版本 4.46.2.1
