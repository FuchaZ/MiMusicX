#!/bin/bash
# 构建 MiMusicX Xposed 模块 APK
# 用法: bash build.sh
# 工具链: D:\reasonix backup\02-移动与安卓\apk开发\sdk (build-tools 35.0.0, android-35)
# 注意: aapt2 不兼容中文路径，构建在 ASCII 临时目录进行，产物拷回本目录
set -e

PROJ="$(cd "$(dirname "$0")" && pwd)"
export JAVA_HOME="/c/Program Files/Eclipse Adoptium/jdk-17.0.19.10-hotspot"
export PATH="$JAVA_HOME/bin:$PATH"
SDK="D:/reasonix backup/02-移动与安卓/apk开发/sdk"
BT="$SDK/build-tools/35.0.0"
W="/c/Users/FuChaZ/AppData/Local/Temp/xmpu_build"

rm -rf "$PROJ/build" && mkdir -p "$PROJ/build/classes" "$PROJ/build/dex" "$W"
cp "$SDK/platforms/android-35/android.jar" /c/Users/FuChaZ/AppData/Local/Temp/android-35.jar

echo "[1/6] javac"
(cd "$PROJ" && find stubs src -name "*.java" > "$W/sources.txt")
(cd "$PROJ" && javac --release 8 -encoding UTF-8 -d build/classes @"$W/sources.txt")

echo "[2/6] d8"
(cd "$PROJ/build/classes" && java -cp "$BT/lib/d8.jar" com.android.tools.r8.D8 \
  --release --min-api 26 --lib /c/Users/FuChaZ/AppData/Local/Temp/android-35.jar \
  --output "$PROJ/build/dex" local/xmplaylist/unlock/*.class)

echo "[3/6] aapt2 link"
cp "$PROJ/AndroidManifest.xml" "$W/"
"$BT/aapt2.exe" link -o "$W/unsigned.apk" --manifest "$W/AndroidManifest.xml" \
  -I /c/Users/FuChaZ/AppData/Local/Temp/android-35.jar \
  --min-sdk-version 26 --target-sdk-version 32 --version-code 5 --version-name 1.3.0 \
  --auto-add-overlay

echo "[4/6] pack dex + assets"
cp "$PROJ/build/dex/classes.dex" "$PROJ/assets/xposed_init" "$PROJ/assets/xposed_scope" "$W/"
(cd "$W" && python -c "
import zipfile
z = zipfile.ZipFile('unsigned.apk', 'a')
z.write('classes.dex', 'classes.dex')
z.write('xposed_init', 'assets/xposed_init')
z.write('xposed_scope', 'assets/xposed_scope')
z.close()
")

echo "[5/6] zipalign"
(cd "$W" && "$BT/zipalign.exe" -f -p 4 unsigned.apk aligned.apk)

echo "[6/6] apksigner"
if [ ! -f "$W/debug.jks" ]; then
  keytool -genkeypair -keystore "$W/debug.jks" -alias androiddebugkey -storepass android \
    -keypass android -keyalg RSA -keysize 2048 -validity 10000 \
    -dname "CN=Android Debug,O=Android,C=US"
fi
(cd "$W" && java -jar "$BT/lib/apksigner.jar" sign --ks debug.jks --ks-pass pass:android \
  --key-pass pass:android --out MiMusicX-1.3.0.apk aligned.apk)

cp "$W/MiMusicX-1.3.0.apk" "$PROJ/"
echo "DONE: $PROJ/MiMusicX-1.3.0.apk"
