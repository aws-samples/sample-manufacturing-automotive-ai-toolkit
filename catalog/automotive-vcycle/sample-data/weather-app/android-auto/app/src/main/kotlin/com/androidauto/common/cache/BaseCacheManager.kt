package com.androidauto.common.cache

/**
 * Service layer interface for cache operations.
 * Manages in-memory caching with LRU eviction policy.
 */
interface CacheManager<T> {
    fun put(key: String, data: T)
    fun get(key: String): T?
    fun clear()
    fun getCacheAge(key: String): Long?
    fun getStats(): CacheStats
}

data class CacheStats(
    val hitCount: Int,
    val missCount: Int,
    val size: Int,
    val maxSize: Int
)

data class CachedEntry<T>(
    val data: T,
    val timestamp: Long
)

/**
 * Abstract base class for cache management with LRU eviction policy.
 * Provides common caching functionality that can be extended for different entity types.
 * Uses LinkedHashMap for LRU behavior, making it testable without Android framework.
 *
 * @param T The type of data being cached
 * @property maxSize Maximum number of entries in the cache
 * @property expiryMinutes Cache expiry time in minutes
 */
abstract class BaseCacheManager<T>(
    protected val maxSize: Int,
    protected val expiryMinutes: Long
) : CacheManager<T> {

    protected val cache = object : LinkedHashMap<String, CachedEntry<T>>(maxSize, 0.75f, true) {
        override fun removeEldestEntry(eldest: MutableMap.MutableEntry<String, CachedEntry<T>>?): Boolean {
            return size > maxSize
        }
    }

    protected var hitCount = 0
    protected var missCount = 0

    @Synchronized
    override fun put(key: String, data: T) {
        val cachedEntry = CachedEntry(
            data = data,
            timestamp = System.currentTimeMillis()
        )
        cache[key] = cachedEntry
    }

    @Synchronized
    override fun get(key: String): T? {
        val cachedEntry = cache[key]

        if (cachedEntry == null) {
            missCount++
            return null
        }

        val age = System.currentTimeMillis() - cachedEntry.timestamp
        val expiryMillis = expiryMinutes * 60 * 1000

        if (age > expiryMillis) {
            cache.remove(key)
            missCount++
            return null
        }

        hitCount++
        return cachedEntry.data
    }

    @Synchronized
    override fun clear() {
        cache.clear()
        hitCount = 0
        missCount = 0
    }

    @Synchronized
    override fun getCacheAge(key: String): Long? {
        val cachedEntry = cache[key] ?: return null
        return System.currentTimeMillis() - cachedEntry.timestamp
    }

    @Synchronized
    override fun getStats(): CacheStats {
        return CacheStats(
            hitCount = hitCount,
            missCount = missCount,
            size = cache.size,
            maxSize = maxSize
        )
    }
}
