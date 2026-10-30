package com.sevbify.app

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.provider.Settings as AndroidSettings
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.core.content.FileProvider
import com.sevbify.app.ui.Nav
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import java.security.MessageDigest

/** In-app updates: once a day (when online) GitHub's newest Sevbify release is checked; a new version is offered
 *  once. "Download" fetches the APK from Sevbify's own release (checked against GitHub's SHA-256) and opens
 *  Android's installer. It's signed with the same key, so it installs over this one and keeps everything. */
object Updater {
    private const val ALLOWED = "https://github.com/Obamna1234/Sevbify/releases/download/"
    var offer by mutableStateOf<JSONObject?>(null)          // the update dialog
    var progress by mutableFloatStateOf(-1f)                // 0..1 while downloading
    var status by mutableStateOf("")

    suspend fun check(manual: Boolean = false): String {
        val s = Library.settings
        if (!s.online) return "Turn on Online features to check for updates."
        if (!manual && System.currentTimeMillis() - s.lastAppCheck < 24L * 3600 * 1000) return ""
        val r = Bridge.obj("check_updates", Library.coreVersion, "android")
        s.lastAppCheck = System.currentTimeMillis(); Library.changed()
        if (r.optBoolean("newer")) {
            val latest = r.optString("latest")
            if (manual || s.updateAsked != latest) {
                s.updateAsked = latest; Library.changed()
                offer = r
            }
        }
        return r.optString("message")
    }

    suspend fun download(context: Context, r: JSONObject) {
        val url = r.optString("url")
        if (!url.startsWith(ALLOWED)) { status = "No Android download in that release."; return }
        val sha = r.optString("sha256").lowercase()
        val size = r.optLong("size")
        progress = 0f; status = "Downloading Sevbify ${r.optString("latest")}…"
        try {
            val apk = withContext(Dispatchers.IO) {
                val dir = File(context.cacheDir, "update").apply { deleteRecursively(); mkdirs() }
                val out = File(dir, "Sevbify.apk")
                val conn = URL(url).openConnection() as HttpURLConnection
                conn.instanceFollowRedirects = true
                conn.connectTimeout = 30_000; conn.readTimeout = 60_000
                conn.setRequestProperty("User-Agent", "Sevbify-updater")
                val total = if (size > 0) size else conn.contentLengthLong
                val md = MessageDigest.getInstance("SHA-256")
                var got = 0L
                conn.inputStream.use { input ->
                    out.outputStream().use { o ->
                        val buf = ByteArray(128 * 1024)
                        while (true) {
                            val n = input.read(buf); if (n < 0) break
                            got += n
                            if (got > 400L * 1024 * 1024) throw CoreError("the download was far bigger than expected")
                            md.update(buf, 0, n); o.write(buf, 0, n)
                            if (total > 0) progress = (got.toFloat() / total).coerceAtMost(1f)
                        }
                    }
                }
                if (size > 0 && got != size) { out.delete(); throw CoreError("the download didn't finish") }
                val hex = md.digest().joinToString("") { "%02x".format(it) }
                if (sha.isNotEmpty() && hex != sha) { out.delete(); throw CoreError("it didn't match GitHub's checksum") }
                out
            }
            progress = -1f; status = ""
            install(context, apk)
        } catch (e: Exception) {
            if (e is kotlinx.coroutines.CancellationException) throw e
            progress = -1f; status = "Couldn't download the update: ${e.message}"
        }
    }

    /** Opens Android's installer for the downloaded APK (asks once for "Install unknown apps" if needed). */
    fun install(context: Context, apk: File? = null) {
        val file = apk ?: File(context.cacheDir, "update/Sevbify.apk")
        if (!file.exists()) return
        if (Build.VERSION.SDK_INT >= 26 && !context.packageManager.canRequestPackageInstalls()) {
            Nav.say("Allow Sevbify to install updates, then come back and tap Install")
            status = "ready"
            context.startActivity(Intent(AndroidSettings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                                         Uri.parse("package:${context.packageName}")).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
            return
        }
        val uri = FileProvider.getUriForFile(context, "${context.packageName}.updates", file)
        context.startActivity(Intent(Intent.ACTION_VIEW).setDataAndType(uri, "application/vnd.android.package-archive")
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK))
        status = "ready"
    }
}
