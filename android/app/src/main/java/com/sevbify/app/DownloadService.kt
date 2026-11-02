package com.sevbify.app

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat

/** Keeps downloads going with the screen off, showing "Downloading 2 of 5" in the notifications. */
class DownloadService : Service() {
    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        // Android requires startForeground() soon after the service is asked to start, even if the downloads
        // already finished in the meantime (otherwise it closes the app with an error). So: always start in the
        // foreground first, then stop straight away if there's nothing left to do.
        val type = if (Build.VERSION.SDK_INT >= 29) ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC else 0
        try {
            ServiceCompat.startForeground(this, ID, build(this), type)
        } catch (e: Exception) {
            if (e is kotlinx.coroutines.CancellationException) throw e   // replaced by a newer request: not an error
            // Android 12+ can refuse a foreground start from the background: downloads continue while Sevbify
            // is open, without the notification.
        }
        running = this
        if (stopWanted) finish()
        return START_NOT_STICKY
    }

    private fun finish() {
        stopWanted = false
        running = null
        ServiceCompat.stopForeground(this, ServiceCompat.STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    override fun onDestroy() {
        if (running === this) running = null
        super.onDestroy()
    }

    companion object {
        private const val ID = 7
        @Volatile private var running: DownloadService? = null
        @Volatile private var stopWanted = false

        /** Downloads finished or stopped: remove the notification (now, or as soon as the service has started). */
        fun requestStop() {
            val s = running
            if (s != null) s.finish() else stopWanted = true
        }

        /** About to start downloading: a stop asked for earlier no longer applies. */
        fun cancelStop() { stopWanted = false }
        private const val CHANNEL = "downloads"

        private fun build(context: Context): Notification {
            val nm = context.getSystemService(NotificationManager::class.java)
            if (Build.VERSION.SDK_INT >= 26 && nm.getNotificationChannel(CHANNEL) == null) {
                nm.createNotificationChannel(NotificationChannel(CHANNEL, "Downloads", NotificationManager.IMPORTANCE_LOW))
            }
            val total = Downloads.batchTotal()
            val waiting = Downloads.waiting()
            val done = (total - waiting).coerceAtLeast(0)
            val now = Downloads.currentTrack()
            val next = Downloads.upcoming(5)
            val open = android.app.PendingIntent.getActivity(context, 0,
                Intent(context, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP),
                android.app.PendingIntent.FLAG_IMMUTABLE or android.app.PendingIntent.FLAG_UPDATE_CURRENT)
            val b = NotificationCompat.Builder(context, CHANNEL)
                .setSmallIcon(android.R.drawable.stat_sys_download)
                .setContentIntent(open)
                .setOngoing(true).setSilent(true).setOnlyAlertOnce(true)
            if (waiting == 0) return b.setContentTitle("Sevbify").setContentText("Downloads finished").build()
            // "Downloading Song title" / "Artist · 3 more", with a bar for the whole batch (a single song just
            // shows a moving bar: the download's own progress isn't reported by the song finder).
            b.setContentTitle(if (now != null) "Downloading ${now.title}" else "Downloading")
                .setContentText(buildString {
                    now?.let { append(it.artist) }
                    if (waiting > 1) { if (isNotEmpty()) append(" · "); append("${waiting - 1} more") }
                })
                .setSubText(if (total > 1) "$done of $total" else null)
                .setProgress(if (total > 1) total else 0, if (total > 1) done else 0, total <= 1)
            if (next.isNotEmpty()) {
                val style = NotificationCompat.InboxStyle().setBigContentTitle(
                    if (now != null) "Downloading ${now.title}" else "Downloading")
                now?.let { style.addLine("▶ ${it.title} — ${it.artist}") }
                next.forEach { style.addLine("${it.title} — ${it.artist}") }
                if (waiting - (if (now != null) 1 else 0) > next.size)
                    style.setSummaryText("+ ${waiting - (if (now != null) 1 else 0) - next.size} more")
                b.setStyle(style)
            }
            return b.build()
        }

        fun update(context: Context) {
            try {
                context.getSystemService(NotificationManager::class.java).notify(ID, build(context))
            } catch (e: SecurityException) { /* notifications not allowed: downloads still run */ }
        }
    }
}
