import Link from 'next/link'

export default function NotFound() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gray-100 dark:bg-gray-900 px-4">
      <h1 className="text-4xl font-bold text-gray-900 dark:text-white mb-2">404 – Page Not Found</h1>
      <p className="text-gray-600 dark:text-gray-300 mb-6 max-w-md text-center">
        Sorry, the page you are looking for doesn’t exist or has been moved.
      </p>
      <Link
        href="/"
        className="inline-block bg-brand text-white px-6 py-3 rounded-md hover:bg-brand-dark transition"
      >
        Go back home
      </Link>
    </div>
  )
}
