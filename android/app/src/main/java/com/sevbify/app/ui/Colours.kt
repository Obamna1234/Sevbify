package com.sevbify.app.ui

import android.graphics.drawable.BitmapDrawable
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.palette.graphics.Palette
import coil.imageLoader
import coil.request.ImageRequest
import coil.request.SuccessResult
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/** The cover's main colour, darkened, for the mini player and page headers (like Spotify). */
@Composable
fun rememberCoverColour(url: String?, fallback: Color = Color(0xFF3A3A3A)): Color {
    val context = LocalContext.current
    var colour by remember(url) { mutableStateOf(fallback) }
    LaunchedEffect(url) {
        if (url.isNullOrEmpty()) return@LaunchedEffect
        val result = context.imageLoader.execute(ImageRequest.Builder(context).data(url).allowHardware(false).size(96).build())
        val bmp = ((result as? SuccessResult)?.drawable as? BitmapDrawable)?.bitmap ?: return@LaunchedEffect
        val swatch = withContext(Dispatchers.Default) {
            val p = Palette.from(bmp).generate()
            p.darkVibrantSwatch ?: p.vibrantSwatch ?: p.darkMutedSwatch ?: p.dominantSwatch
        }
        swatch?.let {
            val c = Color(it.rgb)
            colour = Color(red = c.red * 0.7f, green = c.green * 0.7f, blue = c.blue * 0.7f)
        }
    }
    return colour
}
