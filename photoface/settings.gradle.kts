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

rootProject.name = "PhotoFace"
include(":watchface")
include(":complications")
include(":alarmwatcher:phone")
include(":alarmwatcher:wear")
include(":alarmwatcher:shared")
include(":speedwatcher:phone")
include(":speedwatcher:wear")
include(":speedwatcher:shared")
