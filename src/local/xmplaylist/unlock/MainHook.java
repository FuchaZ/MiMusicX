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
 *
 * 功能四：屏蔽蓝牙设备连接后的「臻品音质」推广弹窗
 *
 *   现象: 连上任意蓝牙耳机/音箱，播放页就会弹出「您的 XXX 设备已连接 /
 *   设备支持播放超级会员臻品音质 / 开启您的尊享权益」。设备名是运行时读出来的，
 *   所以换设备就换名字，并不是写死的。
 *
 *   真实链路 (4.47.0.1):
 *     BluetoothAudioMonitor$audioDeviceCallback$1.onAudioDevicesAdded(devices)
 *       -> deviceName = AudioDeviceInfo.getProductName()
 *                       ?: BluetoothDeviceManager.getBluetoothDeviceName()
 *       -> ExcellentHeadPhoneManager.handleBluetoothConnected(deviceName)
 *            -> currentDeviceName = deviceName; debounceThrottle 防抖后再触发
 *       -> ExcellentHeadPhoneManager.checkAndShow()          // suspend
 *            -> 十余道前置守卫：getDeviceName / isFlipOuter / offline / isLogin /
 *               isDialogShowing / isYoungMode / HorizontalScreenPlayerHelper.goto /
 *               isCurrentAdPage / isCurrentExcellentGuideAlert /
 *               isCurrentExcellentTryEndAlert / isShowingOtherAlert
 *            -> getPopUpWindow(deviceName) -> DialogRepo.getEarphoneConnectPopup(deviceName)
 *                 // 服务端下发 title / subTitle / buttonText / deviceImageUrl / soundQuality
 *            -> DeviceFrequency.canShowHeadPhoneDialog(deviceName, frequency)
 *            -> show(GetEarphoneConnectPopupRsp)
 *                 -> ExcellentHeadPhoneDialog.Companion.show(popUpInfo, onConfirm)
 *                      -> ActivityUtils.getTopActivity() -> FragmentManager -> show()
 *
 *   反查确认无第二条路径: checkAndShow 只有 access$checkAndShow 一个引用方，
 *   Companion.show 只被 ExcellentHeadPhoneManager.show 引用，
 *   DialogRepo.getEarphoneConnectPopup 只被 getPopUpWindow 引用。
 *
 *   绕过方式: Hook checkAndShow() 直接返回（suspend 函数返回 kotlin.Unit），
 *   弹窗连同那次服务端请求一起消失；再 Hook Companion.show() 空实现做兜底，
 *   万一将来 checkAndShow 改名失效，弹窗依然弹不出来。
 */
public class MainHook implements IXposedHookLoadPackage {

    private static final String TAG = "MiMusicX";
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

    /** 功能四主力：蓝牙耳机「臻品音质」推广弹窗的决策入口。 */
    private static final String EXCELLENT_HEADPHONE_MANAGER =
            "com.tencent.qqmusiclite.business.bluetooth.headphone.ExcellentHeadPhoneManager";
    /** 功能四兜底：弹窗真正显示的地方（Companion 是 Kotlin object）。 */
    private static final String EXCELLENT_HEADPHONE_DIALOG =
            "com.tencent.qqmusiclite.business.bluetooth.headphone.ExcellentHeadPhoneDialog";

    /** 功能五：本地音乐数据源，「最近播放歌单」的读取入口在这里。 */
    private static final String LOCAL_MY_MUSIC_DATA_SOURCE =
            "com.tencent.qqmusic.data.mymusic.LocalMyMusicDataSource";
    /** 诊断用：播放时记录「最近播放歌单」的入口（排查写入没生效时打开）。 */
    private static final String MUSIC_PLAYER_HELPER_RECENT =
            "com.tencent.qqmusiccommon.util.music.MusicPlayerHelper$12";
    /** db_tag：最近播放歌单在 folder_info_folders 表里的标签（宿主写入/读取都用它）。 */
    private static final int DB_TAG_RECENT_FAVOR = 0;

    private static final AtomicBoolean sRemovedQuickPlayLogged = new AtomicBoolean(false);
    private static final AtomicBoolean sBlockedLandingLogged = new AtomicBoolean(false);
    private static final AtomicBoolean sNavigatedToMyLogged = new AtomicBoolean(false);
    private static final AtomicBoolean sBlockedHeadphonePopupLogged = new AtomicBoolean(false);

