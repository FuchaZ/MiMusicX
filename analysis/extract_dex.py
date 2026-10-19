# -*- coding: utf-8 -*-
"""把关键 dex 解到 scratch 目录，供 dexdump / baksmali 使用。"""
import sys, zipfile, os
sys.stdout.reconfigure(encoding='utf-8')

# 宿主 APK 路径：可用环境变量 XMPU_APK 覆盖
APK_PATH = os.environ.get("XMPU_APK", r"E:\QQ下载\base.apk")
# 解包产物放 analysis/xm_dex/（已在 .gitignore 中）
OUTDIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "xm_dex")
TARGETS = ["classes.dex", "classes6.dex", "classes8.dex", "classes9.dex",
           "classes10.dex", "classes11.dex"]

os.makedirs(OUTDIR, exist_ok=True)
with zipfile.ZipFile(APK_PATH) as z:
    for n in TARGETS:
        dst = os.path.join(OUTDIR, n)
        with open(dst, "wb") as f:
            f.write(z.read(n))
        print(f"extracted {n:<14} {os.path.getsize(dst):>10} bytes -> {dst}")
