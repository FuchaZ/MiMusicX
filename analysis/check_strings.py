# -*- coding: utf-8 -*-
"""Extract string pool from dex files and check QMHelper hook signature strings."""
import struct, sys, os, json

def dex_strings(path):
    """Return set of strings in dex string pool."""
    strings = set()
    with open(path, 'rb') as f:
        data = f.read()
    if data[:4] != b'dex\n':
        return strings
    string_ids_size, string_ids_off = struct.unpack_from('<II', data, 56)
    for i in range(string_ids_size):
        off = struct.unpack_from('<I', data, string_ids_off + i * 4)[0]
        # uleb128 length
        b0 = data[off]
        if b0 < 0x80:
            off += 1
        else:
            off += 2
        # find terminating 0x00 from off
        end = data.index(b'\x00', off)
        try:
            strings.add(data[off:end].decode('utf-8', errors='replace'))
        except Exception:
            pass
    return strings

def collect(dexdir):
    allstr = set()
    for fn in os.listdir(dexdir):
        if fn.endswith('.dex'):
            allstr |= dex_strings(os.path.join(dexdir, fn))
    return allstr

print("Loading QQ Music dexes...")
qm = collect(os.path.join(os.path.dirname(__file__), 'qm_dex'))
print(f"QQ Music strings: {len(qm)}")
print("Loading Xiaomi Music dexes...")
xm = collect(os.path.join(os.path.dirname(__file__), 'xm_dex'))
print(f"Xiaomi Music strings: {len(xm)}")

# 1. Class name overlap for tencent packages
def classes_starting_with(s, prefix):
    return {x for x in s if x.startswith(prefix)}

prefixes = ['Lcom/tencent/qqmusic/', 'Lcom/tencent/qqmusiccommon/', 'Lcom/tencent/qqmusicmobile/',
            'Lcom/tencentmusic/', 'Lcom/tencent/qqmusicbusiness/']
report = {}
for p in prefixes:
    qmc = classes_starting_with(qm, p)
    xmc = classes_starting_with(xm, p)
    if qmc or xmc:
        inter = qmc & xmc
        report[p] = dict(qm=len(qmc), xm=len(xmc), overlap=len(inter),
                         overlap_pct_of_qm=round(100*len(inter)/len(qmc), 1) if qmc else 0)
print("\n=== Tencent class name overlap (L-prefixed type descriptors) ===")
print(json.dumps(report, indent=2))

