package local.xmplaylist.unlock;

import java.lang.reflect.Method;
import java.util.Iterator;
import java.util.List;
import java.util.concurrent.atomic.AtomicBoolean;

import de.robv.android.xposed.IXposedHookLoadPackage;
import de.robv.android.xposed.XC_MethodHook;
import de.robv.android.xposed.XposedBridge;
import de.robv.android.xposed.XposedHelpers;
import de.robv.android.xposed.callbacks.XC_LoadPackage.LoadPackageParam;

/**
 * 小米音乐（内嵌 QQ 音乐简洁版）增强模块。
 *
 * 功能一：解除歌单 1000 首添加限制
 *   检查点: com.tencent.qqmusiclite.fragment.SongListAddViewModel$addSong$1.invokeSuspend
 *     limit = (folderInfo.getId() == 201L) ? 10000 : 1000;
 *     if (folderInfo.getCount() >= limit) { BannerTips.show(...); return; }
 *     remaining = limit - folderInfo.getCount();
 *   绕过方式: 在该添加流程内让 FolderInfo.getCount() 返回 0。
 *
 * 功能二：阻断「免费听(发现)」自动落地，首屏回到推荐页
 *
 *   实测 (4.47.0.1)：首屏走的是**底部导航**的 NavController 路由，与首页顶部 TabLayout
 *   是两套独立体系。顶部那一排「发现/推荐/听书」是 QuickPlayFragment 自己 header 里的
 *   装饰性文字（不是 TabLayout 的 Tab），删 TopTab id=4 不会影响首屏。
 *
 *   真实链路:
 *     MainActivity.onCreate() 注册监听 -> MainActivity$onCreate$17.invoke(Boolean)
 *       -> QuickPlayManager.isGotoQuickPlayTab()   // ABT "2025QuickStartPlay".page == "1"
 *       -> QuickPlayFragment.Companion.setFrom(1)
 *       -> MainActivity.navigateToDefaultQuickPlayTab()
 *            -> NavController.navigate(R$id.quickPlayFragment)   // 底栏「发现」
 *
 *   isGotoQuickPlayTab() 是唯一总开关，4 个调用方都受它控制:
 *     - MainActivity$onCreate$17.invoke      决定是否 navigate 到 quickPlayFragment
 *     - QuickPlayManager.isEnabled           决定 QuickPlay 是否启用
 *     - QuickPlayManager.needQuickPlayWhenColdStart
 *     - BaseHomeFragment.checkTopTabStartIndex / QuickPlayModel.onVisible
 *
 *   绕过方式: Hook isGotoQuickPlayTab() 让它恒返回 false。它是纯 ABT 读取器、无副作用，
 *   置 false 后上述调用方一致地走推荐页分支。
 */
public class MainHook implements IXposedHookLoadPackage {

    private static final String TAG = "XMPlaylistUnlock";
    private static final String TARGET_PKG = "com.miui.player";

    /** 功能一：歌单数量检查点。 */
    private static final String FOLDER_INFO = "com.tencent.qqmusic.core.folder.FolderInfo";
    private static final String ADD_SONG_CALLER_PREFIX =
            "com.tencent.qqmusiclite.fragment.SongListAddViewModel";

    /** 功能二：首页顶部 Tab 数据源（TopTab DTO 见 MainHook 类注释）。 */
    private static final String MAIN_ACTIVITY_VM =
            "com.tencent.qqmusiclite.activity.main.viewmodel.MainActivityViewModel";
    /** 顶部 Tab id：4 = 免费听（QuickPlayFragment）。 */
    private static final int TAB_ID_QUICK_PLAY = 4;

    /** 功能二主力：QuickPlay（免费听/发现）自动落地的唯一总开关。 */
    private static final String QUICK_PLAY_MANAGER =
            "com.tencent.qqmusiclite.fragment.home.QuickPlayManager";
    /** 首页 Fragment：UI 实际从它的 getTabs() 读顶部 Tab 列表。 */
    private static final String BASE_HOME_FRAGMENT =
            "com.tencent.qqmusiclite.fragment.home.BaseHomeFragment";

