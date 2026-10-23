#!/usr/bin/env bash
set -euo pipefail

bundle="${XIAOHEIHE_NATIVE_BUNDLE:-$HOME/.xhh_sdk/bundles}"
if [ ! -f "$bundle/loader.jar" ]; then
  bundle="$(find "$bundle" -mindepth 1 -maxdepth 1 -type d -exec test -f {}/loader.jar \; -print | sort | head -n 1)"
fi
java="${XIAOHEIHE_NATIVE_JAVAC:-$(dirname "${XIAOHEIHE_NATIVE_JAVA:-/usr/lib/jvm/java-21-openjdk-amd64/bin/java}")/javac}"
root="$(cd "$(dirname "$0")/.." && pwd)"

"$java" -cp "$bundle/loader.jar:$bundle/deps/*" -d "$root/native/classes" "$root/native/XiaoheiheNativeSigner.java"
printf 'built %s\n' "$root/native/classes/com/xiaoheihe/XiaoheiheNativeSigner.class"
