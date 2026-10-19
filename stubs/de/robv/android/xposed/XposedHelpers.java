package de.robv.android.xposed;

import java.lang.reflect.Member;

public final class XposedHelpers {
    // 真实签名返回 XC_MethodHook.Unhook —— 调用点描述符必须与之一致
    public static XC_MethodHook.Unhook findAndHookMethod(String className, ClassLoader classLoader,
            String methodName, Object... parameterTypesAndCallback) { return null; }
    public static Object callMethod(Object obj, String methodName, Object... args) { return null; }
    public static Object getObjectField(Object obj, String fieldName) { return null; }
}
