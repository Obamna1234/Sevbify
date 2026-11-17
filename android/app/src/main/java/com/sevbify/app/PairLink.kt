package com.sevbify.app

import android.content.ContentValues
import android.content.Context
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.os.StatFs
import android.provider.MediaStore
import android.provider.OpenableColumns
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import org.json.JSONArray
import org.json.JSONObject
import java.io.DataInputStream
import java.io.File
import java.io.FileOutputStream
import java.io.OutputStream
import java.math.BigInteger
import java.net.InetSocketAddress
import java.net.Socket
import java.nio.ByteBuffer
import com.sevbify.app.ui.Nav
import java.security.KeyFactory
import java.security.KeyPair
import java.security.KeyPairGenerator
import java.security.MessageDigest
import java.security.PrivateKey
import java.security.PublicKey
import java.security.SecureRandom
import java.security.interfaces.ECPublicKey
import java.security.spec.ECGenParameterSpec
import java.security.spec.ECPoint
import java.security.spec.ECPublicKeySpec
import java.text.Normalizer
import javax.crypto.Cipher
import javax.crypto.KeyAgreement
import javax.crypto.Mac
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.SecretKeySpec

/**
 * Sevbify on this phone and Sevbify on a computer: paired by scanning the computer's QR code, then songs and
 * folders go either way over your own Wi-Fi. The protocol and its safety rules are the computer's
 * (core/pair_crypto.py and core/pairing.py); this is the same in Kotlin, with Android's own crypto.
 *
 * Nothing goes through the internet: the computer's address must be on your local network. Everything after the
 * first two messages is encrypted (AES-256-GCM, keys from P-256 ECDH + HKDF-SHA256 with the QR code's one-time
 * code, or later this phone's own key). Files from the computer are saved only after you accept them, only music
 * (and covers / lyrics / playlists), each offered file once, never more than offered, in Music/Sevbify/From <name>.
 */
object PairCrypto {
    private const val LABEL = "sevbify-pair-v1"
    const val KIND_JSON = 1
    const val KIND_DATA = 2
    const val MAX_FRAME = 1 shl 20
    val rng = SecureRandom()

    fun newKeyPair(): KeyPair = KeyPairGenerator.getInstance("EC").apply { initialize(ECGenParameterSpec("secp256r1")) }
        .generateKeyPair()

    private fun pad32(b: BigInteger): ByteArray {
        val raw = b.toByteArray()
        return when {
            raw.size == 32 -> raw
            raw.size > 32 -> raw.copyOfRange(raw.size - 32, raw.size)
            else -> ByteArray(32 - raw.size) + raw
        }
    }

    fun publicBytes(k: PublicKey): ByteArray {
        val w = (k as ECPublicKey).w
        return byteArrayOf(4) + pad32(w.affineX) + pad32(w.affineY)
    }

    fun loadPublic(raw: ByteArray, like: PublicKey): PublicKey {
        require(raw.size == 65 && raw[0] == 4.toByte()) { "bad key" }
        val point = ECPoint(BigInteger(1, raw.copyOfRange(1, 33)), BigInteger(1, raw.copyOfRange(33, 65)))
        val params = (like as ECPublicKey).params
        // The curve check: y² = x³ + ax + b (mod p). KeyAgreement also refuses points that aren't on the curve.
        val p = (params.curve.field as java.security.spec.ECFieldFp).p
        val x = point.affineX; val y = point.affineY
        require(x.signum() >= 0 && x < p && y.signum() >= 0 && y < p) { "bad key" }
        require(y.modPow(BigInteger.valueOf(2), p) == x.pow(3).add(params.curve.a.multiply(x)).add(params.curve.b).mod(p)) { "bad key" }
        return KeyFactory.getInstance("EC").generatePublic(ECPublicKeySpec(point, params))
    }

    fun ecdh(priv: PrivateKey, pub: PublicKey): ByteArray =
        KeyAgreement.getInstance("ECDH").apply { init(priv); doPhase(pub, true) }.generateSecret()

    fun hmac(key: ByteArray, data: ByteArray): ByteArray =
        Mac.getInstance("HmacSHA256").apply { init(SecretKeySpec(key, "HmacSHA256")) }.doFinal(data)

    fun sha256(b: ByteArray): ByteArray = MessageDigest.getInstance("SHA-256").digest(b)

