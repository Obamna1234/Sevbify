package com.sevbify.app

import android.app.Application
import com.sevbify.app.ui.Nav
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

/** Starts the shared Python core once, loads your library, and connects the player. */
class SevbifyApp : Application() {
    val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)

    override fun onCreate() {
        super.onCreate()
        instance = this
        Library.load(this)
        Player.connect(this)                 // your own songs play even if the online core can't start
        scope.launch {
            // Starting Python takes a few seconds the first time (it unpacks itself): done in the background
            // inside Bridge.setup, so the app never freezes ("isn't responding") on its first start.
            try { Bridge.setup(this@SevbifyApp) } catch (e: Exception) { Nav.say("Online features couldn't start: ${e.message}") }
            autoUpdateYtdlp()
            try { Updater.check() } catch (_: Exception) { /* offline: try again tomorrow */ }
        }
    }

    /** Once a week, when online: the newest official yt-dlp (YouTube changes often), checked against its checksum. */
    private suspend fun autoUpdateYtdlp() {
        val s = Library.settings
        if (!s.online || !s.autoUpdateYtdlp || System.currentTimeMillis() - s.lastYtdlpCheck < 7L * 24 * 3600 * 1000) return
        try {
            val info = Bridge.obj("ytdlp_info")
            s.lastYtdlpCheck = System.currentTimeMillis(); Library.changed()
            if (info.optInt("age_days", 0) < 7) return
            val res = Bridge.obj("update_ytdlp")
            if (res.optBoolean("changed")) Nav.say("yt-dlp was updated; it's used the next time Sevbify starts")
        } catch (_: Exception) { /* offline or GitHub unreachable: try again next week */ }
    }

    companion object {
        lateinit var instance: SevbifyApp
            private set
    }
}
