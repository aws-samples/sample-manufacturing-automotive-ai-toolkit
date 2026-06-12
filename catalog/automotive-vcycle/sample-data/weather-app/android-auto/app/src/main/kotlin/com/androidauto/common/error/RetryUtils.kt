package com.androidauto.common.error

import com.androidauto.common.model.Result
import kotlinx.coroutines.delay
import timber.log.Timber

suspend fun <T> retryWithBackoff(
    maxAttempts: Int = 3,
    initialDelay: Long = 500,
    maxDelay: Long = 4000,
    factor: Double = 2.0,
    block: suspend () -> T
): Result<T> {
    var currentDelay = initialDelay
    repeat(maxAttempts - 1) { attempt ->
        try {
            return Result.Success(block())
        } catch (e: Exception) {
            Timber.w(e, "Attempt ${attempt + 1} failed, retrying in ${currentDelay}ms")
            delay(currentDelay)
            currentDelay = (currentDelay * factor).toLong().coerceAtMost(maxDelay)
        }
    }
    return try {
        Result.Success(block())
    } catch (e: Exception) {
        Timber.e(e, "All $maxAttempts attempts failed")
        Result.Error(e, "Operation failed after $maxAttempts attempts")
    }
}
