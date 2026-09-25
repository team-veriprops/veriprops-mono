import Link from 'next/link'
import { ArrowLeft, MapPinOff } from 'lucide-react'
import { Button } from '@3rdparty/ui/button'
import StatusPage from '@components/ui/StatusPage'
import { ROUTES } from '@lib/routes'

export default function NotFound() {
  return (
    <StatusPage
      code={404}
      eyebrow="Dead link"
      icon={MapPinOff}
      title="Page not found"
      message="The address you followed doesn’t lead anywhere on Veriprops. It may have moved, or the link may be incomplete."
      actions={
        <Button asChild size="lg" className="w-full sm:w-auto">
          <Link href={ROUTES.HOME}>
            <ArrowLeft aria-hidden />
            Go back home
          </Link>
        </Button>
      }
    />
  )
}
