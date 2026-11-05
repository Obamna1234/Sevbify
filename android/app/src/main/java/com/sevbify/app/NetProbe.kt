package com.sevbify.app

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.net.HttpURLConnection
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.Socket
import java.net.URL

/** Small network checks that use the same Java network stack as the player does (Python's can differ), used to
 *  catch a refused stream link before the player waits on it, and to say in the Playback status log what the
 *  phone's network is doing when a stream fails. */
object NetProbe {
    /** The HTTP status the server gives for the first two bytes of [url] (what the player asks for first), or -1
     *  when it couldn't be reached in time. */
    suspend fun check(url: String, headers: Map<String, String>?, timeoutMs: Int = 6000): Int = withContext(Dispatchers.IO) {
        var c: HttpURLConnection? = null
        try {
            c = (URL(url).openConnection() as HttpURLConnection).apply {
                connectTimeout = timeoutMs; readTimeout = timeoutMs; instanceFollowRedirects = true
                headers?.forEach { (k, v) -> setRequestProperty(k, v) }
                setRequestProperty("Range", "bytes=0-1")
            }
            val code = c.responseCode
            if (code < 400) c.inputStream.use { it.read() }
            code
        } catch (e: Exception) { -1 } finally { c?.disconnect() }
    }

    /** "IPv6 ok 40 ms, IPv4 timeout 3000 ms": how each address the host resolves to answers on port 443 (no
     *  addresses are shown). */
    suspend fun describe(host: String): String = withContext(Dispatchers.IO) {
        try {
            val addrs = InetAddress.getAllByName(host)
            addrs.take(4).joinToString(", ") { a ->
                val t0 = System.currentTimeMillis()
                val ok = try { Socket().use { it.connect(InetSocketAddress(a, 443), 3000) }; true } catch (e: Exception) { false }
                "IPv${if (a.address.size == 16) 6 else 4} ${if (ok) "ok" else "no answer"} ${System.currentTimeMillis() - t0} ms"
            }.ifEmpty { "no addresses" }
        } catch (e: Exception) { "couldn't resolve: ${e.message?.take(40)}" }
    }
}
