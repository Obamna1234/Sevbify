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
        }
    }

    companion object {
        lateinit var instance: SevbifyApp
            private set
    }
}
