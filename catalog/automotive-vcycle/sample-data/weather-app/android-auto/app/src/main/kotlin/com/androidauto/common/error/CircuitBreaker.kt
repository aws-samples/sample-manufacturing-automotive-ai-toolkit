package com.androidauto.common.error

import com.androidauto.common.model.Result

class CircuitBreaker(
    private val failureThreshold: Int = 5,
    private val resetTimeout: Long = 60000
) {
    private var failureCount = 0
    private var lastFailureTime = 0L
    private var state = State.CLOSED
    
    enum class State { CLOSED, OPEN, HALF_OPEN }
    
    suspend fun <T> execute(block: suspend () -> T): Result<T> {
        when (state) {
            State.OPEN -> {
                if (System.currentTimeMillis() - lastFailureTime > resetTimeout) {
                    state = State.HALF_OPEN
                } else {
                    return Result.Error(
                        Exception("Circuit breaker is OPEN"),
                        "Service temporarily unavailable"
                    )
                }
            }
            State.HALF_OPEN, State.CLOSED -> {}
        }
        
        return try {
            val result = block()
            onSuccess()
            Result.Success(result)
        } catch (e: Exception) {
            onFailure()
            Result.Error(e, "Operation failed")
        }
    }
    
    private fun onSuccess() {
        failureCount = 0
        state = State.CLOSED
    }
    
    private fun onFailure() {
        failureCount++
        lastFailureTime = System.currentTimeMillis()
        if (failureCount >= failureThreshold) {
            state = State.OPEN
        }
    }
    
    fun reset() {
        failureCount = 0
        state = State.CLOSED
    }
    
    fun getState() = state
    fun getFailureCount() = failureCount
}
