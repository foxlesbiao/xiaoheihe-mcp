# 小黑盒 MCP：签名实现逆向与设计详解

> 本文是小黑盒 MCP Server (`xiaoheihe-mcp`) 的技术细节文档，完整记录了请求签名的逆向过程与实现方案。仓库本身不含签名算法源码，签名器以外部命令方式提供。

## 目录

1. [概述](#概述)
2. [抓包分析](#抓包分析)
3. [Web 签名算法](#web-签名算法)
4. [Native App 签名（Unidbg）](#native-app-签名unidbg)
5. [SMS 登录加密](#sms-登录加密)
6. [外部签名器接口设计](#外部签名器接口设计)
7. [合规与免责](#合规与免责)

---

## 概述

小黑盒（xiaoheihe.cn）的 API 请求需要两类签名参数：

| 签名类型 | 参数 | 使用场景 |
|---|---|---|
| Web 签名 | `hkey`、`_rnd`、`_time`、`nonce` | 公开 Web API 浏览 |
| Native 签名 | `hkey`、`_rnd`（由 SO 库计算） | 登录、已登录功能 |

两者输出格式相似但计算路径完全不同。Web 签名是纯算法，Native 签名由 Android `libnative-lib.so` 中的 JNI 方法计算。

---

## 抓包分析

### 工具

- **Charles Proxy** / **mitmproxy**：HTTPS 中间人抓包
- **Frida**：Hook Java 层方法，追踪调用链
- **Ghidra** / **IDA Pro**：SO 静态分析
- **Unidbg**：ARM 模拟执行 SO

### 关键发现

从 Charles 抓包观察到，每个 API 请求都带有以下签名参数：

```
_time=1700000000
nonce=aBcD...32位随机字符
hkey=XXXX0000
_rnd=15:hex_string
version=999.0.4
```

通过 Frida hook `okhttp3.Request` 和 `OkHttpClient`，定位到签名在 `com.max.xiaoheihe.utils.NDKTools.encode()` 和 `com.graphice.shaderar.ShaderManager` 中生成。

---

## Web 签名算法

Web 签名用于非登录状态的公开 API 请求，不依赖 SO 库，是纯 Python/JS 可实现的算法。

### 参数说明

| 参数 | 说明 |
|---|---|
| `_time` | Unix 时间戳（秒） |
| `nonce` | 32 位随机字符 `[0-9a-zA-Z]` |
| `hkey` | 8 位十六进制签名值 |
| `_rnd` | HMAC-SHA256 签名，前缀 `15:` |
| `version` | 固定 `"999.0.4"` |

### hkey 算法步骤

```python
# 1. 自定义字符表
R_CHARSET = "AB45STUVWZEFGJ6CH01D237IXYPQRKLMN89"

# 2. 将 timestamp+1 通过字符表映射
part_time = _tw(str(timestamp + 1), R_CHARSET, 2)
# _tw: 取字符表前 n 个字符，每个输入字符 ord(char) % n 映射

# 3. 规范化路径：/api/endpoint/ (首尾加 /)
part_path = _rw(normalized_path, R_CHARSET)
# _rw: 每个输入字符 ord(char) % len(charset) 映射

# 4. nonce 同样映射
part_nonce = _rw(nonce, R_CHARSET)

# 5. 三段字符串交错拼接，取前 20 字符
combined = _interleave([part_time, part_path, part_nonce])[:20]

# 6. MD5 摘要
digest = hashlib.md5(combined.encode("utf-8")).hexdigest()

# 7. 取 digest 最后 6 字符，做自定义列混淆
transformed = _mix_columns([ord(c) for c in digest[-6:]])
# _mix_columns 使用 _ty/_da/_vs/_dol_c/_dl 系列位运算和 XOR

# 8. 上半部分：sum(transformed) % 100 补零
upper = f"{sum(transformed) % 100:02d}"

# 9. 下半部分：digest 前 5 字符经字符表映射
lower = _tw(digest[:5], R_CHARSET, 4)

# 10. hkey = lower + upper (8 字符)
```

### _rnd 算法步骤

```python
RND_KEY = "Z7mFG4tQp9Ws2LxB8H"

# HMAC-SHA256，密钥为固定字符串
message = (RND_KEY + nonce + f"{timestamp}:{nonce}").encode("utf-8")
hmac_digest = hmac.new(
    RND_KEY.encode("utf-8"),
    message,
    hashlib.sha256
).hexdigest()

# _rnd = "15:" + hex_digest
```

### 伪代码总结

```
hkey = map(md5(interleave(map(time+1), map(path), map(nonce))[:20]))
     + pad(sum(mix_columns(md5[-6:])) % 100)

_rnd = "15:" + HMAC-SHA256(key=RND_KEY, msg=RND_KEY+nonce+time+":"+nonce)
```

---

## Native App 签名（Unidbg）

Native 签名用于登录和已登录功能，签名值由 Android SO 库计算，无法用纯 Python 复现。方案是使用 [Unidbg](https://github.com/zhkl0228/unidbg) 模拟执行 SO 文件。

### 逆向目标

- `com.graphice.shaderar.ShaderManager`：主要签名生成类
- `com.max.xiaoheihe.utils.NDKTools`：辅助编码类
- `libglesv3_1.so`：ShaderManager 的 JNI 实现
- `libnative-lib.so`：NDKTools 的 JNI 实现

### 签名流程

Native 签名的完整调用链如下：

```
1. 初始化 SO：
   ShaderManager.setParseDepth("/tmp/xhh-cache", false)
   ShaderManager.setSecLevel()
   ShaderManager.setBlendMode(BLEND_SEED, timestamp)

2. 获取 chunk flag：
   ShaderManager.getChunkFlag(context, CHUNK_SEED) → chunk_flag

3. 生成 nonce：
   ShaderManager.getIdxOffset(context, chunk_flag, timestamp, identity) → nonce

4. 设置签名上下文：
   ShaderManager.setViewport(timestamp, nonce)
   ShaderManager.setGramLen(path, nonce)
   ShaderManager.setBuf(timestamp, nonce)
   ShaderManager.setDepRel(device_model, nonce)
   ShaderManager.setDLen(os_version, nonce)
   ShaderManager.setPtrOffset(app_version, nonce)

5. 编码：
   NDKTools.encode(context, path, timestamp, nonce)

6. 获取签名值：
   ShaderManager.getObjType(context, nonce, false) → hkey
   ShaderManager.getObjType(context, nonce, true)  → rnd_suffix

7. 输出：
   _rnd = security_version_or_os_version + ":" + rnd_suffix
```

### 种子常量

从 SO 中提取的两个关键种子：

```
CHUNK_SEED = "PAENEHAMGACOBHIEMIHIJLKJPMMHJMMQABCNGBPPENCENP"
BLEND_SEED = "MFANEHAMGACOBHIEMIHIJLKJPMMHJMMLABCNGBPPENCENPOM"
```

这些种子作为 JNI 参数传入 `getChunkFlag()` 和 `setBlendMode()`。

### JNI Hook 与环境模拟

Unidbg 需要模拟 Android 环境中 SO 期望的所有 JNI 调用：

```java
// 包名
getPackageName() → "com.max.xiaoheihe"

// 文件路径
getFilesDir() → "/data/user/0/com.max.xiaoheihe/files"
getCacheDir() → "/data/user/0/com.max.xiaoheihe/cache"

// 设备信息
Build.MODEL → 设备型号 (如 "V2245A")
Build.BRAND → "vivo"
Build.VERSION.RELEASE → Android 版本

// 签名验证
PackageInfo.signatures → 从 APK 解析证书

// SharedPreferences
getSharedPreferences(...) → 空实现
getString("DebugInfo") → imei + identity (设备指纹)

// 其他
MODE_PRIVATE → 0
```

### 安全上下文（getui/fix）

如果从真机抓包获取了 `/account/getui/fix` 的响应，其中包含 `security_code` 和 `security_version`，需要在签名前注入：

```java
// 注入安全上下文
ShaderManager.setHdrField(Base64.decode(security_code))
ShaderManager.b = true       // 静态字段
ShaderManager.c = security_version  // 静态字段（int）
```

这会影响 `_rnd` 的前缀：使用 `security_version` 而非 `os_version`。

### Unidbg 环境搭建

```java
AndroidEmulator emulator = AndroidEmulatorBuilder.for64Bit()
    .setProcessName("com.max.xiaoheihe")
    .addBackendFactory(new Unicorn2Factory(true))
    .build();

emulator.getSyscallHandler().addIOResolver(this);
Memory memory = emulator.getMemory();
memory.setLibraryResolver(new AndroidResolver(23));

VM vm = emulator.createDalvikVM(new File(resources, "minimal-app.apk"));
vm.setVerbose(false);
vm.setJni(this);

// 加载两个关键 SO
DalvikModule shaderModule = vm.loadLibrary(new File(resources, "libglesv3_1.so"), true);
shaderModule.callJNI_OnLoad(emulator);
DalvikModule nativeModule = vm.loadLibrary(new File(resources, "libnative-lib.so"), true);
nativeModule.callJNI_OnLoad(emulator);

DvmClass shaderManager = vm.resolveClass("com/graphice/shaderar/ShaderManager");
DvmClass ndkTools = vm.resolveClass("com/max/xiaoheihe/utils/NDKTools");
```

### 输出格式

Native 签名的 JSON 输出：

```json
{
  "path": "/account/login_code/",
  "_time": "1700000000",
  "nonce": "aBcD...32字符",
  "hkey": "XXXX0000",
  "_rnd": "15:hex_string"
}
```

---

## SMS 登录加密

### 流程

1. **发送验证码**：`POST /account/get_login_code/`
2. **提交验证码**：`POST /account/login_code/`

两者都需要将手机号 RSA 加密后放入请求体。

### RSA 加密

App 使用 RSA PKCS#1 v1.5 加密手机号，公钥从 APK 中提取：

- 密钥长度：1024 位
- 填充方式：PKCS#1 v1.5
- Base64 编码后按 76 字符换行（Android 风格）

加密实现可以参考 Python 的 `rsa` 库或手写 `pow(m, e, n)`。

### 登录参数

登录请求还需要以下查询参数（与签名一起发送）：

```
heybox_id=-1
imei=<设备指纹>
device_info=<设备型号>
os_type=Android
os_version=<Android版本>
x_os_type=Android
x_client_type=mobile
x_app=heybox
version=1.3.398
build=1142
channel=heybox
time_zone=Asia/Shanghai
dw=600
netmode=wifi
```

---

## 外部签名器接口设计

仓库不包含签名实现，用户需要自行提供外部签名器命令。

### 配置

在 `~/.xiaoheihe-mcp/config.json` 中：

```json
{
  "signer_command": "/path/to/your/signer"
}
```

或通过环境变量：

```bash
export XIAOHEIHE_SIGNER_COMMAND=/path/to/your/signer
```

### 接口约定

外部签名器接受以下命令行参数：

```
signer <path> <timestamp> <identity> <device> <os-version> <app-version> <imei> <security-code> <security-version>
```

输出 JSON（stdout 最后一行）：

```json
{
  "path": "/api/endpoint/",
  "_time": "1700000000",
  "nonce": "随机32字符",
  "hkey": "8位签名",
  "_rnd": "前缀:签名值"
}
```

MCP Server 会将输出中的 `_time`、`nonce`、`hkey`、`_rnd` 合并到查询参数中发送请求。

---

## 合规与免责

- 本文仅供个人学习、研究和兼容性分析使用。
- 逆向工程可能违反平台服务条款和当地法律。
- 请勿将本文内容用于商业化、批量采集或恶意用途。
- 使用签名器产生的账号风险由使用者自行承担。
- 请遵守平台条款，只访问自己有权访问的数据。
