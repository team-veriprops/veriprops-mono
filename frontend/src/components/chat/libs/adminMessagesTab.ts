/** The tabs of the admin messaging console, as they appear in `?tab=` (§11.2, §16.5). */
export enum AdminMessagesTab {
  REVIEW = "review",
  CONVERSATIONS = "conversations",
}

/** An unknown or missing `?tab=` opens the review queue, the console's first job. */
export function parseAdminMessagesTab(value: string | null | undefined): AdminMessagesTab {
  return Object.values(AdminMessagesTab).includes(value as AdminMessagesTab)
    ? (value as AdminMessagesTab)
    : AdminMessagesTab.REVIEW;
}
