# 逆向分析工具集

小米音乐（内嵌 QQ 音乐简洁版）的静态分析脚本。当小米音乐版本更新、
Hook 失效时，按下面流程重新定位检查点并修改 `src/.../MainHook.java`。

依赖：`pip install androguard pyaxmlparser`（纯分析，无需设备）

## 流程

```bash
# 0. 解出宿主 dex（新版本 APK 放到本目录，命名任意）
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

## 4.46.2.1 的结论存档

- 检查点唯一：`SongListAddViewModel$addSong$1.invokeSuspend`（classes8.dex）
- 逻辑：`limit = (getId()==201 ? 10000 : 1000); if (getCount() >= limit) toast+return`
- Hook 目标：`com.tencent.qqmusic.core.folder.FolderInfo`（classes7.dex，public，未混淆）
- 其余脚本（check_strings / deep_analysis / lite_analysis / check_ad_classes /
  final_checks）是当初评估 QMHelper 移植可行性用的双 APK 对比工具，含 QM
  特征串清单，排查其他功能时可直接复用。