    /** 功能三：主界面（启动后默认落地页由它决定）。 */
    private static final String MAIN_ACTIVITY =
            "com.tencent.qqmusiclite.activity.MainActivity";
    /** 底栏「我的」页导航目标 ID（4.47.0.1 实测 0x7f0b0831）。 */
    private static final int NAV_ID_MY_FRAGMENT = 0x7f0b0831;

    private static final AtomicBoolean sRemovedQuickPlayLogged = new AtomicBoolean(false);
    private static final AtomicBoolean sBlockedLandingLogged = new AtomicBoolean(false);
    private static final AtomicBoolean sNavigatedToMyLogged = new AtomicBoolean(false);

    @Override
    public void handleLoadPackage(final LoadPackageParam lpparam) {
        if (!TARGET_PKG.equals(lpparam.packageName)) {
            return;
        }
        hookPlaylistLimit(lpparam.classLoader);
        hookQuickPlayLanding(lpparam.classLoader);
        hookQuickPlayTab(lpparam.classLoader);
        hookStartupToMyPage(lpparam.classLoader);
    }

    // ------------------------------------------------------------------
    // 功能三：启动后直接进入底栏「我的」页
    // ------------------------------------------------------------------

    /**
     * 冷启动首屏：configNavigationAndMinibar() 里才真正 setupWithNavController，
     * 它返回时 NavController 与底栏已就绪，此时切「我的」最稳。
     *
     * 不能挂在 navigateToDefaultQuickPlayTab() 上：功能二把 isGotoQuickPlayTab()
     * 恒置 false 后，MainActivity$onCreate$17 根本不会调用它，那个 Hook 永远不会触发。
     */
    private static void hookStartupToMyPage(final ClassLoader classLoader) {
        try {
            XposedHelpers.findAndHookMethod(MAIN_ACTIVITY, classLoader,
                    "configNavigationAndMinibar", "android.os.Bundle",
                    new XC_MethodHook() {
                        @Override
                        protected void afterHookedMethod(MethodHookParam param) {
                            navigateToMyPage(param.thisObject);
                        }
                    });
            XposedBridge.log("[" + TAG + "] hook installed: " + MAIN_ACTIVITY
                    + ".configNavigationAndMinibar() -> navigate to 我的");
        } catch (Throwable t) {
            XposedBridge.log("[" + TAG + "] hook configNavigationAndMinibar failed: " + t);
        }
    }

    private static void navigateToMyPage(Object activity) {
        if (activity == null) {
            return;
        }
        try {
            // 只在首次冷启动时切，避免后续其它入口复用 main 界面时被反复拉回「我的」
            if (!sNavigatedToMyLogged.compareAndSet(false, true)) {
                return;
            }
            // navigateTopLevelSingleTop(int, Bundle)：底栏切页的标准入口（single top + 顶层动画）
            XposedHelpers.callMethod(activity, "navigateTopLevelSingleTop",
                    NAV_ID_MY_FRAGMENT, null);
            XposedBridge.log("[" + TAG + "] startup navigated to 我的"
                    + " (id=0x" + Integer.toHexString(NAV_ID_MY_FRAGMENT) + ")");
        } catch (Throwable t) {
            sNavigatedToMyLogged.set(false);
            XposedBridge.log("[" + TAG + "] navigate to 我的 failed: " + t);
        }
    }

    // ------------------------------------------------------------------
    // 功能二（主力）：阻断 QuickPlay 自动落地
    // ------------------------------------------------------------------

    private static void hookQuickPlayLanding(final ClassLoader classLoader) {
        try {
            XposedHelpers.findAndHookMethod(QUICK_PLAY_MANAGER, classLoader,
                    "isGotoQuickPlayTab", new XC_MethodHook() {
                        @Override
                        protected void afterHookedMethod(MethodHookParam param) {
                            boolean real = Boolean.TRUE.equals(param.getResult());
                            param.setResult(Boolean.FALSE);
                            if (real && sBlockedLandingLogged.compareAndSet(false, true)) {
                                XposedBridge.log("[" + TAG + "] blocked QuickPlay landing"
                                        + " (isGotoQuickPlayTab was true), home stays on 推荐");
                            }
                        }
                    });
            XposedBridge.log("[" + TAG + "] hook installed: " + QUICK_PLAY_MANAGER
                    + ".isGotoQuickPlayTab() -> always false");
        } catch (Throwable t) {
            XposedBridge.log("[" + TAG + "] hook isGotoQuickPlayTab failed: " + t);
        }
    }

