#!/usr/bin/env bash
# Build file APK của app GHN Dashboard mà KHÔNG cần Android Studio / Gradle.
#
# Cách dùng:
#   ANDROID_SDK=/duong/dan/android-sdk KEYSTORE=/duong/dan/ghn.keystore KEY_PASS=... \
#     ./android/build.sh https://ten-app.onrender.com [versionCode] [versionName]
#
# Cần: JDK 17+, Android SDK có "platforms;android-34" và "build-tools;34.0.0".
# KEYSTORE: file khoá ký app. GIỮ KỸ file này: các bản cập nhật sau phải ký bằng đúng khoá cũ thì
# điện thoại mới cho cài đè. Chưa có thì script tự tạo (lần đầu).
set -euo pipefail

URL="${1:?Cần địa chỉ dashboard, vd. https://ten-app.onrender.com}"
VCODE="${2:-1}"
VNAME="${3:-1.0}"
SDK="${ANDROID_SDK:?Đặt biến ANDROID_SDK trỏ tới thư mục Android SDK}"
BT="$SDK/build-tools/34.0.0"
JAR="$SDK/platforms/android-34/android.jar"
KEYSTORE="${KEYSTORE:?Đặt biến KEYSTORE (đường dẫn file khoá ký app)}"
KEY_PASS="${KEY_PASS:?Đặt biến KEY_PASS (mật khẩu khoá)}"

HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="${OUT_DIR:-$HERE/build}"
rm -rf "$OUT" && mkdir -p "$OUT/gen" "$OUT/classes" "$OUT/res" "$OUT/dex"

# 1) Ghi địa chỉ dashboard + số phiên bản vào bản sao tài nguyên
cp -r "$HERE/res/." "$OUT/res/"
python3 - "$OUT/res/values/strings.xml" "$URL" <<'PY'
import sys, re, html
p, url = sys.argv[1], sys.argv[2]
s = open(p, encoding="utf-8").read()
s = re.sub(r'(<string name="base_url">)[^<]*(</string>)', lambda m: m.group(1) + html.escape(url) + m.group(2), s)
open(p, "w", encoding="utf-8").write(s)
PY
sed -e "s/android:versionCode=\"[0-9]*\"/android:versionCode=\"$VCODE\"/" \
    -e "s/android:versionName=\"[^\"]*\"/android:versionName=\"$VNAME\"/" \
    "$HERE/AndroidManifest.xml" > "$OUT/AndroidManifest.xml"

# 2) Tài nguyên -> APK gốc + R.java
"$BT/aapt2" compile --dir "$OUT/res" -o "$OUT/res.zip"
"$BT/aapt2" link -I "$JAR" --manifest "$OUT/AndroidManifest.xml" --java "$OUT/gen" \
    --min-sdk-version 24 --target-sdk-version 34 -o "$OUT/base.apk" "$OUT/res.zip"

# 3) Java -> class -> dex
javac -encoding UTF-8 -source 8 -target 8 -nowarn -Xlint:-options -bootclasspath "$JAR" -classpath "$BT/core-lambda-stubs.jar" \
    -d "$OUT/classes" $(find "$HERE/src" "$OUT/gen" -name '*.java')
(cd "$OUT/classes" && jar cf "$OUT/classes.jar" .)
# d8 của build-tools 34 lỗi với class biên dịch bằng JDK 21: ưu tiên d8 mới trong cmdline-tools
D8="$SDK/cmdline-tools/latest/bin/d8"; [ -x "$D8" ] || D8="$BT/d8"
"$D8" --release --min-api 24 --lib "$JAR" --output "$OUT/dex" "$OUT/classes.jar"

# 4) Ghép dex vào APK, căn chỉnh, ký
cp "$OUT/base.apk" "$OUT/unsigned.apk"
(cd "$OUT/dex" && zip -q -j "$OUT/unsigned.apk" classes.dex)
"$BT/zipalign" -f -p 4 "$OUT/unsigned.apk" "$OUT/aligned.apk"
if [ ! -f "$KEYSTORE" ]; then
  keytool -genkeypair -keystore "$KEYSTORE" -alias ghn -keyalg RSA -keysize 2048 -validity 10000 \
    -storepass "$KEY_PASS" -keypass "$KEY_PASS" -dname "CN=GHN QBI Dashboard, O=GHN, C=VN" >/dev/null 2>&1
  echo "Đã tạo khoá ký mới: $KEYSTORE (hãy cất giữ cẩn thận)"
fi
"$BT/apksigner" sign --ks "$KEYSTORE" --ks-key-alias ghn --ks-pass "pass:$KEY_PASS" --key-pass "pass:$KEY_PASS" \
    --out "$OUT/GHN-Dashboard-$VNAME.apk" "$OUT/aligned.apk"
"$BT/apksigner" verify "$OUT/GHN-Dashboard-$VNAME.apk"
echo "Xong: $OUT/GHN-Dashboard-$VNAME.apk"
