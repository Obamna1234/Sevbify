package com.sevbify.app.ui

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import com.sevbify.app.Playlist
import com.sevbify.app.Show
import com.sevbify.app.Track
import org.json.JSONObject

/** Every page in the app. Each tab (Home, Search, Your Library) keeps its own back stack, like Spotify. */
sealed class Screen {
    data object Home : Screen()
    data object Search : Screen()
    data object Library : Screen()
    data class PlaylistPage(val id: String) : Screen()
    data class Collection(val kind: String, val title: String, val tracks: List<Track>, val cover: String,
                          val saveable: Boolean = true) : Screen()
    data class Artist(val name: String) : Screen()
    data class Genre(val id: Int, val name: String, val colour: Long) : Screen()
    data object Podcasts : Screen()
    data object Audiobooks : Screen()
    data class ShowPage(val show: Show) : Screen()
    data object Settings : Screen()
    data class Import(val text: String = "") : Screen()
    data object ToDownload : Screen()
    data object YourSongs : Screen()
    data object Downloads : Screen()
}

enum class Tab { HOME, SEARCH, LIBRARY }

data class SongMenu(val track: Track, val playlist: Playlist? = null, val row: Int = -1, val queue: List<Track> = emptyList(),
                    val source: String = "")

object Nav {
    var tab by mutableStateOf(Tab.HOME)
    private val stacks = mapOf(Tab.HOME to mutableStateListOf<Screen>(Screen.Home),
                               Tab.SEARCH to mutableStateListOf<Screen>(Screen.Search),
                               Tab.LIBRARY to mutableStateListOf<Screen>(Screen.Library))
    val stack get() = stacks.getValue(tab)
    val top: Screen get() = stack.last()
    var nowPlayingOpen by mutableStateOf(false)
    var queueOpen by mutableStateOf(false)
    var songMenu by mutableStateOf<SongMenu?>(null)
    var playlistMenu by mutableStateOf<Playlist?>(null)
    var addTo by mutableStateOf<List<Track>?>(null)            // "Add to playlist" picker
    var toast by mutableStateOf("")
    var confirm by mutableStateOf<Triple<String, String, () -> Unit>?>(null)
    var rename by mutableStateOf<Pair<String, (String) -> Unit>?>(null)

    fun go(screen: Screen) { stack.add(screen) }
    fun switch(t: Tab) {
        if (tab == t && stack.size > 1) { while (stack.size > 1) stack.removeAt(stack.size - 1) }   // tap again: back to the top
        tab = t
    }
    fun back(): Boolean {
        if (nowPlayingOpen) { nowPlayingOpen = false; return true }
        if (stack.size > 1) { stack.removeAt(stack.size - 1); return true }
        if (tab != Tab.HOME) { tab = Tab.HOME; return true }
        return false
    }
    fun say(text: String) { toast = text }
}
