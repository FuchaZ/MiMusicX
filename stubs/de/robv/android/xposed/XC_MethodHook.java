package de.robv.android.xposed;

public abstract class XC_MethodHook {
    public static class Unhook {
    }

    public static class MethodHookParam {
        public Object thisObject;
        public Object[] args;
        private Object result;
        public Throwable throwable;
        public boolean returnEarly;

        public Object getResult() { return result; }
        public void setResult(Object result) { this.result = result; this.returnEarly = true; }
        public Throwable getThrowable() { return throwable; }
        public void setThrowable(Throwable t) { this.throwable = t; this.returnEarly = true; }
        public Object getResultOrThrowable() throws Throwable {
            if (throwable != null) throw throwable;
            return result;
        }
    }

    protected void beforeHookedMethod(MethodHookParam param) throws Throwable {}
    protected void afterHookedMethod(MethodHookParam param) throws Throwable {}
}
