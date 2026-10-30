package com.sevbify.app

import android.content.Context

/** Sevbify in 20 languages, following Android's language for Sevbify (Settings → Apps → Sevbify → Language on
 *  Android 13+, otherwise the phone's language). The table is the same file the computer and iPhone apps use
 *  (core/i18n/translations.txt). Anything not in it stays English; search works in every language regardless. */
object I18n {
    private val order = listOf("es", "fr", "de", "pt", "it", "ru", "zh", "ja", "ko", "ar", "hi", "tr", "nl", "pl",
                               "id", "vi", "th", "uk", "sv")
    var lang = "en"
        private set
    private var strings: Map<String, String> = emptyMap()

    fun load(context: Context) {
        var code = context.resources.configuration.locales[0]?.language ?: "en"
        if (code == "in") code = "id"                          // Android's old code for Indonesian
        if (code == lang && (code == "en" || strings.isNotEmpty())) return
        lang = code
        val col = order.indexOf(code)
        if (col < 0) { strings = emptyMap(); lang = "en"; return }
        strings = try {
            context.assets.open("i18n/translations.txt").bufferedReader(Charsets.UTF_8).useLines { lines ->
                lines.filter { it.isNotBlank() && !it.startsWith("#") && '\t' in it }.mapNotNull { line ->
                    val english = line.substringBefore('\t')
                    val parts = line.substringAfter('\t').split('|')
                    if (parts.size == order.size && parts[col].isNotBlank()) english to parts[col].trim() else null
                }.toMap()
            }
        } catch (_: Exception) { emptyMap() }
    }

    fun tr(text: String): String = strings[text] ?: text
}

/** The text in Sevbify's language (English when there's no translation). */
fun tr(text: String): String = I18n.tr(text)
