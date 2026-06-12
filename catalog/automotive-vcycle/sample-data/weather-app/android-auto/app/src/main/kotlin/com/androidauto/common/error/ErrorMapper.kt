package com.androidauto.common.error

import java.io.IOException
import java.net.SocketTimeoutException
import java.net.UnknownHostException

object ErrorMapper {
    fun mapToUserMessage(exception: Exception): String {
        return when (exception) {
            is UnknownHostException -> "No internet connection. Please check your network."
            is SocketTimeoutException -> "Request timed out. Please try again."
            is IOException -> "Network error. Please try again."
            else -> "Something went wrong. Please try again."
        }
    }
}
