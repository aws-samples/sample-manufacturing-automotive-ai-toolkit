package com.androidauto.common.location

import com.androidauto.common.model.Location
import kotlinx.coroutines.delay
import timber.log.Timber
import java.io.IOException

/**
 * Mock implementation of LocationService for testing.
 * Provides configurable behavior for testing various scenarios.
 */
class MockLocationService : LocationService {
    
    var shouldFail: Boolean = false
    var configuredDelay: Long = 100
    var failureCount: Int = 0
    var requestCount: Int = 0
    var successAfterAttempts: Int = 1
    private var attemptCount: Int = 0
    
    private var mockLocation: Location = Location(
        latitude = 37.7749,
        longitude = -122.4194,
        accuracy = 10f,
        timestamp = System.currentTimeMillis()
    )
    
    override suspend fun getLocation(): Location {
        attemptCount++
        requestCount++
        Timber.d("MockLocationService.getLocation() called (attempt #$attemptCount, request #$requestCount)")
        
        delay(configuredDelay)
        
        if (shouldFail) {
            failureCount++
            Timber.w("MockLocationService throwing IOException (shouldFail=true)")
            throw IOException("Mock location service failure")
        }
        
        if (attemptCount < successAfterAttempts) {
            failureCount++
            Timber.w("MockLocationService throwing IOException (attempt $attemptCount < $successAfterAttempts)")
            throw IOException("Mock location service temporary failure")
        }
        
        val location = mockLocation.copy(timestamp = System.currentTimeMillis())
        Timber.d("MockLocationService returning location: lat=${location.latitude}, lon=${location.longitude}, accuracy=${location.accuracy}m")
        return location
    }
    
    fun setMockLocation(location: Location) {
        mockLocation = location
    }
    
    fun reset() {
        shouldFail = false
        configuredDelay = 100
        failureCount = 0
        requestCount = 0
        successAfterAttempts = 1
        attemptCount = 0
        mockLocation = Location(
            latitude = 37.7749,
            longitude = -122.4194,
            accuracy = 10f,
            timestamp = System.currentTimeMillis()
        )
    }
}