    private fun hkdfExpand(prk: ByteArray, info: ByteArray, length: Int): ByteArray {
        var out = ByteArray(0); var block = ByteArray(0); var i = 1
        while (out.size < length) { block = hmac(prk, block + info + byteArrayOf(i.toByte())); out += block; i++ }
        return out.copyOf(length)
    }

    /** -> (client-to-server key, server-to-client key); the hellos are the frames exactly as sent/received. */
    fun deriveKeys(secret: ByteArray, psk: ByteArray, mode: String, dev: String, cNonce: ByteArray, sNonce: ByteArray,
                   cEpk: ByteArray, sEpk: ByteArray, cHello: ByteArray, sHello: ByteArray): Pair<ByteArray, ByteArray> {
        val salt = sha256(LABEL.toByteArray() + mode.toByteArray() + "|".toByteArray() + dev.toByteArray() +
                "|".toByteArray() + cNonce + sNonce + cEpk + sEpk + sha256(cHello) + sha256(sHello))
        val prk = hmac(salt, secret + psk)
        val okm = hkdfExpand(prk, "sevbify v1 keys".toByteArray(), 64)
        return okm.copyOfRange(0, 32) to okm.copyOfRange(32, 64)
    }

    /** The computer's fixed inputs (core/pair_crypto.test_vector, pinned in tests/test_pairing.py) must give the
     *  same keys here: checked by the end-to-end test (debug builds log the result). */
    fun selfTest(): Boolean = try {
        val params = (newKeyPair().public as ECPublicKey).params
        val cPriv = KeyFactory.getInstance("EC").generatePrivate(
            java.security.spec.ECPrivateKeySpec(BigInteger("11".repeat(32), 16), params))
        val cEpk = hex(V_C_EPK); val sEpk = hex(V_S_EPK)
        val like = newKeyPair().public
        val secret = ecdh(cPriv, loadPublic(sEpk, like))
        val (c2s, s2c) = deriveKeys(secret, ByteArray(32) { it.toByte() }, "pair", "", ByteArray(32) { 1 },
            ByteArray(32) { 2 }, cEpk, sEpk, hex("000000027b7d"), hex("000000035b315d"))
        val frame = PairChannel(c2s, s2c).seal(KIND_JSON, "{\"t\":\"ping\"}".toByteArray())
        c2s.toHex() == V_C2S && frame.toHex() == V_FRAME && publicBytes(loadPublic(cEpk, like)).toHex() == V_C_EPK
    } catch (e: Exception) { false }

    private const val V_C2S = "8638dfdad0487dfde8d45c9487939f51f72828040e0c707ec4dfc5bdb4725b52"
    private const val V_FRAME = "0000001d66d891584379f9cd9fcd93c63311ea622004319f5c86f7e1c96a625ae2"
    private const val V_C_EPK = "040217e617f0b6443928278f96999e69a23a4f2c152bdf6d6cdf66e5b80282d4ed194a7debcb97712d2dda3ca85aa8765a56f45fc758599652f2897c65306e5794"
    private const val V_S_EPK = "04d65a93977caa3d1b081852ff57a79e465f1660577304baead505dd3a48589cf350185e895372df6221ea3a137557e473fddb6755f05bd507c3c533fce9c91285"

    fun hex(s: String) = ByteArray(s.length / 2) { s.substring(it * 2, it * 2 + 2).toInt(16).toByte() }
    fun ByteArray.toHex() = joinToString("") { "%02x".format(it) }
}

class PairChannel(private val sendKey: ByteArray, private val recvKey: ByteArray) {
    private var sendN = 0L
    private var recvN = 0L
    private fun nonce(n: Long) = ByteBuffer.allocate(12).putInt(0).putLong(n).array()

    @Synchronized fun seal(kind: Int, payload: ByteArray): ByteArray {
        val c = Cipher.getInstance("AES/GCM/NoPadding")
        c.init(Cipher.ENCRYPT_MODE, SecretKeySpec(sendKey, "AES"), GCMParameterSpec(128, nonce(sendN)))
        sendN++
        val body = c.doFinal(byteArrayOf(kind.toByte()) + payload)
        return ByteBuffer.allocate(4).putInt(body.size).array() + body
    }

