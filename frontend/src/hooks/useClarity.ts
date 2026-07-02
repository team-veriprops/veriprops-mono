'use client'

import { useCallback } from 'react'

type ClarityQueue = NonNullable<Window['clarity']>

export function useClarity() {
  const clarity = typeof window !== 'undefined' ? window.clarity : undefined

  const init = useCallback((projectId: string | undefined) => {
    if (!projectId || typeof window === 'undefined') return

    const w = window
    const queue: ClarityQueue =
      w.clarity ||
      ((...args: unknown[]) => {
        queue.q = queue.q || []
        queue.q.push(args)
      })
    w.clarity = queue

    const script = document.createElement('script')
    script.async = true
    script.src = 'https://www.clarity.ms/tag/' + projectId
    const first = document.getElementsByTagName('script')[0]
    first?.parentNode?.insertBefore(script, first)
  }, [])

  const identify = useCallback((userId: string, sessionId?: string, pageId?: string, name?: string) => {
    clarity?.('identify', userId, sessionId, pageId, name)
  }, [clarity])

  const setTag = useCallback((key: string, value: string) => {
    clarity?.('set', key, value)
  }, [clarity])

  const event = useCallback((name: string) => {
    clarity?.('event', name)
  }, [clarity])

  const consent = useCallback(() => {
    clarity?.('consent')
  }, [clarity])

  const upgrade = useCallback((reason: string) => {
    clarity?.('upgrade', reason)
  }, [clarity])

  return {
    init,
    identify,
    setTag,
    event,
    consent,
    upgrade,
  }
}
