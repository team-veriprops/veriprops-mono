'use client'

import { useCallback } from 'react'

declare global {
  interface Window {
    clarity?: (...args: [string, ...any[]]) => void
  }
}

export function useClarity() {
  const clarity = typeof window !== 'undefined' ? window.clarity : undefined

const init = useCallback((projectId: string) => {
  if (!projectId || typeof window === 'undefined') return;

  (function (c: any, l: any, a: any, r: any, i: string, t: any, y: any) {
    c[a] = c[a] || function () {
      (c[a].q = c[a].q || []).push(arguments)
    }
    t = l.createElement(r)
    t.async = 1
    t.src = 'https://www.clarity.ms/tag/' + i
    y = l.getElementsByTagName(r)[0]
    y?.parentNode?.insertBefore(t, y)
  })(window, document, 'clarity', 'script', projectId, null, null) // ✅ supply all 7 arguments
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
