package com.androidauto.common.location

import com.androidauto.common.model.Location
import com.androidauto.common.model.Result
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.filterNotNull
import timber.log.Timber

/**
 * Service layer interface for location operations.
 * Manages location data retrieval from in-vehicle services.
 */
interface LocationManager {
    suspend fun getCurrentLocation(): Result<Location>
    fun observeLocation(): Flow<Location>
}

/**
 * Abstract base class for location management.
 * Provides common location functionality including caching and flow management.
 *
 * @property cacheValidityMs Cache validity duration in milliseconds
 */
abstract class BaseLocationManager(
    protected val cacheValidityMs: Long = DEFAULT_CACHE_VALIDITY_MS
) : LocationManager {

    protected val _locationFlow = MutableStateFlow<Location?>(null)
    protected var cachedLocation: Location? = null
    protected var lastFetchTime: Long = 0

    companion object {
        const val DEFAULT_CACHE_VALIDITY_MS = 60000L
    }

    override fun observeLocation(): Flow<Location> {
        return _locationFlow.filterNotNull()
    }

    protected fun cacheLocation(location: Location) {
        cachedLocation = location
        lastFetchTime = System.currentTimeMillis()
        _locationFlow.value = location
        Timber.d("Location cached: lat=${location.latitude}, lon=${location.longitude}")
    }

    protected fun isCacheValid(): Boolean {
        return cachedLocation != null && getCacheAgeMs() < cacheValidityMs
    }

    protected fun getCacheAgeMs(): Long {
        return if (lastFetchTime > 0) {
            System.currentTimeMillis() - lastFetchTime
        } else {
            Long.MAX_VALUE
        }
    }
}
