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
            val waiting = Downloads.waiting()
            return NotificationCompat.Builder(context, CHANNEL)
                .setSmallIcon(android.R.drawable.stat_sys_download)
                .setContentTitle("Sevbify")
                .setContentText(if (waiting > 0) "Downloading · $waiting to go" else "Downloads finished")
                .setOngoing(true).setSilent(true).build()
        }

        fun update(context: Context) {
            try {
                context.getSystemService(NotificationManager::class.java).notify(ID, build(context))
            } catch (e: SecurityException) { /* notifications not allowed: downloads still run */ }
        }
    }
}
