'use client'

import { useClarity } from '@hooks/useClarity'
import { microsoftClarityProjectId } from '@/containers'
import { usePathname } from 'next/navigation'
import { useEffect } from 'react'

export function ClarityPageTracker() {
  const pathname = usePathname()
  const { init, identify, setTag, event } = useClarity()

  useEffect(() => {
    // Wait for route to be client-side navigated
    if (pathname) {
        init(microsoftClarityProjectId!)
        identify('user_456', undefined, undefined, 'Kingsley')
        setTag('plan', 'Startup')
        event(`page_view: ${pathname}`)
    }
  }, [pathname, init, identify, setTag, event])

  return null
}
