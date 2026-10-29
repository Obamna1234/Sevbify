package com.sevbify.app

import android.app.PendingIntent
import android.content.Intent
import android.net.Uri
import androidx.media3.common.AudioAttributes
import androidx.media3.common.C
import androidx.media3.common.ForwardingPlayer
import androidx.media3.common.Player as MediaPlayer
import androidx.media3.common.util.UnstableApi
import androidx.media3.datasource.DefaultDataSource
import androidx.media3.datasource.DefaultHttpDataSource
import androidx.media3.datasource.ResolvingDataSource
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory
import androidx.media3.session.MediaSession
import androidx.media3.session.MediaSessionService
import java.util.concurrent.ConcurrentHashMap

/**
 * Plays music with the screen off, with Android's notification / lock-screen controls. The queue itself is
 * Sevbify's (see Player): songs you don't have are looked up just before they play, so the session only
 * ever holds the current song; Next / Previous on the lock screen go back to Sevbify's queue.
 */
@UnstableApi
class PlaybackService : MediaSessionService() {
    private var session: MediaSession? = null

    override fun onCreate() {
        super.onCreate()
        val http = DefaultHttpDataSource.Factory().setAllowCrossProtocolRedirects(true)
            .setUserAgent("Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Mobile Safari/537.36")
        val withHeaders = ResolvingDataSource.Factory(DefaultDataSource.Factory(this, http)) { spec ->
            val extra = headers[spec.uri.toString()]
            if (extra.isNullOrEmpty()) spec else spec.withAdditionalHeaders(extra)
        }
        val exo = ExoPlayer.Builder(this)
            .setMediaSourceFactory(DefaultMediaSourceFactory(withHeaders))
            .setAudioAttributes(AudioAttributes.Builder().setUsage(C.USAGE_MEDIA)
                                    .setContentType(C.AUDIO_CONTENT_TYPE_MUSIC).build(), true)
            .setHandleAudioBecomingNoisy(true)       // headphones unplugged: pause, like Spotify
            .setWakeMode(C.WAKE_MODE_NETWORK)
            .build()
        val player = object : ForwardingPlayer(exo) {
            override fun getAvailableCommands(): MediaPlayer.Commands = super.getAvailableCommands().buildUpon()
                .add(MediaPlayer.COMMAND_SEEK_TO_NEXT).add(MediaPlayer.COMMAND_SEEK_TO_NEXT_MEDIA_ITEM)
                .add(MediaPlayer.COMMAND_SEEK_TO_PREVIOUS).add(MediaPlayer.COMMAND_SEEK_TO_PREVIOUS_MEDIA_ITEM).build()
            override fun isCommandAvailable(command: Int): Boolean =
                command == MediaPlayer.COMMAND_SEEK_TO_NEXT || command == MediaPlayer.COMMAND_SEEK_TO_PREVIOUS ||
                    command == MediaPlayer.COMMAND_SEEK_TO_NEXT_MEDIA_ITEM ||
                    command == MediaPlayer.COMMAND_SEEK_TO_PREVIOUS_MEDIA_ITEM || super.isCommandAvailable(command)
            override fun seekToNext() { Player.next() }
            override fun seekToNextMediaItem() { Player.next() }
            override fun seekToPrevious() { Player.previous() }
            override fun seekToPreviousMediaItem() { Player.previous() }
            override fun hasNextMediaItem() = true
            override fun hasPreviousMediaItem() = true
        }
        val open = PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java)
                                                 .addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP),
                                             PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        session = MediaSession.Builder(this, player).setSessionActivity(open).build()
    }

    override fun onGetSession(controllerInfo: MediaSession.ControllerInfo): MediaSession? = session

    override fun onTaskRemoved(rootIntent: Intent?) {
        val p = session?.player
        if (p == null || !p.playWhenReady || p.mediaItemCount == 0) stopSelf()
    }

    override fun onDestroy() {
        session?.run { player.release(); release() }
        session = null
        super.onDestroy()
    }

    companion object {
        /** HTTP headers some streams need (yt-dlp gives them with the link). */
        val headers = ConcurrentHashMap<String, Map<String, String>>()
    }
}
