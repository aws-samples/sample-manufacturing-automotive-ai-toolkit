package com.androidauto.common.model

/**
 * Sealed class representing the result of an operation that can succeed or fail.
 *
 * @param T The type of data returned on success
 */
sealed class Result<out T> {
    data class Success<T>(val data: T) : Result<T>()
    data class Error(val exception: Exception, val message: String) : Result<Nothing>()
    
    inline fun <R> map(transform: (T) -> R): Result<R> = when (this) {
        is Success -> Success(transform(data))
        is Error -> this
    }
    
    inline fun onSuccess(action: (T) -> Unit): Result<T> {
        if (this is Success) action(data)
        return this
    }
    
    inline fun onError(action: (Exception, String) -> Unit): Result<T> {
        if (this is Error) action(exception, message)
        return this
    }
}
