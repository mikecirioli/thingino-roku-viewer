package com.watchman.bridge

import com.watchman.bridge.data.SettingsRepository
import io.mockk.*
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [33])
class TrialManagerTest {

    private lateinit var settingsRepository: SettingsRepository
    private var mockTime = 0L

    private val TRIAL_DURATION_MS = 3 * 24 * 60 * 60 * 1000L // 3 Days

    @Before
    fun setup() {
        settingsRepository = mockk(relaxed = true)
        mockTime = 0L
        // Ensure getInstallTime returns something by default to avoid init block issues in setup
        every { settingsRepository.getInstallTime() } returns 1000L
    }

    @After
    fun teardown() {
        unmockkAll()
    }

    private fun createTrialManager(isDebug: Boolean = false): TrialManager {
        return TrialManager(settingsRepository, { mockTime }, isDebug = isDebug)
    }

    @Test
    fun `TrialManager initializes install time if not set`() {
        every { settingsRepository.getInstallTime() } returns 0L 
        mockTime = 1234L
        createTrialManager()

        verify { settingsRepository.setInstallTime(1234L) } 
    }

    @Test
    fun `TrialManager does not re-initialize install time if already set`() {
        every { settingsRepository.getInstallTime() } returns 1000L 
        createTrialManager()

        verify(exactly = 0) { settingsRepository.setInstallTime(any()) }
    }

    @Test
    fun `isProUser returns true if settingsRepository reports pro user`() {
        every { settingsRepository.isProUser() } returns true
        val trialManager = createTrialManager(isDebug = false)

        assertTrue(trialManager.isProUser())
    }

    @Test
    fun `isProUser returns false if settingsRepository reports not pro user`() {
        every { settingsRepository.isProUser() } returns false
        val trialManager = createTrialManager(isDebug = false)

        assertFalse(trialManager.isProUser())
    }

    @Test
    fun `isProUser returns true in debug build regardless of settingsRepository`() {
        every { settingsRepository.isProUser() } returns false 
        val trialManager = createTrialManager(isDebug = true)

        assertTrue(trialManager.isProUser())
    }

    @Test
    fun `setProUser calls settingsRepository to update status`() {
        val trialManager = createTrialManager()
        trialManager.setProUser(true)

        verify { settingsRepository.setProUser(true) }
    }

    @Test
    fun `isTrialActive returns true for pro users`() {
        every { settingsRepository.isProUser() } returns true
        val trialManager = createTrialManager()

        assertTrue(trialManager.isTrialActive())
    }

    @Test
    fun `isTrialActive returns true during trial period`() {
        every { settingsRepository.isProUser() } returns false
        every { settingsRepository.getInstallTime() } returns 1000L
        mockTime = 1000L + (TRIAL_DURATION_MS / 2)
        
        val trialManager = createTrialManager(isDebug = false)

        assertTrue(trialManager.isTrialActive())
    }

    @Test
    fun `isTrialActive returns false after trial period`() {
        every { settingsRepository.isProUser() } returns false
        every { settingsRepository.getInstallTime() } returns 1000L
        mockTime = 1000L + TRIAL_DURATION_MS + 1000L 
        
        val trialManager = createTrialManager(isDebug = false)

        assertFalse(trialManager.isTrialActive())
    }

    @Test
    fun `getRemainingHours returns -1 for pro users`() {
        every { settingsRepository.isProUser() } returns true
        val trialManager = createTrialManager()

        assertEquals(-1, trialManager.getRemainingHours())
    }

    @Test
    fun `getRemainingHours calculates correctly during trial`() {
        every { settingsRepository.isProUser() } returns false
        every { settingsRepository.getInstallTime() } returns 1000L
        mockTime = 1000L + (TRIAL_DURATION_MS / 3)
        
        val trialManager = createTrialManager(isDebug = false)

        val expectedRemainingMs = (TRIAL_DURATION_MS * 2 / 3)
        val expectedRemainingHours = (expectedRemainingMs / (1000 * 60 * 60)).toInt()
        assertEquals(expectedRemainingHours, trialManager.getRemainingHours())
    }

    @Test
    fun `getRemainingHours returns 0 after trial ends`() {
        every { settingsRepository.isProUser() } returns false
        every { settingsRepository.getInstallTime() } returns 1000L
        mockTime = 1000L + TRIAL_DURATION_MS + 1000L 
        
        val trialManager = createTrialManager(isDebug = false)

        assertEquals(0, trialManager.getRemainingHours())
    }
}