    @Override
    public void handleLoadPackage(final LoadPackageParam lpparam) {
        if (!TARGET_PKG.equals(lpparam.packageName)) {
            return;
        }
        hookPlaylistLimit(lpparam.classLoader);
        hookQuickPlayLanding(lpparam.classLoader);
        hookQuickPlayTab(lpparam.classLoader);
        hookStartupToMyPage(lpparam.classLoader);
        hookBluetoothQualityPopup(lpparam.classLoader);
        hookRecentPlayFolderWrite(lpparam.classLoader);
    }

    // ------------------------------------------------------------------
    // 功能四：屏蔽蓝牙设备连接后的「臻品音质」推广弹窗
    // ------------------------------------------------------------------

    /**
     * 双保险：
     *   1) checkAndShow() 直接早退 —— 连服务端请求都不发，最干净
     *   2) Companion.show() 空实现 —— 万一 checkAndShow 改名/改签名，兜底吞掉弹窗
     *
     * 只屏蔽这一个弹窗，蓝牙连接本身、音频切换、其它蓝牙提示都不受影响：
     * handleBluetoothConnected/disconnected 只负责记录设备名并触发 checkAndShow。
     */
    private static void hookBluetoothQualityPopup(final ClassLoader classLoader) {
        final Object unit = kotlinUnit(classLoader);

        // ---- 1) 主力：决策入口早退。suspend 函数返回 kotlin.Unit，调用方视为「检查完、无事发生」 ----
        final XC_MethodHook checkHook = new XC_MethodHook() {
            @Override
            protected void beforeHookedMethod(MethodHookParam param) {
                param.setResult(unit);
                logBlockedHeadphonePopup("at checkAndShow()");
            }
        };
        boolean checkHooked = false;
        try {
            XposedHelpers.findAndHookMethod(EXCELLENT_HEADPHONE_MANAGER, classLoader,
                    "checkAndShow", "kotlin.coroutines.Continuation", checkHook);
            checkHooked = true;
            XposedBridge.log("[" + TAG + "] hook installed: " + EXCELLENT_HEADPHONE_MANAGER
                    + ".checkAndShow(Continuation) -> always return Unit"
                    + " (no popup, no request)");
        } catch (Throwable t) {
            XposedBridge.log("[" + TAG + "] hook checkAndShow failed: " + t);
        }
        if (!checkHooked) {
            // 兜底：精确签名没匹配上（版本更新改了签名/加了默认参数）时，按方法名挂
            hookMethodsByName(classLoader, EXCELLENT_HEADPHONE_MANAGER, "checkAndShow", checkHook);
        }

        // ---- 2) 兜底：真正显示弹窗的地方直接吞掉 ----
        final XC_MethodHook showHook = new XC_MethodHook() {
            @Override
            protected void beforeHookedMethod(MethodHookParam param) {
                param.setResult(null);
                logBlockedHeadphonePopup("at Companion.show()");
            }
        };
        final String companion = EXCELLENT_HEADPHONE_DIALOG + "$Companion";
        boolean showHooked = false;
        try {
            XposedHelpers.findAndHookMethod(companion, classLoader, "show",
                    EXCELLENT_HEADPHONE_DIALOG + "$EarphoneConnectPopupInfo",
                    "kotlin.jvm.functions.Function0", showHook);
            showHooked = true;
            XposedBridge.log("[" + TAG + "] hook installed: " + companion
                    + ".show() -> no-op (fallback)");
        } catch (Throwable t) {
            XposedBridge.log("[" + TAG + "] hook Companion.show failed: " + t);
        }
        if (!showHooked) {
            hookMethodsByName(classLoader, companion, "show", showHook);
        }
    }

