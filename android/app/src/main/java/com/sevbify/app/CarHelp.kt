package com.sevbify.app

import android.app.UiModeManager
import android.content.Context
import android.content.Intent
import android.content.res.Configuration
import com.sevbify.app.ui.Nav

/** Android Auto only lists apps from the Play Store unless "Unknown sources" is on in its developer settings.
 *  There's no way for an app to switch that on (or even to read it), so Sevbify explains it: once when Android Auto
 *  is on the phone, and again when the phone is in a car but Android Auto hasn't connected to Sevbify. */
object CarHelp {
    fun androidAutoInstalled(context: Context): Boolean = try {
        context.packageManager.getPackageInfo(PlaybackService.ANDROID_AUTO, 0); true
    } catch (_: Exception) { false }

    fun inCar(context: Context): Boolean {
        val ui = context.getSystemService(Context.UI_MODE_SERVICE) as? UiModeManager
        return ui?.currentModeType == Configuration.UI_MODE_TYPE_CAR
    }

    /** Opens Android Auto's settings (or the phone's, if that can't be opened directly). */
    fun openAndroidAuto(context: Context) {
        val tries = listOf(
            Intent().setClassName(PlaybackService.ANDROID_AUTO, "com.google.android.apps.auto.carservice.settings.SettingsActivity"),
            context.packageManager.getLaunchIntentForPackage(PlaybackService.ANDROID_AUTO),
            Intent(android.provider.Settings.ACTION_SETTINGS))
        for (i in tries) {
            if (i == null) continue
            try { context.startActivity(i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)); return } catch (_: Exception) {}
        }
    }

    /** Called when Sevbify opens: maybe show the Android Auto tip. */
    fun check(context: Context) {
        val s = Library.settings
        if (s.carTipShown || !androidAutoInstalled(context)) return
        if (PlaybackService.carConnected) { s.carTipShown = true; Library.changed(); return }
        Nav.carTip = true
    }

    /** In a car (car mode) for a while, but Android Auto never asked Sevbify for its songs: explain again. */
    fun checkInCar(context: Context) {
        if (!inCar(context) || PlaybackService.carConnected || !androidAutoInstalled(context)) return
        val now = System.currentTimeMillis()
        if (now - Library.settings.carTipAt < 24L * 3600 * 1000) return
        Library.settings.carTipAt = now; Library.changed()
        Nav.carTip = true
    }
}
