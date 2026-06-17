import { useState, useEffect, useCallback, useRef } from 'react'
import type { APIResponse } from '../types'

const POLL_INTERVAL = 10_000 // 10 seconds

/**
 * Custom hook for polling the monitor backend.
 * Fetches data on mount and every 10 s thereafter.
 * Automatically cleans up on unmount or when params change.
 */
export function useMonitorAPI<T>(
  path: string,
  params?: Record<string, string>,
): APIResponse<T> {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const buildURL = useCallback(() => {
    const url = new URL(path, window.location.origin)
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v) url.searchParams.set(k, v)
      })
    }
    return url.toString()
  }, [path, params])

  const fetchData = useCallback(async (isInitial = false) => {
    // Abort any in-flight request
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    if (isInitial) setLoading(true)

    try {
      const res = await fetch(buildURL(), { signal: controller.signal })
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`)
      }
      const json = (await res.json()) as T
      setData(json)
      setError(null)
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === 'AbortError') return
      const message = err instanceof Error ? err.message : 'Unknown error'
      setError(message)
    } finally {
      if (isInitial) setLoading(false)
    }
  }, [buildURL])

  // Serialise params for dependency tracking
  const paramKey = params ? JSON.stringify(params) : ''

  useEffect(() => {
    fetchData(true)

    intervalRef.current = setInterval(() => fetchData(false), POLL_INTERVAL)

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
      abortRef.current?.abort()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, paramKey])

  const refetch = useCallback(() => fetchData(true), [fetchData])

  return { data, loading, error, refetch }
}
