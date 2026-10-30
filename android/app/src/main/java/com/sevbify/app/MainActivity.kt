package com.sevbify.app

import android.Manifest
import android.content.Intent
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.lifecycle.lifecycleScope
import com.sevbify.app.ui.AppRoot
import com.sevbify.app.ui.Nav
import com.sevbify.app.ui.Screen
import com.sevbify.app.ui.SevbifyTheme
import com.sevbify.app.ui.Tab
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class MainActivity : ComponentActivity() {
    private val askMusic = registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { rescan() }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent { SevbifyTheme { AppRoot() } }
        com.sevbify.app.ui.AudioOutput.start(this)
        val wanted = if (Build.VERSION.SDK_INT >= 33)
            arrayOf(Manifest.permission.READ_MEDIA_AUDIO, Manifest.permission.POST_NOTIFICATIONS)
        else arrayOf(Manifest.permission.READ_EXTERNAL_STORAGE)
        askMusic.launch(wanted)
        handleShare(intent)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleShare(intent)
    }

    /** Leaving Sevbify (home button) while a video podcast plays: keep watching in a small window. */
    override fun onUserLeaveHint() {
        super.onUserLeaveHint()
        if (Player.videoMode && VideoPlayer.playing) enterSystemPip()
    }

    private fun enterSystemPip() {
        try {
            enterPictureInPictureMode(
                android.app.PictureInPictureParams.Builder().setAspectRatio(android.util.Rational(16, 9)).build())
        } catch (e: Exception) { /* picture-in-picture is switched off for Sevbify in Android's settings */ }
    }

    override fun onPictureInPictureModeChanged(isInPictureInPictureMode: Boolean, newConfig: android.content.res.Configuration) {
        super.onPictureInPictureModeChanged(isInPictureInPictureMode, newConfig)
        VideoPlayer.inPip = isInPictureInPictureMode
    }

    override fun onStop() {
        super.onStop()
        // Settings ▸ Keep a copy in Downloads: the profile file, so it survives uninstalling Sevbify.
        SevbifyApp.instance.scope.launch {
            try { Profile.backupToDownloads(this@MainActivity) } catch (e: Exception) {
                if (e is kotlinx.coroutines.CancellationException) throw e
                android.util.Log.w("Sevbify", "profile backup: ${e.message}")
            }
        }
        // The picture-in-picture window was closed (or Sevbify went away without it): pause the video.
        if (!isInPictureInPictureMode) { VideoPlayer.inPip = false; VideoPlayer.pause() }
    }

    override fun onResume() {
        super.onResume()
        rescan()
    }

    fun rescan() {
        lifecycleScope.launch {
            val songs = withContext(Dispatchers.IO) { LocalMusic.scan(this@MainActivity) }
            Library.localSongs = songs
            Library.changed(save = false)
        }
    }

    /** A link shared from Spotify, Apple Music or YouTube: open Import (or the channel) with it filled in. */
    private fun handleShare(intent: Intent?) {
        if (intent?.action != Intent.ACTION_SEND) return
        val text = intent.getStringExtra(Intent.EXTRA_TEXT) ?: return
        Nav.tab = Tab.LIBRARY
        Nav.go(Screen.Import(text))
    }
}
