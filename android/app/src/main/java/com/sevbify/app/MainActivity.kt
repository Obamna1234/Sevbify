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
