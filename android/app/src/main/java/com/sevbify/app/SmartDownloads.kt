package com.sevbify.app

import android.content.Context
import android.net.ConnectivityManager

/** Smart downloads, like Spotify's and the PC's (core/smart_downloads.py): a streamed song in your playlists that
 *  you played at least 3 times in the last 30 days is downloaded for you, at most 20 a day, and only on Wi-Fi (or
 *  another unmetered connection). Off unless you turn it on in Settings. Worked out on the phone. */
object SmartDownloads {
    private const val MIN_PLAYS = 3
    private const val DAYS = 30
    private const val PER_DAY = 20
    private var lastCheck = 0L

    fun check(context: Context, force: Boolean = false) {
        val s = Library.settings
        if (!s.smartDownloads || !s.online || Library.privateSession) return
        val now = System.currentTimeMillis()
        if (!force && now - lastCheck < 600_000) return
        lastCheck = now
        val cm = context.getSystemService(ConnectivityManager::class.java)
        if (cm == null || cm.isActiveNetworkMetered) return              // mobile data: never
        val today = android.text.format.DateFormat.format("yyyyMMdd", now).toString()
        val done = s.smartDay.split(":").let { if (it.size == 2 && it[0] == today) it[1].toIntOrNull() ?: 0 else 0 }
        val room = PER_DAY - done
        if (room <= 0) return
        val since = now / 1000 - DAYS * 86400L
        val counts = HashMap<String, Int>()
        Library.listens.forEach { (a, t, at) -> if (at >= since) Track.matchKeyOf(a, t).let { counts[it] = (counts[it] ?: 0) + 1 } }
        val seen = HashSet<String>()
        val picks = Library.playlists.flatMap { it.tracks }
            .filter { t -> !t.isLocal && !t.isItem && seen.add(t.matchKey) && (counts[t.matchKey] ?: 0) >= MIN_PLAYS &&
                           Library.localFor(t) == null && Downloads.stateOf(t) == null }
            .sortedByDescending { counts[it.matchKey] ?: 0 }
            .take(room)
        if (picks.isEmpty()) return
        val added = Downloads.request(picks)
        if (added > 0) {
            s.smartDay = "$today:${done + added}"
            Library.changed()
            Player.fileLog("download", "smart downloads: $added song(s) you keep playing")
        }
    }
}