    /** 按方法名挂上所有重载：精确签名失配时的兜底。 */
    private static void hookMethodsByName(final ClassLoader classLoader, final String className,
            final String methodName, final XC_MethodHook hook) {
        try {
            Class<?> clazz = Class.forName(className, false, classLoader);
            int count = 0;
            for (Method m : clazz.getDeclaredMethods()) {
                if (m.getName().equals(methodName)) {
                    XposedBridge.hookMethod(m, hook);
                    count++;
                }
            }
            XposedBridge.log("[" + TAG + "] hook installed via hookMethod fallback: "
                    + className + "." + methodName + " x" + count);
        } catch (Throwable t) {
            XposedBridge.log("[" + TAG + "] fallback hook " + className + "." + methodName
                    + " failed: " + t);
        }
    }

    /** kotlin.Unit 常量：suspend 函数「正常结束但什么也没做」的返回值。 */
    private static Object kotlinUnit(final ClassLoader classLoader) {
        try {
            // 用宿主的 ClassLoader 取，模块自己的 ClassLoader 看不到 kotlin 标准库
            return Class.forName("kotlin.Unit", false, classLoader)
                    .getField("INSTANCE").get(null);
        } catch (Throwable t) {
            XposedBridge.log("[" + TAG + "] resolve kotlin.Unit failed: " + t);
            return null;
        }
    }

    private static void logBlockedHeadphonePopup(final String where) {
        if (sBlockedHeadphonePopupLogged.compareAndSet(false, true)) {
            XposedBridge.log("[" + TAG + "] blocked bluetooth quality popup " + where);
        }
    }

    // ------------------------------------------------------------------
    // 功能五：修好「最近播放」不更新播放过的歌单
    // ------------------------------------------------------------------

    /**
     * 小米版「我的 → 最近播放」不记录实际播放过的歌单（官方 QQ 音乐正常）。
     *
     * 根因（4.47.0.1 实测，logcat + 数据库双重确认）:
     *   播放歌曲时 MusicPlayerHelper$12.addRecentPlaySong(SongInfomation) 被正常调用，
     *   但它内部要同时满足两个条件才会走到「写最近播放歌单」：
     *     1) MusicPlayList.getPlayListType() ∈ {11, 16, 18}
     *     2) RecentManager.getTempPlayList().getId() == MusicPlayList.getPlayListTypeId()
     *   任一不满足就直接 return，于是 insertRecentPlayFolderInternal 从不被调用、
     *   数据库里 folder_info_folders 的 db_tag=0 一直是旧记录。
     *   实测日志：addRecentPlaySong 连续触发，insertRecentPlayFolderInternal 一次都没有。
     *
     * 做法: 在 addRecentPlaySong 返回后兜底补写。
     *   若这一轮宿主确实没写库（db_tag=0 里查不到当前歌单），
     *   就把 RecentManager.getTempPlayList() 组装成 FolderInfo，
     *   交给宿主自己的 LocalMyMusicDataSource.insertRecentPlayFolder() 写入 ——
     *   走的是官方那条写库路径，tag 等细节全由宿主决定，模块不自己拼 SQL。
     *
     * 为什么不改读取侧: 曾尝试把 db_tag=4 的记录合并进列表，实测那批是历史/同步遗留
     *   数据（例如「纯音乐 0首」），合并进来只会显示错误条目，该方案已废弃。
     */
    private static void hookRecentPlayFolderWrite(final ClassLoader classLoader) {
        try {
            XposedHelpers.findAndHookMethod(MUSIC_PLAYER_HELPER_RECENT, classLoader,
                    "addRecentPlaySong", "com.tencent.qqmusicsdk.protocol.SongInfomation",
                    new XC_MethodHook() {
                        @Override
                        protected void afterHookedMethod(MethodHookParam param) {
                            try {
                                recordCurrentPlaylist(classLoader);
                            } catch (Throwable t) {
                                XposedBridge.log("[" + TAG + "] recordCurrentPlaylist failed: " + t);
                            }
                        }
                    });
            XposedBridge.log("[" + TAG + "] hook installed: " + MUSIC_PLAYER_HELPER_RECENT
                    + ".addRecentPlaySong() -> ensure current playlist enters 最近播放");
        } catch (Throwable t) {
            XposedBridge.log("[" + TAG + "] hook addRecentPlaySong failed: " + t);
        }
    }

