import NotificationPreferencesForm from "@components/shared/notifications/NotificationPreferencesForm";

export const metadata = { title: "Notification Preferences" };

export default function AgentNotificationPreferencesPage() {
  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <h1 className="text-xl font-semibold text-gray-900 mb-2">Notification Preferences</h1>
      <p className="text-sm text-gray-500 mb-6">
        Choose how you receive updates for each event type.
      </p>
      <NotificationPreferencesForm />
    </div>
  );
}
