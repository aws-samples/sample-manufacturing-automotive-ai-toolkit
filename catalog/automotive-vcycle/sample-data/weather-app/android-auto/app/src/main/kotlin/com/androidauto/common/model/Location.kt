package com.androidauto.common.model

/**
 * Represents a geographic location with accuracy information.
 *
 * @property latitude Latitude coordinate
 * @property longitude Longitude coordinate
 * @property accuracy Location accuracy in meters
 * @property timestamp Time when location was obtained (milliseconds since epoch)
 */
data class Location(
    val latitude: Double,
    val longitude: Double,
    val accuracy: Float,
    val timestamp: Long
) {
    val isAccurate: Boolean
        get() = accuracy <= 200.0f
}
