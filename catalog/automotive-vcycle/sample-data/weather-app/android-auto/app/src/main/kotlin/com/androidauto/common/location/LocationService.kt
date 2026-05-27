package com.androidauto.common.location

import com.androidauto.common.model.Location
import java.io.IOException

/**
 * Interface for the underlying location service.
 * This abstraction allows for different implementations (real GPS, mock, etc.)
 */
interface LocationService {
    /**
     * Gets the current location from the underlying service.
     * 
     * @return Location data
     * @throws IOException if the service is unavailable
     */
    suspend fun getLocation(): Location
}
