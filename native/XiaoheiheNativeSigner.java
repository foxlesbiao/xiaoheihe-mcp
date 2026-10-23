package com.xiaoheihe;

import com.github.unidbg.AndroidEmulator;
import com.github.unidbg.Module;
import com.github.unidbg.arm.backend.Unicorn2Factory;
import com.github.unidbg.file.FileResult;
import com.github.unidbg.file.IOResolver;
import com.github.unidbg.linux.android.dvm.api.PackageInfo;
import com.github.unidbg.linux.android.dvm.api.Signature;
import com.github.unidbg.linux.android.dvm.array.ArrayObject;
import com.github.unidbg.linux.android.AndroidEmulatorBuilder;
import com.github.unidbg.linux.android.AndroidResolver;
import com.github.unidbg.linux.android.dvm.AbstractJni;
import com.github.unidbg.file.linux.AndroidFileIO;
import com.github.unidbg.linux.android.dvm.BaseVM;
import com.github.unidbg.linux.android.dvm.DalvikModule;
import com.github.unidbg.linux.android.dvm.DvmField;
import com.github.unidbg.linux.android.dvm.wrapper.DvmInteger;
import com.github.unidbg.linux.android.dvm.DvmClass;
import com.github.unidbg.linux.android.dvm.DvmObject;
import com.github.unidbg.linux.android.dvm.StringObject;
import com.github.unidbg.linux.android.dvm.VM;
import com.github.unidbg.linux.android.dvm.VaList;
import com.github.unidbg.linux.android.dvm.VarArg;
import com.github.unidbg.linux.android.dvm.array.ByteArray;
import com.github.unidbg.linux.file.ByteArrayFileIO;
import com.github.unidbg.memory.Memory;
import com.github.unidbg.Emulator;

import java.io.File;
import java.nio.charset.Charset;
import java.lang.reflect.Method;
import java.util.Base64;
import net.dongliu.apk.parser.ApkParser;
import net.dongliu.apk.parser.bean.CertificateMeta;
import java.nio.charset.StandardCharsets;

