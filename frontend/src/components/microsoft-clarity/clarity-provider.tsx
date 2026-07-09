'use client'

import { microsoftClarityProjectId } from '@/containers';
import { useEffect } from 'react'
import { useClarity } from '@hooks/useClarity'

export function ClarityProvider() {
  const { init } = useClarity()

  useEffect(() => {
    init(microsoftClarityProjectId)
  }, [init])

  return null
}
