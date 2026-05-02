package com.watchman.bridge

import com.watchman.bridge.data.WearSettingsRepository
import io.mockk.*
import org.junit.Assert.assertEquals
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [33])
class WatchEventProcessorTest {

    private lateinit var mockRepository: WearSettingsRepository
    private lateinit var startActivityCallback: (String?, String?, Float?, Boolean?, Int?, String?, Boolean?) -> Unit
    private lateinit var sendBroadcastCallback: (String) -> Unit
    private lateinit var processor: WatchEventProcessor

    @Before
    fun setup() {
        mockRepository = mockk(relaxed = true)
        startActivityCallback = mockk(relaxed = true)
        sendBroadcastCallback = mockk(relaxed = true)
        processor = WatchEventProcessor(mockRepository, startActivityCallback, sendBroadcastCallback)
    }

    @Test
    fun `processDndState calls repository syncDndState`() {
        processor.processDndState(1)
        verify { mockRepository.syncDndState(1) }
    }

    @Test
    fun `processDndOverride calls repository setDndOverrideEnabled`() {
        processor.processDndOverride(true)
        verify { mockRepository.setDndOverrideEnabled(true) }
    }

    @Test
    fun `processAlarmVolume calls repository setAlarmVolume`() {
        processor.processAlarmVolume(0.5f)
        verify { mockRepository.setAlarmVolume(0.5f) }
    }

    @Test
    fun `processNextAlarmTime calls repository setNextAlarmTime`() {
        processor.processNextAlarmTime(12345L)
        verify { mockRepository.setNextAlarmTime(12345L) }
    }

    @Test
    fun `processVibrateOnly calls repository setVibrateOnly`() {
        processor.processVibrateOnly(true)
        verify { mockRepository.setVibrateOnly(true) }
    }

    @Test
    fun `processVibrationPattern calls repository setVibrationPattern`() {
        processor.processVibrationPattern("Heartbeat")
        verify { mockRepository.setVibrationPattern("Heartbeat") }
    }

    @Test
    fun `processVibrationPattern with null defaults to Standard`() {
        processor.processVibrationPattern(null)
        verify { mockRepository.setVibrationPattern("Standard") }
    }

    @Test
    fun `processStartAlarm calls startActivityCallback`() {
        processor.processStartAlarm()
        verify { startActivityCallback("custom_alarm.mp3", null, null, null, null, null, null) }
    }

    @Test
    fun `processStopAlarm calls sendBroadcastCallback`() {
        processor.processStopAlarm()
        verify { sendBroadcastCallback("com.watchman.bridge.FINISH_ALARM") }
    }

    @Test
    fun `processCriticalAlert parses minimal payload (JSON)`() {
        val payload = """{"message":"Test Message","volume":0.8,"overrideDnd":true}"""
        processor.processCriticalAlert(payload)
        verify { startActivityCallback("custom_alarm.mp3", "Test Message", 0.8f, true, -1, "Standard", false) }
    }

    @Test
    fun `processCriticalAlert parses full payload (JSON)`() {
        val payload = """{"message":"Test Message","volume":0.8,"overrideDnd":true,"soundFile":"test_sound.mp3","playDurationSeconds":30,"vibrationPattern":"Heartbeat","vibrateOnly":true}"""
        processor.processCriticalAlert(payload)
        verify { startActivityCallback("test_sound.mp3", "Test Message", 0.8f, true, 30, "Heartbeat", true) }
    }

    @Test
    fun `processCriticalAlert rejects payload with fewer than 3 parts`() {
        processor.processCriticalAlert("only|two")
        verify(exactly = 0) { startActivityCallback(any(), any(), any(), any(), any(), any(), any()) }
    }
}
