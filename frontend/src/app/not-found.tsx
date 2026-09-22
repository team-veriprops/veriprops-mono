import Link from 'next/link'
import { Button } from '@3rdparty/ui/button'
import StatusPage from '@components/ui/StatusPage'
import { ROUTES } from '@lib/routes'

export default function NotFound() {
  return (
    <StatusPage
      code={404}
      title="Page not found"
      message="Sorry, the page you are looking for doesn’t exist or has been moved."
      actions={
        <Button asChild>
          <Link href={ROUTES.HOME}>Go back home</Link>
        </Button>
      }
    />
  )
}
