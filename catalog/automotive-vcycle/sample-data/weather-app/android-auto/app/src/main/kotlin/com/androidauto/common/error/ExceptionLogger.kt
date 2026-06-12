package com.androidauto.common.error

import timber.log.Timber

object ExceptionLogger {
    fun logError(tag: String, exception: Exception, message: String) {
        Timber.tag(tag).e(exception, message)
    }
    
    fun logWarning(tag: String, exception: Exception, message: String) {
        Timber.tag(tag).w(exception, message)
    }
}
