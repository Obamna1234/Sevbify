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
        val type = if (Build.VERSION.SDK_INT >= 29) ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC else 0
        ServiceCompat.startForeground(this, ID, build(this), type)
        return START_NOT_STICKY
    }

    companion object {
        private const val ID = 7
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
