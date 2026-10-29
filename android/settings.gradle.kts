// Sevbify for Android. Lives in the same repository as the Windows app and shares its core/ folder
// (copied in at build time, see app/build.gradle.kts), so fixes in the core reach both apps.
pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "Sevbify"
include(":app")
