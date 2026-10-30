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
import androidx.media3.common.MediaItem
import androidx.media3.common.MediaMetadata
import androidx.media3.session.LibraryResult
import androidx.media3.session.MediaLibraryService
import androidx.media3.session.MediaSession
import com.google.common.collect.ImmutableList
import com.google.common.util.concurrent.Futures
import com.google.common.util.concurrent.ListenableFuture
import java.util.concurrent.ConcurrentHashMap

/**
 * Plays music with the screen off, with Android's notification / lock-screen controls. The queue itself is
 * Sevbify's (see Player): songs you don't have are looked up just before they play, so the session only
 * ever holds the current song; Next / Previous on the lock screen go back to Sevbify's queue.
 */
@androidx.annotation.OptIn(markerClass = [UnstableApi::class])
class PlaybackService : MediaLibraryService() {
    private var session: MediaLibrarySession? = null
    private val main = android.os.Handler(android.os.Looper.getMainLooper())

    override fun onCreate() {
        super.onCreate()
        val http = DefaultHttpDataSource.Factory().setAllowCrossProtocolRedirects(true)
            .setUserAgent("Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Mobile Safari/537.36")
        val withHeaders = ResolvingDataSource.Factory(DefaultDataSource.Factory(this, http)) { spec ->
            val extra = headers[spec.uri.toString()]
            if (extra.isNullOrEmpty()) spec else spec.withAdditionalHeaders(extra)
        }
        // Songs from your own server carry a sign-in. They use a connection that lets Android follow redirects
        // itself: it drops the sign-in when a redirect leaves the server and never goes from https to http.
        val strictHttp = DefaultHttpDataSource.Factory().setAllowCrossProtocolRedirects(false)
            .setUserAgent("Sevbify")
        val signedIn = ResolvingDataSource.Factory(DefaultDataSource.Factory(this, strictHttp)) { spec ->
            val extra = headers[spec.uri.toString()]
            if (extra.isNullOrEmpty()) spec else spec.withAdditionalHeaders(extra)
        }
        val picking = androidx.media3.datasource.DataSource.Factory {
            PickingDataSource(withHeaders.createDataSource(), signedIn.createDataSource())
        }
        val exo = ExoPlayer.Builder(this)
            .setMediaSourceFactory(DefaultMediaSourceFactory(picking))
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
        session = MediaLibrarySession.Builder(this, player, CarLibrary()).setSessionActivity(open).build()
    }

    override fun onGetSession(controllerInfo: MediaSession.ControllerInfo): MediaLibrarySession? {
        if (controllerInfo.packageName == ANDROID_AUTO) carConnected = true      // Android Auto found Sevbify
        return session
    }

