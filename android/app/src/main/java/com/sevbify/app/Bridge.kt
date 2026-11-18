package com.sevbify.app

import android.content.Context
import com.chaquo.python.PyObject
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONObject
import androidx.compose.runtime.getValue
import androidx.compose.runtime.setValue

/** Thrown when the shared core reports a problem (no internet, nothing found...). The message is readable. */
class CoreError(message: String) : Exception(message)

/**
 * Calls into the shared Python core (core/ in the repository, the same code as the Windows app) through
 * android/app/src/main/python/sevbify_bridge.py. Everything is JSON in and out.
 */
object Bridge {
    private val ready = Mutex()
    @Volatile private var setUp = false
    private val module: PyObject by lazy { Python.getInstance().getModule("sevbify_bridge") }

    suspend fun setup(context: Context) = ready.withLock {
        if (setUp) return@withLock
        withContext(Dispatchers.IO) {
            if (!Python.isStarted()) Python.start(AndroidPlatform(context.applicationContext))
            val data = context.filesDir.resolve("core").absolutePath
            val cache = context.cacheDir.resolve("online").absolutePath
            // The app's version (from the same VERSION file as Windows, set at build time).
            val version = try {
                context.packageManager.getPackageInfo(context.packageName, 0).versionName ?: ""
            } catch (e: Exception) { "" }
            val res = JSONObject(module.callAttr("setup", data, cache, Library.settings.online, "", version).toString())
            if (!res.optBoolean("ok")) throw CoreError(res.optString("error"))
            Library.coreVersion = res.getJSONObject("value").optString("version").ifEmpty { version }
        }
        setUp = true
    }

    /** Call a bridge function on a background thread. Returns its "value" (JSONObject, JSONArray, String...). */
    suspend fun call(name: String, vararg args: Any?): Any? {
        if (!setUp) setup(SevbifyApp.instance)
        return withContext(Dispatchers.IO) {
            val raw = module.callAttr(name, *args).toString()
            val res = JSONObject(raw)
            if (!res.optBoolean("ok")) {
                // Test builds only: errors can hold song names or addresses, so the released app logs nothing.
                if (SevbifyApp.debuggable)
                    android.util.Log.w("Sevbify", "$name failed: ${res.optString("error")}\n${res.optString("trace").takeLast(800)}")
                if (res.optBoolean("engine_check")) EngineFix.await()
                throw CoreError(res.optString("error", "Something went wrong"))
            }
            if (res.isNull("value")) null else res.get("value")
        }
    }

    suspend fun obj(name: String, vararg args: Any?): JSONObject = call(name, *args) as? JSONObject ?: JSONObject()
    suspend fun arr(name: String, vararg args: Any?): JSONArray = call(name, *args) as? JSONArray ?: JSONArray()

    suspend fun tracks(name: String, vararg args: Any?): List<Track> = arr(name, *args).let { a ->
        (0 until a.length()).map { Track.fromJson(a.getJSONObject(it)) }
    }
}


/** YouTube or SoundCloud kept failing, so the core is checking for a newer yt-dlp (core/engine_fix.py). When it's
 *  done, a dialog says what happened: a fix was downloaded (Restart now), or there's nothing newer yet. */
object EngineFix {
    var result by androidx.compose.runtime.mutableStateOf<JSONObject?>(null)

    fun await() {
        SevbifyApp.instance.scope.launch {
            try { (Bridge.call("engine_fix_result") as? JSONObject)?.let { result = it } }
            catch (e: Exception) { if (e is kotlinx.coroutines.CancellationException) throw e }
        }
    }

    /** Start Sevbify again so the new yt-dlp is used. */
    fun restart(context: android.content.Context) {
        val launch = context.packageManager.getLaunchIntentForPackage(context.packageName) ?: return
        context.startActivity(android.content.Intent.makeRestartActivityTask(launch.component))
        Runtime.getRuntime().exit(0)
    }
}
