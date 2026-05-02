package com.speedwatcher.wear

import android.app.Activity
import android.os.Bundle

class MainActivity : Activity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        finish() // Dummy activity just to break out of "stopped" state
    }
}
