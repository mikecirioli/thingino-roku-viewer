plugins {
    id("com.android.application")
}

android {
    namespace = "com.mcirioli.photoface"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.mcirioli.photoface"
        minSdk = 34  // WFF v4 requires API 34+ (Wear OS 5)
        targetSdk = 36
        versionCode = 21
        versionName = "21.0-wff"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
}

dependencies {
    // No Jetpack dependencies needed for pure WFF
    // WFF uses the system runtime
}