    fun open(body: ByteArray): Pair<Int, ByteArray> {
        require(body.size in 17..(PairCrypto.MAX_FRAME + 64)) { "bad frame size" }
        val c = Cipher.getInstance("AES/GCM/NoPadding")
        c.init(Cipher.DECRYPT_MODE, SecretKeySpec(recvKey, "AES"), GCMParameterSpec(128, nonce(recvN)))
        val plain = c.doFinal(body)                 // throws when the frame wasn't made with the right key
        recvN++
        return (plain[0].toInt() and 0xff) to plain.copyOfRange(1, plain.size)
    }
}

/** What the phone knows about its paired computer (kept in Sevbify's private storage). */
data class PairedComputer(val name: String, val pcId: String, val addresses: List<String>, val port: Int,
                          val dev: String, val ltk: ByteArray)

/** A pairing code from a QR code (or a sevbify://pair link). */
data class PairCode(val addresses: List<String>, val port: Int, val code: ByteArray, val pcId: String, val name: String)

class IncomingOffer(val id: String, val title: String, val items: List<Pair<String, Long>>) {
    val total get() = items.sumOf { it.second }
}

object PairLink {
    // UI state
    var computer by mutableStateOf<PairedComputer?>(null)
    var status by mutableStateOf("")              // "", "Connecting…", "Connected", "Can't reach <name>"
    var offer by mutableStateOf<IncomingOffer?>(null)
    var pendingCode by mutableStateOf<PairCode?>(null)   // scanned/opened, waiting for "Pair"
    var progress by mutableStateOf("")
    val connected get() = status == "Connected"

    private const val FILE = "paired_computer.json"
    private val AUDIO = setOf("mp3", "m4a", "aac", "flac", "ogg", "opus", "wav", "wma", "aiff", "aif", "alac", "ape", "mka", "webm")
    private val EXTRA = mapOf("jpg" to (30L shl 20), "jpeg" to (30L shl 20), "png" to (30L shl 20), "lrc" to (1L shl 20),
                              "m3u" to (1L shl 20), "m3u8" to (1L shl 20))
    private val RESERVED = setOf("con", "prn", "aux", "nul", "conin$", "conout$", "clock$") +
        (("0123456789¹²³").flatMap { listOf("com$it", "lpt$it") })
    private const val MAX_FILE = 4L shl 30
    private const val MAX_TOTAL = 40L shl 30
    private const val MAX_FILES = 3000
    private val OFFER_ID = Regex("[A-Za-z0-9_-]{1,40}")

    @Volatile private var socket: Socket? = null
    @Volatile private var channel: PairChannel? = null
    private val sendLock = Object()
    private val transferLock = Object()
    private lateinit var app: Context
    private val accepted = HashMap<String, Receiving>()
    private val usedIds = HashSet<String>()
    private val waiting = HashMap<String, java.util.concurrent.CompletableFuture<Boolean>>()
    @Volatile private var stop = false
    private var loop: Thread? = null

    // --- the QR code --------------------------------------------------------------------------------------------
    fun isLocal(addr: String): Boolean {
        val m = Regex("""^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$""").find(addr) ?: return false
        val (a, b) = m.destructured.toList().take(2).map { it.toInt() }
        if (m.destructured.toList().any { it.toInt() > 255 }) return false
        return a == 10 || (a == 172 && b in 16..31) || (a == 192 && b == 168) || (a == 169 && b == 254) || a == 127 ||
            (a == 100 && b in 64..127)
    }

    fun parse(link: String): PairCode? = try {
        val u = Uri.parse(link)
        if (link.length > 600 || u.scheme != "sevbify" || u.host != "pair") null else {
            val s = (u.getQueryParameter("s") ?: "").replace('-', '+').replace('_', '/')
            val code = android.util.Base64.decode(s + "=".repeat((4 - s.length % 4) % 4), android.util.Base64.DEFAULT)
            val port = (u.getQueryParameter("p") ?: "0").toInt()
            val addrs = (u.getQueryParameter("a") ?: "").split(",").filter { it.isNotBlank() && isLocal(it) }.take(4)
            if (code.size != 32 || addrs.isEmpty() || port !in 1024..65535) null
            else PairCode(addrs, port, code, (u.getQueryParameter("id") ?: "").take(32),
                          cleanName(u.getQueryParameter("n") ?: "", "Computer"))
        }
    } catch (e: Exception) { null }

    fun cleanName(name: String, fallback: String = "Computer"): String {
        val n = Normalizer.normalize(name, Normalizer.Form.NFC).filter {
            val t = Character.getType(it)
            t != Character.CONTROL.toInt() && t != Character.FORMAT.toInt() && t != Character.SURROGATE.toInt() &&
                t != Character.PRIVATE_USE.toInt() && t != Character.UNASSIGNED.toInt() && it !in "<>&"
        }.take(40).trim()
        return n.ifEmpty { fallback }
    }

