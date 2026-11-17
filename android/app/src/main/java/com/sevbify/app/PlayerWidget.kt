package com.sevbify.app

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.widget.RemoteViews
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/** The home-screen widget, like Spotify's: cover, song and artist, with previous / play-pause / next. Tapping the
 *  song opens Sevbify. It's updated by the player when the song or play state changes. */
class PlayerWidget : AppWidgetProvider() {
    override fun onUpdate(context: Context, manager: AppWidgetManager, ids: IntArray) = refresh(context)

    override fun onReceive(context: Context, intent: Intent) {
        super.onReceive(context, intent)
        val action = intent.action ?: return
        if (action !in listOf(PLAY, NEXT, PREV)) return
        if (Player.current == null) {                      // nothing loaded (the app was closed): open it instead
            context.startActivity(Intent(context, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
            return
        }
        when (action) { PLAY -> Player.playPause(); NEXT -> Player.next(); PREV -> Player.previous() }
    }

    companion object {
        private const val PLAY = "com.sevbify.app.widget.PLAY"
        private const val NEXT = "com.sevbify.app.widget.NEXT"
        private const val PREV = "com.sevbify.app.widget.PREV"
        private var shownArt = ""
        private var artBitmap: android.graphics.Bitmap? = null

        private fun button(context: Context, action: String, code: Int): PendingIntent =
            PendingIntent.getBroadcast(context, code, Intent(context, PlayerWidget::class.java).setAction(action),
                                       PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)

        /** Redraw every Sevbify widget with what's playing now. Safe to call often. */
        fun refresh(context: Context) {
            try {
                val manager = AppWidgetManager.getInstance(context)
                val ids = manager.getAppWidgetIds(ComponentName(context, PlayerWidget::class.java))
                if (ids.isEmpty()) return
                val t = Player.current
                val v = RemoteViews(context.packageName, R.layout.widget_player)
                v.setTextViewText(R.id.widget_title, t?.title ?: "Sevbify")
                v.setTextViewText(R.id.widget_artist, t?.artist ?: "Tap to open")
                v.setImageViewResource(R.id.widget_play,
                    if (Player.showPlaying) android.R.drawable.ic_media_pause else android.R.drawable.ic_media_play)
                val art = t?.art.orEmpty()
                if (art.isNotEmpty() && art == shownArt && artBitmap != null) v.setImageViewBitmap(R.id.widget_art, artBitmap)
                else v.setImageViewResource(R.id.widget_art, R.mipmap.ic_launcher)
                v.setOnClickPendingIntent(R.id.widget_play, button(context, PLAY, 1))
                v.setOnClickPendingIntent(R.id.widget_next, button(context, NEXT, 2))
                v.setOnClickPendingIntent(R.id.widget_prev, button(context, PREV, 3))
                v.setOnClickPendingIntent(R.id.widget_root, PendingIntent.getActivity(context, 4,
                    Intent(context, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE))
                manager.updateAppWidget(ids, v)
                if (art.isNotEmpty() && art != shownArt) loadArt(context, art)
            } catch (t: Throwable) {
                android.util.Log.w("Sevbify", "widget: ${t.message}")
            }
        }

        private fun loadArt(context: Context, art: String) {
            shownArt = art
            artBitmap = null
            SevbifyApp.instance.scope.launch {
                val bmp = withContext(Dispatchers.IO) {
                    runCatching {
                        val req = coil.request.ImageRequest.Builder(context).data(art).size(192).allowHardware(false).build()
                        (coil.Coil.imageLoader(context).execute(req).drawable as? android.graphics.drawable.BitmapDrawable)?.bitmap
                    }.getOrNull()
                }
                if (bmp != null && shownArt == art) { artBitmap = bmp; refresh(context) }
            }
        }
    }
}