    /**
     * 把「当前播放的歌单」补写进最近播放。
     *
     * 只在宿主自己没写成功时补，避免和官方逻辑打架：
     *   - tempPlayList 为空 ⇒ 这次播放不来自歌单（单曲 / 电台），不处理
     *   - db_tag=0 里已有该歌单 ⇒ 宿主写过了，不动
     */
    private static void recordCurrentPlaylist(final ClassLoader classLoader) {
        Object playList = currentTempPlayList(classLoader);
        if (playList == null) {
            return;
        }
        Long id = longGetter(playList, "getId");
        if (id == null || id.longValue() <= 0L) {
            return;
        }
        String name = stringGetter(playList, "getTitle");
        if (name == null || name.length() == 0) {
            return;
        }
        // 宿主已经写过就不再插手（同一次播放可能触发多次）
        if (isAlreadyRecorded(classLoader, id.longValue())) {
            return;
        }

        try {
            Class<?> folderInfoCls = Class.forName(
                    "com.tencent.qqmusic.core.folder.FolderInfo", false, classLoader);
            Object folderInfo = folderInfoCls.newInstance();
            XposedHelpers.callMethod(folderInfo, "setId", id);
            XposedHelpers.callMethod(folderInfo, "setDisstId", id);
            XposedHelpers.callMethod(folderInfo, "setName", name);
            String cover = stringGetter(playList, "getCoverUrl");
            if (cover != null) {
                XposedHelpers.callMethod(folderInfo, "setPicUrl", cover);
            }
            Object songNum = XposedHelpers.callMethod(playList, "getSongNum");
            if (songNum instanceof Integer) {
                XposedHelpers.callMethod(folderInfo, "setCount", songNum);
            }

            Object dataSource = Class.forName(LOCAL_MY_MUSIC_DATA_SOURCE, false, classLoader)
                    .newInstance();
            XposedHelpers.callMethod(dataSource, "insertRecentPlayFolder", folderInfo);
            XposedBridge.log("[" + TAG + "] recorded current playlist into 最近播放: "
                    + name + " (id=" + id + ")");
        } catch (Throwable t) {
            XposedBridge.log("[" + TAG + "] insert recent play folder failed: " + t);
        }
    }

    /** RecentManager.INSTANCE.getTempPlayList()，取不到返回 null。 */
    private static Object currentTempPlayList(final ClassLoader classLoader) {
        try {
            Class<?> rm = Class.forName(
                    "com.tencent.qqmusiclite.manager.RecentManager", false, classLoader);
            Object instance = rm.getField("INSTANCE").get(null);
            return XposedHelpers.callMethod(instance, "getTempPlayList");
        } catch (Throwable t) {
            return null;
        }
    }

    /** db_tag=0 里是否已有这个歌单（宿主已经写过了）。 */
    private static boolean isAlreadyRecorded(final ClassLoader classLoader, final long disstId) {
        try {
            Class<?> globalContext = Class.forName(
                    "com.tencent.qqmusiclite.api.GlobalContext", false, classLoader);
            Object context = XposedHelpers.callMethod(
                    globalContext.getField("INSTANCE").get(null), "getContext");
            Class<?> qmDatabase = Class.forName(
                    "com.tencent.qqmusic.data.db.QMDatabase", false, classLoader);
            Object companion = qmDatabase.getField("Companion").get(null);
            Object db = XposedHelpers.callMethod(companion, "getDatabase", context);
            Object dao = XposedHelpers.callMethod(db, "folderInfoDAO");
            Object entity = XposedHelpers.callMethod(dao, "getFolderByDisstIdAndTag",
                    Long.valueOf(disstId), Integer.valueOf(DB_TAG_RECENT_FAVOR));
            return entity != null;
        } catch (Throwable t) {
            return false;  // 查不到就按「没写过」处理，交给宿主去重
        }
    }

    private static Long longGetter(final Object target, final String method) {
        try {
            Object v = XposedHelpers.callMethod(target, method);
            if (v instanceof Long) {
                return (Long) v;
            }
            if (v instanceof Integer) {
                return Long.valueOf(((Integer) v).longValue());
            }
        } catch (Throwable ignored) {
        }
        return null;
    }

    private static String stringGetter(final Object target, final String method) {
        try {
            Object v = XposedHelpers.callMethod(target, method);
            if (v != null) {
                return v.toString();
            }
        } catch (Throwable ignored) {
        }
        return null;
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