    // --- start / stop --------------------------------------------------------------------------------------------
    fun init(context: Context) {
        app = context.applicationContext
        computer = load()
    }

    private fun load(): PairedComputer? = try {
        val o = JSONObject(File(app.filesDir, FILE).readText())
        PairedComputer(o.getString("name"), o.optString("pc_id"), o.getJSONArray("addresses").let { a -> List(a.length()) { a.getString(it) } },
                       o.getInt("port"), o.getString("dev"), android.util.Base64.decode(o.getString("ltk"), android.util.Base64.NO_WRAP))
    } catch (e: Exception) { null }

    private fun save(c: PairedComputer?) {
        val f = File(app.filesDir, FILE)
        if (c == null) { f.delete(); return }
        val o = JSONObject().put("name", c.name).put("pc_id", c.pcId).put("addresses", JSONArray(c.addresses))
            .put("port", c.port).put("dev", c.dev).put("ltk", android.util.Base64.encodeToString(c.ltk, android.util.Base64.NO_WRAP))
        val tmp = File(app.filesDir, "$FILE.tmp")
        tmp.writeText(o.toString())
        tmp.renameTo(f)
    }

    /** Keep a connection to the paired computer while Sevbify runs (tries again every 30 s). */
    fun start() {
        if (loop?.isAlive == true || computer == null) return
        stop = false
        loop = Thread({
            while (!stop && computer != null) {
                val c = computer ?: break
                try {
                    connect(c.addresses, c.port, null, c)
                } catch (e: Exception) {
                    if (SevbifyApp.debuggable) android.util.Log.w("Sevbify", "pair link: ${e.message}")
                }
                close()
                if (!stop && computer != null) status = "Can't reach ${c.name}"
                var waited = 0
                while (!stop && waited < 30_000) { Thread.sleep(500); waited += 500 }
            }
        }, "sevbify-pair").apply { isDaemon = true; start() }
    }

    fun stopAll() { stop = true; close() }

    /** Pair with a scanned code (after you tapped Pair). Runs the connection from then on. */
    fun pair(code: PairCode) {
        pendingCode = null
        status = "Connecting…"
        val old = loop
        stopAll()
        loop = Thread({
            try { old?.join(3000) } catch (_: Exception) {}
            stop = false
            status = "Connecting…"
            try {
                connect(code.addresses, code.port, code, null)
            } catch (e: Exception) {
                status = if (computer == null) "Couldn't pair: scan a new code on the computer" else "Can't reach ${code.name}"
            }
            close()
            if (computer != null && !stop) { loop = null; start() }
        }, "sevbify-pair").apply { isDaemon = true; start() }
    }

    fun forget() {
        stopAll()
        computer = null
        save(null)
        status = ""
    }

    private fun close() {
        try { socket?.close() } catch (_: Exception) {}
        socket = null; channel = null
        synchronized(accepted) { accepted.values.forEach { it.abort() }; accepted.clear() }
        synchronized(waiting) { waiting.values.forEach { it.complete(false) }; waiting.clear() }
        offer = null
        if (status == "Connected") status = ""
    }

    // --- the connection ------------------------------------------------------------------------------------------
    private fun frame(o: JSONObject): ByteArray {
        val b = o.toString().toByteArray()
        return ByteBuffer.allocate(4).putInt(b.size).array() + b
    }

    private fun readPlain(inp: DataInputStream): Pair<JSONObject, ByteArray> {
        val n = inp.readInt()
        require(n in 1..1024) { "bad hello" }
        val body = ByteArray(n); inp.readFully(body)
        return JSONObject(String(body)) to (ByteBuffer.allocate(4).putInt(n).array() + body)
    }

    private fun recv(inp: DataInputStream, ch: PairChannel, limit: Int = PairCrypto.MAX_FRAME + 64): Pair<Int, ByteArray> {
        val n = inp.readInt()
        require(n in 17..limit) { "frame too big" }
        val body = ByteArray(n); inp.readFully(body)
        return ch.open(body)
    }

    fun sendJson(o: JSONObject) {
        val ch = channel ?: throw IllegalStateException("not connected")
        synchronized(sendLock) { socket?.getOutputStream()?.apply { write(ch.seal(PairCrypto.KIND_JSON, o.toString().toByteArray())); flush() } }
    }

