package com.sevbify.app

import android.content.Context
import com.chaquo.python.PyObject
import com.chaquo.python.Python
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject

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
            if (!res.optBoolean("ok")) throw CoreError(res.optString("error", "Something went wrong"))
            if (res.isNull("value")) null else res.get("value")
        }
    }

    suspend fun obj(name: String, vararg args: Any?): JSONObject = call(name, *args) as? JSONObject ?: JSONObject()
    suspend fun arr(name: String, vararg args: Any?): JSONArray = call(name, *args) as? JSONArray ?: JSONArray()

    suspend fun tracks(name: String, vararg args: Any?): List<Track> = arr(name, *args).let { a ->
        (0 until a.length()).map { Track.fromJson(a.getJSONObject(it)) }
    }
}
