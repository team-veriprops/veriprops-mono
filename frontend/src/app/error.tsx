'use client'

import { useEffect } from 'react'
import { TriangleAlert } from 'lucide-react'
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
      eyebrow="Unexpected error"
      icon={TriangleAlert}
      title="Something went wrong"
      message="Something on our side didn’t load as it should. Your data is safe. Please try again, or contact support if it keeps happening."
      actions={
        <Button type="button" size="lg" className="w-full sm:w-auto" onClick={reset}>
          Try again
        </Button>
      }
    />
  )
}
