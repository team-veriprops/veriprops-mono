'use client'

import { useEffect } from 'react'

interface ErrorPageProps {
  error: Error & { digest?: string }
  reset: () => void
}

export default function Error({ error, reset }: ErrorPageProps) {
  useEffect(() => {
    console.error('App error:', error)
  }, [error])

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-red-50 dark:bg-red-950 px-4">
      <h1 className="text-3xl font-bold text-red-800 dark:text-red-300 mb-2">Something went wrong</h1>
      <p className="text-center text-gray-700 dark:text-gray-200 max-w-md mb-4">
        We encountered an unexpected error. Please try again or contact support if the problem persists.
      </p>
      <button
        onClick={reset}
        className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 transition"
      >
        Try Again
      </button>
    </div>
  )
}