    // ------------------------------------------------------------------
    // 功能一：歌单 1000 首限制
    // ------------------------------------------------------------------

    private static void hookPlaylistLimit(final ClassLoader classLoader) {
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
            XposedHelpers.findAndHookMethod(FOLDER_INFO, classLoader, "getCount", hook);
            ok = true;
            XposedBridge.log("[" + TAG + "] hook installed via findAndHookMethod: "
                    + FOLDER_INFO + ".getCount()");
        } catch (Throwable t) {
            XposedBridge.log("[" + TAG + "] findAndHookMethod failed: " + t);
        }
        // 兜底: 反射拿到 Method 后走 XposedBridge.hookMethod
        if (!ok) {
            try {
                Class<?> clazz = Class.forName(FOLDER_INFO, false, classLoader);
                Method getCount = clazz.getDeclaredMethod("getCount");
                XposedBridge.hookMethod(getCount, hook);
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
            if (cn != null && cn.startsWith(ADD_SONG_CALLER_PREFIX)) {
                return true;
            }
        }
        return false;
    }

    // ------------------------------------------------------------------
    // 功能二：移除首页「免费听」Tab
    // ------------------------------------------------------------------

    private static void hookQuickPlayTab(final ClassLoader classLoader) {
        // UI 实际读取处是 BaseHomeFragment.getTabs()（它再转发到 VM.getTabs()）。
        // 两处都挂，任一被 updateTabs() 的 addAll 回填都能在下次读取时再清掉。
        hookTabsGetter(MAIN_ACTIVITY_VM, classLoader);
        hookTabsGetter(BASE_HOME_FRAGMENT, classLoader);
    }

    private static void hookTabsGetter(final String className, final ClassLoader classLoader) {
        try {
            XposedHelpers.findAndHookMethod(className, classLoader, "getTabs",
                    new XC_MethodHook() {
                        @Override
                        protected void afterHookedMethod(MethodHookParam param) {
                            removeQuickPlayTab(param.getResult());
                        }
                    });
            XposedBridge.log("[" + TAG + "] hook installed: " + className
                    + ".getTabs() -> strip TopTab id=" + TAB_ID_QUICK_PLAY);
        } catch (Throwable t) {
            XposedBridge.log("[" + TAG + "] hook " + className + ".getTabs failed: " + t);
        }
    }

    /**
     * 就地删除「免费听」Tab，保持 List 引用不变。
     *
     * 不能返回新 List: BaseHomeFragment.updateTabs() 会对 getTabs() 的结果执行
     * clear() + addAll()，换成新引用会让真实字段与调用方操作的对象不一致。
     */
    private static void removeQuickPlayTab(Object tabsObj) {
        if (!(tabsObj instanceof List)) {
            return;
        }
        List<?> tabs = (List<?>) tabsObj;
        boolean removed = false;
        try {
            Iterator<?> it = tabs.iterator();
            while (it.hasNext()) {
                Object tab = it.next();
                if (tab == null) {
                    continue;
                }
                Integer id = tabId(tab);
                if (id != null && id.intValue() == TAB_ID_QUICK_PLAY) {
                    it.remove();
                    removed = true;
                }
            }
        } catch (Throwable t) {
            XposedBridge.log("[" + TAG + "] strip quick-play tab failed: " + t);
            return;
        }
        if (removed && sRemovedQuickPlayLogged.compareAndSet(false, true)) {
            XposedBridge.log("[" + TAG + "] removed 免费听 tab (TopTab id="
                    + TAB_ID_QUICK_PLAY + "), home falls back to 推荐");
        }
    }

    /** 取 TopTab.id；字段名未混淆，读不到时退回 getId()。 */
    private static Integer tabId(Object tab) {
        try {
            Object id = XposedHelpers.getObjectField(tab, "id");
            if (id instanceof Integer) {
                return (Integer) id;
            }
        } catch (Throwable ignored) {
        }
        try {
            Object id = XposedHelpers.callMethod(tab, "getId");
            if (id instanceof Integer) {
                return (Integer) id;
            }
        } catch (Throwable ignored) {
        }
        return null;
    }
}
