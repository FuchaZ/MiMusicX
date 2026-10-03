# -*- coding: utf-8 -*-
"""Final checks: ad-mark fields, home/settings/player classes in qqmusiclite (XM)."""
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

xm = collect(os.path.join(HERE, 'xm_dex'))

# 1. Ad-mark related field/strings in XM
print("=== XM ad-mark strings (CommonAdsHook relies on creative/option/isShowAdMark, madAdInfo/adTag) ===")
for n in ["isShowAdMark", "madAdInfo", "creative", "adTag", "广告", "VipAdBarData(posId=", "AdResponseData(retCode=", "getAds"]:
    hits = sum(1 for x in xm if n in x)
    print(f"  {n:<28} hits: {hits}")

# 2. XM qqmusiclite home/settings/player representative classes
def sample(prefix, n=15):
    return sorted(x for x in xm if x.startswith(prefix))[:n]

for label, prefix in [
    ("home", "Lcom/tencent/qqmusiclite/ui/Main"),
    ("home2", "Lcom/tencent/qqmusiclite/ui/Home"),
    ("settings", "Lcom/tencent/qqmusiclite/fragment/morefeatures"),
    ("settings2", "Lcom/tencent/qqmusiclite/fragment/setting"),
    ("player", "Lcom/tencent/qqmusiclite/business/playernew"),
    ("ad biz", "Lcom/tencent/qqmusiclite/ad/"),
    ("live", "Lcom/tencent/qqmusiclite/business/live"),
    ("debug", "Lcom/tencent/qqmusiclite/fragment/debug"),
]:
    s = sample(prefix)
    print(f"\n=== XM {label} ({prefix}) : {sum(1 for x in xm if x.startswith(prefix))} classes ===")
    for x in s[:12]:
        print("   " + x)

# 3. XM: strings that look like strategy/config — 'strategy'
print("\n=== XM strings with 'Strategy' (count) ===")
print("  ", sum(1 for x in xm if 'Strategy' in x))
# 4. XM: red dot
print("=== XM strings w/ redDot|RedDot ===")
for n in ["redDot", "RedDot"]:
    print(f"  {n}: {sum(1 for x in xm if n in x)}")
# 5. XM process names / application class hints
apps = sorted(x for x in xm if x.startswith('Lcom/miui/player/') and ('Application' in x or 'App;' in x))[:15]
print("\n=== XM application classes ===")
for x in apps:
    print("   " + x)
