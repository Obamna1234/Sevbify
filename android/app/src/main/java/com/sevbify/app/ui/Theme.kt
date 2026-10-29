package com.sevbify.app.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import com.sevbify.app.R

/** Spotify's Android colours, with Figtree (the free look-alike of Spotify's font, shared with Windows). */
object C {
    val Black = Color(0xFF000000)
    val Bg = Color(0xFF121212)
    val Elevated = Color(0xFF1F1F1F)
    val Card = Color(0xFF2A2A2A)
    val Highlight = Color(0xFF3E3E3E)
    val Text = Color(0xFFFFFFFF)
    val Sub = Color(0xFFB3B3B3)
    val Dim = Color(0xFF6A6A6A)
    val Green = Color(0xFF1ED760)
    val Red = Color(0xFFF15E6C)
    val Blue = Color(0xFF509BF5)
}

val Figtree = FontFamily(
    Font(R.font.figtree_regular, FontWeight.Normal),
    Font(R.font.figtree_semibold, FontWeight.SemiBold),
    Font(R.font.figtree_bold, FontWeight.Bold),
    Font(R.font.figtree_extrabold, FontWeight.ExtraBold),
)

private val base = TextStyle(fontFamily = Figtree, color = C.Text)

val Type = Typography(
    headlineLarge = base.copy(fontSize = 28.sp, fontWeight = FontWeight.ExtraBold),
    headlineMedium = base.copy(fontSize = 24.sp, fontWeight = FontWeight.Bold),
    titleLarge = base.copy(fontSize = 22.sp, fontWeight = FontWeight.Bold),
    titleMedium = base.copy(fontSize = 16.sp, fontWeight = FontWeight.SemiBold),
    titleSmall = base.copy(fontSize = 14.sp, fontWeight = FontWeight.SemiBold),
    bodyLarge = base.copy(fontSize = 16.sp),
    bodyMedium = base.copy(fontSize = 14.sp),
    bodySmall = base.copy(fontSize = 13.sp, color = C.Sub),
    labelLarge = base.copy(fontSize = 14.sp, fontWeight = FontWeight.Bold),
    labelMedium = base.copy(fontSize = 12.sp, fontWeight = FontWeight.SemiBold),
    labelSmall = base.copy(fontSize = 11.sp, color = C.Sub),
)

@Composable
fun SevbifyTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = darkColorScheme(primary = C.Green, onPrimary = C.Black, background = C.Bg, surface = C.Bg,
                                      onBackground = C.Text, onSurface = C.Text, surfaceVariant = C.Card,
                                      onSurfaceVariant = C.Sub, secondaryContainer = C.Card),
        typography = Type,
        content = content,
    )
}