    private fun sendData(b: ByteArray) {
        val ch = channel ?: throw IllegalStateException("not connected")
        synchronized(sendLock) { socket?.getOutputStream()?.apply { write(ch.seal(PairCrypto.KIND_DATA, b)) } }
    }

    private fun connect(addresses: List<String>, port: Int, code: PairCode?, known: PairedComputer?) {
        var sock: Socket? = null
        for (a in addresses) {
            if (!isLocal(a)) continue
            for (p in listOf(port) + (1..5).map { port + it }) {
                try { sock = Socket().apply { connect(InetSocketAddress(a, p), 4000); soTimeout = 10_000 }; break } catch (_: Exception) {}
            }
            if (sock != null) break
        }
        val s = sock ?: throw java.io.IOException("can't reach")
        socket = s
        val inp = DataInputStream(s.getInputStream().buffered())
        val out = s.getOutputStream()
        val mode = if (code != null) "pair" else "resume"
        val dev = if (code != null) "" else known!!.dev
        val kp = PairCrypto.newKeyPair()
        val cEpk = PairCrypto.publicBytes(kp.public)
        val cNonce = ByteArray(32).also { PairCrypto.rng.nextBytes(it) }
        val b64 = { b: ByteArray -> android.util.Base64.encodeToString(b, android.util.Base64.NO_WRAP) }
        val cHello = frame(JSONObject().put("t", "hello").put("v", JSONArray(listOf(1))).put("mode", mode).put("dev", dev)
            .put("epk", b64(cEpk)).put("nonce", b64(cNonce)))
        out.write(cHello); out.flush()
        val (reply, sHello) = readPlain(inp)
        if (reply.optString("t") == "error") throw java.io.IOException(reply.optString("code"))   // shown only; never forgets the pairing
        require(reply.optString("t") == "hello" && reply.optInt("v") == 1) { "unexpected reply" }
        val sEpk = android.util.Base64.decode(reply.getString("epk"), android.util.Base64.DEFAULT)
        val sNonce = android.util.Base64.decode(reply.getString("nonce"), android.util.Base64.DEFAULT)
        require(sEpk.size == 65 && sNonce.size == 32) { "bad hello" }
        val secret = PairCrypto.ecdh(kp.private, PairCrypto.loadPublic(sEpk, kp.public))
        val psk = code?.code ?: known!!.ltk
        val (c2s, s2c) = PairCrypto.deriveKeys(secret, psk, mode, dev, cNonce, sNonce, cEpk, sEpk, cHello, sHello)
        val ch = PairChannel(c2s, s2c)
        channel = ch
        sendJson(JSONObject().put("t", mode).put("name", phoneName()).put("platform", "android")
            .put("app", appVersion()).put("features", JSONArray(listOf("send_files"))))
        val (kind, payload) = recv(inp, ch, 8 * 1024)
        require(kind == PairCrypto.KIND_JSON) { "unexpected reply" }
        val info = JSONObject(String(payload))
        val name = cleanName(info.optString("name"), code?.name ?: known?.name ?: "Computer")
        val portNow = info.optInt("port", port).takeIf { it in 1024..65535 } ?: port
        when (info.optString("t")) {
            "paired" -> {
                val ltk = android.util.Base64.decode(info.getString("ltk"), android.util.Base64.DEFAULT)
                val devId = info.getString("dev")
                require(ltk.size == 32 && Regex("[0-9a-f]{32}").matches(devId)) { "bad reply" }
                val c = PairedComputer(name, info.optString("pc_id").take(32), code!!.addresses, portNow, devId, ltk)
                computer = c; save(c)
            }
            "welcome" -> {
                val c = known!!.copy(name = name, port = portNow, addresses = listOf(s.inetAddress.hostAddress ?: "") +
                    known.addresses.filter { it != s.inetAddress.hostAddress })
                computer = c; save(c)
            }
            else -> throw java.io.IOException("unexpected reply")
        }
        status = "Connected"
        s.soTimeout = 90_000
        val pinger = Thread({
            try { while (socket === s && !s.isClosed) { Thread.sleep(60_000); sendJson(JSONObject().put("t", "ping")) } } catch (_: Exception) {}
        }, "sevbify-pair-ping").apply { isDaemon = true; start() }
        try {
            while (!stop) {
                val (k, p) = recv(inp, ch)
                if (k == PairCrypto.KIND_DATA) onData(p) else if (k == PairCrypto.KIND_JSON) handle(JSONObject(String(p)))
            }
        } finally { pinger.interrupt() }
    }

