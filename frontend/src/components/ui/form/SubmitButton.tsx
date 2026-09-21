"use client";

import { Button } from "@3rdparty/ui/button";
import { useHydrated } from "@hooks/useHydrated";

type ButtonProps = React.ComponentProps<typeof Button>;

/**
 * A submit button that cannot submit until the form behind it is interactive.
 *
 * Before hydration a form's React `onSubmit` is not attached, so a submit is handled by the
 * browser: a native navigation that appends every field to the URL. Disabling the form's only
 * submit control until mount also blocks implicit submission — pressing Enter in a text field
 * submits by activating a submit button, and a disabled one cannot be activated.
 *
 * Pair it with `method="post"` on the form, so that even an unforeseen native submit puts the
 * values in a request body rather than in the address bar.
 */
export function SubmitButton({ disabled, children, ...props }: ButtonProps) {
  const hydrated = useHydrated();

  return (
    <Button type="submit" disabled={disabled || !hydrated} {...props}>
      {children}
    </Button>
  );
}
