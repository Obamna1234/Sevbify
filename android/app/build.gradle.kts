import java.io.File

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
    id("com.chaquo.python")
}

// --- Shared with the Windows app -------------------------------------------------------------------------
// The repository's core/ folder (search, radio, imports, podcasts, audiobooks, finding full songs, storage
// rules...) is copied into the APK at build time, so both apps always run the same core. The VERSION file
// sets the app's version, and the Figtree font and the logo come from the shared assets/ folder.
val repoRoot: File = rootProject.projectDir.parentFile
val sharedPython = layout.buildDirectory.dir("shared-python").get().asFile
val sharedRes = layout.buildDirectory.dir("shared-res").get().asFile
val sharedAssets = layout.buildDirectory.dir("shared-assets").get().asFile

fun syncShared() {
    delete(sharedPython)
    copy {
        from(File(repoRoot, "core")) { exclude("**/__pycache__/**", "**/*.pyc") }
        into(File(sharedPython, "core"))
    }
    copy { from(File(repoRoot, "VERSION")); into(sharedPython) }
    delete(sharedRes)
    val fonts = mapOf("Regular" to "figtree_regular", "SemiBold" to "figtree_semibold",
                      "Bold" to "figtree_bold", "ExtraBold" to "figtree_extrabold")
    for ((weight, name) in fonts) {
        copy {
            from(File(repoRoot, "assets/fonts/Figtree-$weight.ttf"))
            into(File(sharedRes, "font"))
            rename { "$name.ttf" }
        }
    }
    copy {
        from(File(repoRoot, "assets/branding/sevbify_icon_512.png"))
        into(File(sharedRes, "mipmap-xxxhdpi"))
        rename { "ic_launcher.png" }
    }
    copy {
        from(File(repoRoot, "assets/branding/sevbify_icon_512.png"))
        into(File(sharedRes, "drawable"))
        rename { "sevbify_logo.png" }
    }
    // The 20 languages: the same table the computer and iPhone apps use.
    delete(sharedAssets)
    copy { from(File(repoRoot, "core/i18n/translations.txt")); into(File(sharedAssets, "i18n")) }
}
syncShared()

val appVersion: String = File(repoRoot, "VERSION").readText().trim()

fun versionCodeOf(v: String): Int {
    // 5.0.0-beta.7 -> 5000007 (beta), 5.0.0 -> 5000099 (final is always higher than its betas)
    val main = v.substringBefore("-").split(".").map { it.toIntOrNull() ?: 0 } + listOf(0, 0, 0)
    val beta = Regex("""(\d+)$""").find(v.substringAfter("-", ""))?.value?.toIntOrNull()
    return main[0] * 1_000_000 + main[1] * 10_000 + main[2] * 100 + (if (v.contains("-")) (beta ?: 0) else 99)
}

android {
    namespace = "com.sevbify.app"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.obamna1234.sevbify"
        minSdk = 26
        targetSdk = 35
        versionName = appVersion
        versionCode = versionCodeOf(appVersion)
        ndk { abiFilters += listOf("arm64-v8a", "x86_64") }
    }

    // The release key is never in the repository: the automatic build gets it from the GitHub secrets
    // ANDROID_KEYSTORE_BASE64 / ANDROID_KEYSTORE_PASSWORD (written to a temporary file, see build.yml).
    // Without them (someone else building from the code) the APK is signed with Android's debug key instead.
    val keystorePath = System.getenv("SEVBIFY_KEYSTORE") ?: ""
    val keystorePassword = System.getenv("SEVBIFY_KEYSTORE_PASSWORD") ?: ""
    val haveReleaseKey = keystorePath.isNotEmpty() && file(keystorePath).exists() && keystorePassword.isNotEmpty()
    signingConfigs {
        if (haveReleaseKey) {
            create("release") {
                storeFile = file(keystorePath)
                storePassword = keystorePassword
                keyAlias = "sevbify"
                keyPassword = keystorePassword
            }
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            signingConfig = if (haveReleaseKey) signingConfigs.getByName("release") else signingConfigs.getByName("debug")
        }
    }

    sourceSets["main"].res.srcDir(sharedRes)
    sourceSets["main"].assets.srcDir(sharedAssets)

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
    buildFeatures { compose = true }
    lint {
        // Lint warnings shouldn't stop the APK from being built (they're reviewed separately).
        abortOnError = false
        checkReleaseBuilds = false
    }
    packaging { resources { excludes += "/META-INF/{AL2.0,LGPL2.1}" } }
}

chaquopy {
    defaultConfig {
        version = "3.12"
        pip {
            install("yt-dlp")
            install("mutagen")
            install("certifi")
        }
    }
    sourceSets {
        getByName("main") {
            srcDir("src/main/python")
            srcDir(sharedPython)
        }
    }
}

dependencies {
    val composeBom = platform("androidx.compose:compose-bom:2024.12.01")
    implementation(composeBom)
    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-graphics")
    implementation("androidx.compose.foundation:foundation")
    implementation("androidx.compose.material3:material3")
    implementation("androidx.compose.material:material-icons-extended")
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
    implementation("androidx.media3:media3-exoplayer:1.5.1")
    implementation("androidx.media3:media3-session:1.5.1")
    implementation("androidx.media3:media3-datasource:1.5.1")
    implementation("androidx.media3:media3-ui:1.5.1")
    implementation("androidx.palette:palette-ktx:1.0.0")
    implementation("io.coil-kt:coil-compose:2.7.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.9.0")
    implementation("com.google.guava:guava:33.3.1-android")
}
