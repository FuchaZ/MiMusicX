# XMPlaylistUnlock — 小米音乐歌单 1000 首限制解除

解除小米音乐（内嵌 QQ 音乐简洁版 `com.tencent.qqmusiclite`）在"添加到歌单"时
"该歌单已超过1000首歌啦"的客户端限制。原版 QQ 音乐允许超过 1000 首（服务端接受），
限制只在小米音乐客户端本地。

## 原理

检查点（小米音乐 4.46.2.1，classes8.dex）：

```
com.tencent.qqmusiclite.fragment.SongListAddViewModel$addSong$1.invokeSuspend
  limit = (folderInfo.getId() == 201L /* 我喜欢 */) ? 10000 : 1000
  if (folderInfo.getCount() >= limit) -> BannerTips("该歌单已超过1000首歌啦") -> return（不发请求）
  remaining = limit - folderInfo.getCount()
  AddSongs.invoke(new AddSongs$Param(folderId, songs 截断至 remaining))
```

本模块 Hook `com.tencent.qqmusic.core.folder.FolderInfo.getCount()`（public，未混淆），
当调用栈处于 `SongListAddViewModel` 添加流程时返回 0，使检查通过；
`remaining` 变为 1000，真实 folderId 不受影响（不会加错歌单）。
调用栈过滤保证歌单列表页等处的数量显示完全不受影响。

## 安装激活

1. 安装 `XMPlaylistUnlock-1.0.1.apk`
2. LSPosed → 模块 → 启用"小米歌单1000解锁"→ 作用域勾选"音乐（小米音乐）"
   （已通过 assets/xposed_scope 默认声明 com.miui.player）
3. 强制停止小米音乐后重新打开

## 验证

LSPosed 日志里出现：
```
[XMPlaylistUnlock] hook installed: com.tencent.qqmusic.core.folder.FolderInfo.getCount()
[XMPlaylistUnlock] bypassed playlist limit: folderId=xxx realCount=xxx (reported 0)
```

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
analysis/     逆向分析脚本与 4.46.2.1 检查点存档（版本更新失效时从这里开始）
build.sh      一键构建（aapt2 不兼容中文路径，脚本自动在 ASCII 临时目录构建）
```

## 已知边界

- 单次批量添加最多 1000 首（客户端按 remaining 截断）；逐首/小批量添加无感知
- 若小米音乐未来版本改动 `SongListAddViewModel` / `FolderInfo`（qqmusiclite 命名空间
  历来不混淆，风险低），需重新定位检查点
- 服务端行为与原版 QQ 音乐一致（同一套接口）；若服务端未来加限制，会表现为
  添加请求失败弹其他错误，届时需另行分析
