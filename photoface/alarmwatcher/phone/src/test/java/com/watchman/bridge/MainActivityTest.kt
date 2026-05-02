package com.watchman.bridge

import android.content.Context
import android.content.Intent
import androidx.test.core.app.ApplicationProvider
import io.mockk.*
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assert.assertFalse
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import androidx.core.app.NotificationManagerCompat

import com.watchman.bridge.data.SettingsRepository
import com.watchman.bridge.shared.data.AlertRule
import com.watchman.bridge.shared.WatchmanPaths
import android.os.PowerManager

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [33])
class MainViewModelTest {

    private lateinit var viewModel: MainViewModel
    private lateinit var mockSettingsRepository: SettingsRepository
    private lateinit var mockWearableRepository: WearableRepository
    private lateinit var mockTrialManager: TrialManager
    private lateinit var context: Context

    @Before
    fun setup() {
        context = ApplicationProvider.getApplicationContext()
        mockSettingsRepository = mockk(relaxed = true)
        mockWearableRepository = mockk(relaxed = true)
        mockTrialManager = mockk(relaxed = true)

        viewModel = MainViewModel(
            mockSettingsRepository,
            mockWearableRepository,
            mockTrialManager,
            context
        )
    }

    @After
    fun teardown() {
        unmockkAll()
    }

    @Test
    fun `test volume change updates repository and wearable`() {
        viewModel.updateAlarmVolume(0.7f)
        verify { mockSettingsRepository.setAlarmVolume(0.7f) }
        verify { mockWearableRepository.updateData(WatchmanPaths.ALARM_VOLUME_PREF, any()) }
    }

    @Test
    fun `test DND override change updates repository and wearable`() {
        viewModel.updateDndOverride(true)
        verify { mockSettingsRepository.setDndOverrideEnabled(true) }
        verify { mockWearableRepository.updateData(WatchmanPaths.DND_OVERRIDE_PREF, any()) }
    }

    @Test
    fun `test adding alert rule calls repository`() {
        val rule = AlertRule(sender = "TestSender")
        viewModel.saveRule(rule)
        verify { mockSettingsRepository.saveAlertRule(rule) }
    }

    @Test
    fun `test deleting alert rule calls repository`() {
        val ruleId = "test-id"
        viewModel.deleteRule(ruleId)
        verify { mockSettingsRepository.deleteAlertRule(ruleId) }
    }
}