    private fun appVersion(): String = try {
        app.packageManager.getPackageInfo(app.packageName, 0).versionName ?: ""
    } catch (_: Exception) { "" }

    /** Called (on the main thread) after songs arrived, to show them in Your Songs. */
    var onReceived: (() -> Unit)? = null

    private fun phoneName(): String = cleanName(
        (try { android.provider.Settings.Global.getString(app.contentResolver, "device_name") } catch (_: Exception) { null })
            ?: "${Build.MANUFACTURER} ${Build.MODEL}", "Phone")

    // --- receiving -----------------------------------------------------------------------------------------------
    private fun safePart(part: String): String {
        var p = Normalizer.normalize(part, Normalizer.Form.NFC).filter {
            val t = Character.getType(it); t != Character.CONTROL.toInt() && t != Character.FORMAT.toInt() &&
                t != Character.SURROGATE.toInt() && t != Character.PRIVATE_USE.toInt() && t != Character.UNASSIGNED.toInt()
        }.replace(Regex("""[<>:"/\\|?*]"""), "_").trim().trimEnd('.', ' ')
        if (p.isEmpty() || p == "." || p == "..") return "_"
        if (p.substringBefore('.').trimEnd(' ', '.').lowercase() in RESERVED) p = "_$p"
        return p.take(120).trimEnd('.', ' ').ifEmpty { "_" }
    }

    /** "Album/01 Song.mp3" from whatever the computer wrote, or null when it isn't something we take. */
    fun safeRelative(path: String, size: Long): String? {
        if (path.length > 600) return null
        val parts = path.split(Regex("""[\\/]+""")).filter { it.isNotEmpty() && it != "." }
        if (parts.isEmpty() || parts.size > 6 || parts.any { it == ".." }) return null
        val safe = parts.map { safePart(it) }
        val ext = safe.last().substringAfterLast('.', "").lowercase()
        val limit = when { ext in AUDIO -> MAX_FILE; ext in EXTRA -> EXTRA[ext]!!; else -> return null }
        if (size < 0 || size > limit) return null
        val rel = safe.joinToString("/")
        return if (rel.length <= 200) rel else null
    }

    private fun handle(m: JSONObject) {
        val t = m.optString("t")
        val id = if (m.has("id")) m.get("id").let { if (it is String && OFFER_ID.matches(it)) it else throw java.io.IOException("bad id") } else null
        when (t) {
            "ping" -> sendJson(JSONObject().put("t", "pong"))
            "offer" -> {
                val items = ArrayList<Pair<String, Long>>()
                val seen = HashSet<String>()
                val arr = m.optJSONArray("items")
                var ok = id != null && arr != null && arr.length() in 1..MAX_FILES && offer == null && id !in usedIds
                if (id != null) usedIds.add(id)
                if (ok) for (i in 0 until arr!!.length()) {
                    val it = arr.optJSONObject(i) ?: continue
                    val sizeAny = it.opt("size")
                    if (sizeAny !is Int && sizeAny !is Long) continue
                    val size = (sizeAny as Number).toLong()
                    val rel = safeRelative(it.optString("path"), size) ?: continue
                    if (!seen.add(Normalizer.normalize(rel, Normalizer.Form.NFC).lowercase())) continue
                    items.add(rel to size)
                }
                if (items.isEmpty() || items.sumOf { it.second } > MAX_TOTAL) ok = false
                if (!ok) { if (id != null) sendJson(JSONObject().put("t", "answer").put("id", id).put("accept", false)); return }
                offer = IncomingOffer(id!!, cleanName(m.optString("title"), "").take(100), items)
            }
            "answer" -> synchronized(waiting) { waiting[id]?.complete(m.optBoolean("accept", false)) }
            "file" -> synchronized(accepted) {
                val r = accepted[id] ?: throw java.io.IOException("not accepted")
                if (accepted.values.any { it.open }) throw java.io.IOException("one file at a time")
                r.start(m.optInt("i", -1))
            }
            "file_end" -> synchronized(accepted) {
                val r = accepted[id] ?: throw java.io.IOException("unexpected end")
                r.end(m.optInt("i", -1), m.optString("sha256"))
                progress = "${r.saved} of ${r.items.size} received"
            }
            "offer_end" -> {
                val r = synchronized(accepted) { accepted.remove(id) } ?: return
                r.abort()
                sendJson(JSONObject().put("t", "received").put("id", id).put("saved", r.saved))
                progress = ""
                Nav.toast = "Received ${r.saved} song${if (r.saved == 1) "" else "s"} from ${computer?.name ?: "your computer"}"
                android.os.Handler(android.os.Looper.getMainLooper()).post { onReceived?.invoke() }
            }
            "cancel" -> {
                synchronized(accepted) { accepted.remove(id)?.abort() }
                if (offer?.id == id) offer = null
                synchronized(waiting) { waiting[id]?.complete(false) }
            }
            else -> {}   // a newer version's message
        }
    }

