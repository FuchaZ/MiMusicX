# -*- coding: utf-8 -*-
"""Quantify qqmusiclite namespace in Xiaomi Music and map QMHelper targets to it."""
import os, struct
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))

def dex_strings(path):
    strings = set()
    with open(path, 'rb') as f:
        data = f.read()
    if data[:4] != b'dex\n':
        return strings
    string_ids_size, string_ids_off = struct.unpack_from('<II', data, 56)
    for i in range(string_ids_size):
        off = struct.unpack_from('<I', data, string_ids_off + i * 4)[0]
        b0 = data[off]
        off += 1 if b0 < 0x80 else 2
        end = data.index(b'\x00', off)
        try:
            strings.add(data[off:end].decode('utf-8', errors='replace'))
        except Exception:
            pass
    return strings

def collect(dexdir):
    s = set()
    for fn in sorted(os.listdir(dexdir)):
        if fn.endswith('.dex'):
            s |= dex_strings(os.path.join(dexdir, fn))
    return s

qm = collect(os.path.join(HERE, 'qm_dex'))
xm = collect(os.path.join(HERE, 'xm_dex'))

# 1. qqmusiclite scale in both
for label, s in [("QQ(12.0.5.8)", qm), ("XM(4.46.2.1)", xm)]:
    n = sum(1 for x in s if x.startswith('Lcom/tencent/qqmusiclite/'))
    print(f"{label}: Lcom/tencent/qqmusiclite/* classes = {n}")

xm_lite = sorted(x for x in xm if x.startswith('Lcom/tencent/qqmusiclite/'))
qm_lite = {x for x in qm if x.startswith('Lcom/tencent/qqmusiclite/')}
inter = qm_lite & set(xm_lite)
print(f"overlap qqmusiclite classes QM∩XM: {len(inter)} ({round(100*len(inter)/max(1,len(qm_lite)),1)}% of QM's)")
c = Counter('/'.join(x.split('/')[:4]) for x in xm_lite)
print("\nXM qqmusiclite subpackages (top 25):")
for k, v in c.most_common(25):
    print(f"   {k}: {v}")

# 2. Key QMHelper target equivalents under qqmusiclite in XM
lite_equivs = {
  "MainDesktopHeader": "Lcom/tencent/qqmusiclite/ui/MainDesktopHeader;",
  "AppStarterActivity": "Lcom/tencent/qqmusiclite/activity/AppStarterActivity;",
  "PlayerViewModel": "Lcom/tencent/qqmusiclite/business/playernew/viewmodel/PlayerViewModel;",
  "DebugSettingFragment": "Lcom/tencent/qqmusiclite/fragment/debug/DebugSettingFragment;",
  "ModeSettingFragment": "Lcom/tencent/qqmusiclite/fragment/morefeatures/ModeSettingFragment;",
  "SettingFeaturesFragment": "Lcom/tencent/qqmusiclite/fragment/morefeatures/SettingFeaturesFragment;",
  "PersonalCenterEntryView": "Lcom/tencent/qqmusiclite/fragment/morefeatures/settings/view/PersonalCenterEntryView;",
  "SettingView": "Lcom/tencent/qqmusiclite/fragment/morefeatures/settings/view/SettingView;",
  "AlbumIntroduceViewHolder": "Lcom/tencent/qqmusiclite/albumdetail/ui/viewholders/AlbumIntroduceViewHolder;",
  "ApkDownloadAdBar": "Lcom/tencent/qqmusiclite/business/ad/topbarad/apkdownload/ApkDownloadAdBar;",
  "splashad pkg": "Lcom/tencent/qqmusiclite/business/splashad/",
  "MusicWorldPullEntrance": "Lcom/tencent/qqmusiclite/fragment/mymusic/my/musicworld/MusicWorldPullEntrance;",
  "MERJni": "Lcom/tencent/qqmusiclite/modular/framework/encrypt/logic/MERJni;",
}
print("\n=== qqmusiclite equivalents in XM ===")
print(f"{'class':<32} {'XM(qqmusiclite)':<16} {'XM(qqmusic)':<14}")
for name, desc in lite_equivs.items():
    xm_l = 'Y' if desc in xm else '-'
    xm_q = 'Y' if desc.replace('qqmusiclite', 'qqmusic') in xm else '-'
    print(f"{name:<32} {xm_l:<16} {xm_q:<14}")

# 3. XM: strings under qqmusiclite splashad
sp = sorted(x for x in xm if x.startswith('Lcom/tencent/qqmusiclite/business/splashad/'))
print(f"\nXM qqmusiclite splashad classes ({len(sp)}):")
for x in sp[:40]:
    print("   " + x)

# 4. XM strings referencing key QMHelper-located services in lite namespace
needles = [
  "[parseModuleItem] ",
  "AdResponseData(retCode=",
  "getFileEKey filePath is empty!",
  "decryptFile srcFilePath = ",
  "decryptFile create dest = ",
  "StorageVolume From Android API SDK_INT : ",
  "StorageVolume [mStorageId=",
  "getMusicUin",
  "postSplashResult",
  "LOGIN_CHECK_SDK",
  "GSON cannot serialize",
  "JceResponseItemConverter",
  " ReleasedForAndroid[",
  "PlayerViewModel",
  "SPManager",
  "DebugMode",
  "UIModeManager",
]
print("\n=== QMHelper signature strings in XM (with class-context if findable) ===")
# naive context: print neighboring strings that look like class descriptors in same dex won't be easy; just count
for n in needles:
    cnt_xm = sum(1 for x in xm if n in x)
    print(f"  {n:<45} XM exact-string-pool hits: {cnt_xm}")
