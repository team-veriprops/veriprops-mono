import { useEffect, useRef } from "react";

export default function InfiniteScrollTriggerComponent({
  hasNextPage,
  fetchNextPage,
  isFetchingNextPage,
}: {
  hasNextPage: boolean;
  fetchNextPage: () => void;
  isFetchingNextPage: boolean;
}) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const target = bottomRef.current;
    if (!target) return;

    const observer = new IntersectionObserver(
      async ([entry]) => {
        // Keep attempting to scroll as long as we're in view and there's a next page
        if (entry.isIntersecting && hasNextPage && !isFetchingNextPage) {
          await fetchNextPage();
        }
      },
      {
        root: null,         // viewport
        rootMargin: "200px", // trigger early for smoother experience
        threshold: 0.1,
      }
    );

    observer.observe(target);

    return () => {
      observer.unobserve(target);
      observer.disconnect();
    };
  }, [hasNextPage, fetchNextPage, isFetchingNextPage]);

  return (
    <div ref={bottomRef} className="py-4">
      {/* `gray-600`, not `gray-500`: 500 is 4.39:1 on the app's surfaces and fails WCAG AA. */}
      {isFetchingNextPage && (
        <p className="text-center text-sm text-gray-600">Loading more...</p>
      )}
    </div>
  );
}