import { useRef } from 'react'
import { isMobileBrowser } from '@lib/utils'
import { PaymentMethod } from '@/types/models'
import { SocialAuthProvider } from '@components/website/auth/models'

type PopupProvider = SocialAuthProvider | PaymentMethod

export function openPopup(url: string, provider: PopupProvider) {
  if (typeof window === 'undefined') {
    throw new Error('Popup can only be opened in browser')
  }

  const width = 500
  const height = 600

  const left = window.screenX + (window.outerWidth - width) / 2
  const top = window.screenY + (window.outerHeight - height) / 2

  const popup = window.open(
    url,
    `${provider}-window`,
    `
      width=${width},
      height=${height},
      left=${left},
      top=${top},
      resizable=yes,
      scrollbars=yes
    `.replace(/\s+/g, '')
  )

  if (!popup) {
    throw new Error('Popup blocked by browser')
  }

  popup.focus()
  return popup
}

export function usePopup() {
  const popupRef = useRef<Window | null>(null)
  const providerRef = useRef<PopupProvider | null>(null)
  const isMobileRef = useRef(false)

  const initPopup = (provider: PopupProvider) => {
    const mobile = isMobileBrowser()
    isMobileRef.current = mobile
    providerRef.current = provider

    popupRef.current = !mobile
      ? openPopup('about:blank', provider)
      : null
  }

  const updatePopupUrl = (url: string) => {
    if (isMobileRef.current) {
      window.location.href = url
      return
    }

    // Reopen if popup was manually closed
    if (!popupRef.current || popupRef.current.closed) {
      if (!providerRef.current) return
      popupRef.current = openPopup(url, providerRef.current)
      return
    }

    popupRef.current.location.assign(url)
  }

  const closePopup = () => {
    popupRef.current?.close()
    popupRef.current = null
  }

  return {
    popupRef,
    initPopup,
    updatePopupUrl,
    closePopup,
  }
}