    private fun onData(b: ByteArray) {
        synchronized(accepted) {
            val r = accepted.values.firstOrNull { it.open } ?: throw java.io.IOException("unexpected data")
            r.data(b)
        }
    }

    /** Your answer to "Receive music?". */
    fun answer(accept: Boolean) {
        val o = offer ?: return
        offer = null
        var ok = accept
        if (ok) {
            val free = try { StatFs(app.getExternalFilesDir(null)?.path ?: app.filesDir.path).availableBytes } catch (_: Exception) { 0L }
            ok = free >= o.total + (200L shl 20)
            if (!ok) Nav.toast = "Not enough space on your phone"
        }
        if (ok) synchronized(accepted) { accepted[o.id] = Receiving(o.id, o.items, cleanName("From ${computer?.name ?: "computer"}")) }
        Thread { try { sendJson(JSONObject().put("t", "answer").put("id", o.id).put("accept", ok)) } catch (_: Exception) {} }.start()
    }

    /** One accepted offer: each file once, as a temporary file, checked (size, SHA-256), then put in Music. */
    private class Receiving(val id: String, val items: List<Pair<String, Long>>, val folder: String) {
        val started = HashSet<Int>()
        val offered = items.sumOf { it.second }
        var written = 0L
        var saved = 0
        private var index = -1
        private var tmp: File? = null
        private var out: OutputStream? = null
        private var got = 0L
        private var hash: MessageDigest? = null
        val open get() = index >= 0

        fun start(i: Int) {
            if (i !in items.indices || i in started || open) throw java.io.IOException("bad file index")
            started.add(i)
            index = i; got = 0
            hash = MessageDigest.getInstance("SHA-256")
            tmp = try { File.createTempFile("pair", ".part", File(PairLink.app.cacheDir, "incoming").apply { mkdirs() }) } catch (_: Exception) { null }
            out = try { tmp?.let { FileOutputStream(it) } } catch (_: Exception) { null }
        }

        fun data(b: ByteArray) {
            got += b.size; written += b.size
            if (got > items[index].second || written > offered) { abort(); throw java.io.IOException("more than offered") }
            hash?.update(b)
            try { out?.write(b) } catch (_: Exception) { try { out?.close() } catch (_: Exception) {}; out = null; tmp?.delete() }
        }

        fun end(i: Int, sha: String) {
            if (i != index) throw java.io.IOException("file end out of order")
            val (rel, size) = items[i]
            val ok = out != null && got == size && hash!!.digest().joinToString("") { "%02x".format(it) } == sha
            try { out?.close() } catch (_: Exception) {}
            if (ok) { if (publish(tmp!!, rel)) saved++ }
            tmp?.delete()
            index = -1; out = null; tmp = null
        }

        fun abort() { try { out?.close() } catch (_: Exception) {}; tmp?.delete(); index = -1; out = null; tmp = null }

