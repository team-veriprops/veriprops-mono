import WhatsAppConsentSettings from "@components/account/WhatsAppConsentSettings";
import WhatsAppLinkSettings from "@components/account/WhatsAppLinkSettings";

export default function AccountWhatsAppPage() {
  return (
    <div className="space-y-4">
      <WhatsAppLinkSettings />
      <WhatsAppConsentSettings />
    </div>
  );
}
