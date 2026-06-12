package com.androidauto.common.network

import okhttp3.Interceptor
import okhttp3.Response
import timber.log.Timber

/**
 * OkHttp interceptor for logging API requests and responses.
 */
class LoggingInterceptor(private val tag: String = "API") : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val request = chain.request()
        val startTime = System.currentTimeMillis()
        
        Timber.tag(tag).d(
            "Request: %s %s",
            request.method,
            request.url
        )
        
        val response = chain.proceed(request)
        val duration = System.currentTimeMillis() - startTime
        
        Timber.tag(tag).d(
            "Response: %d %s (%dms, %d bytes)",
            response.code,
            request.url,
            duration,
            response.body?.contentLength() ?: 0
        )
        
        return response
    }
}