        /** Into Music/Sevbify/From <computer>/<folders> (visible to music apps); older Androids: Sevbify's own folder. */
        private fun publish(file: File, rel: String): Boolean {
            val dir = rel.substringBeforeLast('/', "")
            val name = rel.substringAfterLast('/')
            return try {
                if (Build.VERSION.SDK_INT >= 29) {
                    val ext = name.substringAfterLast('.', "").lowercase()
                    val audio = ext in PairLink.AUDIO
                    val collection = if (audio) MediaStore.Audio.Media.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY)
                                     else MediaStore.Files.getContentUri(MediaStore.VOLUME_EXTERNAL_PRIMARY)
                    val values = ContentValues().apply {
                        put(MediaStore.MediaColumns.DISPLAY_NAME, name)
                        put(MediaStore.MediaColumns.RELATIVE_PATH,
                            "${Environment.DIRECTORY_MUSIC}/Sevbify/$folder" + if (dir.isNotEmpty()) "/$dir" else "")
                        put(MediaStore.MediaColumns.IS_PENDING, 1)
                    }
                    val resolver = PairLink.app.contentResolver
                    val uri = resolver.insert(collection, values) ?: return false
                    try {
                        resolver.openOutputStream(uri)?.use { o -> file.inputStream().use { it.copyTo(o) } }
                        values.clear(); values.put(MediaStore.MediaColumns.IS_PENDING, 0)
                        resolver.update(uri, values, null, null)
                        true
                    } catch (e: Exception) { resolver.delete(uri, null, null); false }
                } else {
                    val base = File(PairLink.app.getExternalFilesDir(Environment.DIRECTORY_MUSIC), "$folder/$dir").apply { mkdirs() }
                    var target = File(base, name); var n = 2
                    while (target.exists()) { target = File(base, name.substringBeforeLast('.') + " ($n)." + name.substringAfterLast('.')); n++ }
                    file.copyTo(target); true
                }
            } catch (e: Exception) { false }
        }
    }

    // --- sending -------------------------------------------------------------------------------------------------
    /** Offer songs (on this phone) to the computer; folder = a playlist's name to keep them together. */
    fun send(tracks: List<Track>, folder: String = "") {
        val items = ArrayList<Triple<String, Long, Uri>>()
        val prefix = if (folder.isNotBlank()) safePart(folder) + "/" else ""
        val seen = HashSet<String>()
        for (t in tracks) {
            val uri = t.localUri.takeIf { it.isNotEmpty() }?.let { Uri.parse(it) } ?: continue
            var name = ""; var size = -1L
            try {
                app.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE), null, null, null)?.use { c ->
                    if (c.moveToFirst()) { name = c.getString(0) ?: ""; size = c.getLong(1) }
                }
            } catch (_: Exception) {}
            if (size < 0 || name.isEmpty()) continue
            val rel = safeRelative(prefix + name, size) ?: continue
            if (!seen.add(rel.lowercase())) continue
            items.add(Triple(rel, size, uri))
        }
        if (items.isEmpty()) { Nav.toast = "Only songs on your phone can be sent"; return }
        val id = (1..16).map { "0123456789abcdef"[PairCrypto.rng.nextInt(16)] }.joinToString("")
        val answer = java.util.concurrent.CompletableFuture<Boolean>()
        synchronized(waiting) { waiting[id] = answer }
        Thread({
            var ok = false
            try {
                sendJson(JSONObject().put("t", "offer").put("id", id).put("title", folder.take(100))
                    .put("items", JSONArray(items.map { JSONObject().put("path", it.first).put("size", it.second) })))
                Nav.toast = "Waiting for ${computer?.name ?: "your computer"} to accept…"
                if (answer.get(600, java.util.concurrent.TimeUnit.SECONDS) == true) synchronized(transferLock) {
                    for ((i, item) in items.withIndex()) {
                        val (_, size, uri) = item
                        val md = MessageDigest.getInstance("SHA-256")
                        sendJson(JSONObject().put("t", "file").put("id", id).put("i", i))
                        var sent = 0L
                        try {
                            app.contentResolver.openInputStream(uri)?.use { inp ->
                                val buf = ByteArray(256 * 1024)
                                while (sent < size) {
                                    val n = inp.read(buf, 0, minOf(buf.size.toLong(), size - sent).toInt())
                                    if (n <= 0) break
                                    md.update(buf, 0, n); sendData(buf.copyOf(n)); sent += n
                                }
                            }
                        } catch (e: Exception) { if (socket == null) throw e }
                        sendJson(JSONObject().put("t", "file_end").put("id", id).put("i", i)
                            .put("sha256", md.digest().joinToString("") { "%02x".format(it) }))
                        progress = "Sending ${i + 1} of ${items.size}"
                    }
                    sendJson(JSONObject().put("t", "offer_end").put("id", id))
                    ok = true
                }
            } catch (_: Exception) {}
            synchronized(waiting) { waiting.remove(id) }
            progress = ""
            Nav.toast = if (ok) "Sent to ${computer?.name ?: "your computer"}" else "${computer?.name ?: "Your computer"} didn't take the music"
        }, "sevbify-pair-send").apply { isDaemon = true; start() }
    }
}