    /** What Android Auto shows on the car's screen: Recently played, Your Songs, your playlists. Picking a song
     *  plays it through Sevbify's own queue (full songs looked up as usual). */
    private inner class CarLibrary : MediaLibrarySession.Callback {
        private fun folder(id: String, title: String) = MediaItem.Builder().setMediaId(id).setMediaMetadata(
            MediaMetadata.Builder().setTitle(title).setIsBrowsable(true).setIsPlayable(false)
                .setMediaType(MediaMetadata.MEDIA_TYPE_FOLDER_MIXED).build()).build()

        private fun song(id: String, t: Track) = MediaItem.Builder().setMediaId(id).setMediaMetadata(
            MediaMetadata.Builder().setTitle(t.title).setArtist(t.artist).setAlbumTitle(t.album)
                .setArtworkUri(t.art.takeIf { it.startsWith("content:") || it.startsWith("https:") }?.let { Uri.parse(it) })
                .setIsBrowsable(false).setIsPlayable(true).setMediaType(MediaMetadata.MEDIA_TYPE_MUSIC).build()).build()

        /** (songs, source name) for a folder id. */
        private fun list(id: String): Pair<List<Track>, String> = when {
            id == "recent" -> Library.recent.toList() to "Recently played"
            id == "songs" -> Library.localSongs to "Your Songs"
            id.startsWith("pl:") -> Library.playlists.firstOrNull { it.id == id.removePrefix("pl:") }
                ?.let { it.tracks.toList() to it.name } ?: (emptyList<Track>() to "")
            else -> emptyList<Track>() to ""
        }

        /** Only Sevbify itself, the phone's own media controls (lock screen, Bluetooth, notification) and Android
         *  Auto may connect: other apps can't read your playlists or what you listened to. */
        override fun onConnect(session: MediaSession, controller: MediaSession.ControllerInfo): MediaSession.ConnectionResult {
            val ok = controller.packageName == packageName || controller.isTrusted ||
                controller.packageName == ANDROID_AUTO || controller.packageName == "com.google.android.carassistant"
            return if (ok) super.onConnect(session, controller) else MediaSession.ConnectionResult.reject()
        }

        override fun onGetLibraryRoot(session: MediaLibrarySession, browser: MediaSession.ControllerInfo,
                                      params: LibraryParams?): ListenableFuture<LibraryResult<MediaItem>> =
            Futures.immediateFuture(LibraryResult.ofItem(folder("root", "Sevbify"), params))

        override fun onGetChildren(session: MediaLibrarySession, browser: MediaSession.ControllerInfo, parentId: String,
                                   page: Int, pageSize: Int, params: LibraryParams?):
            ListenableFuture<LibraryResult<ImmutableList<MediaItem>>> {
            val items: List<MediaItem> = when (parentId) {
                "root" -> listOf(folder("recent", "Recently played"), folder("songs", "Your Songs"),
                                 folder("playlists", "Your playlists"))
                "playlists" -> Library.playlists.map { folder("pl:" + it.id, it.name) }
                else -> list(parentId).first.mapIndexed { i, t -> song("$parentId#$i", t) }
            }
            val from = (page * pageSize).coerceAtMost(items.size)
            val to = (from + pageSize.coerceAtLeast(1)).coerceAtMost(items.size)
            return Futures.immediateFuture(LibraryResult.ofItemList(ImmutableList.copyOf(items.subList(from, to)), params))
        }

        override fun onAddMediaItems(mediaSession: MediaSession, controller: MediaSession.ControllerInfo,
                                     mediaItems: MutableList<MediaItem>): ListenableFuture<MutableList<MediaItem>> {
            val id = mediaItems.firstOrNull()?.mediaId.orEmpty()
            val folderId = id.substringBeforeLast('#', "")
            val index = id.substringAfterLast('#', "").toIntOrNull()
            val (tracks, source) = list(folderId)
            if (index != null && index in tracks.indices) {
                main.post { Player.play(tracks[index], tracks, source) }   // after the session has applied this answer
            }
            return Futures.immediateFuture(mutableListOf())
        }
    }

    override fun onTaskRemoved(rootIntent: Intent?) {
        val p = session?.player
        if (p == null || !p.playWhenReady || p.mediaItemCount == 0) stopSelf()
    }

    override fun onDestroy() {
        session?.run { player.release(); release() }
        session = null
        super.onDestroy()
    }

    /** Opens a link with the signed-in connection when it carries a server sign-in, otherwise the normal one. */
    private class PickingDataSource(val normal: androidx.media3.datasource.DataSource,
                                    val strict: androidx.media3.datasource.DataSource) : androidx.media3.datasource.DataSource {
        private var current: androidx.media3.datasource.DataSource? = null
        override fun addTransferListener(l: androidx.media3.datasource.TransferListener) {
            normal.addTransferListener(l); strict.addTransferListener(l)
        }
        override fun open(dataSpec: androidx.media3.datasource.DataSpec): Long {
            val signed = headers[dataSpec.uri.toString()]?.keys?.any { it.equals("Authorization", true) } == true
            val ds = if (signed) strict else normal
            current = ds
            return ds.open(dataSpec)
        }
        override fun read(buffer: ByteArray, offset: Int, length: Int) = current!!.read(buffer, offset, length)
        override fun getUri(): Uri? = current?.uri
        override fun getResponseHeaders(): Map<String, List<String>> = current?.responseHeaders ?: emptyMap()
        override fun close() { try { current?.close() } finally { current = null } }
    }

    companion object {
        const val ANDROID_AUTO = "com.google.android.projection.gearhead"
        @Volatile var carConnected = false
        /** HTTP headers some streams need (yt-dlp gives them with the link). */
        val headers = ConcurrentHashMap<String, Map<String, String>>()
    }
}
