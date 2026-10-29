package com.sevbify.app

import android.app.Application
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
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
        if (!Python.isStarted()) Python.start(AndroidPlatform(this))
        Library.load(this)
        scope.launch {
            Bridge.setup(this@SevbifyApp)
            Player.connect(this@SevbifyApp)
        }
    }

    companion object {
        lateinit var instance: SevbifyApp
            private set
    }
}