public final class XiaoheiheNativeSigner extends AbstractJni
        implements IOResolver<AndroidFileIO> {
    private static final String PACKAGE_NAME = "com.max.xiaoheihe";
    private static final String CHUNK_SEED =
            "PAENEHAMGACOBHIEMIHIJLKJPMMHJMMQABCNGBPPENCENP";
    private static final String BLEND_SEED =
            "MFANEHAMGACOBHIEMIHIJLKJPMMHJMMLABCNGBPPENCENPOM";

    private final AndroidEmulator emulator;
    private final VM vm;
    private final DvmClass shaderManager;
    private final DvmClass ndkTools;
    private final DvmObject<?> context;
    private final String deviceModel;
    private final String osVersion;
    private final String imei;
    private final File apkFile;
    private boolean shaderHasRnd;
    private int shaderVersion;
    private String currentIdentity = "-1";

    public static void main(String[] args) throws Exception {
        if (args.length != 10) {
            throw new IllegalArgumentException(
                    "usage: XiaoheiheNativeSigner <resources> <path> <timestamp> <identity> <device> <os-version> <app-version> <imei> <security-code> <security-version>");
        }
        String timestamp = args[2].isBlank()
                ? String.valueOf(System.currentTimeMillis() / 1000)
                : args[2];
        XiaoheiheNativeSigner signer = new XiaoheiheNativeSigner(args[0], args[4], args[5], args[7]);
        try {
            signer.printJson(signer.sign(
                    args[1], timestamp, args[3], args[6], args[7], args[8], args[9]));
        } finally {
            signer.close();
        }
    }

    private XiaoheiheNativeSigner(String resources, String deviceModel, String osVersion, String imei)
            throws Exception {
        this.deviceModel = deviceModel;
        this.osVersion = osVersion;
        this.imei = imei;
        this.apkFile = new File(resources + "/minimal-app.apk");
        emulator = AndroidEmulatorBuilder.for64Bit()
                .setProcessName(PACKAGE_NAME)
                .addBackendFactory(new Unicorn2Factory(true))
                .build();
        emulator.getSyscallHandler().addIOResolver(this);
        Memory memory = emulator.getMemory();
        memory.setLibraryResolver(new AndroidResolver(23));
        vm = emulator.createDalvikVM(new File(resources + "/minimal-app.apk"));
        vm.setVerbose(false);
        vm.setJni(this);
        DalvikModule module = vm.loadLibrary(new File(resources + "/libglesv3_1.so"), true);
        module.callJNI_OnLoad(emulator);
        DalvikModule nativeModule = vm.loadLibrary(new File(resources + "/libnative-lib.so"), true);
        nativeModule.callJNI_OnLoad(emulator);
        shaderManager = vm.resolveClass("com/graphice/shaderar/ShaderManager");
        ndkTools = vm.resolveClass("com/max/xiaoheihe/utils/NDKTools");
        context = vm.resolveClass(
                "android/content/ContextWrapper",
                vm.resolveClass("android/content/Context")
        ).newObject(null);
    }

    private void printJson(String json) {
        System.out.println(json);
    }

    private String sign(
            String rawPath,
            String timestamp,
            String identity,
            String appVersion,
            String imei,
            String securityCode,
            String securityVersion) {
        String path = normalizePath(rawPath);
        currentIdentity = identity == null || identity.isBlank() ? "-1" : identity;
        initialize();
        if (!securityCode.isBlank()) {
            shaderManager.callStaticJniMethod(
                    emulator,
                    "setHdrField([B)V",
                    new ByteArray(vm, Base64.getDecoder().decode(securityCode)));
            setShaderState("b", "Z", Boolean.TRUE);
            try {
                setShaderState("c", "Ljava/lang/Integer;",
                        DvmInteger.valueOf(vm, Integer.parseInt(securityVersion)));
            } catch (NumberFormatException ignored) {
            }
        }
        String chunkFlag = stringOf(shaderManager.callStaticJniMethodObject(
                emulator,
                "getChunkFlag(Landroid/content/Context;Ljava/lang/String;)Ljava/lang/String;",
                context, new StringObject(vm, CHUNK_SEED)));
        String nonce = stringOf(shaderManager.callStaticJniMethodObject(
                emulator,
                "getIdxOffset(Landroid/content/Context;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;",
                context, new StringObject(vm, chunkFlag),
                new StringObject(vm, timestamp), new StringObject(vm, identity)));
        call("setViewport(Ljava/lang/String;Ljava/lang/String;)V", timestamp, nonce);
        call("setGramLen(Ljava/lang/String;Ljava/lang/String;)V", path, nonce);
        call("setBuf(Ljava/lang/String;Ljava/lang/String;)V", timestamp, nonce);
        call("setDepRel(Ljava/lang/String;Ljava/lang/String;)V", deviceModel, nonce);
        call("setDLen(Ljava/lang/String;Ljava/lang/String;)V", osVersion, nonce);
        call("setPtrOffset(Ljava/lang/String;Ljava/lang/String;)V", appVersion, nonce);
        ndkTools.callStaticJniMethodObject(
                emulator,
                "encode(Ljava/lang/Object;Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;",
                context, new StringObject(vm, path), new StringObject(vm, timestamp),
                new StringObject(vm, nonce));
        String hkey = stringOf(shaderManager.callStaticJniMethodObject(
                emulator,
                "getObjType(Landroid/content/Context;Ljava/lang/String;Z)Ljava/lang/String;",
                context, new StringObject(vm, nonce), Boolean.FALSE));
        String random = stringOf(shaderManager.callStaticJniMethodObject(
                emulator,
                "getObjType(Landroid/content/Context;Ljava/lang/String;Z)Ljava/lang/String;",
                context, new StringObject(vm, nonce), Boolean.TRUE));
        String randomPrefix = securityVersion.isBlank() ? osVersion : securityVersion;
        return "{\"path\":\"" + escape(path) + "\",\"_time\":\"" + escape(timestamp)
                + "\",\"nonce\":\"" + escape(nonce) + "\",\"hkey\":\"" + escape(hkey)
                + "\",\"_rnd\":\"" + escape(randomPrefix + ":" + random) + "\"}";
    }

    private void initialize() {
        shaderManager.callStaticJniMethod(
                emulator, "setParseDepth(Ljava/lang/String;Z)V",
                new StringObject(vm, "/tmp/xhh-cache"),
                Boolean.FALSE);
        shaderManager.callStaticJniMethod(emulator, "setSecLevel()V");
        shaderManager.callStaticJniMethod(
                emulator, "setBlendMode(Ljava/lang/String;Ljava/lang/String;)V",
                new StringObject(vm, BLEND_SEED),
                new StringObject(vm, String.valueOf(System.currentTimeMillis())));
    }

    private static String normalizePath(String path) {
        String value = path == null || path.isBlank() ? "/" : path.trim();
        if (!value.startsWith("/")) value = "/" + value;
        while (value.length() > 1 && value.endsWith("/")) value = value.substring(0, value.length() - 1);
        return value + "/";
    }

    @Override
    public void setStaticBooleanField(BaseVM vm, DvmClass dvmClass, DvmField field, boolean value) {
        if (dvmClass == shaderManager && field.getFieldName().equals("b")) {
            shaderHasRnd = value;
            return;
        }
        super.setStaticBooleanField(vm, dvmClass, field, value);
    }

    @Override
    public boolean getStaticBooleanField(BaseVM vm, DvmClass dvmClass, DvmField field) {
        if (dvmClass == shaderManager && field.getFieldName().equals("b")) {
            return shaderHasRnd;
        }
        return super.getStaticBooleanField(vm, dvmClass, field);
    }

    @Override
    public void setStaticObjectField(BaseVM vm, DvmClass dvmClass, DvmField field, DvmObject<?> value) {
        if (dvmClass == shaderManager && field.getFieldName().equals("c") && value.getValue() instanceof Integer) {
            shaderVersion = (Integer) value.getValue();
            return;
        }
        super.setStaticObjectField(vm, dvmClass, field, value);
    }

    @Override
    public DvmObject<?> getStaticObjectField(BaseVM vm, DvmClass dvmClass, DvmField field) {
        if (dvmClass == shaderManager && field.getFieldName().equals("c")) {
            return DvmInteger.valueOf(vm, shaderVersion);
        }
        return super.getStaticObjectField(vm, dvmClass, field);
    }

    private void setShaderState(String name, String type, Object value) {
        try {
            Method idGetter = DvmClass.class.getDeclaredMethod("getStaticFieldID", String.class, String.class);
            idGetter.setAccessible(true);
            int fieldId = (Integer) idGetter.invoke(shaderManager, name, type);
            Method getter = DvmClass.class.getDeclaredMethod("getStaticField", int.class);
            getter.setAccessible(true);
            DvmField field = (DvmField) getter.invoke(shaderManager, fieldId);
            if (value instanceof Boolean) {
                Method setter = DvmField.class.getDeclaredMethod("setStaticBooleanField", boolean.class);
                setter.setAccessible(true);
                setter.invoke(field, value);
            } else {
                Method setter = DvmField.class.getDeclaredMethod("setStaticObjectField", DvmObject.class);
                setter.setAccessible(true);
                setter.invoke(field, value);
            }
        } catch (ReflectiveOperationException error) {
            throw new IllegalStateException("failed to set ShaderManager state: " + name, error);
        }
    }

    private void call(String signature, String first, String second) {
        shaderManager.callStaticJniMethod(
                emulator, signature,
                new StringObject(vm, first), new StringObject(vm, second));
    }

    private String stringOf(DvmObject<?> value) {
        Object content = value == null ? null : value.getValue();
        if (!(content instanceof String) || ((String) content).isEmpty()) {
            throw new IllegalStateException("native signing call returned no value");
        }
        return (String) content;
    }

    private static String escape(String value) {
        StringBuilder escaped = new StringBuilder(value.length() + 8);
        for (int index = 0; index < value.length(); index++) {
            char current = value.charAt(index);
            switch (current) {
                case '\\' -> escaped.append("\\\\");
                case '"' -> escaped.append("\\\"");
                case '\b' -> escaped.append("\\b");
                case '\f' -> escaped.append("\\f");
                case '\n' -> escaped.append("\\n");
                case '\r' -> escaped.append("\\r");
                case '\t' -> escaped.append("\\t");
                default -> {
                    if (current < 0x20) escaped.append(String.format("\\u%04x", (int) current));
                    else escaped.append(current);
                }
            }
        }
        return escaped.toString();
    }

    public void close() {
        try {
            emulator.close();
        } catch (Exception ignored) {
        }
    }

    @Override
    public FileResult resolve(Emulator<AndroidFileIO> emulator, String pathname, int oflags) {
        if ("/proc/self/cmdline".equals(pathname)) {
            return FileResult.success(new ByteArrayFileIO(
                    oflags, pathname, (PACKAGE_NAME + "\0").getBytes(StandardCharsets.UTF_8)));
        }
        if ("/proc/self/status".equals(pathname)) {
            return FileResult.success(new ByteArrayFileIO(
                    oflags, pathname,
                    "TracerPid:\t0\nState:\tS (sleeping)\n".getBytes(StandardCharsets.UTF_8)));
        }
        return null;
    }

    @Override
    public DvmObject<?> getStaticObjectField(BaseVM vm, DvmClass dvmClass, String signature) {
        if ("android/os/Build->MODEL:Ljava/lang/String;".equals(signature)) {
            return new StringObject(vm, deviceModel);
        }
        if ("android/os/Build->BRAND:Ljava/lang/String;".equals(signature)) {
            return new StringObject(vm, "vivo");
        }
        if ("android/os/Build$VERSION->RELEASE:Ljava/lang/String;".equals(signature)) {
            return new StringObject(vm, osVersion);
        }
        return super.getStaticObjectField(vm, dvmClass, signature);
    }

    @Override
    public DvmObject<?> getObjectField(BaseVM vm, DvmObject<?> object, String signature) {
        if (signature != null && signature.contains("android/content/pm/PackageInfo->signatures")) {
            try (ApkParser parser = new ApkParser(apkFile)) {
                CertificateMeta meta = parser.getCertificateMetaList().getFirst();
                return new ArrayObject(new Signature(vm, meta));
            } catch (Exception exception) {
                throw new IllegalStateException("cannot read APK signature", exception);
            }
        }
        return super.getObjectField(vm, object, signature);
    }

    @Override
    public int getStaticIntField(BaseVM vm, DvmClass dvmClass, String signature) {
        if (signature != null && signature.contains("MODE_PRIVATE")) return 0;
        return super.getStaticIntField(vm, dvmClass, signature);
    }

    @Override
    public DvmObject<?> callObjectMethod(
            BaseVM vm, DvmObject<?> object, String signature, VarArg args) {
        DvmObject<?> value = handle(signature, object, args);
        return value != null ? value : super.callObjectMethod(vm, object, signature, args);
    }

    @Override
    public DvmObject<?> callObjectMethodV(
            BaseVM vm, DvmObject<?> object, String signature, VaList args) {
        DvmObject<?> value = handle(signature, object, args);
        return value != null ? value : super.callObjectMethodV(vm, object, signature, args);
    }

    private DvmObject<?> handle(String signature, DvmObject<?> object, VarArg args) {
        if (signature == null) return null;
        if (signature.contains("getSharedPreferences(") || signature.contains("getString(")
                || signature.contains("getFilesDir()") || signature.contains("getCacheDir()")) {
            Object key = args.getObjectArg(0) == null ? null : args.getObjectArg(0).getValue();
            System.err.println("JNI " + signature + " key=" + key);
        }
        if (signature.contains("getPackageName()")) {
            return new StringObject(vm, PACKAGE_NAME);
        }
        if (signature.contains("getFilesDir()")) {
            return vm.resolveClass("java/io/File")
                    .newObject(new File("/data/user/0/" + PACKAGE_NAME + "/files"));
        }
        if (signature.contains("getCacheDir()")) {
            return vm.resolveClass("java/io/File")
                    .newObject(new File("/data/user/0/" + PACKAGE_NAME + "/cache"));
        }
        if (signature.contains("getPackageManager()")) {
            return vm.resolveClass("android/content/pm/PackageManager").newObject(null);
        }
        if (signature.contains("getPackageInfo(Ljava/lang/String;I)Landroid/content/pm/PackageInfo;")) {
            return new PackageInfo(vm, PACKAGE_NAME, 64);
        }
        if (signature.contains("getSharedPreferences(")) {
            return vm.resolveClass("android/content/SharedPreferences").newObject(null);
        }
        if (signature.contains("getString(")) {
            Object key = args.getObjectArg(0) == null ? null : args.getObjectArg(0).getValue();
            if ("DebugInfo".equals(key)) {
                return new StringObject(vm, imei + currentIdentity);
            }
            return new StringObject(vm, "0123456789abcdef123");
        }
        if ("java/lang/String->getBytes(Ljava/lang/String;)[B".equals(signature)) {
            Object content = object.getValue();
            Object charsetValue = args.getObjectArg(0).getValue();
            String charsetName = charsetValue == null ? "UTF-8" : charsetValue.toString();
            return new ByteArray(vm,
                    ((String) content).getBytes(Charset.forName(charsetName)));
        }
        return null;
    }
}
