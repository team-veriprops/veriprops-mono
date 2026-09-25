'use client'

import { useEffect } from 'react'
import { Button } from '@3rdparty/ui/button'
import StatusPage from '@components/ui/StatusPage'

interface ErrorPageProps {
  error: Error & { digest?: string }
  reset: () => void
}

/** The boundary a user lands on when a render actually failed — same shell as 404/403. */
export default function Error({ error, reset }: ErrorPageProps) {
  useEffect(() => {
    console.error('App error:', error)
  }, [error])

  return (
    <StatusPage
      code={500}
      title="Something went wrong"
      message="We encountered an unexpected error. Please try again, or contact support if the problem persists."
      actions={
        <Button type="button" onClick={reset}>
          Try again
        </Button>
      }
    />
  )
}