# 2. Check QMHelper hook signature strings
signatures = {
  # name: (search string, is_class_descriptor_or_fullname)
  "BaseFragment [onResume]this[%s]": "[onResume]this[%s]",
  "splash postSplashResult": "postSplashResult",
  "HomePage not support native tab": "not support native tab, do nothing",
  "CLS MainDesktopHeader(fqcn)": "com.tencent.qqmusic.ui.MainDesktopHeader",
  "MainDesktopHeader showMusicWorldEntranceBtn": "showMusicWorldEntranceBtn",
  "CLS AppStarterActivity(fqcn)": "com.tencent.qqmusic.activity.AppStarterActivity",
  "Setting TYPE_SWITCH log": "onSwitchLister can't be null while type is TYPE_SWITCH",
  "DebugSettingFragment 'DebugMode'": "DebugMode",
  "setting is null": "setting is null",
  "initMusicAccoutEnter: start": "initMusicAccoutEnter: start",
  "CLS PersonalCenterEntryView(fqcn)": "com.tencent.qqmusic.fragment.morefeatures.settings.view.PersonalCenterEntryView",
  "PersonalCenterEntryView(str)": "PersonalCenterEntryView",
  "BannerTips QPLAY_AUTO log": "IS USING QPLAY_AUTO, FORBID BANNER_TIPS",
  "CLS SettingFeaturesFragment(fqcn)": "com.tencent.qqmusic.fragment.morefeatures.SettingFeaturesFragment",
  "KEY_SETTING_JUMP_ITEM_ENUM": "KEY_SETTING_JUMP_ITEM_ENUM",
  "CLS MyMusicUserInfoViewHolder(fqcn)": "com.tencent.qqmusic.modular.module.musichall.views.viewholders.cell.MyMusicUserInfoViewHolder",
  "showTaskAndVipBubble": "showTaskAndVipBubble",
  "refreshVipIcons": "refreshVipIcons",
  "[getClientStrategyStrategyId]": "[getClientStrategyStrategyId]: this:",
  "[initLiveGuide]": "[initLiveGuide]",
  "[showCurrentListen] long audio ad": "[showCurrentListen]--block by long audio ad recall entrance show",
  "ACTION_QQFRIEND": "ACTION_QQFRIEND",
  "CLS PlayerViewModel(fqcn)": "com.tencent.qqmusic.business.playernew.viewmodel.PlayerViewModel",
  "PlayerViewModel(str)": "PlayerViewModel",
  "SPManager": "SPManager",
  "Appstarter activity oncreate": "Appstarter activity oncreate",
  "[addSecondFragment] gotoFirstFragment": "[addSecondFragment] gotoFirstFragment",
  "LOGIN_CHECK_SDK": "LOGIN_CHECK_SDK",
  "[parseModuleItem] ": "[parseModuleItem] ",
  "GSON cannot serialize ": "GSON cannot serialize ",
  "UIModeManager": "UIModeManager",
  "CLS ApkDownloadAdBar(fqcn)": "com.tencent.qqmusic.business.ad.topbarad.apkdownload.ApkDownloadAdBar",
  "ApkDownloadAdBar(str)": "ApkDownloadAdBar",
  "MusicWorldEntrance": "MusicWorldEntrance",
  "getFileEKey filePath is empty!": "getFileEKey filePath is empty!",
  "decryptFile srcFilePath = ": "decryptFile srcFilePath = ",
  "decryptFile create dest = ": "decryptFile create dest = ",
  "updateBottomTips ": "updateBottomTips ",
  "[onResult] show mv icon.": "[onResult] show mv icon.",
  "[onBind] hide the song genre tags info.": "[onBind] hide the song genre tags info.",
  "showNewUserGuide hasGuideShowing =": "showNewUserGuide hasGuideShowing =",
  "[onBind] show top song info: peakCount=": "[onBind] show top song info: peakCount=",
  "[handleJsRequest] writeGlobalData": "[handleJsRequest] writeGlobalData",
  "CLS AlbumIntroduceViewHolder(fqcn)": "com.tencent.qqmusic.albumdetail.ui.viewholders.AlbumIntroduceViewHolder",
  "tvAlbumDetail": "tvAlbumDetail",
  "tvAlbumInfo": "tvAlbumInfo",
  "CLS SettingView(fqcn)": "com.tencent.qqmusic.fragment.morefeatures.settings.view.SettingView",
  "initView: titleText ": "initView: titleText ",
  "[getDownloadSongName] songInfo is null": "[getDownloadSongName] songInfo is null",
  "CLS StorageVolume(fqcn)": "com.tencent.qqmusiccommon.storage.StorageVolume",
  "StorageVolume [mStorageId=": "StorageVolume [mStorageId=",
  "StorageVolume From Android API": "StorageVolume From Android API SDK_INT : ",
  "VipAdBarData(posId=": "VipAdBarData(posId=",
  "[getSyncSkinIdInUse]": "[getSyncSkinIdInUse][event:has not update skinIdInUse,use SkinIdToSwitch = %s]",
  "AdResponseData(retCode=": "AdResponseData(retCode=",
  "JceResponseItemConverter": "JceResponseItemConverter",
  " ReleasedForAndroid[": " ReleasedForAndroid[",
  "getMusicUin": "getMusicUin",
  "[requestAdvertisement] start": "[requestAdvertisement] start",
  "CLS MusicWorldPullEntrance(fqcn)": "com.tencent.qqmusic.fragment.mymusic.my.musicworld.MusicWorldPullEntrance",
  "CLS MERJni(fqcn)": "com.tencent.qqmusic.modular.framework.encrypt.logic.MERJni",
  "CLS ModeSettingFragment(fqcn)": "com.tencent.qqmusic.fragment.morefeatures.ModeSettingFragment",
  "runningModeSetting": "runningModeSetting",
  "X5 WebView(fqcn)": "com.tencent.smtt.sdk.WebView",
  "CLS DebugSettingFragment(fqcn)": "com.tencent.qqmusic.fragment.debug.DebugSettingFragment",
  "GSON cannot serialize": "GSON cannot serialize",
}

def raw_search(dexdir, needle):
    """Raw byte search in all dex files (works for MUTF-8 ASCII and UTF-8 CJK)."""
    nb = needle.encode('utf-8', errors='replace')
    hits = []
    for fn in sorted(os.listdir(dexdir)):
        if not fn.endswith('.dex'):
            continue
        with open(os.path.join(dexdir, fn), 'rb') as f:
            data = f.read()
        if nb in data:
            hits.append(fn)
    return hits

print("\n=== QMHelper hook signature strings: presence in each APK ===")
print(f"{'signature':<50} {'QQ':<3} {'XM':<3} note")
results = {}
for name, needle in signatures.items():
    in_qm = 'Y' if raw_search(os.path.join(os.path.dirname(__file__), 'qm_dex'), needle) else '-'
    in_xm = 'Y' if raw_search(os.path.join(os.path.dirname(__file__), 'xm_dex'), needle) else '-'
    results[name] = (in_qm, in_xm)
    print(f"{name:<50} {in_qm:<3} {in_xm:<3}")

ok = sum(1 for q, x in results.values() if x == 'Y')
print(f"\nSignatures present in Xiaomi Music: {ok}/{len(results)}")

# also save strings sets for later analysis
with open(os.path.join(os.path.dirname(__file__), 'qm_strings.txt'), 'w', encoding='utf-8') as f:
    f.write('\n'.join(sorted(qm)))
with open(os.path.join(os.path.dirname(__file__), 'xm_strings.txt'), 'w', encoding='utf-8') as f:
    f.write('\n'.join(sorted(xm)))
