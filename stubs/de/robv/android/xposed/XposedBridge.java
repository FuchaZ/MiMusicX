package de.robv.android.xposed;

import java.lang.reflect.Member;

public final class XposedBridge {
    public static void log(String text) {}
    // 真实签名返回 XC_MethodHook.Unhook
    public static XC_MethodHook.Unhook hookMethod(Member hookMethod, XC_MethodHook callback) { return null; }
}
