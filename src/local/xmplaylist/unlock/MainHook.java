package local.xmplaylist.unlock;

import java.lang.reflect.Method;

import de.robv.android.xposed.IXposedHookLoadPackage;
import de.robv.android.xposed.XC_MethodHook;
import de.robv.android.xposed.XposedBridge;
import de.robv.android.xposed.XposedHelpers;
import de.robv.android.xposed.callbacks.XC_LoadPackage.LoadPackageParam;

/**
 * 解除小米音乐（内嵌QQ音乐简洁版）"该歌单已超过1000首歌啦"的客户端添加限制。
 *
 * 检查点（小米音乐 4.46.x）:
 *   com.tencent.qqmusiclite.fragment.SongListAddViewModel$addSong$1.invokeSuspend
 *     limit = (folderInfo.getId() == 201L) ? 10000 : 1000;
 *     if (folderInfo.getCount() >= limit) { BannerTips.show(...); return; }
 *     remaining = limit - folderInfo.getCount();
 *     AddSongs.invoke(new AddSongs$Param(folderId, songs截断至remaining));
 *
 * 绕过方式: 在该添加流程内让 FolderInfo.getCount() 返回 0。
 */
public class MainHook implements IXposedHookLoadPackage {

    private static final String TAG = "XMPlaylistUnlock";
    private static final String TARGET_PKG = "com.miui.player";
    private static final String FOLDER_INFO = "com.tencent.qqmusic.core.folder.FolderInfo";
    private static final String CALLER_PREFIX = "com.tencent.qqmusiclite.fragment.SongListAddViewModel";

    @Override
    public void handleLoadPackage(final LoadPackageParam lpparam) {
        if (!TARGET_PKG.equals(lpparam.packageName)) {
            return;
        }
        final XC_MethodHook hook = new XC_MethodHook() {
            @Override
            protected void beforeHookedMethod(MethodHookParam param) {
                if (!isInAddSongFlow()) {
                    return;
                }
                Object self = param.thisObject;
                int real = 0;
                try {
                    real = ((Integer) param.getResult()).intValue();
                } catch (Throwable ignored) {
                }
                param.setResult(Integer.valueOf(0));
                try {
                    XposedBridge.log("[" + TAG + "] bypassed playlist limit: folderId="
                            + XposedHelpers.callMethod(self, "getId")
                            + " realCount=" + real + " (reported 0)");
                } catch (Throwable ignored) {
                }
            }
        };

        boolean ok = false;
        // 主路径: 签名必须与真实 Xposed API 完全一致（返回 XC_MethodHook.Unhook）
        try {
            XposedHelpers.findAndHookMethod(FOLDER_INFO, lpparam.classLoader, "getCount", hook);
            ok = true;
            XposedBridge.log("[" + TAG + "] hook installed via findAndHookMethod: "
                    + FOLDER_INFO + ".getCount()");
        } catch (Throwable t) {
            XposedBridge.log("[" + TAG + "] findAndHookMethod failed: " + t);
        }
        // 兜底: 反射拿到 Method 后走 XposedBridge.hookMethod
        if (!ok) {
            try {
                Class<?> clazz = Class.forName(FOLDER_INFO, false, lpparam.classLoader);
                Method getCount = clazz.getDeclaredMethod("getCount");
                XposedBridge.hookMethod(getCount, hook);
                ok = true;
                XposedBridge.log("[" + TAG + "] hook installed via hookMethod: "
                        + FOLDER_INFO + ".getCount()");
            } catch (Throwable t) {
                XposedBridge.log("[" + TAG + "] fallback hookMethod failed: " + t);
            }
        }
    }

    private static boolean isInAddSongFlow() {
        StackTraceElement[] stack = Thread.currentThread().getStackTrace();
        for (StackTraceElement e : stack) {
            String cn = e.getClassName();
            if (cn != null && cn.startsWith(CALLER_PREFIX)) {
                return true;
            }
        }
        return false;
    }
}
