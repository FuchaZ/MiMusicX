# -*- coding: utf-8 -*-
"""Deep analysis: what QQ Music code exists inside Xiaomi Music."""
import os, struct, json

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

# 1. L-descriptor form check for fqcn classes used by QMHelper
fqcn_checks = {
  "MainDesktopHeader": "Lcom/tencent/qqmusic/ui/MainDesktopHeader;",
  "AppStarterActivity": "Lcom/tencent/qqmusic/activity/AppStarterActivity;",
  "PersonalCenterEntryView": "Lcom/tencent/qqmusic/fragment/morefeatures/settings/view/PersonalCenterEntryView;",
  "SettingFeaturesFragment": "Lcom/tencent/qqmusic/fragment/morefeatures/SettingFeaturesFragment;",
  "MyMusicUserInfoViewHolder": "Lcom/tencent/qqmusic/modular/module/musichall/views/viewholders/cell/MyMusicUserInfoViewHolder;",
  "PlayerViewModel": "Lcom/tencent/qqmusic/business/playernew/viewmodel/PlayerViewModel;",
  "ApkDownloadAdBar": "Lcom/tencent/qqmusic/business/ad/topbarad/apkdownload/ApkDownloadAdBar;",
  "AlbumIntroduceViewHolder": "Lcom/tencent/qqmusic/albumdetail/ui/viewholders/AlbumIntroduceViewHolder;",
  "SettingView(morefeatures)": "Lcom/tencent/qqmusic/fragment/morefeatures/settings/view/SettingView;",
  "StorageVolume(qqmusiccommon)": "Lcom/tencent/qqmusiccommon/storage/StorageVolume;",
  "MusicWorldPullEntrance": "Lcom/tencent/qqmusic/fragment/mymusic/my/musicworld/MusicWorldPullEntrance;",
  "MERJni": "Lcom/tencent/qqmusic/modular/framework/encrypt/logic/MERJni;",
  "ModeSettingFragment": "Lcom/tencent/qqmusic/fragment/morefeatures/ModeSettingFragment;",
  "DebugSettingFragment": "Lcom/tencent/qqmusic/fragment/debug/DebugSettingFragment;",
  "X5 WebView": "Lcom/tencent/smtt/sdk/WebView;",
  "TinkerApplication": "Lcom/tencent/tinker/loader/app/TinkerApplication;",
}
print("=== fqcn classes (L-descriptor) ===")
print(f"{'class':<32} {'QQ':<3} {'XM':<3}")
for name, desc in fqcn_checks.items():
    print(f"{name:<32} {'Y' if desc in qm else '-':<3} {'Y' if desc in xm else '-':<3}")

# 2. Which QQ music subpackages exist in Xiaomi Music?
xm_qm_classes = sorted(x for x in xm if x.startswith('Lcom/tencent/qqmusic/'))
print(f"\n=== Xiaomi Music com.tencent.qqmusic.* classes: {len(xm_qm_classes)} ===")
# group by second-level package
from collections import Counter
c = Counter()
for x in xm_qm_classes:
    parts = x.split('/')
    c[parts[2] if len(parts) > 3 else '(root)'] += 1
for k, v in c.most_common(40):
    print(f"  {k}: {v}")

# 3. Overlap classes sample (present in both)
qmq = {x for x in qm if x.startswith('Lcom/tencent/qqmusic/')}
xmset = set(xm_qm_classes)
inter = sorted(qmq & xmset)
print(f"\n=== Overlap classes: {len(inter)} — sample 60 ===")
for x in inter[:60]:
    print("  " + x)

# 4. Ad-related & key business strings in XM
print("\n=== Ad/business string scan in Xiaomi Music ===")
ad_needles = [
  "com.tencentmusic.ad",          # tencentmusic ad sdk
  "AdResponseData(retCode=",      # ad response
  "splashAd", "SplashAd", "openAd", "adProxy", "requestAdvertisement",
  "FeedAd", "feedAd", "bannerAd", "BannerAd",
  "getStrategyId", "StrategyId",
  "qqmusiccommon",                # generic
  "Lcom/tencent/qqmusiccommon/",
  "ekey", "EKey", "ekeyDecrypt",
  "migu", "kuwo",                 # sound source replacement
  "MIUI", "miui",                 # miui markers
  "com.miui.player",
  "kotlin", "Lkotlin/",
  " hippy", "Hippy",              # tencent hippy framework
  "GdtM", "com.qq.e",             # GDT ad sdk
]
for n in ad_needles:
    qm_hit = sum(1 for s in qm if n in s) > 0
    xm_hit = sum(1 for s in xm if n in s) > 0
    print(f"  {n:<28} QQ:{'Y' if qm_hit else '-':<3} XM:{'Y' if xm_hit else '-':<3}")

# 5. Count com.tencentmusic.ad classes each side
for label, s in [("QQ", qm), ("XM", xm)]:
    ad = [x for x in s if x.startswith('Lcom/tencentmusic/ad/')]
    print(f"\n{label} com.tencentmusic.ad.* classes: {len(ad)}")
    from collections import Counter as C2
    c2 = C2(x.split('/')[3] if len(x.split('/')) > 4 else '(root)' for x in ad)
    for k, v in c2.most_common(15):
        print(f"   {k}: {v}")
