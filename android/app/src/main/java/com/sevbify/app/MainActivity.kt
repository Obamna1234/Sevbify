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
        I18n.load(this)                       // Sevbify's language (Android's per-app language setting)
        enableEdgeToEdge()
        setContent { SevbifyTheme { AppRoot() } }
        com.sevbify.app.ui.AudioOutput.start(this)
        val wanted = if (Build.VERSION.SDK_INT >= 33)
            arrayOf(Manifest.permission.READ_MEDIA_AUDIO, Manifest.permission.POST_NOTIFICATIONS)
        else arrayOf(Manifest.permission.READ_EXTERNAL_STORAGE)
        askMusic.launch(wanted)
        handleIncoming(intent)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleIncoming(intent)
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
                if (SevbifyApp.debuggable) android.util.Log.w("Sevbify", "profile backup: ${e.message}")
            }
        }
        // The picture-in-picture window was closed (or Sevbify went away without it): pause the video.
        if (!isInPictureInPictureMode) { VideoPlayer.inPip = false; VideoPlayer.pause() }
    }

    override fun onResume() {
        super.onResume()
        rescan(cloud = CloudFolders.cached == null)
        CarHelp.check(this)
        window.decorView.postDelayed({ CarHelp.checkInCar(this) }, 30_000)   // in a car, but no Android Auto?
    }

    /** cloud = also list the folders from other apps again (slow for cloud apps, so not on every return). */
    fun rescan(cloud: Boolean = true) {
        lifecycleScope.launch {
            val songs = withContext(Dispatchers.IO) {
                val phone = LocalMusic.scan(this@MainActivity)
                val keys = phone.map { it.matchKey }.toHashSet()
                if (cloud || CloudFolders.cached == null) CloudFolders.cached = CloudFolders.scan(this@MainActivity)
                phone + CloudFolders.cached.orEmpty().filter { it.matchKey !in keys }   // phone copy first
            }
            Library.localSongs = songs
            Library.changed(save = false)
        }
    }

    /** Something handed to Sevbify from another app: an audio file to play ("Open with" / "Share" a song), or
     *  a Spotify / Apple Music / YouTube link to import. */
    private fun handleIncoming(intent: Intent?) {
        intent ?: return
        when (intent.action) {
            // "Open with ▸ Sevbify" on an audio file in a file manager.
            Intent.ACTION_VIEW -> intent.data?.let { playUri(it) }
            Intent.ACTION_SEND -> {
                val type = intent.type.orEmpty()
                if (type.startsWith("audio") || type == "application/ogg") {
                    // "Share ▸ Sevbify" on a song.
                    val uri = if (Build.VERSION.SDK_INT >= 33)
                        intent.getParcelableExtra(Intent.EXTRA_STREAM, android.net.Uri::class.java)
                    else @Suppress("DEPRECATION") intent.getParcelableExtra(Intent.EXTRA_STREAM)
                    uri?.let { playUri(it) }
                } else {
                    // A shared link (Spotify / Apple Music / YouTube): open Import with it filled in.
                    val text = intent.getStringExtra(Intent.EXTRA_TEXT) ?: return
                    Nav.tab = Tab.LIBRARY
                    Nav.go(Screen.Import(text))
                }
            }
        }
    }

    /** Play one audio file handed to Sevbify from another app. Reads its tags off the UI thread; the player
     *  starts it as soon as it's connected (see Player.pendingPlay) if the app was cold-started by this. */
    private fun playUri(uri: android.net.Uri) {
        lifecycleScope.launch {
            try {
                val t = withContext(Dispatchers.IO) { LocalMusic.trackFromUri(this@MainActivity, uri) }
                Nav.tab = Tab.LIBRARY
                Player.play(t, listOf(t), tr("File"))
            } catch (e: Exception) {
                if (e is kotlinx.coroutines.CancellationException) throw e
                Nav.say("⚠ ${tr("Couldn't play that file")}: ${e.message}")
            }
        }
    }
}
